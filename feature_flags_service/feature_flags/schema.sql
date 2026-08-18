-- feature flags module schema
-- Run this in your Supabase SQL editor before using the module.

create table if not exists feature_flags (
    key varchar(100) primary key,
    description varchar(255),
    is_active boolean not null default false,
    rollout_percentage integer not null default 0,
    rules jsonb not null default '{}',
    updated_at timestamptz not null default now()
);

-- Seed: Maintenance Mode (Default disabled)
insert into feature_flags (key, description, is_active)
values ('maintenance-mode', 'Global master switch for site-wide maintenance', false)
on conflict do nothing;

-- RLS: matching library convention. Zero permissive policies.
alter table feature_flags enable row level security;
