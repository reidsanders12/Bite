-- Friend Circles: shared, custom accountability goals.
--
-- Run this once in the Supabase SQL editor for your project (Dashboard ->
-- SQL Editor -> New query). Mirrors the food_logs/user_goals pattern already
-- in use, except circle_members/circle_checkins are deliberately readable by
-- every member of a shared circle (not just the row owner) -- that's the
-- whole point of an accountability circle. Nothing sensitive (no macros, no
-- meal data) ever lives in these tables, only a per-day boolean check-in
-- against a free-text goal the circle's creator wrote, so widening read
-- access here doesn't leak anything from food_logs.
--
-- This file is safe to re-run: tables use `if not exists` and every policy
-- is dropped before being recreated.

create table if not exists circles (
    id bigint generated always as identity primary key,
    name text not null,
    goal_description text not null,
    -- 'custom' = manual check-in only. 'workout' = auto check-in the day the
    -- member logs any workout. 'calories' = auto check-in the day the
    -- member's logged calories reach goal_value. Enforced app-side, not by a
    -- DB check constraint (kept simple for a single-developer project).
    goal_type text not null default 'custom',
    goal_value integer,
    invite_code text not null unique,
    created_by uuid not null references auth.users(id),
    created_at timestamptz not null default now()
);

alter table circles add column if not exists goal_type text not null default 'custom';
alter table circles add column if not exists goal_value integer;

create table if not exists circle_members (
    circle_id bigint not null references circles(id) on delete cascade,
    user_id uuid not null references auth.users(id),
    display_name text not null,
    joined_at timestamptz not null default now(),
    primary key (circle_id, user_id)
);

create table if not exists circle_checkins (
    id bigint generated always as identity primary key,
    circle_id bigint not null references circles(id) on delete cascade,
    user_id uuid not null references auth.users(id),
    checkin_date date not null,
    created_at timestamptz not null default now(),
    unique (circle_id, user_id, checkin_date)
);

-- Workout logs: same private, per-user shape as food_logs (strictly scoped
-- to user_id, no cross-member visibility -- unlike the circle tables above,
-- there's no accountability reason to expose workout detail to anyone).
create table if not exists workout_logs (
    id bigint generated always as identity primary key,
    user_id uuid not null references auth.users(id),
    workout_name text not null,
    duration_minutes integer,
    calories_burned integer,
    created_at timestamptz not null default now()
);

-- Weight logs: same private, per-user shape as food_logs/workout_logs.
-- Stored in kg always; the app converts to/from lb for display based on the
-- user's saved unit preference from onboarding.
create table if not exists weight_logs (
    id bigint generated always as identity primary key,
    user_id uuid not null references auth.users(id),
    weight_kg double precision not null,
    created_at timestamptz not null default now()
);

-- Sponsors: home-screen promo slot, plus a submit-then-approve workflow.
-- Anyone can submit a sponsor request (e.g. via sponsor_signup.html, a
-- static public form) -- it lands as status='pending' and is invisible to
-- the app. Only rows with status='approved' AND active=true ever show on
-- the home screen. You review pending requests and approve/reject them from
-- the in-app "Sponsor Requests" screen (Profile -> Sponsor Requests, only
-- visible to whichever email you set as ADMIN_EMAIL in .env -- see below).
-- icon_name is a plain string (see app/promotions.py's icon map) so
-- submitters don't need to know Flet's icon enum; unrecognized names fall
-- back to a generic megaphone icon.
create table if not exists sponsors (
    id bigint generated always as identity primary key,
    sponsor_label text not null default 'Sponsored',
    title text not null,
    subtitle text not null,
    cta_text text not null default 'Learn More',
    icon_name text not null default 'campaign',
    -- 'pending' (just submitted, awaiting your review) -> 'approved' or
    -- 'rejected'. Enforced app-side, not a DB check constraint (kept simple
    -- for a single-developer project, same as circles.goal_type).
    status text not null default 'pending',
    active boolean not null default false,
    sort_order integer not null default 0,
    contact_name text,
    contact_email text,
    created_at timestamptz not null default now()
);

alter table sponsors add column if not exists status text not null default 'pending';
alter table sponsors add column if not exists contact_name text;
alter table sponsors add column if not exists contact_email text;
alter table sponsors alter column active set default false;

-- Seeds one example row, pre-approved, so the home screen isn't empty out
-- of the box. Only runs if the table is empty, so re-running this file
-- won't duplicate it or resurrect a row you've since deleted in the
-- Dashboard.
insert into sponsors (sponsor_label, title, subtitle, cta_text, icon_name, status, active)
select 'Sponsored', 'IronWorks Gym', 'New members get 20% off your first 3 months.', 'Learn More', 'fitness_center', 'approved', true
where not exists (select 1 from sponsors);

alter table circles enable row level security;
alter table circle_members enable row level security;
alter table circle_checkins enable row level security;
alter table workout_logs enable row level security;
alter table weight_logs enable row level security;
alter table sponsors enable row level security;

drop policy if exists "sponsors_select_active" on sponsors;
create policy "sponsors_select_active" on sponsors
    for select to authenticated using (active = true and status = 'approved');

-- Public submission: anyone (signed in or not) can insert a new sponsor
-- request, but the WITH CHECK forces it to land as pending/inactive --
-- a submitter can never self-approve or self-activate their own row.
drop policy if exists "sponsors_insert_public_submission" on sponsors;
create policy "sponsors_insert_public_submission" on sponsors
    for insert to anon, authenticated
    with check (status = 'pending' and active = false);

-- Owner-only review access: lets you see and moderate every sponsor row
-- regardless of status from the in-app "Sponsor Requests" screen. Scoped to
-- reidsanders12@gmail.com -- also set that same address as ADMIN_EMAIL in
-- your .env so the app knows to show that account the review screen.
drop policy if exists "sponsors_select_owner" on sponsors;
create policy "sponsors_select_owner" on sponsors
    for select to authenticated using (auth.email() = 'reidsanders12@gmail.com');

drop policy if exists "sponsors_update_owner" on sponsors;
create policy "sponsors_update_owner" on sponsors
    for update to authenticated using (auth.email() = 'reidsanders12@gmail.com');

drop policy if exists "workout_logs_select_own" on workout_logs;
create policy "workout_logs_select_own" on workout_logs
    for select to authenticated using (user_id = auth.uid());

drop policy if exists "workout_logs_insert_own" on workout_logs;
create policy "workout_logs_insert_own" on workout_logs
    for insert to authenticated with check (user_id = auth.uid());

drop policy if exists "workout_logs_delete_own" on workout_logs;
create policy "workout_logs_delete_own" on workout_logs
    for delete to authenticated using (user_id = auth.uid());

drop policy if exists "weight_logs_select_own" on weight_logs;
create policy "weight_logs_select_own" on weight_logs
    for select to authenticated using (user_id = auth.uid());

drop policy if exists "weight_logs_insert_own" on weight_logs;
create policy "weight_logs_insert_own" on weight_logs
    for insert to authenticated with check (user_id = auth.uid());

drop policy if exists "weight_logs_delete_own" on weight_logs;
create policy "weight_logs_delete_own" on weight_logs
    for delete to authenticated using (user_id = auth.uid());

-- Returns the circle_ids the calling user belongs to. SECURITY DEFINER
-- makes it run as the function's owner (the table owner in Supabase),
-- who is exempt from RLS on tables they own -- so this lookup never
-- re-triggers circle_members' own RLS policy. Policies below call this
-- instead of querying circle_members directly from within its own policy,
-- which otherwise causes "infinite recursion detected in policy" (42P17).
create or replace function my_circle_ids()
returns setof bigint
language sql
security definer
stable
set search_path = public
as $$
    select circle_id from circle_members where user_id = auth.uid()
$$;

-- circles: name/goal text only, nothing sensitive -- any signed-in user can
-- read (needed to look a circle up by invite code before joining it) or
-- create one. Only the creator can rename/delete.
drop policy if exists "circles_select_authenticated" on circles;
create policy "circles_select_authenticated" on circles
    for select to authenticated using (true);

drop policy if exists "circles_insert_own" on circles;
create policy "circles_insert_own" on circles
    for insert to authenticated with check (created_by = auth.uid());

drop policy if exists "circles_update_own" on circles;
create policy "circles_update_own" on circles
    for update to authenticated using (created_by = auth.uid());

drop policy if exists "circles_delete_own" on circles;
create policy "circles_delete_own" on circles
    for delete to authenticated using (created_by = auth.uid());

-- circle_members: readable by anyone who is also a member of that circle,
-- via my_circle_ids() (see comment above -- avoids self-referencing RLS
-- recursion). Insert/delete are restricted to your own membership row.
--
-- The `user_id = auth.uid()` clause below is not redundant with
-- my_circle_ids(): it's what lets you see your *own* just-inserted row
-- immediately. supabase-py requests the row back after insert (RETURNING),
-- and Postgres checks that against this SELECT policy in the same
-- statement -- without a direct, non-recursive way to see your own row,
-- that check can fail and surfaces as "new row violates row-level security
-- policy for table circle_members" on what looks like a plain insert.
drop policy if exists "circle_members_select_fellow_members" on circle_members;
create policy "circle_members_select_fellow_members" on circle_members
    for select to authenticated using (
        user_id = auth.uid()
        or circle_id in (select my_circle_ids())
    );

drop policy if exists "circle_members_insert_self" on circle_members;
create policy "circle_members_insert_self" on circle_members
    for insert to authenticated with check (user_id = auth.uid());

drop policy if exists "circle_members_delete_self" on circle_members;
create policy "circle_members_delete_self" on circle_members
    for delete to authenticated using (user_id = auth.uid());

-- circle_checkins: same fellow-member visibility as circle_members (and the
-- same `user_id = auth.uid()` direct clause, for the same RETURNING-check
-- reason explained above). Only boolean "did they check in on this date" --
-- no macro/meal content.
drop policy if exists "circle_checkins_select_fellow_members" on circle_checkins;
create policy "circle_checkins_select_fellow_members" on circle_checkins
    for select to authenticated using (
        user_id = auth.uid()
        or circle_id in (select my_circle_ids())
    );

drop policy if exists "circle_checkins_insert_self" on circle_checkins;
create policy "circle_checkins_insert_self" on circle_checkins
    for insert to authenticated with check (
        user_id = auth.uid()
        and circle_id in (select my_circle_ids())
    );
