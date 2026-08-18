import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, func, Uuid, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase


class StorageBase(DeclarativeBase):
    """
    To integrate with a host project's SQLAlchemy Base, have StorageBase inherit 
    from your host's Base instead of DeclarativeBase.
    """
    pass


class StoredFile(StorageBase):
    __tablename__ = "stored_files"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Ownership (optional)
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), index=True, nullable=True)
    
    # Storage details
    bucket: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    key: Mapped[str] = mapped_column(String(500), index=True, nullable=False)  # Path in storage
    
    # Metadata
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    def to_dict(self):
        return {
            "id": str(self.id),
            "owner_id": str(self.owner_id) if self.owner_id else None,
            "bucket": self.bucket,
            "key": self.key,
            "filename": self.filename,
            "content_type": self.content_type,
            "size_bytes": self.size_bytes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
