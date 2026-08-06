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

-- Profiles: currently holds just the `is_admin` flag. Everything else about
-- a user (name, biometrics, workout goals) lives in auth.users.user_metadata
-- via GoTrue, not here -- this table exists purely so the Sponsor Requests
-- admin gate (further below) can check a real, non-spoofable database flag
-- instead of the caller-supplied `auth.email()` string. Relying on
-- auth.email() alone is unsafe if email confirmation is ever turned off (or
-- was off when an account was created): an attacker can register a brand
-- new account using someone else's email address and get a live session
-- where auth.email() returns that string, without ever proving they own
-- that mailbox. Turn on email confirmation in Dashboard -> Authentication
-- -> Providers as well -- this table is a second, independent layer, not a
-- replacement for that.
create table if not exists profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    is_admin boolean not null default false
);

alter table profiles enable row level security;

drop policy if exists "profiles_select_self" on profiles;
create policy "profiles_select_self" on profiles
    for select to authenticated using (id = auth.uid());

-- Deliberately no insert/update policy for authenticated/anon: rows (and
-- especially the is_admin flag) are only ever created/edited by you, from
-- the Supabase Table Editor / SQL editor -- never by the app or its users.
-- (The trigger below runs as SECURITY DEFINER, so it can insert despite
-- there being no insert policy for regular users.)

-- Auto-creates a (non-admin) profile row for every new signup, so the
-- admin-check policies further below can always join against this table
-- instead of getting no row at all for brand-new accounts.
create or replace function handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    insert into profiles (id, is_admin) values (new.id, false)
    on conflict (id) do nothing;
    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function handle_new_user();

-- Backfills a profile row for any account(s) that already existed before
-- this migration ran (the trigger above only fires for signups from now
-- on). Safe to re-run -- `on conflict do nothing` skips rows that already
-- have one.
insert into profiles (id, is_admin)
select id, false from auth.users
on conflict (id) do nothing;

-- One-time step you run yourself, once, to make your own account the
-- admin (replace the email, then run just this one statement -- everything
-- above is fine to re-run as-is on every deploy, this line is not, since
-- re-running it after you've since revoked admin from that account would
-- silently re-grant it):
--   update profiles set is_admin = true
--   where id = (select id from auth.users where email = 'you@example.com');

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
    -- Where the home screen's CTA button takes the user -- the sponsor's own
    -- site, not Bite's. Nullable: a submission without one just renders its
    -- promo card without a tappable CTA (see home_view.py).
    website_url text,
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
alter table sponsors add column if not exists website_url text;
alter table sponsors alter column active set default false;

-- Sponsorship tier. Purely a label + display weight at the 'bronze'/'silver'
-- end (see home_view.py's weighted pick) -- 'gold' additionally implies a
-- native-integration promise (e.g. the sponsor's menu items appear as
-- one-tap log options, or a gym's classes show up as suggested workouts)
-- that isn't built by this migration; that's a separate feature to spec
-- once a gold sponsor actually needs it. Enforced app-side (not a DB check
-- constraint) same as `status` above -- kept simple for a single-developer
-- project.
alter table sponsors add column if not exists level text not null default 'bronze';
alter table sponsors drop constraint if exists sponsors_level_check;
alter table sponsors add constraint sponsors_level_check
    check (level in ('bronze', 'silver', 'gold', 'category_exclusive'));

-- Free-text business category (e.g. 'gym', 'QSR', 'yoga studio') -- only
-- meaningful (and required app-side) when level = 'category_exclusive';
-- null/ignored otherwise. Matching is case/whitespace-normalized via the
-- unique index below so "Gym" and "gym " collide as the same category.
alter table sponsors add column if not exists category text;

-- Enforces "only one category-exclusive sponsor per category" at the
-- database level so two concurrent approvals can never both slip through --
-- an app-side-only check has a race window between read and write, this
-- doesn't. Scoped to approved + active rows only, so a pending/rejected/
-- paused row never blocks a new signup or a swap to a different exclusive
-- partner in the same category.
--
-- NOTE: this is app-wide, not per-region -- Bite doesn't collect any
-- per-user location data today, so "only shown to users in their area"
-- can't be enforced by area yet. Revisit if/when the app gains location
-- data; until then, category-exclusive means exclusive across the whole
-- app, which is a strict superset of "exclusive in your area."
drop index if exists sponsors_category_exclusive_unique;
create unique index sponsors_category_exclusive_unique on sponsors (lower(trim(category)))
    where level = 'category_exclusive' and status = 'approved' and active = true;

-- Seeds one example row, pre-approved, so the home screen isn't empty out
-- of the box. Only runs if the table is empty, so re-running this file
-- won't duplicate it or resurrect a row you've since deleted in the
-- Dashboard.
insert into sponsors (sponsor_label, title, subtitle, cta_text, icon_name, website_url, status, active)
select 'Sponsored', 'IronWorks Gym', 'New members get 20% off your first 3 months.', 'Learn More', 'fitness_center', 'https://example.com', 'approved', true
where not exists (select 1 from sponsors);

-- Sponsor Menu Items: the Gold-tier "native integration" promise --
-- a restaurant's menu items appear as one-tap log options (see
-- lookup_view.py's "Sponsored" tab), or a gym's classes show up as
-- suggested workouts (see log_workout_view.py's "Suggested Classes"
-- section). You (the admin) enter these yourself, per sponsor, from the
-- in-app Sponsor Requests screen -- there's no sponsor-facing submission
-- form for this, same admin-managed pattern as approving the sponsor row
-- itself. item_type picks which set of fields is meaningful: 'meal' uses
-- calories/protein/carbs/fat, 'workout' uses duration_minutes/
-- calories_burned; the unused set stays null rather than having two
-- separate tables, since a menu item never needs both.
create table if not exists sponsor_menu_items (
    id bigint generated always as identity primary key,
    sponsor_id bigint not null references sponsors(id) on delete cascade,
    item_type text not null default 'meal',
    name text not null,
    calories integer,
    protein integer,
    carbs integer,
    fat integer,
    duration_minutes integer,
    calories_burned integer,
    active boolean not null default true,
    sort_order integer not null default 0,
    created_at timestamptz not null default now()
);

alter table sponsor_menu_items drop constraint if exists sponsor_menu_items_item_type_check;
alter table sponsor_menu_items add constraint sponsor_menu_items_item_type_check
    check (item_type in ('meal', 'workout'));

alter table sponsor_menu_items enable row level security;

-- Readable by any signed-in user, but only items belonging to a sponsor
-- that's actually approved, active, AND Gold tier -- Bronze/Silver/Category
-- Exclusive sponsors don't carry the native-integration promise, so their
-- items (if any exist from a since-downgraded sponsor) never surface even
-- if left active=true here.
drop policy if exists "sponsor_menu_items_select_gold_active" on sponsor_menu_items;
create policy "sponsor_menu_items_select_gold_active" on sponsor_menu_items
    for select to authenticated using (
        active = true
        and exists (
            select 1 from sponsors s
            where s.id = sponsor_menu_items.sponsor_id
            and s.status = 'approved' and s.active = true and s.level = 'gold'
        )
    );

-- Admin-only write access -- same profiles.is_admin check as
-- sponsors_update_owner, no separate sponsor login exists for this.
drop policy if exists "sponsor_menu_items_all_owner" on sponsor_menu_items;
create policy "sponsor_menu_items_all_owner" on sponsor_menu_items
    for all to authenticated
    using (exists (select 1 from profiles where id = auth.uid() and is_admin))
    with check (exists (select 1 from profiles where id = auth.uid() and is_admin));

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
-- regardless of status from the in-app "Sponsor Requests" screen. Checks
-- the profiles.is_admin flag (set once, manually, by you -- see the
-- profiles table above) rather than a hardcoded email string: `auth.email()`
-- is whatever the caller registered with, which isn't proof of anything
-- unless email confirmation is also enforced. Also set that same address
-- as ADMIN_EMAIL in your .env -- that's a second, app-layer check the UI
-- uses to decide whether to even show the nav link; this policy is the one
-- that actually matters for security.
drop policy if exists "sponsors_select_owner" on sponsors;
create policy "sponsors_select_owner" on sponsors
    for select to authenticated
    using (exists (select 1 from profiles where id = auth.uid() and is_admin));

drop policy if exists "sponsors_update_owner" on sponsors;
create policy "sponsors_update_owner" on sponsors
    for update to authenticated
    using (exists (select 1 from profiles where id = auth.uid() and is_admin));

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

-- circles: readable by the creator and by existing members only -- NOT by
-- every authenticated user. (Previously this was `using (true)`, which let
-- any signed-in user enumerate every circle's name and goal_description
-- app-wide, not just ones they belong to or hold an invite code for.
-- Nothing sensitive lives in this table, but that was broader exposure
-- than the UI implies, and more than the stated purpose -- "look a circle
-- up by invite code before joining" -- actually needs.) Looking a circle up
-- by invite code before joining now goes through the
-- find_circle_by_invite_code() function below instead, which is
-- SECURITY DEFINER and only ever returns the single row matching an exact
-- code the caller already has -- not the whole table.
drop policy if exists "circles_select_authenticated" on circles;
drop policy if exists "circles_select_own_or_member" on circles;
create policy "circles_select_own_or_member" on circles
    for select to authenticated using (
        created_by = auth.uid()
        or id in (select my_circle_ids())
    );

-- Looks up a single circle by its exact invite code, for the "Join a
-- Circle" flow. SECURITY DEFINER so it can find the row even though the
-- caller isn't a member yet (that's the whole point -- they're about to
-- become one) without re-opening blanket table-wide read access the way
-- the old `circles_select_authenticated` policy did.
create or replace function find_circle_by_invite_code(code text)
returns setof circles
language sql
security definer
stable
set search_path = public
as $$
    select * from circles where invite_code = upper(trim(code))
$$;

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

-- Meal Posts: a lightweight photo-sharing feed, separate from food_logs.
-- Posting is a deliberate share, not a side effect of AI logging. Macro
-- fields are optional (nullable) -- a post can be just a photo + caption,
-- or the poster can choose to include the meal's calories/protein/carbs/fat
-- alongside it. Each post is either 'public' (any signed-in user can see
-- it) or 'circle' (only members of the one circle_id it's posted to, via
-- my_circle_ids() -- see above). Deleting a circle cascades to its
-- circle-only posts.
create table if not exists meal_posts (
    id bigint generated always as identity primary key,
    user_id uuid not null references auth.users(id),
    display_name text not null,
    photo_url text not null,
    meal_name text,
    ingredients text,
    caption text,
    visibility text not null default 'public', -- 'public' or 'circle'
    circle_id bigint references circles(id) on delete cascade,
    calories integer,
    protein integer,
    carbs integer,
    fat integer,
    created_at timestamptz not null default now()
);

alter table meal_posts add column if not exists calories integer;
alter table meal_posts add column if not exists protein integer;
alter table meal_posts add column if not exists carbs integer;
alter table meal_posts add column if not exists fat integer;
alter table meal_posts add column if not exists meal_name text;
alter table meal_posts add column if not exists ingredients text;

alter table meal_posts enable row level security;

drop policy if exists "meal_posts_select_visible" on meal_posts;
create policy "meal_posts_select_visible" on meal_posts
    for select to authenticated using (
        visibility = 'public'
        or user_id = auth.uid()
        or (visibility = 'circle' and circle_id in (select my_circle_ids()))
    );

drop policy if exists "meal_posts_insert_own" on meal_posts;
create policy "meal_posts_insert_own" on meal_posts
    for insert to authenticated with check (
        user_id = auth.uid()
        and (
            visibility = 'public'
            or (visibility = 'circle' and circle_id in (select my_circle_ids()))
        )
    );

drop policy if exists "meal_posts_delete_own" on meal_posts;
create policy "meal_posts_delete_own" on meal_posts
    for delete to authenticated using (user_id = auth.uid());

-- Meal Post Likes: anonymous by construction, not just by hiding it in the
-- UI. The select policy below only ever lets a caller see their *own* like
-- rows (to know whether to render a filled/outline heart) -- there is no
-- policy letting anyone read anyone else's like rows, so who-liked-what
-- can't be reconstructed even with direct table access. Aggregate counts
-- are exposed separately via meal_post_like_counts(), a SECURITY DEFINER
-- RPC that returns totals only (same pattern as my_circle_ids() above).
create table if not exists meal_post_likes (
    id bigint generated always as identity primary key,
    post_id bigint not null references meal_posts(id) on delete cascade,
    user_id uuid not null references auth.users(id),
    created_at timestamptz not null default now(),
    unique (post_id, user_id)
);

alter table meal_post_likes enable row level security;

drop policy if exists "meal_post_likes_select_own" on meal_post_likes;
create policy "meal_post_likes_select_own" on meal_post_likes
    for select to authenticated using (user_id = auth.uid());

-- Can only like a post you're actually allowed to see -- mirrors
-- meal_posts_select_visible's own visibility rule exactly, so liking can't
-- be used to probe the existence of a circle-only post you're not a
-- member of.
drop policy if exists "meal_post_likes_insert_own" on meal_post_likes;
create policy "meal_post_likes_insert_own" on meal_post_likes
    for insert to authenticated with check (
        user_id = auth.uid()
        and exists (
            select 1 from meal_posts mp
            where mp.id = meal_post_likes.post_id
            and (
                mp.visibility = 'public'
                or mp.user_id = auth.uid()
                or (mp.visibility = 'circle' and mp.circle_id in (select my_circle_ids()))
            )
        )
    );

drop policy if exists "meal_post_likes_delete_own" on meal_post_likes;
create policy "meal_post_likes_delete_own" on meal_post_likes
    for delete to authenticated using (user_id = auth.uid());

-- Returns {post_id, like_count} for a batch of posts in one round trip.
-- SECURITY DEFINER means it bypasses meal_post_likes' own RLS to compute
-- the count -- but it only ever returns a count, never a user_id, so this
-- doesn't reopen the "who liked what" visibility that policy deliberately
-- withholds.
create or replace function meal_post_like_counts(post_ids bigint[])
returns table(post_id bigint, like_count bigint)
language sql
security definer
stable
set search_path = public
as $$
    select mpl.post_id, count(*) as like_count
    from meal_post_likes mpl
    where mpl.post_id = any(post_ids)
    group by mpl.post_id
$$;

-- Storage: a public-read bucket for meal photos. Public means anyone
-- holding the exact file URL can view it directly -- visibility of a *post*
-- (public vs. circle-only) is enforced by meal_posts' RLS above, but the
-- underlying photo URL itself isn't further access-controlled once
-- uploaded. That's a deliberate simplification (no signed-URL plumbing)
-- consistent with this project's single-developer scope; worth revisiting
-- if circle-only privacy ever needs to be airtight.
insert into storage.buckets (id, name, public)
values ('meal-photos', 'meal-photos', true)
on conflict (id) do nothing;

-- Uploads/deletes are restricted to a path starting with the caller's own
-- uid (app/database.py's upload_meal_photo() writes to `{uid}/{filename}`)
-- -- storage.foldername() splits the object path into its folder segments,
-- so [1] is that leading uid segment.
drop policy if exists "meal_photos_insert_own" on storage.objects;
create policy "meal_photos_insert_own" on storage.objects
    for insert to authenticated
    with check (bucket_id = 'meal-photos' and (storage.foldername(name))[1] = auth.uid()::text);

drop policy if exists "meal_photos_delete_own" on storage.objects;
create policy "meal_photos_delete_own" on storage.objects
    for delete to authenticated
    using (bucket_id = 'meal-photos' and (storage.foldername(name))[1] = auth.uid()::text);

-- Moderation: required by Apple App Store Review Guideline 1.2 (Safety --
-- User Generated Content) and Google Play's User Generated Content policy,
-- both of which apply once an app has a feed of user-posted photos/text
-- visible to other users, as Meal Feed now is. Both require: a way to
-- report content, a way to block abusive users, and a way for you (the
-- developer) to act on reports -- this section plus the admin-only
-- moderation screen (app/views/reported_posts_view.py) are that.

-- Blocked Users: blocking is a personal preference, not a security
-- boundary -- app/database.py's get_meal_feed() filters out posts from
-- anyone the caller has blocked. Only the blocker can ever see their own
-- block list (mirrors meal_post_likes' anonymity approach).
create table if not exists blocked_users (
    blocker_id uuid not null references auth.users(id),
    blocked_id uuid not null references auth.users(id),
    created_at timestamptz not null default now(),
    primary key (blocker_id, blocked_id)
);

alter table blocked_users enable row level security;

drop policy if exists "blocked_users_select_own" on blocked_users;
create policy "blocked_users_select_own" on blocked_users
    for select to authenticated using (blocker_id = auth.uid());

drop policy if exists "blocked_users_insert_own" on blocked_users;
create policy "blocked_users_insert_own" on blocked_users
    for insert to authenticated with check (blocker_id = auth.uid());

drop policy if exists "blocked_users_delete_own" on blocked_users;
create policy "blocked_users_delete_own" on blocked_users
    for delete to authenticated using (blocker_id = auth.uid());

-- Meal Post Reports: flags a post for your review. Only the reporter and
-- the admin account (via the same profiles.is_admin flag sponsors_select_owner
-- uses) can ever read a report row -- an accused poster never sees who
-- reported them or why. A reason is mandatory -- reports never auto-remove
-- a post (that stays a deliberate admin decision in the moderation queue,
-- see reported_posts_view.py), but a required, non-blank reason gives the
-- admin something concrete to act on instead of an unexplained flag.
create table if not exists meal_post_reports (
    id bigint generated always as identity primary key,
    post_id bigint not null references meal_posts(id) on delete cascade,
    reporter_id uuid not null references auth.users(id),
    reason text not null check (char_length(trim(reason)) > 0),
    created_at timestamptz not null default now()
);

update meal_post_reports set reason = 'No reason given' where reason is null or char_length(trim(reason)) = 0;
alter table meal_post_reports alter column reason set not null;
alter table meal_post_reports drop constraint if exists meal_post_reports_reason_not_blank;
alter table meal_post_reports add constraint meal_post_reports_reason_not_blank check (char_length(trim(reason)) > 0);

alter table meal_post_reports enable row level security;

drop policy if exists "meal_post_reports_select_owner" on meal_post_reports;
create policy "meal_post_reports_select_owner" on meal_post_reports
    for select to authenticated using (
        reporter_id = auth.uid()
        or exists (select 1 from profiles where id = auth.uid() and is_admin)
    );

-- Can only report a post you're actually allowed to see -- same visibility
-- rule as meal_post_likes_insert_own, for the same reason (reporting can't
-- be used to probe the existence of a circle-only post you're not in).
drop policy if exists "meal_post_reports_insert_own" on meal_post_reports;
create policy "meal_post_reports_insert_own" on meal_post_reports
    for insert to authenticated with check (
        reporter_id = auth.uid()
        and exists (
            select 1 from meal_posts mp
            where mp.id = meal_post_reports.post_id
            and (
                mp.visibility = 'public'
                or mp.user_id = auth.uid()
                or (mp.visibility = 'circle' and mp.circle_id in (select my_circle_ids()))
            )
        )
    );

-- Admin can dismiss (delete) a report once reviewed -- resolving it without
-- necessarily deleting the underlying post (e.g. a report that turns out to
-- be unfounded).
drop policy if exists "meal_post_reports_delete_admin" on meal_post_reports;
create policy "meal_post_reports_delete_admin" on meal_post_reports
    for delete to authenticated using (
        exists (select 1 from profiles where id = auth.uid() and is_admin)
    );

-- Second, additive DELETE policy on meal_posts (Postgres ORs multiple
-- permissive policies for the same command together) -- lets the admin
-- remove a reported post, not just its owner. This is what makes
-- "a mechanism to report offensive content" actually actionable instead of
-- reports just piling up unread.
drop policy if exists "meal_posts_delete_admin" on meal_posts;
create policy "meal_posts_delete_admin" on meal_posts
    for delete to authenticated using (
        exists (select 1 from profiles where id = auth.uid() and is_admin)
    );
