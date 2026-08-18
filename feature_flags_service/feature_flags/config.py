from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class FeatureFlagsConfig(BaseSettings):
    """
    Configuration for the Feature Flags module.
    Settings are prefixed with FLAGS_ in environment variables.
    """
    table_name: str = Field("feature_flags", description="Name of the feature flags table")
    cache_ttl_seconds: int = Field(60, description="How long to cache flag states in memory")

    model_config = SettingsConfigDict(env_prefix="FLAGS_", extra="ignore")
