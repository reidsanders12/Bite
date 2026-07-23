-- Gemini proxy support: per-user daily request counter used by
-- supabase/functions/gemini-proxy/index.ts to rate-limit AI calls now that
-- they're routed through that Edge Function instead of straight from the
-- app to Gemini with an embedded key.
--
-- Run this once in the Supabase SQL editor (Dashboard -> SQL Editor -> New
-- query), before deploying the Edge Function. Safe to re-run: table uses
-- `if not exists` and the function is `create or replace`.

create table if not exists gemini_usage (
    user_id uuid not null references auth.users(id) on delete cascade,
    usage_date date not null default current_date,
    request_count integer not null default 0,
    primary key (user_id, usage_date)
);

alter table gemini_usage enable row level security;

-- Deliberately no select/insert/update policies for anon or authenticated:
-- this table is bookkeeping for the proxy only. The Edge Function talks to
-- it with the service-role key, which bypasses RLS entirely -- the app and
-- its users never read or write this table directly.

-- Atomically bumps (and creates, on first call of the day) today's counter
-- for a user and returns the new count. SECURITY DEFINER + no grants to
-- anon/authenticated means this is only callable by the service-role
-- client the Edge Function uses -- a regular user's session can't call it
-- to reset or inspect anyone's counter.
create or replace function increment_gemini_usage(p_user_id uuid, p_usage_date date)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
    new_count integer;
begin
    insert into gemini_usage (user_id, usage_date, request_count)
    values (p_user_id, p_usage_date, 1)
    on conflict (user_id, usage_date)
    do update set request_count = gemini_usage.request_count + 1
    returning request_count into new_count;
    return new_count;
end;
$$;

revoke execute on function increment_gemini_usage(uuid, date) from anon, authenticated;
