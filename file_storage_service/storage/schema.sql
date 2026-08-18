-- file storage module schema
-- Run this in your Supabase SQL editor before using the module.

create table if not exists stored_files (
    id uuid primary key default gen_random_uuid(),
    owner_id uuid,
    bucket varchar(100) not null,
    key varchar(500) not null,
    filename varchar(255) not null,
    content_type varchar(100) not null,
    size_bytes bigint not null,
    created_at timestamptz not null default now()
);

create index if not exists ix_stored_files_owner_id on stored_files (owner_id);
create index if not exists ix_stored_files_bucket_key on stored_files (bucket, key);
create index if not exists ix_stored_files_created_at on stored_files (created_at);

-- RLS: matching KerfSuite convention. Zero permissive policies.
-- Access via service_role key only.
alter table stored_files enable row level security;
