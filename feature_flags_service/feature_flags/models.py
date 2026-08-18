import uuid
from datetime import datetime
from typing import Optional, Any, Dict

from sqlalchemy import DateTime, String, func, Uuid, JSON, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase


class FlagBase(DeclarativeBase):
    """
    To integrate with a host project's SQLAlchemy Base, have FlagBase inherit 
    from your host's Base instead of DeclarativeBase.
    """
    pass


class FeatureFlag(FlagBase):
    __tablename__ = "feature_flags"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Global master switch
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Percentage-based rollout (0-100)
    rollout_percentage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Targeting rules (e.g., {"user_ids": ["uuid-1"], "environments": ["staging"]})
    rules: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "description": self.description,
            "is_active": self.is_active,
            "rollout_percentage": self.rollout_percentage,
            "rules": self.rules,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
