from typing import Dict

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_db
from app.main import app
from app.models.archive import NomenclatorEntry, PastrareEnum, Dosar
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
    get_response = client.get(f"/archive/{dosar.id}", headers=_auth_headers(auditor_token))

    assert list_response.status_code == 200
    assert get_response.status_code == 200


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
