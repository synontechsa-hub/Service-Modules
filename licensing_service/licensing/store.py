import logging
from datetime import datetime, timezone
from typing import Optional

from supabase import Client, create_client

from .config import LicensingConfig
from .keygen import generate_key_string
from .models import LicenseKey, LicenseSource, LicenseStatus, TrialUsage
from .exceptions import PoolEmptyError, IssuanceFailedError, LicenseNotFoundError

logger = logging.getLogger(__name__)


class LicensingStore:
    def __init__(self, config: LicensingConfig, client: Optional[Client] = None):
        self.config = config
        if client is not None:
            self._client = client
        else:
            self._client = create_client(
                config.supabase_url, config.supabase_service_role_key
            )
        self._keys_table = config.license_keys_table
        self._pool_table = config.license_key_pool_table
        self._trial_table = config.trial_usage_table

    def add_to_pool(self, product: str, count: int) -> int:
        rows = []
        for _ in range(count):
            rows.append({
                "key": generate_key_string(
                    self.config.license_key_segment_length,
                    self.config.license_key_segment_count
                ),
                "product": product,
                "assigned": False
            })

        inserted = 0
        for row in rows:
            try:
                self._client.table(self._pool_table).insert(row).execute()
                inserted += 1
            except Exception as e:
                logger.warning("pool_insertion_failed", product=product, error=str(e))
                continue
        
        logger.info("pool_keys_added", product=product, count=inserted)
        return inserted

    def _pull_from_pool(self, product: str) -> Optional[str]:
        result = self._client.rpc(
            "claim_pool_key",
            {"p_table": self._pool_table, "p_product": product},
        ).execute()
        if not result.data:
            return None
        return result.data[0]["key"]

    def issue_license(
        self,
        product: str,
        source: LicenseSource = LicenseSource.ON_DEMAND,
        customer_email: Optional[str] = None,
        bind_machine_id: Optional[str] = None,
        max_attempts: int = 5,
    ) -> LicenseKey:
        for attempt in range(max_attempts):
            if source == LicenseSource.POOL:
                key_string = self._pull_from_pool(product)
                if key_string is None:
                    logger.error("issuance_failed_pool_empty", product=product)
                    raise PoolEmptyError(f"Pool for product '{product}' is empty")
            else:
                key_string = generate_key_string(
                    self.config.license_key_segment_length,
                    self.config.license_key_segment_count
                )

            license_key = LicenseKey(
                key=key_string,
                product=product,
                source=source,
                customer_email=customer_email,
                bound_machine_id=bind_machine_id,
            )
            try:
                result = self._client.table(self._keys_table).insert(license_key.to_row()).execute()
                license_key.id = result.data[0]["id"]
                logger.info("license_issued", product=product, key_id=license_key.id, source=source.value)
                return license_key
            except Exception as e:
                logger.warning("issuance_attempt_failed", product=product, attempt=attempt+1, error=str(e))
                if source == LicenseSource.POOL:
                    # Rare race condition where pool claim succeeded but keys table insert failed
                    # likely due to a manual DB edit causing a collision.
                    raise IssuanceFailedError("Pool key claimed but issuance failed") from e
                continue

        logger.error("issuance_failed_max_attempts", product=product, attempts=max_attempts)
        raise IssuanceFailedError("Failed to issue unique license after retries")

    def get_license(self, key: str) -> Optional[LicenseKey]:
        result = (
            self._client.table(self._keys_table)
            .select("*")
            .eq("key", key)
            .limit(1)
            .execute()
        )
        if not result.data:
            return None
        return LicenseKey.from_row(result.data[0])

    def increment_run_count(self, trial_id: str) -> None:
        try:
            self._client.rpc("increment_trial_runs", {"p_trial_id": trial_id}).execute()
        except Exception as e:
            logger.error("increment_run_count_failed", trial_id=trial_id, error=str(e))
            raise

    def revoke(self, license_key: LicenseKey) -> None:
        license_key.status = LicenseStatus.REVOKED
        license_key.revoked_at = datetime.now(timezone.utc)
        try:
            self._client.table(self._keys_table).update(
                {"status": license_key.status.value, "revoked_at": license_key.revoked_at.isoformat()}
            ).eq("id", license_key.id).execute()
            logger.info("license_revoked", key_id=license_key.id)
        except Exception as e:
            logger.error("revoke_failed", key_id=license_key.id, error=str(e))
            raise
