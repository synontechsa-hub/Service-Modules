import logging
from typing import Optional, Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession
from .models import AuditLog
from .schemas import AuditLogCreate

logger = logging.getLogger(__name__)


class AuditTrailService:
    def __init__(self, db: AsyncSession, observability_handler: Optional[Any] = None):
        """
        :param db: SQLAlchemy async session.
        :param observability_handler: Optional RemoteLogHandler from observability_service to mirror logs.
        """
        self.db = db
        self.observability_handler = observability_handler

    async def log_action(
        self,
        action: str,
        target_type: str,
        target_id: Optional[str] = None,
        user_id: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """
        Record a sensitive action in the audit trail.
        """
        log_entry = AuditLog(
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            metadata_json=metadata or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        try:
            self.db.add(log_entry)
            await self.db.commit()
            await self.db.refresh(log_entry)
            
            logger.info("audit_log_created", action=action, user_id=str(user_id) if user_id else None)
            
            # Optional: Mirror to observability service if handler provided
            if self.observability_handler:
                self._mirror_to_observability(log_entry)
                
            return log_entry
        except Exception as e:
            await self.db.rollback()
            logger.error("audit_log_failed", action=action, error=str(e))
            raise

    def _mirror_to_observability(self, log_entry: AuditLog):
        """
        Sends the audit log as a structured event to the observability service.
        """
        try:
            # Observability service expects a logging.LogRecord or similar.
            # We can use the handler's emit logic or a specialized method.
            # For now, we'll log it as a structured INFO message that the handler will catch.
            record = logging.LogRecord(
                name="audit_trail",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg=f"Audit Event: {log_entry.action}",
                args=(),
                exc_info=None,
            )
            # Inject extra context for structured logging
            record.__dict__["audit_event"] = log_entry.to_dict()
            self.observability_handler.emit(record)
        except Exception as e:
            logger.warning("audit_mirror_failed", error=str(e))
