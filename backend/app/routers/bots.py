"""Bot management. Every route is org-scoped through deps.get_org_bot."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, get_org_bot, require_role
from app.models import Bot, User
from app.schemas import BotCreateRequest, BotOut

router = APIRouter(prefix="/api/bots", tags=["bots"])

# All three roles can manage bots for v1 (editors run the day-to-day).
BOT_ROLES = ("owner", "admin", "editor")


@router.post("", response_model=BotOut, status_code=status.HTTP_201_CREATED)
def create_bot(
    body: BotCreateRequest,
    user: User = Depends(require_role(*BOT_ROLES)),
    db: Session = Depends(get_db),
):
    bot = Bot(org_id=user.org_id, name=body.name, widget_settings=body.widget_settings)
    db.add(bot)
    db.commit()
    return bot


@router.get("", response_model=list[BotOut])
def list_bots(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Bot).filter(Bot.org_id == user.org_id).order_by(Bot.id.desc()).all()


@router.delete("/{bot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bot(
    bot_id: int,
    user: User = Depends(require_role("owner", "admin")),  # editors can't delete bots
    db: Session = Depends(get_db),
):
    bot = get_org_bot(bot_id, user, db)
    db.delete(bot)
    db.commit()
