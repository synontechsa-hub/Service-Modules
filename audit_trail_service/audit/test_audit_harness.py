import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from audit.models import AuditBase
from audit.service import AuditTrailService

async def run_verification():
    print("Starting Audit Trail Module Verification...")
    
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(AuditBase.metadata.create_all)
        
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with Session() as db:
        service = AuditTrailService(db)
        
        # 1. Test basic logging
        print("Testing basic action logging...")
        user_id = uuid.uuid4()
        log = await service.log_action(
            action="test.action",
            target_type="test_target",
            target_id="123",
            user_id=user_id,
            metadata={"foo": "bar"}
        )
        
        assert log.action == "test.action"
        assert log.user_id == user_id
        assert log.metadata_json == {"foo": "bar"}
        print("Basic logging OK.")
        
        # 2. Test anonymous logging
        print("Testing anonymous logging...")
        log_anon = await service.log_action(
            action="anon.action",
            target_type="global"
        )
        assert log_anon.user_id is None
        print("Anonymous logging OK.")

    print("\nAudit Trail Module Verification Successful!")

if __name__ == "__main__":
    asyncio.run(run_verification())
