import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from supabase import Client, create_client

from .config import WebhooksConfig
from .models import WebhookEvent, WebhookStatus

logger = logging.getLogger(__name__)


class WebhookStore:
    def __init__(self, config: WebhooksConfig, client: Optional[Client] = None):
        self.config = config
        if client is not None:
            self._client = client
        else:
            self._client = create_client(
                config.supabase_url, config.supabase_service_role_key
            )
        self._table = config.events_table

    def already_processed(self, provider: str, idempotency_key: str) -> bool:
        cutoff = datetime.now(timezone.utc) - timedelta(
            hours=self.config.idempotency_window_hours
        )
        try:
            result = (
                self._client.table(self._table)
                .select("id")
                .eq("provider", provider)
                .eq("idempotency_key", idempotency_key)
                .eq("status", WebhookStatus.SUCCEEDED.value)
                .gte("processed_at", cutoff.isoformat())
                .limit(1)
                .execute()
            )
            return len(result.data) > 0
        except Exception as e:
            logger.error("idempotency_check_failed", provider=provider, error=str(e))
            return False

    def insert(self, event: WebhookEvent) -> WebhookEvent:
        try:
            result = self._client.table(self._table).insert(event.to_row()).execute()
            row = result.data[0]
            event.id = row["id"]
            logger.info("webhook_event_inserted", provider=event.provider, event_id=event.id)
            return event
        except Exception as e:
            logger.error("webhook_insertion_failed", provider=event.provider, error=str(e))
            raise

    def mark_succeeded(self, event: WebhookEvent) -> None:
        event.status = WebhookStatus.SUCCEEDED
        event.processed_at = datetime.now(timezone.utc)
        try:
            self._update(event)
            logger.info("webhook_succeeded", event_id=event.id)
        except Exception as e:
            logger.error("mark_succeeded_failed", event_id=event.id, error=str(e))
            raise

    def mark_failed(self, event: WebhookEvent, error: str, next_retry_at: Optional[datetime]) -> None:
        event.attempt_count += 1
        event.last_error = error[:2000]

        if next_retry_at is not None and event.attempt_count < event.max_retries:
            event.status = WebhookStatus.PENDING
            event.next_retry_at = next_retry_at
            logger.info("webhook_failed_retrying", event_id=event.id, next_retry=next_retry_at)
        else:
            event.status = WebhookStatus.DEAD_LETTERED
            event.next_retry_at = None
            logger.warning("webhook_dead_lettered", event_id=event.id, error=error)

        try:
            self._update(event)
        except Exception as e:
            logger.error("mark_failed_update_failed", event_id=event.id, error=str(e))
            raise

    def mark_processing(self, event: WebhookEvent) -> None:
        event.status = WebhookStatus.PROCESSING
        try:
            self._update(event)
        except Exception as e:
            logger.error("mark_processing_failed", event_id=event.id, error=str(e))
            raise

    def _update(self, event: WebhookEvent) -> None:
        self._client.table(self._table).update(event.to_row()).eq("id", event.id).execute()

    def claim_due_events(self, limit: int = 50) -> list[WebhookEvent]:
        now = datetime.now(timezone.utc)
        try:
            result = self._client.rpc(
                "claim_webhook_events",
                {
                    "p_table": self._table,
                    "p_limit": limit,
                    "p_now": now.isoformat(),
                },
            ).execute()
            
            events = [WebhookEvent.from_row(row) for row in result.data]
            if events:
                logger.debug("webhooks_claimed", count=len(events))
            return events
        except Exception as e:
            logger.error("claim_webhooks_failed", error=str(e))
            raise
