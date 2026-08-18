import hashlib
import logging
from typing import Optional, Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from .config import FeatureFlagsConfig
from .models import FeatureFlag

logger = logging.getLogger(__name__)


class FeatureFlagService:
    def __init__(self, db: AsyncSession, config: FeatureFlagsConfig):
        self.db = db
        self.config = config

    async def is_enabled(self, key: str, user_id: Optional[Any] = None, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Primary check for whether a feature is enabled.
        Logic: Global is_active -> Targeting Rules -> Rollout Percentage.
        """
        flag = await self._get_flag(key)
        if not flag:
            return False

        # 1. Global switch
        if not flag.is_active:
            return False

        # 2. Targeted Rules (segments, envs, user_ids)
        if flag.rules:
            if not self._eval_rules(flag.rules, user_id, context):
                return False

        # 3. Deterministic Rollout
        if flag.rollout_percentage >= 100:
            return True
        if flag.rollout_percentage <= 0:
            return False

        if user_id:
            # Deterministic hash: same user + same flag key = same rollout decision
            score = self._get_rollout_score(key, str(user_id))
            return score <= flag.rollout_percentage

        # If no user_id and percentage < 100, we fail safe to disabled
        return False

    async def get_all_enabled(self, user_id: Optional[Any] = None, context: Optional[Dict[str, Any]] = None) -> Dict[str, bool]:
        """
        Returns all active flags for a given context.
        """
        stmt = select(FeatureFlag).where(FeatureFlag.is_active == True)
        result = await self.db.execute(stmt)
        flags = result.scalars().all()
        
        out = {}
        for flag in flags:
            if flag.rollout_percentage >= 100 and not flag.rules:
                out[flag.key] = True
            else:
                # Run full eval for complex ones
                if await self.is_enabled(flag.key, user_id, context):
                    out[flag.key] = True
        return out

    async def _get_flag(self, key: str) -> Optional[FeatureFlag]:
        # In a high-traffic setup, this would hit Redis/LRU Cache first
        return await self.db.get(FeatureFlag, key)

    def _eval_rules(self, rules: Dict[str, Any], user_id: Any, context: Optional[Dict[str, Any]]) -> bool:
        """
        Simple rule engine. Supports:
        - user_ids: list of allowed IDs
        - environments: list of allowed environments (requires 'environment' in context)
        """
        context = context or {}
        
        # User ID whitelist
        if "user_ids" in rules:
            if str(user_id) not in [str(uid) for uid in rules["user_ids"]]:
                return False

        # Environment restriction
        if "environments" in rules:
            current_env = context.get("environment")
            if current_env not in rules["environments"]:
                return False

        return True

    def _get_rollout_score(self, flag_key: str, user_id_str: str) -> int:
        """
        Returns a deterministic number between 1 and 100 for a user/flag combination.
        """
        hash_input = f"{flag_key}:{user_id_str}".encode()
        hash_hex = hashlib.sha256(hash_input).hexdigest()
        # Use first 8 chars for a stable integer
        hash_int = int(hash_hex[:8], 16)
        return (hash_int % 100) + 1
