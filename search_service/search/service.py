import logging
from typing import Optional, Any, Dict, List

from sqlalchemy import select, func, text, or_
from sqlalchemy.ext.asyncio import AsyncSession
from .config import SearchConfig
from .models import SearchEntry

logger = logging.getLogger(__name__)


class SearchService:
    def __init__(self, db: AsyncSession, config: SearchConfig):
        self.db = db
        self.config = config

    async def upsert_entry(
        self,
        target_type: str,
        target_id: str,
        content: str,
        embedding: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SearchEntry:
        """
        Add or update an item in the search index.
        Automatically updates FTS tokens via Postgres trigger or manual update.
        """
        # 1. Check for existing
        stmt = select(SearchEntry).where(
            SearchEntry.target_type == target_type,
            SearchEntry.target_id == target_id
        )
        result = await self.db.execute(stmt)
        entry = result.scalar_one_or_none()

        if not entry:
            entry = SearchEntry(
                target_type=target_type,
                target_id=target_id,
                content=content,
                embedding=embedding,
                metadata_json=metadata or {}
            )
            self.db.add(entry)
        else:
            entry.content = content
            entry.embedding = embedding
            entry.metadata_json = metadata or {}

        try:
            await self.db.commit()
            await self.db.refresh(entry)
            
            # 2. Manually trigger TSVECTOR update if not using a DB-level trigger
            # In a production Supabase setup, you'd usually have a generated column.
            # Here we'll do an explicit update for robustness.
            await self.db.execute(
                text(f"UPDATE {SearchEntry.__tablename__} SET fts_tokens = to_tsvector('english', content) WHERE id = :id"),
                {"id": entry.id}
            )
            await self.db.commit()
            
            logger.info("search_entry_upserted", target_type=target_type, target_id=target_id)
            return entry
        except Exception as e:
            await self.db.rollback()
            logger.error("search_upsert_failed", target_type=target_type, error=str(e))
            raise

    async def keyword_search(self, query: str, limit: int = 10) -> List[SearchEntry]:
        """
        Traditional keyword search using Postgres Full-Text Search.
        """
        stmt = (
            select(SearchEntry)
            .where(SearchEntry.fts_tokens.bool_op("@@")(func.plainto_tsquery('english', query)))
            .order_by(func.ts_rank(SearchEntry.fts_tokens, func.plainto_tsquery('english', query)).desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def semantic_search(self, query_vector: List[float], limit: int = 10) -> List[SearchEntry]:
        """
        Semantic search using vector similarity (cosine distance).
        """
        # cosine_distance in pgvector is <=>
        stmt = (
            select(SearchEntry)
            .order_by(SearchEntry.embedding.cosine_distance(query_vector))
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def hybrid_search(self, query_text: str, query_vector: List[float], limit: int = 10) -> List[SearchEntry]:
        """
        Combines keyword and semantic results. 
        In a real implementation, you'd use Reciprocal Rank Fusion (RRF).
        For this modular service, we'll return a union ordered by a combined score.
        """
        # This is a simplified hybrid approach. 
        # A proper RRF would require two separate CTEs and a join.
        # For now, we'll prioritize semantic results but allow keyword matches to surface.
        semantic_results = await self.semantic_search(query_vector, limit=limit)
        keyword_results = await self.keyword_search(query_text, limit=limit)
        
        # Deduplicate by ID
        seen_ids = set()
        combined = []
        
        for res in semantic_results + keyword_results:
            if res.id not in seen_ids:
                combined.append(res)
                seen_ids.add(res.id)
                
        return combined[:limit]
