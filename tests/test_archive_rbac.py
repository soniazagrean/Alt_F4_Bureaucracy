from typing import Dict
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_db
from app.main import app
from app.models.archive import NomenclatorEntry, PastrareEnum, Dosar
from app.models.document import Document, DocumentStatusEnum, DocumentTypeEnum
from app.models.user import RoleEnum, User
from app.services.auth import auth_service


class FakeRedis:
    def __init__(self):
        self._store: Dict[str, str] = {}

    def setex(self, key: str, _ttl: int, value: str):
        self._store[key] = value

    def exists(self, key: str) -> int:
        return 1 if key in self._store else 0

    def delete(self, key: str) -> int:
        return 1 if self._store.pop(key, None) is not None else 0


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()

    # Minimal nomenclator seed required by /archive POST.
    db.add(
        NomenclatorEntry(
            code="II.1",
            name="Facturi",
            description="Nomenclator test entry",
            default_termen_pastrare=PastrareEnum.FIVE_YEARS,
        )
    )
    db.commit()

    yield db
    db.close()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    original_redis = auth_service._redis
    auth_service._redis = FakeRedis()
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    auth_service._redis = original_redis


def _create_user(db_session, username: str, role: RoleEnum) -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        hashed_password="not_used_in_this_test",
        role=role,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _access_token_for(db_session, username: str, role: RoleEnum) -> str:
    user = _create_user(db_session, username, role)
    return auth_service.create_token_pair(user)["access_token"]


def _auth_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_document(db_session, created_by_id: int, number: str) -> Document:
    doc = Document(
        document_number=number,
        document_type=DocumentTypeEnum.INVOICE,
        title=f"Doc {number}",
        description="Archive linking test document",
        file_path=f"uploads/{number}.pdf",
        file_hash=f"hash-{number}",
        status=DocumentStatusEnum.ARCHIVED,
        created_by_id=created_by_id,
        document_date=datetime.now(timezone.utc),
        amount=100.0,
        currency="RON",
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    return doc


def test_archive_create_allowed_for_admin_and_operator(client: TestClient, db_session):
    admin_token = _access_token_for(db_session, "admin_archive", RoleEnum.ADMIN)
    operator_token = _access_token_for(db_session, "operator_archive", RoleEnum.ARCHIVIST)

    payload_admin = {
        "dosar_number": "DOS-ADMIN-001",
        "title": "Dosar Admin",
        "description": "Created by admin",
        "nomenclator_id": 1,
        "termen_pastrare": "5_years",
    }
    payload_operator = {
        "dosar_number": "DOS-OP-001",
        "title": "Dosar Operator",
        "description": "Created by operator",
        "nomenclator_id": 1,
        "termen_pastrare": "5_years",
    }

    resp_admin = client.post("/archive/", json=payload_admin, headers=_auth_headers(admin_token))
    resp_operator = client.post("/archive/", json=payload_operator, headers=_auth_headers(operator_token))

    assert resp_admin.status_code == 201
    assert resp_operator.status_code == 201


def test_archive_create_forbidden_for_auditor(client: TestClient, db_session):
    auditor_token = _access_token_for(db_session, "auditor_archive", RoleEnum.VIEWER)

    payload = {
        "dosar_number": "DOS-AUD-001",
        "title": "Dosar Auditor",
        "description": "Should fail",
        "nomenclator_id": 1,
        "termen_pastrare": "5_years",
    }

    response = client.post("/archive/", json=payload, headers=_auth_headers(auditor_token))
    assert response.status_code == 403


def test_archive_list_and_get_allowed_for_auditor(client: TestClient, db_session):
    dosar = Dosar(
        dosar_number="DOS-VIEW-001",
        title="Dosar Vizibil",
        description="List and get should work",
        nomenclator_id=1,
        termen_pastrare=PastrareEnum.FIVE_YEARS,
    )
    db_session.add(dosar)
    db_session.commit()
    db_session.refresh(dosar)

    auditor_token = _access_token_for(db_session, "auditor_view_archive", RoleEnum.VIEWER)

    list_response = client.get("/archive/", headers=_auth_headers(auditor_token))
    get_response = client.get(f"/archive/dosar/{dosar.id}", headers=_auth_headers(auditor_token))

    assert list_response.status_code == 200
    assert get_response.status_code == 200


def test_archive_tree_endpoint_available_for_auditor(client: TestClient, db_session):
    parent = NomenclatorEntry(
        code="I",
        name="General",
        description="Parent category",
        default_termen_pastrare=PastrareEnum.FIVE_YEARS,
    )
    db_session.add(parent)
    db_session.commit()
    db_session.refresh(parent)

    child = NomenclatorEntry(
        code="I.1",
        name="Subcategory",
        description="Child category",
        parent_id=parent.id,
        default_termen_pastrare=PastrareEnum.THREE_YEARS,
    )
    db_session.add(child)
    db_session.commit()
    db_session.refresh(child)

    db_session.add(
        Dosar(
            dosar_number="DOS-TREE-001",
            title="Tree Dosar",
            description="Should appear under child",
            nomenclator_id=child.id,
            termen_pastrare=PastrareEnum.THREE_YEARS,
        )
    )
    db_session.commit()

    auditor_token = _access_token_for(db_session, "auditor_tree_archive", RoleEnum.VIEWER)
    response = client.get("/archive/tree", headers=_auth_headers(auditor_token))

    assert response.status_code == 200
    body = response.json()
    assert "roots" in body
    assert body["total_categories"] >= 1
    assert body["total_dosare"] >= 1


def test_archive_search_endpoint_returns_matches(client: TestClient, db_session):
    db_session.add(
        Dosar(
            dosar_number="DOS-SEARCH-001",
            title="Contracte 2026",
            description="Search test entry",
            nomenclator_id=1,
            termen_pastrare=PastrareEnum.FIVE_YEARS,
        )
    )
    db_session.commit()

    auditor_token = _access_token_for(db_session, "auditor_search_archive", RoleEnum.VIEWER)
    response = client.get("/archive/search?q=Contracte", headers=_auth_headers(auditor_token))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert len(body["items"]) >= 1


def test_archive_create_can_link_documents_to_dosar(client: TestClient, db_session):
    admin_user = _create_user(db_session, "admin_link_archive", RoleEnum.ADMIN)
    admin_token = auth_service.create_token_pair(admin_user)["access_token"]

    doc_a = _create_document(db_session, admin_user.id, "DOC-LINK-001")
    doc_b = _create_document(db_session, admin_user.id, "DOC-LINK-002")

    payload = {
        "dosar_number": "DOS-LINK-001",
        "title": "Dosar linked docs",
        "description": "Should link two documents",
        "nomenclator_id": 1,
        "termen_pastrare": "5_years",
        "document_ids": [doc_a.id, doc_b.id],
    }

    create_response = client.post("/archive/", json=payload, headers=_auth_headers(admin_token))
    assert create_response.status_code == 201
    body = create_response.json()
    assert sorted(body["linked_document_ids"]) == sorted([doc_a.id, doc_b.id])

    detail_response = client.get(f"/archive/dosar/{body['id']}", headers=_auth_headers(admin_token))
    assert detail_response.status_code == 200
    detail_body = detail_response.json()
    assert len(detail_body["documents"]) == 2


def test_archive_delete_admin_only(client: TestClient, db_session):
    dosar = Dosar(
        dosar_number="DOS-DEL-001",
        title="Dosar Delete",
        description="Delete auth test",
        nomenclator_id=1,
        termen_pastrare=PastrareEnum.FIVE_YEARS,
    )
    db_session.add(dosar)
    db_session.commit()
    db_session.refresh(dosar)

    operator_token = _access_token_for(db_session, "operator_delete_archive", RoleEnum.ARCHIVIST)
    admin_token = _access_token_for(db_session, "admin_delete_archive", RoleEnum.ADMIN)

    operator_response = client.delete(f"/archive/{dosar.id}", headers=_auth_headers(operator_token))
    assert operator_response.status_code == 403

    admin_response = client.delete(f"/archive/{dosar.id}", headers=_auth_headers(admin_token))
    assert admin_response.status_code == 200

    refreshed = db_session.query(Dosar).filter(Dosar.id == dosar.id).first()
    assert refreshed is not None
    assert refreshed.is_active == 0
    assert refreshed.archived_at is not None
