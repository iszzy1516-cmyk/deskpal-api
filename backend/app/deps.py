"""FastAPI dependencies: authentication, RBAC, and tenant scoping.

This file is the security boundary of the whole API:
- get_current_user: parses the Bearer token, loads the user, refuses inactive
  accounts.
- require_role: role-based access control (owner > admin > editor).
- Scoped queries: bots/documents are always fetched with org_id in the filter,
  so a token from org A can never address org B's resources — even by guessing
  sequential integer IDs. The cross-tenant test in tests/ proves this.
"""
from typing import Literal

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Bot, Document, User
from app.security import decode_access_token

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    payload = decode_access_token(creds.credentials)
    if payload is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found or disabled")
    return user


def require_role(*roles: Literal["owner", "admin", "editor"]):
    """RBAC dependency factory. Usage: Depends(require_role('owner', 'admin'))"""
    allowed = set(roles)

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Requires one of these roles: {sorted(allowed)}",
            )
        return user

    return checker


def get_org_bot(bot_id: int, user: User, db: Session) -> Bot:
    """Fetch a bot ONLY if it belongs to the caller's organization."""
    bot = db.query(Bot).filter(Bot.id == bot_id, Bot.org_id == user.org_id).first()
    if bot is None:
        # 404, not 403: we don't reveal whether the ID exists in another org.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bot not found")
    return bot


def get_org_document(document_id: int, bot_id: int, user: User, db: Session) -> Document:
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.bot_id == bot_id, Document.org_id == user.org_id)
        .first()
    )
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return doc


def request_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"
