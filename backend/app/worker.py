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

        clean_chunks, quarantined = process_document_text(doc.content_text)
        doc.quarantined_chunks = quarantined  # quarantined hostile sentences

        vectors = embeddings.embed_texts(clean_chunks) if clean_chunks else []

        db.query(Chunk).filter(Chunk.document_id == doc.id).delete()
        for idx, (content, vec) in enumerate(zip(clean_chunks, vectors)):
            db.add(Chunk(
                document_id=doc.id,
                bot_id=doc.bot_id,
                org_id=doc.org_id,
                chunk_index=idx,
                content=content,
                quarantined=False,  # hostile sentences were stripped, not stored
                embedding=embeddings.dumps_vector(vec),
            ))

        doc.status = "ready" if clean_chunks else "failed"
        db.commit()
        log.info("document %s processed: %d chunks, %d hostile sentences quarantined", doc.id, len(clean_chunks), quarantined)
    except Exception:
        db.rollback()
        doc = db.get(Document, document_id)
        if doc:
            doc.status = "failed"
            db.commit()
        log.exception("document %s failed", document_id)
    finally:
        db.close()
