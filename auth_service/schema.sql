-- Auth module schema (PostgreSQL / Supabase)
-- The host application owns the database connection and migrations.

create table if not exists auth_users (
    id uuid primary key default gen_random_uuid(),
    username varchar(32) not null,
    email varchar(255) not null,
    password_hash varchar(255),
    is_active boolean not null default true,
    is_verified boolean not null default false,
    failed_login_attempts integer not null default 0,
    locked_until timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint uq_auth_users_username unique (username)
);
create unique index if not exists uq_auth_users_email_lower on auth_users (lower(email));

create table if not exists auth_oauth_accounts (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth_users (id) on delete cascade,
    provider varchar(32) not null,
    provider_user_id varchar(255) not null,
    created_at timestamptz not null default now(),
    constraint uq_auth_provider_account unique (provider, provider_user_id)
);

create table if not exists auth_refresh_tokens (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth_users (id) on delete cascade,
    family_id uuid not null,
    token_hash varchar(64) not null,
    expires_at timestamptz not null,
    revoked boolean not null default false,
    revoked_at timestamptz,
    created_at timestamptz not null default now(),
    constraint uq_auth_refresh_tokens_hash unique (token_hash)
);
create index if not exists ix_auth_refresh_tokens_user_family on auth_refresh_tokens (user_id, family_id);

-- For Supabase projects, enabling RLS with no permissive policies denies anon/authenticated PostgREST access.
alter table auth_users enable row level security;
alter table auth_oauth_accounts enable row level security;
alter table auth_refresh_tokens enable row level security;
