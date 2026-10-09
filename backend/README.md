# Deskpal API

Backend for Deskpal — chatbot-as-a-service for SMEs. Businesses upload documents;
the API indexes them (RAG) and answers customer questions **only** from those
documents, with source citations.

## What's inside (the security story)

| Layer | Implementation |
|---|---|
| Password hashing | bcrypt, 12 rounds (passlib) |
| Auth tokens | JWT access (30 min) + rotating refresh tokens (7 days, stored as SHA-256) |
| Refresh reuse detection | reusing a revoked token revokes the whole session |
| RBAC | `owner` > `admin` > `editor`, enforced per-route via `require_role()` |
| Multi-tenancy | every row carries `org_id`; every query is org-scoped; cross-org IDs return 404 |
| Rate limiting | login 5/min/IP, signup 10/min/IP, chat 20/min/user |
| Upload security | extension allow-list, 10MB cap, content sanity check |
| Prompt-injection defense | chunks screened at index time (suspicious chunks quarantined, never retrieved) + system prompt declares documents are data, never instructions |
| Never-hallucinate rule | no relevant chunks → the bot says so and offers a human handoff |
| LLM | Local-first **Qwen via Ollama** (`CHAT_PROVIDER=ollama`); OpenAI or stub as fallbacks |
| Headers | CORS allow-list, `nosniff`, `X-Frame-Options: DENY`, Referrer-Policy, CSP |
| Container | non-root user in the Dockerfile |

## Quick start (Docker)

```bash
cp .env.example .env   # then edit JWT_SECRET
docker compose up --build
# API at http://localhost:8000  — docs at /docs
```

## Local dev without Docker

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=sqlite:///./deskpal.db
export JWT_SECRET=$(openssl rand -hex 32)
uvicorn app.main:app --reload
```

With no API key and no Ollama, the API runs in **stub mode**: deterministic fake
embeddings + lexical retrieval, so the full pipeline works offline. Set a key
to get real semantic retrieval + GPT answers.

## Tests

```bash
pytest
```

21 tests covering: password hashing, signup/login/refresh rotation + reuse
detection, rate limiting (429s), RBAC denials, cross-org isolation, upload
validation, filename-replace semantics, injection quarantine, cited answers,
and the never-hallucinate path.

## API overview

- `POST /api/auth/signup` — creates org (free plan) + owner, returns tokens
- `POST /api/auth/login` · `POST /api/auth/refresh` · `GET /api/auth/me`
- `POST /api/bots` · `GET /api/bots` · `DELETE /api/bots/{id}` (owner/admin)
- `POST /api/bots/{id}/documents` — multipart upload (pdf/docx/txt, ≤10MB)
- `GET /api/bots/{id}/documents` · `DELETE .../documents/{doc_id}`
- `POST /api/bots/{id}/chat` — `{message}` → `{answer, sources[], used_documents}`
- `GET /api/bots/{id}/conversations`

Interactive docs: `http://localhost:8000/docs` (Swagger UI).
