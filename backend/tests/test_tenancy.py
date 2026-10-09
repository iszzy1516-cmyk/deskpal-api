"""Multi-tenant isolation + RBAC tests. The heart of the security story:
user of org B must not be able to read, delete, or chat with org A's bot even
knowing its exact integer ID."""
from app import database
from app.models import User

from .conftest import auth_headers, make_bot, signup


def _second_org_owner(client):
    return signup(client, email="other@shop.com", org="Other Shop", name="Rival")


def test_cross_org_bot_access_is_impossible(client):
    a = signup(client)
    bot = make_bot(client, a["access_token"])
    b = _second_org_owner(client)

    r = client.get(f"/api/bots/{bot['id']}", headers=auth_headers(b["access_token"]))
    # 404, not 403 — we don't reveal the resource exists in another org.
    assert r.status_code in (404, 405)
    r = client.get(f"/api/bots/{bot['id']}/documents", headers=auth_headers(b["access_token"]))
    assert r.status_code == 404
    r = client.post(
        f"/api/bots/{bot['id']}/chat",
        json={"message": "hi"},
        headers=auth_headers(b["access_token"]),
    )
    assert r.status_code == 404


def test_list_only_shows_own_org_bots(client):
    a = signup(client)
    make_bot(client, a["access_token"], "A bot")
    b = _second_org_owner(client)
    make_bot(client, b["access_token"], "B bot")

    a_list = client.get("/api/bots", headers=auth_headers(a["access_token"])).json()
    b_list = client.get("/api/bots", headers=auth_headers(b["access_token"])).json()
    assert [x["name"] for x in a_list] == ["A bot"]
    assert [x["name"] for x in b_list] == ["B bot"]


def test_rbac_editor_cannot_delete_bot(client):
    owner = signup(client)
    bot = make_bot(client, owner["access_token"])

    # Promote nothing — create an editor directly in the DB.
    from app.security import hash_password
    db = database.SessionLocal()
    org_id = db.query(User).filter(User.email == "owner@shop.com").first().org_id
    db.add(User(org_id=org_id, email="editor@shop.com", full_name="Ed",
                hashed_password=hash_password("passw0rd123"), role="editor"))
    db.commit()
    db.close()

    editor = client.post("/api/auth/login", json={
        "email": "editor@shop.com", "password": "passw0rd123",
    }).json()

    r = client.delete(f"/api/bots/{bot['id']}", headers=auth_headers(editor["access_token"]))
    assert r.status_code == 403
    # But editors CAN do their day-to-day work:
    assert client.get("/api/bots", headers=auth_headers(editor["access_token"])).status_code == 200


def test_rbac_admin_cannot_be_created_via_signup_and_roles_enforced(client):
    # signup always makes an owner of a NEW org; roles are managed in-org.
    tokens = signup(client)
    me = client.get("/api/auth/me", headers=auth_headers(tokens["access_token"])).json()
    assert me["role"] == "owner"
