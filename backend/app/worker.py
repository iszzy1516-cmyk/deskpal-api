"""Background document processing.

Runs in FastAPI BackgroundTasks for v1 (single-process, fine at this scale).
The pipeline: chunk → screen for injection patterns → embed → store.
"""
import logging

from app import database
from app.models import Chunk, Document
from app.services import embeddings
from app.services.documents import process_document_text

log = logging.getLogger("deskpal.worker")


def process_document(document_id: int) -> None:
    # SessionLocal resolved at call time: tests rebind the engine per test.
    db = database.SessionLocal()
    try:
        doc = db.get(Document, document_id)
        if doc is None:
            return
        doc.status = "processing"
        db.commit()

        flagged, quarantined = process_document_text(doc.content_text)
        doc.quarantined_chunks = quarantined

        # Embed only the clean chunks; quarantined ones are stored flagged so
        # they stay auditable but can never be retrieved.
        clean = [content for content, is_bad in flagged if not is_bad]
        vectors = embeddings.embed_texts(clean) if clean else []

        db.query(Chunk).filter(Chunk.document_id == doc.id).delete()
        vec_iter = iter(vectors)
        for idx, (content, is_bad) in enumerate(flagged):
            chunk = Chunk(
                document_id=doc.id,
                bot_id=doc.bot_id,
                org_id=doc.org_id,
                chunk_index=idx,
                content=content,
                quarantined=is_bad,
                embedding=None if is_bad else embeddings.dumps_vector(next(vec_iter)),
            )
            db.add(chunk)

        doc.status = "ready" if clean else "failed"
        db.commit()
        log.info("document %s processed: %d chunks, %d quarantined", doc.id, len(flagged), quarantined)
    except Exception:
        db.rollback()
        doc = db.get(Document, document_id)
        if doc:
            doc.status = "failed"
            db.commit()
        log.exception("document %s failed", document_id)
    finally:
        db.close()
