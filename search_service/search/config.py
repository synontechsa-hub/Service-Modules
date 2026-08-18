from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SearchConfig(BaseSettings):
    """
    Configuration for the Search module.
    Settings are prefixed with SEARCH_ in environment variables.
    """
    table_name: str = Field("search_entries", description="Name of the search index table")
    vector_dimensions: int = Field(1536, description="Dimensions for the vector embeddings (e.g., 1536 for text-embedding-3-small)")
    
    # Optional performance tuning
    hnsw_m: int = Field(16, description="HNSW index M parameter")
    hnsw_ef_construction: int = Field(64, description="HNSW index ef_construction parameter")

    model_config = SettingsConfigDict(env_prefix="SEARCH_", extra="ignore")
