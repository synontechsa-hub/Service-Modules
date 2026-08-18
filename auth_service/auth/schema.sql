-- auth module schema
-- Run this in your Supabase SQL editor before using the module.

create extension if not exists "uuid-ossp";

create table if not exists auth_users (
    id uuid primary key default gen_random_uuid(),
    username varchar(32) unique not null,
    email varchar(255) unique not null,
    password_hash varchar(255),
    is_active boolean not null default true,
    is_verified boolean not null default false,
    failed_login_attempts integer not null default 0,
    locked_until timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists ix_auth_users_username on auth_users (username);
create index if not exists ix_auth_users_email on auth_users (email);

create table if not exists auth_oauth_accounts (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth_users (id) on delete cascade,
    provider varchar(20) not null,
    provider_user_id varchar(255) not null,
    created_at timestamptz not null default now(),
    constraint uq_auth_provider_account unique (provider, provider_user_id)
);

create table if not exists auth_refresh_tokens (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth_users (id) on delete cascade,
    token_hash varchar(255) unique not null,
    expires_at timestamptz not null,
    revoked boolean not null default false,
    created_at timestamptz not null default now()
);

create index if not exists ix_auth_refresh_tokens_hash on auth_refresh_tokens (token_hash);

-- RLS: matching KerfSuite convention. Zero permissive policies.
-- Access via service_role key only.
alter table auth_users enable row level security;
alter table auth_oauth_accounts enable row level security;
alter table auth_refresh_tokens enable row level security;
