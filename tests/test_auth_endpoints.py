from typing import Dict

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_db
from app.main import app
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
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
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
        yield test_client

    app.dependency_overrides.clear()
    auth_service._redis = original_redis


def _register_user(client: TestClient, username: str = "alice", email: str = "alice@example.com"):
    return client.post(
        "/auth/register",
        json={
            "username": username,
            "email": email,
            "password": "Password123",
            "full_name": "Alice",
            "role": "viewer",
        },
    )


def _login_user(client: TestClient, username: str = "alice"):
    return client.post(
        "/auth/login",
        json={"username": username, "password": "Password123"},
    )


def test_register_login_and_me_flow(client: TestClient):
    register_resp = _register_user(client)
    assert register_resp.status_code == 200

    login_resp = _login_user(client)
    assert login_resp.status_code == 200
    tokens = login_resp.json()

    me_resp = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert me_resp.status_code == 200
    me_body = me_resp.json()
    assert me_body["username"] == "alice"
    assert me_body["email"] == "alice@example.com"


def test_refresh_rotates_and_old_refresh_becomes_invalid(client: TestClient):
    _register_user(client, username="bob", email="bob@example.com")

    login_resp = _login_user(client, username="bob")
    refresh_1 = login_resp.json()["refresh_token"]

    refresh_resp = client.post("/auth/refresh", json={"refresh_token": refresh_1})
    assert refresh_resp.status_code == 200
    refresh_2 = refresh_resp.json()["refresh_token"]
    assert refresh_2 != refresh_1

    old_refresh_resp = client.post("/auth/refresh", json={"refresh_token": refresh_1})
    assert old_refresh_resp.status_code == 401


def test_logout_revokes_refresh_token(client: TestClient):
    _register_user(client, username="carol", email="carol@example.com")

    login_resp = _login_user(client, username="carol")
    refresh_token = login_resp.json()["refresh_token"]

    logout_resp = client.post("/auth/logout", json={"refresh_token": refresh_token})
    assert logout_resp.status_code == 200

    refresh_after_logout = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_after_logout.status_code == 401


def test_register_duplicate_username_returns_409(client: TestClient):
    first = _register_user(client, username="dana", email="dana1@example.com")
    assert first.status_code == 200

    second = _register_user(client, username="dana", email="dana2@example.com")
    assert second.status_code == 409
