import uuid
from datetime import datetime
from typing import Optional, Any

from sqlalchemy import DateTime, String, func, Uuid, JSON
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase


class AuditBase(DeclarativeBase):
    """
    To integrate with a host project's SQLAlchemy Base, have AuditBase inherit 
    from your host's Base instead of DeclarativeBase.
    """
    pass


class AuditLog(AuditBase):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Who did it? (Optional for anonymous actions)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), index=True, nullable=True)
    
    # What did they do? (e.g., 'user.login', 'billing.payment_received')
    action: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    
    # What was the target of the action?
    target_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    target_id: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)
    
    # Unstructured context
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    
    # Contextual info
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id) if self.user_id else None,
            "action": self.action,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "metadata": self.metadata_json,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
