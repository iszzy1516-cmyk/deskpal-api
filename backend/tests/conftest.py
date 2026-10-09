"""Shared test fixtures: isolated sqlite DB per test, limiter reset."""
import os
import tempfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    # Fresh DB file per test so nothing leaks between tests.
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.environ["DATABASE_URL"] = f"sqlite:///{path}"
    os.environ["JWT_SECRET"] = "test-secret"
    os.environ["OPENAI_API_KEY"] = ""  # force stub embedding mode

    # Settings are lru_cached + engine bound at import: build app fresh.
    from app import config
    config.get_settings.cache_clear()
    import app.database as database
    import app.ratelimit as ratelimit

    database.engine.dispose()
    from app.config import get_settings
    settings = get_settings()
    database.engine = database.create_engine(
        settings.database_url, connect_args={"check_same_thread": False}
    )
    database.SessionLocal = database.sessionmaker(
        bind=database.engine, autoflush=False, autocommit=False
    )
    from app.main import app
    from app.database import Base
    Base.metadata.create_all(bind=database.engine)
    ratelimit.limiter._hits.clear()

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    database.engine.dispose()
    os.unlink(path)


def signup(client, email="owner@shop.com", org="Shop", name="Owner", password="passw0rd123"):
    r = client.post("/api/auth/signup", json={
        "org_name": org, "full_name": name, "email": email, "password": password,
    })
    assert r.status_code == 201, r.text
    return r.json()


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def make_bot(client, token, name="Support Bot"):
    r = client.post("/api/bots", json={"name": name}, headers=auth_headers(token))
    assert r.status_code == 201, r.text
    return r.json()
