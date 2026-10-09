"""Auth + security tests: hashing, validation, rate limiting, token flow."""
from app.security import hash_password, verify_password

from .conftest import auth_headers, signup


def test_password_hash_is_not_plaintext_and_verifies():
    h = hash_password("passw0rd123")
    assert h != "passw0rd123"
    assert h.startswith("$2b$12$")  # bcrypt, 12 rounds
    assert verify_password("passw0rd123", h)
    assert not verify_password("wrongpass1", h)


def test_signup_creates_org_and_owner(client):
    tokens = signup(client)
    assert tokens["access_token"] and tokens["refresh_token"]
    me = client.get("/api/auth/me", headers=auth_headers(tokens["access_token"]))
    assert me.status_code == 200
    body = me.json()
    assert body["role"] == "owner"
    assert body["org_plan"] == "free"
    assert body["email"] == "owner@shop.com"


def test_signup_rejects_weak_password(client):
    r = client.post("/api/auth/signup", json={
        "org_name": "Shop", "full_name": "Owner",
        "email": "a@b.com", "password": "short",
    })
    assert r.status_code == 422


def test_signup_rejects_duplicate_email_without_revealing_account(client):
    signup(client)
    r = client.post("/api/auth/signup", json={
        "org_name": "Other", "full_name": "Someone",
        "email": "owner@shop.com", "password": "passw0rd123",
    })
    assert r.status_code == 400
    assert "exist" not in r.json()["detail"].lower()


def test_login_success_and_failure_is_generic(client):
    signup(client)
    ok = client.post("/api/auth/login", json={"email": "owner@shop.com", "password": "passw0rd123"})
    assert ok.status_code == 200
    for bad in ({"email": "owner@shop.com", "password": "nope12345"},
                {"email": "ghost@shop.com", "password": "passw0rd123"}):
        r = client.post("/api/auth/login", json=bad)
        assert r.status_code == 401
        assert r.json()["detail"] == "Invalid credentials"


def test_login_rate_limited_after_5_attempts(client):
    signup(client)
    last = None
    for _ in range(6):
        last = client.post("/api/auth/login", json={"email": "owner@shop.com", "password": "wrong123"})
    assert last.status_code == 429


def test_refresh_rotates_and_rejects_reuse(client):
    tokens = signup(client)
    r = client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200
    rotated = r.json()
    assert rotated["refresh_token"] != tokens["refresh_token"]

    # Old token is dead — and using it again triggers session-wide revocation.
    again = client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert again.status_code == 401
    reuse = client.post("/api/auth/refresh", json={"refresh_token": rotated["refresh_token"]})
    assert reuse.status_code == 401  # everything revoked after reuse detected


def test_protected_route_rejects_missing_and_bad_tokens(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_security_headers_present(client):
    r = client.get("/api/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
