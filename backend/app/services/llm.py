"""LLM provider abstraction.

Priority for chat: the configured `chat_provider`.
- "ollama": local Qwen (or any pulled model) via Ollama's /api/chat — no API
  keys, no per-token cost, documents never leave the machine.
- "openai": cloud fallback.
- "stub": no LLM — the RAG pipeline answers by quoting the best chunk.

Embeddings live in app/services/embeddings.py (Ollama / OpenAI / stub).
"""
import httpx

from app.config import get_settings

settings = get_settings()


def chat_available() -> bool:
    return settings.chat_provider in ("ollama", "openai")


def chat(messages: list[dict]) -> str:
    if settings.chat_provider == "ollama":
        return _ollama_chat(messages)
    if settings.chat_provider == "openai":
        return _openai_chat(messages)
    raise RuntimeError("No chat provider configured (chat_provider=stub)")


def _ollama_chat(messages: list[dict]) -> str:
    # Thinking models like qwen3.5 emit reasoning; "think": False keeps
    # answers immediate and is ignored by models that don't support it.
    payload = {
        "model": settings.ollama_chat_model,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": {"temperature": 0.2},
    }
    resp = httpx.post(f"{settings.ollama_base_url}/api/chat", json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()["message"]["content"].strip()


def _openai_chat(messages: list[dict]) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    resp = client.chat.completions.create(
        model=settings.openai_chat_model,
        messages=messages,
        temperature=0.2,
        max_tokens=300,
    )
    return resp.choices[0].message.content.strip()
