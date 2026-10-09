"""Application settings, loaded from environment / .env file."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./deskpal.db"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "insecure-dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 7

    cors_origins: str = "http://localhost:5173"

    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    openai_chat_model: str = "gpt-4o-mini"

    # LLM provider: "stub" (offline fallback), "ollama" (local Qwen), or
    # "openai". Local-first: Ollama runs Qwen with zero per-token cost.
    chat_provider: str = "stub"
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "qwen3.5:9b"
    # Empty = stub embeddings (hash-based). Set to e.g. "nomic-embed-text"
    # after `ollama pull nomic-embed-text` for real semantic retrieval.
    ollama_embed_model: str = ""

    max_upload_mb: int = 10
    storage_dir: str = "./storage"


@lru_cache
def get_settings() -> Settings:
    return Settings()
