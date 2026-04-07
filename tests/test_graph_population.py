import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base, SessionLocal
from app.db.neo4j import get_neo4j_session
from app.models.document import Document, DocumentStatusEnum, DocumentTypeEnum, ExtractedData
from app.models.user import User, RoleEnum
import app.services.graph_service as graph_service


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


@pytest.fixture()
def db_session_factory():
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
    return TestingSessionLocal


@pytest.fixture()
def patch_graph_session(monkeypatch, db_session_factory):
    monkeypatch.setattr(graph_service, "SessionLocal", db_session_factory)
    return db_session_factory


def test_populate_graph_for_document_full_data(patch_graph_session, monkeypatch):
    db = patch_graph_session()
    try:
        user = _create_user(db, "graph_user")
        document = Document(
            document_number="DOC-100",
            document_type=DocumentTypeEnum.INVOICE,
            title="Test Invoice",
            file_path="uploads/doc-100.pdf",
            created_by_id=user.id,
            status=DocumentStatusEnum.ARCHIVED,
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        db.add_all(
            [
                ExtractedData(
                    document_id=document.id,
                    field_name="nr_factura",
                    field_value="INV-001",
                    extraction_confidence=0.9,
                ),
                ExtractedData(
                    document_id=document.id,
                    field_name="data",
                    field_value="2024-03-15",
                    extraction_confidence=0.9,
                ),
                ExtractedData(
                    document_id=document.id,
                    field_name="furnizor",
                    field_value="Supplier SRL",
                    extraction_confidence=0.9,
                ),
                ExtractedData(
                    document_id=document.id,
                    field_name="CUI",
                    field_value="12345678",
                    extraction_confidence=0.9,
                ),
                ExtractedData(
                    document_id=document.id,
                    field_name="IBAN",
                    field_value="RO49AAAA1B31007593840000",
                    extraction_confidence=0.9,
                ),
                ExtractedData(
                    document_id=document.id,
                    field_name="total",
                    field_value="238.00",
                    extraction_confidence=0.9,
                ),
                ExtractedData(
                    document_id=document.id,
                    field_name="cod_nomenclator",
                    field_value="II.1",
                    extraction_confidence=0.9,
                ),
                ExtractedData(
                    document_id=document.id,
                    field_name="dosar_propus",
                    field_value="Financial Documents 2024",
                    extraction_confidence=0.9,
                ),
                ExtractedData(
                    document_id=document.id,
                    field_name="termen_pastrare",
                    field_value="7_years",
                    extraction_confidence=0.9,
                ),
            ]
        )
        db.commit()
        document_id = document.id
    finally:
        db.close()

    called = {
        "document": None,
        "furnizor": None,
        "dosar": None,
        "nomenclator": None,
        "doc_dosar": None,
        "doc_furnizor": None,
        "dosar_nomenclator": None,
    }

    def capture_document_node(payload):
        called["document"] = payload
        return {}

    def capture_furnizor_node(cui, name, iban=None):
        called["furnizor"] = (cui, name, iban)
        return {}

    def capture_dosar_node(payload):
        called["dosar"] = payload
        return {}

    def capture_nomenclator_node(payload):
        called["nomenclator"] = payload
        return {}

    def capture_link_doc_dosar(doc_id, dosar_id):
        called["doc_dosar"] = (doc_id, dosar_id)
        return {}

    def capture_link_doc_furnizor(doc_id, cui):
        called["doc_furnizor"] = (doc_id, cui)
        return {}

    def capture_link_dosar_nomenclator(dosar_id, code):
        called["dosar_nomenclator"] = (dosar_id, code)
        return {}

    monkeypatch.setattr(graph_service, "create_document_node", capture_document_node)
    monkeypatch.setattr(graph_service, "create_furnizor_node", capture_furnizor_node)
    monkeypatch.setattr(graph_service, "create_dosar_node", capture_dosar_node)
    monkeypatch.setattr(graph_service, "create_nomenclator_node", capture_nomenclator_node)
    monkeypatch.setattr(graph_service, "link_document_to_dosar", capture_link_doc_dosar)
    monkeypatch.setattr(graph_service, "link_document_to_furnizor", capture_link_doc_furnizor)
    monkeypatch.setattr(graph_service, "link_dosar_to_nomenclator", capture_link_dosar_nomenclator)

    graph_service.populate_graph_for_document(document_id)

    assert called["document"] is not None
    doc_node = called["document"]
    assert doc_node.id == str(document_id)
    assert doc_node.nr_factura == "INV-001"
    assert doc_node.tip_document == "invoice"
    assert doc_node.data == "2024-03-15"
    assert doc_node.total == 238.0
    assert doc_node.status == "archived"

    assert called["furnizor"] == (
        "12345678",
        "Supplier SRL",
        "RO49AAAA1B31007593840000",
    )
    assert called["dosar"]["id"] == "Financial Documents 2024"
    assert called["doc_dosar"] == (str(document_id), "Financial Documents 2024")
    assert called["doc_furnizor"] == (str(document_id), "12345678")
    assert called["nomenclator"]["code"] == "II.1"
    assert called["dosar_nomenclator"] == ("Financial Documents 2024", "II.1")


def test_populate_graph_for_document_skips_optional_fields(patch_graph_session, monkeypatch):
    db = patch_graph_session()
    try:
        user = _create_user(db, "graph_user_partial")
        document = Document(
            document_number="DOC-101",
            document_type=DocumentTypeEnum.REPORT,
            title="Test Report",
            file_path="uploads/doc-101.pdf",
            created_by_id=user.id,
            status=DocumentStatusEnum.ARCHIVED,
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        db.add(
            ExtractedData(
                document_id=document.id,
                field_name="nr_factura",
                field_value="INV-002",
                extraction_confidence=0.8,
            )
        )
        db.commit()
        document_id = document.id
    finally:
        db.close()

    calls = {"furnizor": 0, "dosar": 0, "doc_furnizor": 0, "doc_dosar": 0}

    monkeypatch.setattr(graph_service, "create_document_node", lambda payload: {})
    monkeypatch.setattr(graph_service, "create_furnizor_node", lambda *args, **kwargs: calls.__setitem__("furnizor", calls["furnizor"] + 1) or {})
    monkeypatch.setattr(graph_service, "create_dosar_node", lambda *args, **kwargs: calls.__setitem__("dosar", calls["dosar"] + 1) or {})
    monkeypatch.setattr(graph_service, "link_document_to_furnizor", lambda *args, **kwargs: calls.__setitem__("doc_furnizor", calls["doc_furnizor"] + 1) or {})
    monkeypatch.setattr(graph_service, "link_document_to_dosar", lambda *args, **kwargs: calls.__setitem__("doc_dosar", calls["doc_dosar"] + 1) or {})

    graph_service.populate_graph_for_document(document_id)

    assert calls["furnizor"] == 0
    assert calls["dosar"] == 0
    assert calls["doc_furnizor"] == 0
    assert calls["doc_dosar"] == 0


def test_populate_graph_for_document_logs_error(patch_graph_session, monkeypatch, caplog):
    db = patch_graph_session()
    try:
        user = _create_user(db, "graph_user_error")
        document = Document(
            document_number="DOC-102",
            document_type=DocumentTypeEnum.OTHER,
            title="Test Other",
            file_path="uploads/doc-102.pdf",
            created_by_id=user.id,
            status=DocumentStatusEnum.ARCHIVED,
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        document_id = document.id
    finally:
        db.close()

    def raise_error(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(graph_service, "create_document_node", raise_error)
    caplog.set_level("ERROR")

    graph_service.populate_graph_for_document(document_id)

    assert "populate_graph_for_document" in caplog.text


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("NEO4J_URI") is None,
    reason="NEO4j connection URL is not configured",
)
def test_populate_graph_for_document_integration():
    document_id = None
    username = f"graph_user_{uuid4().hex[:8]}"
    cui = f"{uuid4().int % 10000000000:010d}"

    try:
        db = SessionLocal()
    except Exception as exc:
        pytest.skip(f"Postgres not available: {exc}")

    try:
        user = _create_user(db, username)
        document = Document(
            document_number=f"DOC-{uuid4().hex[:6]}",
            document_type=DocumentTypeEnum.INVOICE,
            title="Integration Invoice",
            file_path="uploads/integration-doc.pdf",
            created_by_id=user.id,
            status=DocumentStatusEnum.ARCHIVED,
            amount=123.45,
            document_date=datetime.now(timezone.utc),
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        db.add_all(
            [
                ExtractedData(
                    document_id=document.id,
                    field_name="furnizor",
                    field_value="Integration Supplier",
                    extraction_confidence=0.9,
                ),
                ExtractedData(
                    document_id=document.id,
                    field_name="CUI",
                    field_value=cui,
                    extraction_confidence=0.9,
                ),
            ]
        )
        db.commit()
        document_id = document.id
    except SQLAlchemyError as exc:
        db.rollback()
        pytest.skip(f"Postgres not available: {exc}")
    finally:
        db.close()

    graph_service.populate_graph_for_document(document_id)

    with get_neo4j_session() as session:
        doc_record = session.run(
            "MATCH (d:Document {id: $id}) RETURN d AS node",
            id=str(document_id),
        ).single()
        furnizor_record = session.run(
            "MATCH (f:Furnizor {CUI: $cui}) RETURN f AS node",
            cui=cui,
        ).single()
        relation_record = session.run(
            "MATCH (d:Document {id: $id})-[:EMIS_DE]->(f:Furnizor {CUI: $cui}) "
            "RETURN count(d) AS count",
            id=str(document_id),
            cui=cui,
        ).single()

    assert doc_record is not None
    assert furnizor_record is not None
    assert relation_record["count"] == 1

    with get_neo4j_session() as session:
        session.run("MATCH (d:Document {id: $id}) DETACH DELETE d", id=str(document_id))
        session.run("MATCH (f:Furnizor {CUI: $cui}) DETACH DELETE f", cui=cui)

    db = SessionLocal()
    try:
        db.query(ExtractedData).filter(ExtractedData.document_id == document_id).delete()
        db.query(Document).filter(Document.id == document_id).delete()
        db.query(User).filter(User.username == username).delete()
        db.commit()
    finally:
        db.close()


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("NEO4J_URI") is None,
    reason="NEO4j connection URL is not configured",
)
def test_graph_population_deduplicates_furnizor():
    document_ids = []
    username = f"graph_user_{uuid4().hex[:8]}"
    cui = f"{uuid4().int % 10000000000:010d}"

    try:
        db = SessionLocal()
    except Exception as exc:
        pytest.skip(f"Postgres not available: {exc}")

    try:
        user = _create_user(db, username)
        for idx in range(2):
            document = Document(
                document_number=f"DOC-{uuid4().hex[:6]}",
                document_type=DocumentTypeEnum.INVOICE,
                title=f"Integration Invoice {idx + 1}",
                file_path=f"uploads/integration-doc-{idx + 1}.pdf",
                created_by_id=user.id,
                status=DocumentStatusEnum.ARCHIVED,
                amount=100 + idx,
                document_date=datetime.now(timezone.utc),
            )
            db.add(document)
            db.commit()
            db.refresh(document)
            document_ids.append(document.id)

            db.add_all(
                [
                    ExtractedData(
                        document_id=document.id,
                        field_name="furnizor",
                        field_value="Integration Supplier",
                        extraction_confidence=0.9,
                    ),
                    ExtractedData(
                        document_id=document.id,
                        field_name="CUI",
                        field_value=cui,
                        extraction_confidence=0.9,
                    ),
                ]
            )
            db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        pytest.skip(f"Postgres not available: {exc}")
    finally:
        db.close()

    for document_id in document_ids:
        graph_service.populate_graph_for_document(document_id)

    with get_neo4j_session() as session:
        furnizor_count = session.run(
            "MATCH (f:Furnizor {CUI: $cui}) RETURN count(f) AS count",
            cui=cui,
        ).single()
        relations_count = session.run(
            "MATCH (d:Document)-[:EMIS_DE]->(f:Furnizor {CUI: $cui}) "
            "RETURN count(d) AS count",
            cui=cui,
        ).single()

    assert furnizor_count["count"] == 1
    assert relations_count["count"] == 2

    with get_neo4j_session() as session:
        session.run("MATCH (d:Document)-[:EMIS_DE]->(f:Furnizor {CUI: $cui}) DETACH DELETE d", cui=cui)
        session.run("MATCH (f:Furnizor {CUI: $cui}) DETACH DELETE f", cui=cui)

    db = SessionLocal()
    try:
        db.query(ExtractedData).filter(ExtractedData.document_id.in_(document_ids)).delete(synchronize_session=False)
        db.query(Document).filter(Document.id.in_(document_ids)).delete(synchronize_session=False)
        db.query(User).filter(User.username == username).delete()
        db.commit()
    finally:
        db.close()
