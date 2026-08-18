# file_storage

Copy-in file storage module that abstracts cloud storage (S3/Supabase Storage) and provides secure file handling via presigned URLs, validation, and metadata tracking.

**Convention:** importable Python package, not a standalone service.
Copy the `storage/` folder into your project and wire it into your services.

## What it does

- **Multi-backend support**: Supports Supabase Storage and Amazon S3.
- **Secure uploads/downloads**: Generates presigned URLs so clients can talk to storage directly.
- **File metadata tracking**: Stores file details (owner, size, type) in a local `stored_files` table.
- **Validation**: Enforces size limits before issuing upload URLs.

## Setup

1. Copy the `storage/` folder into your project.
2. Run `schema.sql` in your Supabase project.
3. Define your SQLAlchemy models by inheriting from `StorageBase`.
4. `pip install -r requirements.snippet.txt`.
5. Set `STORAGE_BACKEND` and provider creds in your environment.

## Wiring it in

```python
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from storage import FileStorageService, StorageConfig

app = FastAPI()
config = StorageConfig()

# 1. Service Dependency
async def get_storage_service(db: AsyncSession = Depends(get_db)):
    return FileStorageService(config=config, db=db)

# 2. Usage
async def upload_endpoint(filename: str, size: int, service: FileStorageService = Depends(get_storage_service)):
    # Create record and get presigned URL
    stored_file, upload_url = await service.get_upload_url(
        filename=filename,
        content_type="image/png",
        size_bytes=size
    )
    return {"id": stored_file.id, "upload_url": upload_url}
```

## Files

| File | Purpose |
|---|---|
| `config.py` | Env-driven settings (`STORAGE_` prefix) |
| `models.py` | SQLAlchemy model (`StoredFile`) |
| `service.py` | `FileStorageService` — the core logic |
| `backends/` | S3 and Supabase specific implementations |
| `schema.sql` | Postgres table and indexes |
