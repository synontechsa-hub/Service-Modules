import uuid
from datetime import datetime
from typing import Optional, Any

from sqlalchemy import DateTime, String, func, Uuid, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
from sqlalchemy.dialects.postgresql import TSVECTOR
from pgvector.sqlalchemy import Vector


class SearchBase(DeclarativeBase):
    """
    To integrate with a host project's SQLAlchemy Base, have SearchBase inherit 
    from your host's Base instead of DeclarativeBase.
    """
    pass


class SearchEntry(SearchBase):
    __tablename__ = "search_entries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Cross-reference to external data
    target_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    target_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    
    # Searchable content
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # 1. Full-Text Search Tokens (Postgres FTS)
    fts_tokens: Mapped[Optional[Any]] = mapped_column(TSVECTOR, index=False, nullable=True)
    
    # 2. Semantic Search Vector (pgvector)
    # The dimension is often configured dynamically, but we'll use a placeholder here.
    # In practice, you might need to use a custom type if dimensions vary.
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(1536), nullable=True)
    
    # Unstructured context
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "target_type": self.target_type,
            "target_id": self.target_id,
            "content": self.content,
            "metadata": self.metadata_json,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
