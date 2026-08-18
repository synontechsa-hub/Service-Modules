from typing import Optional
from storage3 import create_client as create_storage_client
from .base import StorageBackend


class SupabaseStorageBackend(StorageBackend):
    def __init__(self, url: str, key: str):
        # We use the storage-specific client from storage3 or the main supabase client
        # In this modular package, we'll assume the user might provide just the storage bits.
        self._client = create_storage_client(f"{url}/storage/v1", {"Authorization": f"Bearer {key}"})

    def get_upload_url(
        self, 
        bucket: str, 
        key: str, 
        content_type: str, 
        expiry_seconds: int
    ) -> str:
        # Supabase storage-py / storage3 supports create_signed_upload_url
        # Note: key is the path within the bucket
        res = self._client.from_(bucket).create_signed_upload_url(key)
        return res["url"]

    def get_download_url(
        self, 
        bucket: str, 
        key: str, 
        expiry_seconds: int
    ) -> str:
        res = self._client.from_(bucket).create_signed_url(key, expiry_seconds)
        return res["signedURL"]

    def delete_file(self, bucket: str, key: str) -> None:
        self._client.from_(bucket).remove([key])

    def file_exists(self, bucket: str, key: str) -> bool:
        # Supabase doesn't have a direct 'exists' but we can try to get metadata
        try:
            # list() with a prefix matching the key
            res = self._client.from_(bucket).list(path="/".join(key.split("/")[:-1]), search=key.split("/")[-1])
            return any(item["name"] == key.split("/")[-1] for item in res)
        except Exception:
            return False
