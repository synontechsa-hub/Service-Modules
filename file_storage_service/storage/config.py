from typing import Literal, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class StorageConfig(BaseSettings):
    """
    Configuration for the File Storage module.
    Settings are prefixed with STORAGE_ in environment variables.
    """
    backend: Literal["s3", "supabase"] = Field("supabase", description="Storage backend to use")
    
    # Common
    default_bucket: str = Field("uploads", description="Default bucket/container name")
    max_file_size_mb: int = Field(50, description="Global max file size limit")
    presigned_url_expiry_seconds: int = Field(3600, description="Expiry for presigned URLs")

    # Supabase Specific
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None

    # S3 Specific
    s3_endpoint_url: Optional[str] = None
    s3_access_key_id: Optional[str] = None
    s3_secret_access_key: Optional[str] = None
    s3_region_name: Optional[str] = "us-east-1"

    model_config = SettingsConfigDict(env_prefix="STORAGE_", extra="ignore")
