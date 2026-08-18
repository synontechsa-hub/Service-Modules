import logging
import uuid
from typing import Optional, Any

from sqlalchemy.ext.asyncio import AsyncSession
from .config import StorageConfig
from .models import StoredFile
from .backends.base import StorageBackend


logger = logging.getLogger(__name__)


class StorageError(Exception):
    pass


class FileTooLargeError(StorageError):
    pass


class FileNotFoundError(StorageError):
    pass


class FileStorageService:
    def __init__(self, config: StorageConfig, db: AsyncSession, backend: Optional[StorageBackend] = None):
        self.config = config
        self.db = db
        self._backend = backend or self._init_backend()

    def _init_backend(self) -> StorageBackend:
        if self.config.backend == "supabase":
            from .backends.supabase_backend import SupabaseStorageBackend
            if not self.config.supabase_url or not self.config.supabase_key:
                raise ValueError("supabase_url and supabase_key are required for supabase backend")
            return SupabaseStorageBackend(self.config.supabase_url, self.config.supabase_key)
        elif self.config.backend == "s3":
            from .backends.s3_backend import S3Backend
            return S3Backend(
                endpoint_url=self.config.s3_endpoint_url,
                access_key_id=self.config.s3_access_key_id,
                secret_access_key=self.config.s3_secret_access_key,
                region_name=self.config.s3_region_name
            )
        else:
            raise ValueError(f"Unsupported backend: {self.config.backend}")

    async def get_upload_url(
        self, 
        filename: str, 
        content_type: str, 
        size_bytes: int,
        owner_id: Optional[uuid.UUID] = None,
        bucket: Optional[str] = None
    ) -> tuple[StoredFile, str]:
        """
        Validates size and returns a metadata record (pending) and a presigned URL.
        """
        # 1. Validation
        max_bytes = self.config.max_file_size_mb * 1024 * 1024
        if size_bytes > max_bytes:
            raise FileTooLargeError(f"File exceeds limit of {self.config.max_file_size_mb}MB")

        target_bucket = bucket or self.config.default_bucket
        
        # 2. Generate a unique key for storage
        file_id = uuid.uuid4()
        extension = filename.split(".")[-1] if "." in filename else ""
        storage_key = f"{owner_id or 'anon'}/{file_id}.{extension}" if extension else f"{owner_id or 'anon'}/{file_id}"

        # 3. Create database record
        stored_file = StoredFile(
            id=file_id,
            owner_id=owner_id,
            bucket=target_bucket,
            key=storage_key,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes
        )
        self.db.add(stored_file)
        await self.db.commit()
        await self.db.refresh(stored_file)

        # 4. Generate URL
        upload_url = self._backend.get_upload_url(
            bucket=target_bucket,
            key=storage_key,
            content_type=content_type,
            expiry_seconds=self.config.presigned_url_expiry_seconds
        )

        logger.info("upload_url_issued", file_id=str(file_id), bucket=target_bucket, key=storage_key)
        return stored_file, upload_url

    async def get_download_url(self, file_id: uuid.UUID) -> str:
        stored_file = await self.db.get(StoredFile, file_id)
        if not stored_file:
            raise FileNotFoundError(f"File {file_id} not found")

        url = self._backend.get_download_url(
            bucket=stored_file.bucket,
            key=stored_file.key,
            expiry_seconds=self.config.presigned_url_expiry_seconds
        )
        return url

    async def delete_file(self, file_id: uuid.UUID) -> None:
        stored_file = await self.db.get(StoredFile, file_id)
        if not stored_file:
            return

        # Delete from cloud
        try:
            self._backend.delete_file(stored_file.bucket, stored_file.key)
        except Exception as e:
            logger.warning("cloud_delete_failed", file_id=str(file_id), error=str(e))
            # We continue to delete from DB either way to keep sync

        # Delete from DB
        await self.db.delete(stored_file)
        await self.db.commit()
        logger.info("file_deleted", file_id=str(file_id))

    async def verify_upload(self, file_id: uuid.UUID) -> bool:
        """Checks if the file actually exists in the cloud after a client-side upload."""
        stored_file = await self.db.get(StoredFile, file_id)
        if not stored_file:
            return False

        exists = self._backend.file_exists(stored_file.bucket, stored_file.key)
        return exists
