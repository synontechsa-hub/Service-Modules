from abc import ABC, abstractmethod
from typing import Optional


class StorageBackend(ABC):
    @abstractmethod
    def get_upload_url(
        self, 
        bucket: str, 
        key: str, 
        content_type: str, 
        expiry_seconds: int
    ) -> str:
        """Generates a presigned URL for uploading a file."""
        pass

    @abstractmethod
    def get_download_url(
        self, 
        bucket: str, 
        key: str, 
        expiry_seconds: int
    ) -> str:
        """Generates a presigned URL for downloading a file."""
        pass

    @abstractmethod
    def delete_file(self, bucket: str, key: str) -> None:
        """Deletes a file from the storage provider."""
        pass

    @abstractmethod
    def file_exists(self, bucket: str, key: str) -> bool:
        """Checks if a file exists in the storage provider."""
        pass
