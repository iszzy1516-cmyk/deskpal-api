"""Authentication routes: signup, login, refresh, me.

Rate limiting on the brute-force targets: 5 login attempts / minute / IP and
10 signups / minute / IP. Login failures are always the same generic 401 so
the endpoint can't be used to enumerate which emails are registered.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, request_ip
from app.models import Organization, RefreshToken, User
from app.ratelimit import limiter
from app.schemas import (
    LoginRequest, RefreshRequest, SignupRequest, TokenResponse, UserOut,
)
from app.security import (
    create_access_token, generate_refresh_token, hash_password,
    hash_refresh_token, verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _issue_tokens(db: Session, user: User) -> TokenResponse:
    raw, token_hash, expires_at = generate_refresh_token()
    db.add(RefreshToken(user_id=user.id, token_hash=token_hash, expires_at=expires_at))
    db.commit()
    return TokenResponse(
        access_token=create_access_token(user.id, user.org_id, user.role),
        refresh_token=raw,
    )


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest, request: Request, db: Session = Depends(get_db)):
    if not limiter.check("signup", request_ip(request), max_hits=10, window_seconds=60):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts — try again in a minute")

    existing = db.query(User).filter(User.email == body.email.lower()).first()
    if existing:
        # Same generic behavior as login: don't reveal the account exists.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Could not create account")

    org = Organization(name=body.org_name, plan="free")
    db.add(org)
    db.flush()
    user = User(
        org_id=org.id,
        email=body.email.lower(),
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        role="owner",
    )
    db.add(user)
    db.commit()
    return _issue_tokens(db, user)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    if not limiter.check("login", request_ip(request), max_hits=5, window_seconds=60):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts — try again in a minute")

    user = db.query(User).filter(User.email == body.email.lower()).first()
    # Generic failure message on purpose — no account enumeration.
    if user is None or not user.is_active or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    return _issue_tokens(db, user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    token_hash = hash_refresh_token(body.refresh_token)
    row = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()

    # Reuse of a revoked token = the raw token leaked. Kill the whole session.
    if row is not None and row.revoked:
        db.query(RefreshToken).filter(RefreshToken.user_id == row.user_id).update({"revoked": True})
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token reuse detected")

    if (
        row is None
        or row.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc)
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")

    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found or disabled")

    # Rotate: the old token dies the moment the new one is issued.
    row.revoked = True
    return _issue_tokens(db, user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        org_id=user.org_id,
        org_name=user.org.name,
        org_plan=user.org.plan,
    )
