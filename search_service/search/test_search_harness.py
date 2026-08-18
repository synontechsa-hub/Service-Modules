import asyncio
from unittest.mock import MagicMock, AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession
from search.config import SearchConfig
from search.service import SearchService
from search.models import SearchEntry

async def run_verification():
    print("Starting Search Module Verification...")
    
    # 1. Test Service Initialization
    mock_db = MagicMock(spec=AsyncSession)
    config = SearchConfig(vector_dimensions=1536)
    service = SearchService(mock_db, config)
    
    print("Service initialized.")
    
    # 2. Verify Hybrid Search logic (Deduplication)
    print("Testing Hybrid Search Logic...")
    
    # Mocking results
    entry1 = SearchEntry(target_type="lore", target_id="1", content="test")
    entry1.id = "uuid1"
    entry2 = SearchEntry(target_type="lore", target_id="2", content="test")
    entry2.id = "uuid2"
    
    service.semantic_search = AsyncMock(return_value=[entry1])
    service.keyword_search = AsyncMock(return_value=[entry1, entry2])
    
    results = await service.hybrid_search("test", [0.1] * 1536, limit=10)
    
    assert len(results) == 2, f"Expected 2 unique results, got {len(results)}"
    assert results[0].id == "uuid1"
    assert results[1].id == "uuid2"
    
    print("Hybrid Search logic OK.")
    print("\nSearch Module logic verified (Import & Logic)!")

if __name__ == "__main__":
    asyncio.run(run_verification())
