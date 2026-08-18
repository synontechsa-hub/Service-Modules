from typing import Optional
from .base import StorageBackend


class S3Backend(StorageBackend):
    def __init__(
        self, 
        endpoint_url: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        region_name: Optional[str] = "us-east-1"
    ):
        try:
            import boto3
        except ImportError as e:
            raise ImportError("s3: S3Backend requires the 'boto3' package.") from e

        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region_name,
        )

    def get_upload_url(
        self, 
        bucket: str, 
        key: str, 
        content_type: str, 
        expiry_seconds: int
    ) -> str:
        # Default to PUT for S3 presigned URLs unless otherwise needed
        return self._client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": bucket,
                "Key": key,
                "ContentType": content_type
            },
            ExpiresIn=expiry_seconds,
        )

    def get_download_url(
        self, 
        bucket: str, 
        key: str, 
        expiry_seconds: int
    ) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expiry_seconds,
        )

    def delete_file(self, bucket: str, key: str) -> None:
        self._client.delete_object(Bucket=bucket, Key=key)

    def file_exists(self, bucket: str, key: str) -> bool:
        try:
            self._client.head_object(Bucket=bucket, Key=key)
            return True
        except Exception:
            return False
