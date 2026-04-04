from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_db
from app.main import app
from app.models.document import Document, DocumentStatusEnum, DocumentTypeEnum, ExtractedData
from app.models.user import RoleEnum, User
from app.services.auth import auth_service
from app.services.storage import storage


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
    original_presign = storage.client.presigned_get_object
    auth_service._redis = FakeRedis()
    storage.client.presigned_get_object = lambda bucket_name, object_name, expires=None: f"http://minio.local/{bucket_name}/{object_name}?expires=900"
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client, TestingSessionLocal

    app.dependency_overrides.clear()
    auth_service._redis = original_redis
    storage.client.presigned_get_object = original_presign


@pytest.fixture()
def auth_headers(client):
    test_client, _ = client
    register_response = test_client.post(
        "/auth/register",
        json={
            "username": "viewer1",
            "email": "viewer1@example.com",
            "password": "Password123",
            "full_name": "Viewer One",
            "role": "viewer",
        },
    )
    assert register_response.status_code == 200

    login_response = test_client.post(
        "/auth/login",
        json={"username": "viewer1", "password": "Password123"},
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {access_token}"}


def test_get_document_returns_full_details(client, auth_headers):
    test_client, session_factory = client
    db = session_factory()
    try:
        user = db.query(User).filter(User.username == "viewer1").first()
        document = Document(
            document_number="DOC-001",
            document_type=DocumentTypeEnum.INVOICE,
            title="Test Invoice",
            description="Invoice for testing",
            amount=123.45,
            currency="RON",
            file_path="uploads/test-doc.pdf",
            file_size=2048,
            mime_type="application/pdf",
            file_hash="abc123",
            status=DocumentStatusEnum.ARCHIVED,
            fraud_score=0.1,
            confidence=0.95,
            created_by_id=user.id,
            document_date=datetime.now(timezone.utc),
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        db.add(
            ExtractedData(
                document_id=document.id,
                field_name="invoice_number",
                field_value="INV-001",
                extraction_confidence=0.99,
            )
        )
        db.commit()
        document_id = document.id
    finally:
        db.close()

    response = test_client.get(f"/documents/{document_id}", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == document.id
    assert body["document_number"] == "DOC-001"
    assert body["preview_url"].startswith("http://minio.local/uploads/test-doc.pdf")
    assert body["extracted_data"][0]["field_name"] == "invoice_number"
    assert body["classification"]["confidence"] == pytest.approx(0.95)


def test_get_document_returns_202_when_processing(client, auth_headers):
    test_client, session_factory = client
    db = session_factory()
    try:
        user = db.query(User).filter(User.username == "viewer1").first()
        document = Document(
            document_number="DOC-002",
            document_type=DocumentTypeEnum.REPORT,
            title="Processing Report",
            file_path="uploads/processing-doc.pdf",
            file_size=1024,
            mime_type="application/pdf",
            file_hash="abc124",
            status=DocumentStatusEnum.PROCESSING,
            created_by_id=user.id,
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        document_id = document.id
    finally:
        db.close()

    response = test_client.get(f"/documents/{document_id}", headers=auth_headers)
    assert response.status_code == 202
    assert response.json()["status"] == "processing"
