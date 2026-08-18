import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from storage.models import StorageBase
from storage.service import FileStorageService, FileTooLargeError
from storage.config import StorageConfig
from storage.backends.base import StorageBackend

class MockBackend(StorageBackend):
    def get_upload_url(self, bucket, key, content_type, expiry_seconds):
        return f"https://mock.storage/{bucket}/{key}?content_type={content_type}"
    def get_download_url(self, bucket, key, expiry_seconds):
        return f"https://mock.storage/{bucket}/{key}?signed=true"
    def delete_file(self, bucket, key):
        pass
    def file_exists(self, bucket, key):
        return True

async def run_verification():
    print("Starting File Storage Module Verification...")
    
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(StorageBase.metadata.create_all)
        
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    config = StorageConfig(max_file_size_mb=1)
    
    async with Session() as db:
        service = FileStorageService(config, db, backend=MockBackend())
        
        # 1. Test upload URL generation
        print("Testing Upload URL Generation...")
        owner_id = uuid.uuid4()
        stored_file, url = await service.get_upload_url(
            filename="test.png",
            content_type="image/png",
            size_bytes=1024,
            owner_id=owner_id
        )
        
        assert stored_file.filename == "test.png"
        assert "image/png" in url
        assert str(owner_id) in stored_file.key
        print("Upload URL OK.")
        
        # 2. Test Size Validation
        print("Testing Size Validation...")
        try:
            await service.get_upload_url(
                filename="big.zip",
                content_type="application/zip",
                size_bytes=2 * 1024 * 1024 # 2MB > 1MB limit
            )
            assert False, "Should have raised FileTooLargeError"
        except FileTooLargeError:
            print("Size Validation OK.")
            
        # 3. Test Download URL
        print("Testing Download URL...")
        dl_url = await service.get_download_url(stored_file.id)
        assert "signed=true" in dl_url
        print("Download URL OK.")

    print("\nFile Storage Module Verification Successful!")

if __name__ == "__main__":
    asyncio.run(run_verification())
