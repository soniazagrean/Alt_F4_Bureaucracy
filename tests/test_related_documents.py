import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base, SessionLocal, get_db
from app.main import app
from app.models.document import Document, DocumentStatusEnum, DocumentTypeEnum, ExtractedData
from app.models.user import User, RoleEnum
from app.services.auth import auth_service
import app.services.graph_service as graph_service
from app.db.neo4j import get_neo4j_session


class FakeRedis:
    def __init__(self):
        self._store = {}

    def setex(self, key: str, _ttl: int, value: str):
        self._store[key] = value

    def exists(self, key: str) -> int:
        return 1 if key in self._store else 0

    def delete(self, key: str) -> int:
        return 1 if self._store.pop(key, None) is not None else 0


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        expire_on_commit=False,
    )
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    original_redis = auth_service._redis
    auth_service._redis = FakeRedis()
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client, TestingSessionLocal

    app.dependency_overrides.clear()
    auth_service._redis = original_redis


@pytest.fixture()
def auth_headers(client):
    test_client, _ = client
    register_response = test_client.post(
        "/auth/register",
        json={
            "username": "related_user",
            "email": "related_user@example.com",
            "password": "Password123",
            "full_name": "Related User",
            "role": "viewer",
        },
    )
    assert register_response.status_code == 200

    login_response = test_client.post(
        "/auth/login",
        json={"username": "related_user", "password": "Password123"},
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {access_token}"}


def _create_user(db, username: str) -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        hashed_password="secret",
        role=RoleEnum.SYSTEM,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_related_documents_404_missing_document(client, auth_headers):
    test_client, _ = client
    response = test_client.get("/documents/999/related", headers=auth_headers)
    assert response.status_code == 404


def test_related_documents_empty_when_no_graph_node(client, auth_headers, monkeypatch):
    test_client, session_factory = client
    db = session_factory()
    try:
        user = _create_user(db, "related_doc_user")
        document = Document(
            document_number="DOC-REL-001",
            document_type=DocumentTypeEnum.REPORT,
            title="Related Report",
            file_path="uploads/rel-001.pdf",
            created_by_id=user.id,
            status=DocumentStatusEnum.ARCHIVED,
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        document_id = document.id
    finally:
        db.close()

    monkeypatch.setattr(graph_service, "get_document_node", lambda _doc_id: None)

    response = test_client.get(f"/documents/{document_id}/related", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["related"] == []
    assert body["total_count"] == 0


def test_related_documents_pagination_validation(client, auth_headers):
    test_client, _ = client
    response = test_client.get("/documents/1/related?page=0", headers=auth_headers)
    assert response.status_code == 422

    response = test_client.get("/documents/1/related?page_size=21", headers=auth_headers)
    assert response.status_code == 422


def test_related_documents_relation_type_filter(client, auth_headers, monkeypatch):
    test_client, session_factory = client
    db = session_factory()
    try:
        user = _create_user(db, "related_filter_user")
        document = Document(
            document_number="DOC-REL-002",
            document_type=DocumentTypeEnum.REPORT,
            title="Related Filter Report",
            file_path="uploads/rel-002.pdf",
            created_by_id=user.id,
            status=DocumentStatusEnum.ARCHIVED,
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        document_id = document.id
    finally:
        db.close()

    calls = {"dosar": 0, "furnizor": 0, "all": 0}

    monkeypatch.setattr(graph_service, "get_document_node", lambda _doc_id: {"id": str(document_id)})

    def dosar_call(*_args, **_kwargs):
        calls["dosar"] += 1
        return [], 0

    def furnizor_call(*_args, **_kwargs):
        calls["furnizor"] += 1
        return [], 0

    def all_call(*_args, **_kwargs):
        calls["all"] += 1
        return [], 0

    monkeypatch.setattr(graph_service, "get_related_by_dosar", dosar_call)
    monkeypatch.setattr(graph_service, "get_related_by_furnizor", furnizor_call)
    monkeypatch.setattr(graph_service, "get_all_related", all_call)

    response = test_client.get(
        f"/documents/{document_id}/related?relation_type=same_dosar",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert calls["dosar"] == 1
    assert calls["furnizor"] == 0
    assert calls["all"] == 0


def test_related_documents_auth_required(client):
    test_client, _ = client
    response = test_client.get("/documents/1/related")
    assert response.status_code in {401, 403}


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("NEO4J_URI") is None,
    reason="NEO4j connection URL is not configured",
)
def test_related_documents_integration_same_dosar_and_furnizor(monkeypatch):
    try:
        db = SessionLocal()
    except Exception as exc:
        pytest.skip(f"Postgres not available: {exc}")

    original_redis = auth_service._redis
    auth_service._redis = FakeRedis()

    doc_username = f"rel_doc_user_{uuid4().hex[:8]}"
    auth_username = f"rel_auth_user_{uuid4().hex[:8]}"
    dosar_name = f"Dosar-{uuid4().hex[:6]}"
    cui = f"{uuid4().int % 10000000000:010d}"
    document_ids = []

    try:
        user = _create_user(db, doc_username)

        def add_document(doc_number: str, doc_type: DocumentTypeEnum):
            document = Document(
                document_number=doc_number,
                document_type=doc_type,
                title=f"Title {doc_number}",
                file_path=f"uploads/{doc_number}.pdf",
                created_by_id=user.id,
                status=DocumentStatusEnum.ARCHIVED,
                document_date=datetime.now(timezone.utc),
            )
            db.add(document)
            db.commit()
            db.refresh(document)
            document_ids.append(document.id)
            return document

        doc_a = add_document(f"DOC-{uuid4().hex[:6]}", DocumentTypeEnum.INVOICE)
        doc_b = add_document(f"DOC-{uuid4().hex[:6]}", DocumentTypeEnum.REPORT)
        doc_c = add_document(f"DOC-{uuid4().hex[:6]}", DocumentTypeEnum.REPORT)

        db.add_all(
            [
                ExtractedData(
                    document_id=doc_a.id,
                    field_name="dosar_propus",
                    field_value=dosar_name,
                    extraction_confidence=0.9,
                ),
                ExtractedData(
                    document_id=doc_a.id,
                    field_name="cod_nomenclator",
                    field_value="II.1",
                    extraction_confidence=0.9,
                ),
                ExtractedData(
                    document_id=doc_a.id,
                    field_name="furnizor",
                    field_value="Supplier SRL",
                    extraction_confidence=0.9,
                ),
                ExtractedData(
                    document_id=doc_a.id,
                    field_name="CUI",
                    field_value=cui,
                    extraction_confidence=0.9,
                ),
                ExtractedData(
                    document_id=doc_b.id,
                    field_name="dosar_propus",
                    field_value=dosar_name,
                    extraction_confidence=0.9,
                ),
                ExtractedData(
                    document_id=doc_b.id,
                    field_name="cod_nomenclator",
                    field_value="II.1",
                    extraction_confidence=0.9,
                ),
                ExtractedData(
                    document_id=doc_c.id,
                    field_name="furnizor",
                    field_value="Supplier SRL",
                    extraction_confidence=0.9,
                ),
                ExtractedData(
                    document_id=doc_c.id,
                    field_name="CUI",
                    field_value=cui,
                    extraction_confidence=0.9,
                ),
            ]
        )
        db.commit()

        graph_service.populate_graph_for_document(doc_a.id)
        graph_service.populate_graph_for_document(doc_b.id)
        graph_service.populate_graph_for_document(doc_c.id)

        with TestClient(app) as test_client:
            register_response = test_client.post(
                "/auth/register",
                json={
                    "username": auth_username,
                    "email": f"{auth_username}@example.com",
                    "password": "Password123",
                    "full_name": "Integration User",
                    "role": "viewer",
                },
            )
            if register_response.status_code not in {200, 409}:
                pytest.skip("Auth unavailable")

            login_response = test_client.post(
                "/auth/login",
                json={"username": auth_username, "password": "Password123"},
            )
            if login_response.status_code != 200:
                pytest.skip("Auth unavailable")

            access_token = login_response.json()["access_token"]
            response = test_client.get(
                f"/documents/{doc_a.id}/related",
                headers={"Authorization": f"Bearer {access_token}"},
            )

        assert response.status_code == 200
        body = response.json()
        returned_ids = {item["id"] for item in body["related"]}
        assert str(doc_b.id) in returned_ids
        assert str(doc_c.id) in returned_ids

        relation_map = {item["id"]: item["relation_types"] for item in body["related"]}
        assert relation_map[str(doc_b.id)] == ["same_dosar"]
        assert relation_map[str(doc_c.id)] == ["same_furnizor"]

    except SQLAlchemyError as exc:
        db.rollback()
        pytest.skip(f"Postgres not available: {exc}")
    finally:
        auth_service._redis = original_redis
        db.close()

        with get_neo4j_session() as session:
            for doc_id in document_ids:
                session.run("MATCH (d:Document {id: $id}) DETACH DELETE d", id=str(doc_id))
            session.run("MATCH (d:Dosar {id: $dosar}) DETACH DELETE d", dosar=dosar_name)
            session.run("MATCH (f:Furnizor {CUI: $cui}) DETACH DELETE f", cui=cui)

        db = SessionLocal()
        try:
            db.query(ExtractedData).filter(ExtractedData.document_id.in_(document_ids)).delete(synchronize_session=False)
            db.query(Document).filter(Document.id.in_(document_ids)).delete(synchronize_session=False)
            db.query(User).filter(User.username.in_([doc_username, auth_username])).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("NEO4J_URI") is None,
    reason="NEO4j connection URL is not configured",
)
def test_related_documents_deduplication(monkeypatch):
    try:
        db = SessionLocal()
    except Exception as exc:
        pytest.skip(f"Postgres not available: {exc}")

    original_redis = auth_service._redis
    auth_service._redis = FakeRedis()

    doc_username = f"rel_doc_user_{uuid4().hex[:8]}"
    auth_username = f"rel_auth_user_{uuid4().hex[:8]}"
    dosar_name = f"Dosar-{uuid4().hex[:6]}"
    cui = f"{uuid4().int % 10000000000:010d}"
    document_ids = []

    try:
        user = _create_user(db, doc_username)

        doc_a = Document(
            document_number=f"DOC-{uuid4().hex[:6]}",
            document_type=DocumentTypeEnum.INVOICE,
            title="Doc A",
            file_path="uploads/doc-a.pdf",
            created_by_id=user.id,
            status=DocumentStatusEnum.ARCHIVED,
        )
        doc_d = Document(
            document_number=f"DOC-{uuid4().hex[:6]}",
            document_type=DocumentTypeEnum.INVOICE,
            title="Doc D",
            file_path="uploads/doc-d.pdf",
            created_by_id=user.id,
            status=DocumentStatusEnum.ARCHIVED,
        )
        db.add_all([doc_a, doc_d])
        db.commit()
        db.refresh(doc_a)
        db.refresh(doc_d)
        document_ids.extend([doc_a.id, doc_d.id])

        db.add_all(
            [
                ExtractedData(
                    document_id=doc_a.id,
                    field_name="dosar_propus",
                    field_value=dosar_name,
                    extraction_confidence=0.9,
                ),
                ExtractedData(
                    document_id=doc_a.id,
                    field_name="cod_nomenclator",
                    field_value="II.1",
                    extraction_confidence=0.9,
                ),
                ExtractedData(
                    document_id=doc_a.id,
                    field_name="furnizor",
                    field_value="Supplier SRL",
                    extraction_confidence=0.9,
                ),
                ExtractedData(
                    document_id=doc_a.id,
                    field_name="CUI",
                    field_value=cui,
                    extraction_confidence=0.9,
                ),
                ExtractedData(
                    document_id=doc_d.id,
                    field_name="dosar_propus",
                    field_value=dosar_name,
                    extraction_confidence=0.9,
                ),
                ExtractedData(
                    document_id=doc_d.id,
                    field_name="cod_nomenclator",
                    field_value="II.1",
                    extraction_confidence=0.9,
                ),
                ExtractedData(
                    document_id=doc_d.id,
                    field_name="furnizor",
                    field_value="Supplier SRL",
                    extraction_confidence=0.9,
                ),
                ExtractedData(
                    document_id=doc_d.id,
                    field_name="CUI",
                    field_value=cui,
                    extraction_confidence=0.9,
                ),
            ]
        )
        db.commit()

        graph_service.populate_graph_for_document(doc_a.id)
        graph_service.populate_graph_for_document(doc_d.id)

        with TestClient(app) as test_client:
            register_response = test_client.post(
                "/auth/register",
                json={
                    "username": auth_username,
                    "email": f"{auth_username}@example.com",
                    "password": "Password123",
                    "full_name": "Integration User",
                    "role": "viewer",
                },
            )
            if register_response.status_code not in {200, 409}:
                pytest.skip("Auth unavailable")

            login_response = test_client.post(
                "/auth/login",
                json={"username": auth_username, "password": "Password123"},
            )
            if login_response.status_code != 200:
                pytest.skip("Auth unavailable")

            access_token = login_response.json()["access_token"]
            response = test_client.get(
                f"/documents/{doc_a.id}/related",
                headers={"Authorization": f"Bearer {access_token}"},
            )

        assert response.status_code == 200
        body = response.json()
        items = {item["id"]: item for item in body["related"]}
        assert str(doc_d.id) in items
        assert sorted(items[str(doc_d.id)]["relation_types"]) == ["same_dosar", "same_furnizor"]

    except SQLAlchemyError as exc:
        db.rollback()
        pytest.skip(f"Postgres not available: {exc}")
    finally:
        auth_service._redis = original_redis
        db.close()

        with get_neo4j_session() as session:
            for doc_id in document_ids:
                session.run("MATCH (d:Document {id: $id}) DETACH DELETE d", id=str(doc_id))
            session.run("MATCH (d:Dosar {id: $dosar}) DETACH DELETE d", dosar=dosar_name)
            session.run("MATCH (f:Furnizor {CUI: $cui}) DETACH DELETE f", cui=cui)

        db = SessionLocal()
        try:
            db.query(ExtractedData).filter(ExtractedData.document_id.in_(document_ids)).delete(synchronize_session=False)
            db.query(Document).filter(Document.id.in_(document_ids)).delete(synchronize_session=False)
            db.query(User).filter(User.username.in_([doc_username, auth_username])).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("NEO4J_URI") is None,
    reason="NEO4j connection URL is not configured",
)
def test_related_documents_pagination(monkeypatch):
    try:
        db = SessionLocal()
    except Exception as exc:
        pytest.skip(f"Postgres not available: {exc}")

    original_redis = auth_service._redis
    auth_service._redis = FakeRedis()

    doc_username = f"rel_doc_user_{uuid4().hex[:8]}"
    auth_username = f"rel_auth_user_{uuid4().hex[:8]}"
    dosar_name = f"Dosar-{uuid4().hex[:6]}"
    document_ids = []

    try:
        user = _create_user(db, doc_username)
        doc_a = Document(
            document_number=f"DOC-{uuid4().hex[:6]}",
            document_type=DocumentTypeEnum.INVOICE,
            title="Doc A",
            file_path="uploads/doc-a.pdf",
            created_by_id=user.id,
            status=DocumentStatusEnum.ARCHIVED,
        )
        db.add(doc_a)
        db.commit()
        db.refresh(doc_a)
        document_ids.append(doc_a.id)

        db.add(
            ExtractedData(
                document_id=doc_a.id,
                field_name="dosar_propus",
                field_value=dosar_name,
                extraction_confidence=0.9,
            )
        )
        db.commit()

        for idx in range(25):
            document = Document(
                document_number=f"DOC-{uuid4().hex[:6]}",
                document_type=DocumentTypeEnum.REPORT,
                title=f"Doc {idx}",
                file_path=f"uploads/doc-{idx}.pdf",
                created_by_id=user.id,
                status=DocumentStatusEnum.ARCHIVED,
            )
            db.add(document)
            db.commit()
            db.refresh(document)
            document_ids.append(document.id)

            db.add(
                ExtractedData(
                    document_id=document.id,
                    field_name="dosar_propus",
                    field_value=dosar_name,
                    extraction_confidence=0.9,
                )
            )
            db.commit()

        for doc_id in document_ids:
            graph_service.populate_graph_for_document(doc_id)

        with TestClient(app) as test_client:
            register_response = test_client.post(
                "/auth/register",
                json={
                    "username": auth_username,
                    "email": f"{auth_username}@example.com",
                    "password": "Password123",
                    "full_name": "Integration User",
                    "role": "viewer",
                },
            )
            if register_response.status_code not in {200, 409}:
                pytest.skip("Auth unavailable")

            login_response = test_client.post(
                "/auth/login",
                json={"username": auth_username, "password": "Password123"},
            )
            if login_response.status_code != 200:
                pytest.skip("Auth unavailable")

            access_token = login_response.json()["access_token"]
            headers = {"Authorization": f"Bearer {access_token}"}

            response_page_1 = test_client.get(
                f"/documents/{doc_a.id}/related?page=1&page_size=20",
                headers=headers,
            )
            response_page_2 = test_client.get(
                f"/documents/{doc_a.id}/related?page=2&page_size=20",
                headers=headers,
            )

        assert response_page_1.status_code == 200
        assert response_page_2.status_code == 200
        body_1 = response_page_1.json()
        body_2 = response_page_2.json()
        assert body_1["total_count"] == 25
        assert len(body_1["related"]) == 20
        assert len(body_2["related"]) == 5

    except SQLAlchemyError as exc:
        db.rollback()
        pytest.skip(f"Postgres not available: {exc}")
    finally:
        auth_service._redis = original_redis
        db.close()

        with get_neo4j_session() as session:
            for doc_id in document_ids:
                session.run("MATCH (d:Document {id: $id}) DETACH DELETE d", id=str(doc_id))
            session.run("MATCH (d:Dosar {id: $dosar}) DETACH DELETE d", dosar=dosar_name)

        db = SessionLocal()
        try:
            db.query(ExtractedData).filter(ExtractedData.document_id.in_(document_ids)).delete(synchronize_session=False)
            db.query(Document).filter(Document.id.in_(document_ids)).delete(synchronize_session=False)
            db.query(User).filter(User.username.in_([doc_username, auth_username])).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()
