"""Document upload + management.

Upload path: extension allow-list → size cap → text extraction (which rejects
empty/garbled files) → save to storage dir → queue background processing.

Filename semantics (product decision): uploading a file whose name already
exists for the bot REPLACES its content — old chunks are deleted, the document
is re-indexed, and an activity-style `updated_at` bump records the change.
"""
import os
import re
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import get_org_bot, get_org_document, require_role
from app.models import Bot, Chunk, Document, User
from app.schemas import DocumentOut
from app.worker import process_document

settings = get_settings()
router = APIRouter(prefix="/api/bots/{bot_id}/documents", tags=["documents"])

SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    bot_id: int,
    file: UploadFile,
    background: BackgroundTasks,
    user: User = Depends(require_role("owner", "admin", "editor")),
    db: Session = Depends(get_db),
):
    bot = get_org_bot(bot_id, user, db)

    filename = os.path.basename(file.filename or "")
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in {".pdf", ".docx", ".txt"}:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Only .pdf, .docx and .txt files are supported")

    data = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"File exceeds the {settings.max_upload_mb}MB limit")

    # Basic content sanity before we touch storage.
    from app.services.documents import extract_text

    try:
        text = extract_text(filename, data)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))

    os.makedirs(settings.storage_dir, exist_ok=True)
    safe_name = SAFE_FILENAME.sub("_", filename)
    disk_path = os.path.join(settings.storage_dir, f"{bot_id}_{safe_name}")
    with open(disk_path, "wb") as fh:
        fh.write(data)

    # Same filename → replace (delete old chunks, reuse the row).
    doc = db.query(Document).filter(Document.bot_id == bot.id, Document.filename == filename).first()
    if doc:
        db.query(Chunk).filter(Chunk.document_id == doc.id).delete()
        doc.content_text = text
        doc.status = "pending"
        doc.quarantined_chunks = 0
        doc.updated_at = datetime.utcnow()
    else:
        doc = Document(bot_id=bot.id, org_id=bot.org_id, filename=filename, content_text=text)
        db.add(doc)
    db.commit()

    background.add_task(process_document, doc.id)
    return doc


@router.get("", response_model=list[DocumentOut])
def list_documents(
    bot_id: int,
    user: User = Depends(require_role("owner", "admin", "editor")),
    db: Session = Depends(get_db),
):
    bot = get_org_bot(bot_id, user, db)
    return db.query(Document).filter(Document.bot_id == bot.id).order_by(Document.id.desc()).all()


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    bot_id: int,
    document_id: int,
    user: User = Depends(require_role("owner", "admin", "editor")),
    db: Session = Depends(get_db),
):
    get_org_bot(bot_id, user, db)
    doc = get_org_document(document_id, bot_id, user, db)
    db.delete(doc)  # chunks cascade
    db.commit()
