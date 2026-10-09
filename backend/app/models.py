"""SQLAlchemy models. Multi-tenant rule: every tenant-owned row carries org_id
and every query filters on it (enforced in app/deps.py, not by convention)."""
from datetime import datetime

from sqlalchemy import (
    JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    plan = Column(String(20), nullable=False, default="free")  # free | growth | business
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    users = relationship("User", back_populates="org", cascade="all, delete-orphan")
    bots = relationship("Bot", back_populates="org", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    email = Column(String(320), unique=True, nullable=False, index=True)
    full_name = Column(String(200), nullable=False)
    hashed_password = Column(String(128), nullable=False)
    role = Column(String(20), nullable=False, default="editor")  # owner | admin | editor
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    org = relationship("Organization", back_populates="users")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Bot(Base):
    __tablename__ = "bots"

    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    widget_settings = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    org = relationship("Organization", back_populates="bots")
    documents = relationship("Document", back_populates="bot", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("bot_id", "filename", name="uq_doc_bot_filename"),)

    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False, index=True)
    org_id = Column(Integer, nullable=False, index=True)  # denormalized for scoping
    filename = Column(String(255), nullable=False)
    content_text = Column(Text, nullable=False, default="")
    status = Column(String(20), nullable=False, default="pending")  # pending|processing|ready|failed
    quarantined_chunks = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    bot = relationship("Bot", back_populates="documents")
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    bot_id = Column(Integer, nullable=False, index=True)
    org_id = Column(Integer, nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    # JSON array of floats. Works on sqlite + postgres alike; similarity is
    # computed in app/services/rag.py (fine at portfolio scale; pgvector is
    # the production upgrade path and is provisioned in docker-compose).
    embedding = Column(Text, nullable=True)
    quarantined = Column(Boolean, nullable=False, default=False)

    document = relationship("Document", back_populates="chunks")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, nullable=False, index=True)
    org_id = Column(Integer, nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user | assistant
    content = Column(Text, nullable=False)
    sources = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
