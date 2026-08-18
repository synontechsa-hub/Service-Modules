import uuid
from datetime import datetime
from typing import Optional, Any, Dict

from pydantic import BaseModel, ConfigDict, Field


class AuditLogCreate(BaseModel):
    user_id: Optional[uuid.UUID] = None
    action: str = Field(..., max_length=100)
    target_type: str = Field(..., max_length=50)
    target_id: Optional[str] = Field(None, max_length=255)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    ip_address: Optional[str] = Field(None, max_length=45)
    user_agent: Optional[str] = Field(None, max_length=500)


class AuditLogOut(AuditLogCreate):
    id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
