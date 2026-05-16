-- ===========================================================
-- manak-grant — Postgres schema for Supabase
-- Run this once in Supabase → SQL Editor → New query
-- ===========================================================

-- Extensions
create extension if not exists "uuid-ossp";

-- ===========================================================
-- 1. firms — accounting firms (multi-tenant ready, single firm now)
-- ===========================================================
create table if not exists public.firms (
  id          uuid primary key default uuid_generate_v4(),
  name        text not null,
  created_at  timestamptz not null default now()
);

-- ===========================================================
-- 2. user_profiles — extends Supabase auth.users with firm + role
-- ===========================================================
create table if not exists public.user_profiles (
  id          uuid primary key references auth.users(id) on delete cascade,
  firm_id     uuid not null references public.firms(id) on delete cascade,
  full_name   text not null,
  role        text not null check (role in ('owner', 'clerk')),
  created_at  timestamptz not null default now()
);

create index if not exists idx_user_profiles_firm on public.user_profiles(firm_id);

-- ===========================================================
-- 3. clients — businesses that the firm manages
-- ===========================================================
create table if not exists public.clients (
  id            uuid primary key default uuid_generate_v4(),
  firm_id       uuid not null references public.firms(id) on delete cascade,
  assigned_to   uuid references public.user_profiles(id) on delete set null,
  name          text not null,
  business_id   text,                                                -- ח.פ / ע.מ
  withholding   text,                                                -- תיק ניכויים
  open_date     date,
  occupation    text default 'אחר',                                   -- תחום עיסוק
  reporting     text default 'דו חודשי' check (reporting in ('חד חודשי','דו חודשי')),
  notes         text,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

create index if not exists idx_clients_firm on public.clients(firm_id);
create index if not exists idx_clients_assigned on public.clients(assigned_to);

-- ===========================================================
-- 4. claims — grant requests per client (a client can have multiple over time)
-- ===========================================================
create table if not exists public.claims (
  id            uuid primary key default uuid_generate_v4(),
  client_id     uuid not null references public.clients(id) on delete cascade,
  status        text not null default 'draft'
                check (status in ('draft','review','submitted','rejected')),
  data          jsonb not null default '{}'::jsonb,                  -- calculator inputs
  result        jsonb,                                                -- last computed result (cached)
  notes         text,
  created_by    uuid references public.user_profiles(id) on delete set null,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  submitted_at  timestamptz
);

create index if not exists idx_claims_client on public.claims(client_id);
create index if not exists idx_claims_status on public.claims(status);
create index if not exists idx_claims_created_by on public.claims(created_by);

-- ===========================================================
-- 5. audit_log — append-only log
-- ===========================================================
create table if not exists public.audit_log (
  id            bigint generated always as identity primary key,
  user_id       uuid references public.user_profiles(id) on delete set null,
  action        text not null,                                        -- e.g. "create_client", "submit_claim"
  entity_type   text not null,                                        -- "client" | "claim" | "user"
  entity_id     text,
  changes       jsonb,
  created_at    timestamptz not null default now()
);

create index if not exists idx_audit_user on public.audit_log(user_id);
create index if not exists idx_audit_created on public.audit_log(created_at desc);

-- ===========================================================
-- updated_at trigger
-- ===========================================================
create or replace function public.touch_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at := now();
  return new;
end $$;

drop trigger if exists trg_clients_updated_at on public.clients;
create trigger trg_clients_updated_at before update on public.clients
  for each row execute function public.touch_updated_at();

drop trigger if exists trg_claims_updated_at on public.claims;
create trigger trg_claims_updated_at before update on public.claims
  for each row execute function public.touch_updated_at();

-- ===========================================================
-- Helper functions for RLS
-- ===========================================================
create or replace function public.current_firm_id()
returns uuid language sql stable as $$
  select firm_id from public.user_profiles where id = auth.uid()
$$;

create or replace function public.current_role()
returns text language sql stable as $$
  select role from public.user_profiles where id = auth.uid()
$$;

-- ===========================================================
-- Row-Level Security
-- ===========================================================
alter table public.firms          enable row level security;
alter table public.user_profiles  enable row level security;
alter table public.clients        enable row level security;
alter table public.claims         enable row level security;
alter table public.audit_log      enable row level security;

-- firms: read-only access for users in that firm
drop policy if exists "firms_read" on public.firms;
create policy "firms_read" on public.firms
  for select using (id = public.current_firm_id());

-- user_profiles: users see profiles in their firm
drop policy if exists "profiles_read" on public.user_profiles;
create policy "profiles_read" on public.user_profiles
  for select using (firm_id = public.current_firm_id());

-- Owner can update profile rows in their firm (for changing roles, etc.)
drop policy if exists "profiles_owner_update" on public.user_profiles;
create policy "profiles_owner_update" on public.user_profiles
  for update using (
    firm_id = public.current_firm_id()
    and public.current_role() = 'owner'
  );

-- clients: clerk sees own only; owner sees all in firm
drop policy if exists "clients_select" on public.clients;
create policy "clients_select" on public.clients
  for select using (
    firm_id = public.current_firm_id()
    and (public.current_role() = 'owner' or assigned_to = auth.uid())
  );

drop policy if exists "clients_insert" on public.clients;
create policy "clients_insert" on public.clients
  for insert with check (firm_id = public.current_firm_id());

drop policy if exists "clients_update" on public.clients;
create policy "clients_update" on public.clients
  for update using (
    firm_id = public.current_firm_id()
    and (public.current_role() = 'owner' or assigned_to = auth.uid())
  );

drop policy if exists "clients_delete" on public.clients;
create policy "clients_delete" on public.clients
  for delete using (
    firm_id = public.current_firm_id()
    and (public.current_role() = 'owner' or assigned_to = auth.uid())
  );

-- claims: same rules as the parent client
drop policy if exists "claims_select" on public.claims;
create policy "claims_select" on public.claims
  for select using (
    exists (
      select 1 from public.clients c
      where c.id = claims.client_id
        and c.firm_id = public.current_firm_id()
        and (public.current_role() = 'owner' or c.assigned_to = auth.uid())
    )
  );

drop policy if exists "claims_insert" on public.claims;
create policy "claims_insert" on public.claims
  for insert with check (
    exists (
      select 1 from public.clients c
      where c.id = claims.client_id
        and c.firm_id = public.current_firm_id()
        and (public.current_role() = 'owner' or c.assigned_to = auth.uid())
    )
  );

drop policy if exists "claims_update" on public.claims;
create policy "claims_update" on public.claims
  for update using (
    exists (
      select 1 from public.clients c
      where c.id = claims.client_id
        and c.firm_id = public.current_firm_id()
        and (public.current_role() = 'owner' or c.assigned_to = auth.uid())
    )
  );

drop policy if exists "claims_delete" on public.claims;
create policy "claims_delete" on public.claims
  for delete using (
    exists (
      select 1 from public.clients c
      where c.id = claims.client_id
        and c.firm_id = public.current_firm_id()
        and (public.current_role() = 'owner' or c.assigned_to = auth.uid())
    )
  );

-- audit_log: any authenticated user in firm can read; only server (service_role) writes
drop policy if exists "audit_read" on public.audit_log;
create policy "audit_read" on public.audit_log
  for select using (
    exists (
      select 1 from public.user_profiles up
      where up.id = audit_log.user_id
        and up.firm_id = public.current_firm_id()
    )
  );

-- ===========================================================
-- Done.
-- After running:
-- 1. Run the seed block from SPEC-PHASE-1 (insert firm + owner profile)
-- 2. Test login from frontend
-- ===========================================================
