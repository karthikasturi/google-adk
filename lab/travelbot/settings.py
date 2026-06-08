"""
settings.py — TravelBot configuration (v3+)
-------------------------------------------
All service credentials from environment variables — no hardcoded secrets.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    # PostgreSQL
    pg_host: str = field(default_factory=lambda: os.getenv("PG_HOST", "localhost"))
    pg_port: int = field(default_factory=lambda: int(os.getenv("PG_PORT", "5432")))
    pg_db: str = field(default_factory=lambda: os.getenv("PG_DB", "travelbot"))
    pg_user: str = field(default_factory=lambda: os.getenv("PG_USER", "travelbot"))
    pg_password: str = field(default_factory=lambda: os.getenv("PG_PASSWORD", ""))

    # Redis
    redis_host: str = field(default_factory=lambda: os.getenv("REDIS_HOST", "localhost"))
    redis_port: int = field(default_factory=lambda: int(os.getenv("REDIS_PORT", "6379")))
    redis_password: str = field(default_factory=lambda: os.getenv("REDIS_PASSWORD", ""))
    redis_session_ttl: int = field(
        default_factory=lambda: int(os.getenv("REDIS_SESSION_TTL", "3600"))
    )

    # RAG knowledge base (ChromaDB)
    rag_persist_dir: str = field(default_factory=lambda: os.getenv("RAG_PERSIST_DIR", "chroma_db"))
    rag_collection_name: str = field(
        default_factory=lambda: os.getenv("RAG_COLLECTION_NAME", "travel_kb")
    )
    rag_embedding_model: str = field(
        default_factory=lambda: os.getenv(
            "RAG_EMBEDDING_MODEL", "openrouter/openai/text-embedding-3-small"
        )
    )
    rag_top_k: int = field(default_factory=lambda: int(os.getenv("RAG_TOP_K", "3")))

    @property
    def rag_persist_path(self) -> Path:
        """Absolute path to the local ChromaDB persistence directory.

        Relative paths are resolved against the travelbot project root so the
        store lands in the same place regardless of the current working directory.
        """
        path = Path(self.rag_persist_dir)
        return path if path.is_absolute() else Path(__file__).parent / path

    @property
    def pg_dsn(self) -> str:
        """psycopg2-compatible connection string."""
        return (
            f"host={self.pg_host} port={self.pg_port} "
            f"dbname={self.pg_db} user={self.pg_user} "
            f"password={self.pg_password}"
        )

    @property
    def adk_db_url(self) -> str:
        """SQLAlchemy async URL for ADK DatabaseSessionService."""
        return (
            f"postgresql+asyncpg://{self.pg_user}:{self.pg_password}"
            f"@{self.pg_host}:{self.pg_port}/{self.pg_db}"
        )

    @property
    def redis_url(self) -> str:
        """Redis URL for ADK RedisSessionService."""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}"
        return f"redis://{self.redis_host}:{self.redis_port}"


settings = Settings()
