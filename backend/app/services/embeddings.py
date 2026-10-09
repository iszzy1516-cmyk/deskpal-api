"""Embedding provider.

Uses OpenAI when OPENAI_API_KEY is set. Without a key it falls back to a
hash-based fake embedding — deterministic, same dimension (1536), so the whole
RAG pipeline works in development and tests. The stub is clearly labeled and
must never be used in production (no key configured = misconfiguration there).
"""
import hashlib
import json
import math

from app.config import get_settings

settings = get_settings()
DIM = 1536


def _stub_embedding(text: str) -> list[float]:
    """Deterministic pseudo-embedding from SHA-256 digests of the text's
    character 3-grams. Not semantic — only for dev/tests without an API key."""
    vec = [0.0] * DIM
    grams = [text[i : i + 3] for i in range(len(text))] or [text]
    for g in grams:
        digest = hashlib.sha256(g.encode()).digest()
        for i, byte in enumerate(digest):
            idx = (i * 256 + byte) % DIM
            vec[idx] += 1.0 if byte % 2 == 0 else -1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts. Raises RuntimeError if the OpenAI call fails."""
    if not settings.openai_api_key:
        return [_stub_embedding(t) for t in texts]
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    resp = client.embeddings.create(model=settings.openai_embedding_model, input=texts)
    return [item.embedding for item in resp.data]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


def dumps_vector(v: list[float]) -> str:
    return json.dumps(v)


def loads_vector(s: str | None) -> list[float] | None:
    if not s:
        return None
    return json.loads(s)
