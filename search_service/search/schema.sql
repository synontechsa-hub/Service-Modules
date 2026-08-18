-- search module schema
-- Run this in your Supabase SQL editor before using the module.

-- 1. Enable pgvector extension
create extension if not exists vector;

-- 2. Create search entries table
create table if not exists search_entries (
    id uuid primary key default gen_random_uuid(),
    target_type varchar(50) not null,
    target_id varchar(255) not null,
    content text not null,

    -- Full-Text Search Tokens
    fts_tokens tsvector,

    -- Semantic Search Vector (defaulting to 1536 dimensions for OpenAI/Claude)
    embedding vector(1536),

    metadata_json jsonb not null default '{}',
    created_at timestamptz not null default now(),

    -- Ensure target combination is unique for upserts
    unique (target_type, target_id)
);

-- 3. Optimized Indexes

-- Keyword search (GIN index)
create index if not exists ix_search_fts on search_entries using gin(fts_tokens);

-- Semantic search (HNSW index)
-- Recommended for fast similarity search at scale
create index if not exists ix_search_embedding on search_entries
using hnsw (embedding vector_cosine_ops)
with (m = 16, ef_construction = 64);

-- Lookup index
create index if not exists ix_search_target on search_entries (target_type, target_id);

-- 4. RLS: matching library convention. Zero permissive policies.
-- Access via service_role key only.
alter table search_entries enable row level security;
