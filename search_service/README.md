# search

Copy-in search module that provides an abstraction for both traditional Full-Text Search (FTS) and Semantic (vector) search using PostgreSQL and `pgvector`.

**Convention:** importable Python package, not a standalone service.
Copy the `search/` folder into your project and wire it into your services.

## What it does

- **Dual-Mode Search**: Support for both PostgreSQL Full-Text Search (FTS) and Semantic Vector search (`pgvector`).
- **Hybrid Search Capability**: Combines keyword relevance with semantic similarity.
- **Generic Indexing**: A standardized `search_entries` table that can index any type of content.
- **Performance Optimized**: Uses GIN and HNSW indexes for fast retrieval.

## Setup

1. Copy the `search/` folder into your project.
2. Run `schema.sql` in your Supabase/Postgres project.
3. `pip install -r requirements.snippet.txt`.
4. Ensure the `pgvector` extension is enabled in your database.

## Wiring it in

```python
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from search import SearchService, SearchConfig

app = FastAPI()
config = SearchConfig(vector_dimensions=1536)

# 1. Service Dependency
async def get_search_service(db: AsyncSession = Depends(get_db)):
    return SearchService(db=db, config=config)

# 2. Usage
async def search_endpoint(query: str, service: SearchService = Depends(get_search_service)):
    # Simple keyword search
    results = await service.keyword_search(query)
    
    # Or semantic search (assuming you have the query embedding)
    # query_vector = get_embedding(query)
    # results = await service.semantic_search(query_vector)
    
    return results
```

## Files

| File | Purpose |
|---|---|
| `config.py` | Env-driven settings (`SEARCH_` prefix) |
| `models.py` | SQLAlchemy model (`SearchEntry`) |
| `service.py` | `SearchService` — the core logic |
| `schema.sql` | Postgres extension and table definitions |
