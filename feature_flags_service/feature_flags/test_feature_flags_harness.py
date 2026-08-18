import asyncio
from unittest.mock import MagicMock, AsyncMock
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from feature_flags.config import FeatureFlagsConfig
from feature_flags.models import FlagBase, FeatureFlag
from feature_flags.service import FeatureFlagService

async def run_verification():
    print("Starting Feature Flags Module Verification...")
    
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(FlagBase.metadata.create_all)
        
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    config = FeatureFlagsConfig()
    
    async with Session() as db:
        service = FeatureFlagService(db, config)
        
        # 1. Setup flags
        print("Setting up test flags...")
        
        # Global ON
        db.add(FeatureFlag(key="global-on", is_active=True, rollout_percentage=100))
        # Global OFF
        db.add(FeatureFlag(key="global-off", is_active=False, rollout_percentage=100))
        # 50% Rollout
        db.add(FeatureFlag(key="half-rollout", is_active=True, rollout_percentage=50))
        # Targeted user (Rollout 100% means everyone matching the rule gets it)
        db.add(FeatureFlag(key="targeted", is_active=True, rollout_percentage=100, rules={"user_ids": ["user-123"]}))
        # Targeted environment
        db.add(FeatureFlag(key="staging-only", is_active=True, rollout_percentage=100, rules={"environments": ["staging"]}))
        
        await db.commit()
        
        # 2. Test Basic toggles
        print("Testing basic toggles...")
        assert await service.is_enabled("global-on") is True
        assert await service.is_enabled("global-off") is False
        assert await service.is_enabled("non-existent") is False
        print("Basic toggles OK.")
        
        # 3. Test Targeting
        print("Testing targeting rules...")
        assert await service.is_enabled("targeted", user_id="user-123") is True
        assert await service.is_enabled("targeted", user_id="user-456") is False
        
        assert await service.is_enabled("staging-only", context={"environment": "staging"}) is True
        assert await service.is_enabled("staging-only", context={"environment": "production"}) is False
        print("Targeting rules OK.")
        
        # 4. Test Deterministic Rollout
        print("Testing deterministic rollout...")
        # We check a few users for the 50% rollout. 
        # Since it's deterministic, results should be stable.
        results = []
        for i in range(100):
            res = await service.is_enabled("half-rollout", user_id=f"user-{i}")
            results.append(res)
            
        enabled_count = sum(1 for r in results if r)
        print(f"50% Rollout resulted in {enabled_count}/100 users enabled.")
        assert 30 <= enabled_count <= 70, f"Rollout distribution seems off: {enabled_count}%"
        
        # Re-check same user
        assert await service.is_enabled("half-rollout", user_id="user-1") == results[1]
        print("Deterministic rollout OK.")

    print("\nFeature Flags Module Verification Successful!")

if __name__ == "__main__":
    asyncio.run(run_verification())
