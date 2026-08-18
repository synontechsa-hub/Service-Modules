-- audit module schema
-- Run this in your Supabase SQL editor before using the module.

create table if not exists audit_logs (
    id uuid primary key default gen_random_uuid(),
    user_id uuid,
    action varchar(100) not null,
    target_type varchar(50) not null,
    target_id varchar(255),
    metadata_json jsonb not null default '{}',
    ip_address varchar(45),
    user_agent varchar(500),
    created_at timestamptz not null default now()
);

create index if not exists ix_audit_logs_user_id on audit_logs (user_id);
create index if not exists ix_audit_logs_action on audit_logs (action);
create index if not exists ix_audit_logs_created_at on audit_logs (created_at);
create index if not exists ix_audit_logs_target on audit_logs (target_type, target_id);

-- RLS: matching KerfSuite convention. Zero permissive policies.
-- Access via service_role key only.
alter table audit_logs enable row level security;
