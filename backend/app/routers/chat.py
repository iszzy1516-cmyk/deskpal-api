"""Chat + conversation history."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_org_bot, request_ip, require_role
from app.models import Bot, Message, User
from app.ratelimit import limiter
from app.schemas import ChatRequest, ChatResponse, MessageOut
from app.services import rag

router = APIRouter(prefix="/api/bots/{bot_id}", tags=["chat"])

# The chatbot endpoint is public-facing in the product, but in this API it
# requires a user token (the owner testing in the playground). Rate limit is
# per-user: 20 questions / minute.
@router.post("/chat", response_model=ChatResponse)
def chat(
    bot_id: int,
    body: ChatRequest,
    request: Request,
    user: User = Depends(require_role("owner", "admin", "editor")),
    db: Session = Depends(get_db),
):
    if not limiter.check("chat", f"u{user.id}", max_hits=20, window_seconds=60):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Slow down — ask again in a moment")

    bot = get_org_bot(bot_id, user, db)
    answer, sources, used = rag.chat(bot, user.org_id, body.message.strip(), db)
    return ChatResponse(answer=answer, sources=sources, used_documents=used)


@router.get("/conversations", response_model=list[MessageOut])
def conversations(
    bot_id: int,
    user: User = Depends(require_role("owner", "admin", "editor")),
    db: Session = Depends(get_db),
):
    bot = get_org_bot(bot_id, user, db)
    return (
        db.query(Message)
        .filter(Message.bot_id == bot.id, Message.org_id == user.org_id)
        .order_by(Message.id.desc())
        .limit(100)
        .all()
    )
