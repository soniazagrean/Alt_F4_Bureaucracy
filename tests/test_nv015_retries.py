from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.models.document import Document, DocumentStatusEnum, DocumentTypeEnum
from app.models.user import User, RoleEnum
from app.celery_app import _mark_document_retry, _mark_document_dead_letter, recover_stuck_documents


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
def patch_celery_session(monkeypatch, db_session_factory):
    monkeypatch.setattr("app.celery_app.SessionLocal", db_session_factory)
    return db_session_factory


def create_user_and_document(db, **kwargs):
    username = kwargs.get("username", f"testuser_{kwargs.get('document_number', 'DOC-001')}".replace('-', '_'))
    email = kwargs.get("email", f"{username}@example.com")

    user = User(
        username=username,
        email=email,
        hashed_password="secret",
        role=RoleEnum.SYSTEM,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    document_number = kwargs.get("document_number", "DOC-001")
    document = Document(
        document_number=document_number,
        document_type=kwargs.get("document_type", DocumentTypeEnum.INVOICE),
        title=kwargs.get("title", "Test Document"),
        file_path=kwargs.get("file_path", f"uploads/{document_number}.pdf"),
        file_hash=kwargs.get("file_hash", f"hash_{document_number}"),
        status=kwargs.get("status", DocumentStatusEnum.PROCESSING),
        retry_count=kwargs.get("retry_count", 0),
        created_by_id=user.id,
        document_date=datetime.now(timezone.utc),
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def test_mark_document_retry_increments_retry_count(patch_celery_session):
    TestingSessionLocal = patch_celery_session
    db = TestingSessionLocal()
    try:
        document = create_user_and_document(db, retry_count=0, status=DocumentStatusEnum.PROCESSING)
        _mark_document_retry(document.id, "simulated failure")

        db.refresh(document)
        assert document.retry_count == 1
        assert document.status == DocumentStatusEnum.PROCESSING
        assert document.error_message == "simulated failure"
        assert document.error_timestamp is not None
    finally:
        db.close()


def test_recover_stuck_documents_resets_and_dead_letters(patch_celery_session):
    TestingSessionLocal = patch_celery_session
    db = TestingSessionLocal()
    try:
        old_time = datetime.now(timezone.utc) - timedelta(minutes=20)
        doc_reset = create_user_and_document(
            db,
            document_number="DOC-RESET",
            retry_count=1,
            status=DocumentStatusEnum.PROCESSING,
        )
        doc_hang = create_user_and_document(
            db,
            document_number="DOC-HANG",
            retry_count=3,
            status=DocumentStatusEnum.PROCESSING,
        )
        doc_reset.updated_at = old_time
        doc_hang.updated_at = old_time
        db.commit()

        result = recover_stuck_documents()

        db.refresh(doc_reset)
        db.refresh(doc_hang)
        assert doc_reset.status == DocumentStatusEnum.PENDING
        assert doc_hang.status == DocumentStatusEnum.ERROR
        assert result["reset_documents"] == 1
        assert result["dead_letter_documents"] == 1
    finally:
        db.close()


def test_dead_letter_logs_error_on_final_failure(patch_celery_session, caplog):
    TestingSessionLocal = patch_celery_session
    db = TestingSessionLocal()
    try:
        document = create_user_and_document(db, retry_count=3, status=DocumentStatusEnum.PROCESSING)
        caplog.set_level("ERROR")

        _mark_document_dead_letter(document.id, "final failure", attempt_count=4)

        db.refresh(document)
        assert document.status == DocumentStatusEnum.ERROR
        assert document.error_message == "final failure"
        assert "permanently failed after 4 attempts" in caplog.text
    finally:
        db.close()
