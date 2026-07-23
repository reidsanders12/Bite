# Bite — Frictionless AI Photo Logging

An AI-powered calorie/macro tracker. Snap a photo of your food (or type a
sentence describing it) and Gemini returns a structured calorie/macro
breakdown in seconds — no manual food-database searching required for the
common case. Your account, daily logs, and macro targets sync to the cloud
via Supabase, so your data follows you between devices.

## Architecture

| Layer | Choice |
|---|---|
| UI | [Flet](https://flet.dev) (Python → native Flutter UI, one codebase for desktop/web/mobile) |
| AI | `gemini-2.5-flash`, called through the `gemini-proxy` Supabase Edge Function (see below) |
| Structured output | `pydantic` — the app builds a Gemini-compatible schema from each model, forcing strict JSON output |
| Auth + cloud storage | [Supabase](https://supabase.com) — auth, food logs, macro goals, and profile metadata |
| Barcode lookup | [Open Food Facts](https://world.openfoodfacts.org) (free, no key) |
| Ingredient lookup | [USDA FoodData Central](https://fdc.nal.usda.gov) (free key, `DEMO_KEY` works too) |

There is **no Flask/FastAPI backend** in this codebase — Supabase (Postgres +
Auth + Edge Functions) is the only backend. Open Food Facts and USDA calls go
straight from the app to those public APIs; Gemini calls go through the
`gemini-proxy` Edge Function instead of straight from the app, specifically
so the Gemini API key never has to ship inside a built app (see "Why a
proxy?" below).

### Why a proxy in front of Gemini?

Earlier versions of this app called Gemini directly from the client using a
`GEMINI_API_KEY` embedded in its own `.env`. That key ends up inside every
compiled build (`flet build apk`/`ipa`/etc.) — anyone who installs the app
can pull it back out and spend your Gemini quota/bill outside the app
entirely, with no way for you to rate-limit them per user. `gemini-proxy`
(`supabase/functions/gemini-proxy/index.ts`) fixes that: it's the only place
the real key lives (as a Supabase secret, never in this repo or a built
app), it checks the caller has a live Supabase session before doing
anything, and it enforces a per-user daily request cap
(`supabase_gemini_proxy_schema.sql`) so one leaked session can't run up the
whole project's bill. The app still builds the exact same request it always
did (system instruction, contents, generation config, response schema) —
`app/ai_engine.py` just POSTs it to the proxy instead of calling the
`google-genai` SDK directly.

## Project layout

```
main.py                      # entry point, route-based navigation
app/
  models.py                  # Pydantic schemas (MacroBreakdown, FoodItem, UserGoals)
  database.py                 # Supabase data layer (auth, food_logs, user_goals, profile metadata)
  state.py                     # shared app state passed between views; caches logs/goals/profile
  ai_engine.py                  # Gemini Flash calls (image + text) via gemini-proxy, structured output
  food_apis.py                   # Open Food Facts + USDA FoodData Central lookups
  camera_engine.py                 # photo capture helpers for Snap & Log
  config.py                         # loads .env (USDA/Supabase keys) into the environment
  theme.py                           # shared design tokens (colors, radii, fonts, shared widgets)
  promotions.py                       # icon-name -> ft.Icons map for sponsor rows (data lives in Supabase)
  views/
    auth_view.py                     # sign in / create account (name, email, password)
    survey_view.py                    # onboarding: biometrics -> BMR/TDEE -> macro targets
    home_view.py                       # dashboard: calorie ring, macro bars, today's log
    snap_view.py                        # Instant Snap & Log (photo -> Gemini)
    confirm_view.py                      # Correction Slider (0.5x-2.0x local rescaling)
    text_log_view.py                      # Natural Language Text Log
    lookup_view.py                         # Barcode / ingredient search
    history_view.py                         # full log history, with delete
    profile_view.py                          # name, goal summary, edit targets, log out
    circles_view.py                          # friend circles: create/join/edit-goal, check in on a shared goal
    log_workout_view.py                       # AI-estimated workout entry (describe it, Gemini estimates burn)
    workout_history_view.py                    # full workout history, with delete
    weight_view.py                              # log weight + trend chart + history, with delete
    coach_view.py                                # AI coach chat (linked from the home screen's chat icon)
    sponsor_requests_view.py                      # approve/reject sponsor submissions (ADMIN_EMAIL only)
    settings_view.py                                # legacy goals editor, superseded by profile_view
    widgets.py                                       # shared small UI components
```

[`sponsor_signup.html`](sponsor_signup.html) (repo root) — static public
form for sponsor submissions; not part of the Flet app, hosted/shared
separately. Live at [bitesponsors.netlify.app](https://bitesponsors.netlify.app).

## Setup

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the project root with:

```bash
USDA_API_KEY="your-usda-key"            # https://fdc.nal.usda.gov/api-key-signup (or leave blank for DEMO_KEY)
SUPABASE_URL="https://xxxx.supabase.co"
SUPABASE_ANON_KEY="your-supabase-anon-key"
ADMIN_EMAIL="you@example.com"           # optional -- unlocks Profile -> Sponsor Requests for this account
```

Note there's no `GEMINI_API_KEY` here — that key now lives only as a
Supabase secret used by the `gemini-proxy` Edge Function, never in this
file or in a built app. See "AI setup: the gemini-proxy Edge Function"
below.

Your Supabase project needs two tables: `food_logs` and `user_goals`, both
scoped by `user_id` (matching `auth.users.id`), with Row Level Security
restricting each user to their own rows. `user_goals` needs a **unique
constraint on `user_id`** — the app upserts against it.

### AI setup: the `gemini-proxy` Edge Function

1. **Run the SQL once** — [`supabase_gemini_proxy_schema.sql`](supabase_gemini_proxy_schema.sql)
   in the Supabase SQL editor. Creates the `gemini_usage` table and
   `increment_gemini_usage()` RPC the proxy uses for per-user daily rate
   limiting.
2. **Install the Supabase CLI** if you haven't (`brew install supabase/tap/supabase`
   or see the [CLI docs](https://supabase.com/docs/guides/cli)), then link
   this project: `supabase link --project-ref <your-project-ref>`.
3. **Set the real Gemini key as a secret** (never in `.env`, never
   committed):
   ```bash
   supabase secrets set GEMINI_API_KEY="your-gemini-key"
   ```
4. **Deploy the function**:
   ```bash
   supabase functions deploy gemini-proxy
   ```
   `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and `SUPABASE_SERVICE_ROLE_KEY` are
   injected into the function automatically by the platform — you don't set
   those yourself.
5. The app finds it automatically at
   `${SUPABASE_URL}/functions/v1/gemini-proxy` (see `app/ai_engine.py`) —
   no additional client-side config needed.

The daily per-user cap (100 requests/day by default) is set in
`supabase/functions/gemini-proxy/index.ts` (`DAILY_REQUEST_LIMIT`) — adjust
and redeploy if you need a different limit.

For Friend Circles, Workout Logging, Weight Tracking, and Sponsors, run
[`supabase_circles_schema.sql`](supabase_circles_schema.sql) once in the
Supabase SQL editor. It creates `circles`, `circle_members`,
`circle_checkins`, `workout_logs`, `weight_logs`, and `sponsors`, with RLS
policies that (unlike `food_logs`/`user_goals`) deliberately let every
member of a circle read the other members' check-in status — that's the
whole point of a shared accountability goal. No macro or meal data is ever
exposed this way; check-ins are just a per-day boolean against a goal the
circle's creator set.

`workout_logs` and `weight_logs` are scoped strictly per-user like
`food_logs` — no cross-member visibility.

### Sponsors: how they get submitted and approved

Sponsors go through a submit-then-approve flow, not direct table edits:

1. **Submission** — [`sponsor_signup.html`](sponsor_signup.html) is a
   self-contained static page (no server, no build step) that anyone can
   fill out and submit — a prospective sponsor, or you testing it yourself.
   Fill in its `SUPABASE_URL`/`SUPABASE_ANON_KEY` placeholders from your
   `.env`, then host it anywhere static (GitHub Pages, Netlify, or just
   open the file locally) and send the link to whoever you want to sponsor
   Bite — currently live at
   [bitesponsors.netlify.app](https://bitesponsors.netlify.app). It `POST`s
   straight to Supabase's REST API — the
   `sponsors_insert_public_submission` RLS policy is what actually keeps
   this safe: every submission is forced to land as `status='pending'`,
   `active=false` no matter what the submitter sends, so nothing they
   submit can go live without you reviewing it first.
2. **Review** — sign into Bite with the email you set as `ADMIN_EMAIL`,
   then go to Profile → **Sponsor Requests** (hidden for every other
   account). It lists every submission grouped by Pending / Approved /
   Rejected, with Approve/Reject buttons on pending ones and an on/off
   switch for already-approved sponsors. Only `ADMIN_EMAIL`'s account can
   see or act on this screen — enforced by the `sponsors_select_owner`/
   `sponsors_update_owner` RLS policies, not just by hiding the button.
3. **Go live** — approving a request sets `status='approved'` and
   `active=true`; only then does it become eligible for the home screen's
   random pick.

Two placeholders in [`supabase_circles_schema.sql`](supabase_circles_schema.sql)
need your real email before those owner-only policies work — search the
file for `you@example.com` and replace both occurrences with the same
address you set as `ADMIN_EMAIL`, then rerun the file (it's idempotent). A
starter row ("IronWorks Gym", pre-approved) is seeded once so the home
screen isn't empty out of the box.

## Run it

```bash
flet run main.py          # desktop window
flet run main.py --web    # in your browser
```

To preview on a phone over your local network (no App Store client, no
build step): `flet run --web --host 0.0.0.0 --port 8550 main.py`, then open
`http://<your-computer's-LAN-IP>:8550` in the phone's browser. (`--ios`/
`--android` live preview via the "Flet" App Store/Play Store app currently
doesn't work against this project's pinned `flet==0.28.3` -- that app has
moved on to Flet's newer, incompatible 1.0 protocol.)

To ship as a real mobile app later: `flet build apk` / `flet build ipa`
(see the [Flet packaging docs](https://flet.dev/docs/publish)).

### Known issue: "Receive loop error: 'text'"

`flet==0.28.3` has an upstream bug (unfixed as of this version -- see
[flet-dev/flet#5603](https://github.com/flet-dev/flet/issues/5603) and
[#5972](https://github.com/flet-dev/flet/issues/5972)) where
`flet_web/fastapi/flet_app.py`'s websocket receive loop crashes with a bare
`KeyError: 'text'` on any non-text frame, tearing the session down and
causing the client to reconnect and repeat forever -- especially likely
when connecting from a device other than the one running `flet run` (e.g.
previewing on a phone). This repo works around it with a local patch
applied directly to the installed `flet-web` package (not something `pip`
can express as a version pin, since there's no fixed release between
`0.28.3` and the incompatible `0.80.0`/1.0 rewrite).

**Re-run this after any fresh `pip install` that reinstalls `flet-web`**
(new venv, `pip install --force-reinstall`, etc.) -- installing overwrites
the patched file with the original, buggy one:

```bash
python3 scripts/patch_flet_receive_loop.py
```

Safe to run anytime -- it detects whether the patch is already applied and
no-ops if so.

## Core workflows implemented

1. **Sign up / sign in** — email, password, and name; new accounts are routed
   straight into onboarding since they have no macro targets yet.
2. **Onboarding survey** — enter age, gender, weight, and height (metric
   kg/cm or imperial lb/ft+in — your choice is remembered), pick an activity
   level and a goal (lose/maintain/gain), and the app computes your BMR
   (Mifflin-St Jeor) → TDEE → goal-adjusted calorie target → protein/fat/carb
   split (protein set first from bodyweight, fat as a percentage of
   calories, carbs fill the rest). Every input is saved so revisiting the
   survey later pre-fills instead of starting blank.
3. **Instant Snap & Log** — pick/take a food photo, Gemini Flash returns a
   structured macro breakdown in a couple seconds.
4. **The Correction Slider** — confirmation screen lets you scale the
   estimated portion 0.5x–2.0x; calories/protein/carbs/fat recalculate
   instantly and entirely on-device (no extra API call).
5. **Natural Language Text Log** — type something like *"100g oats, a scoop
   of whey, 1 tbsp peanut butter"* and get the same structured breakdown from
   a cheap text-only Gemini call.
6. **Barcode / Ingredient Lookup** — scan/type a barcode (Open Food Facts) or
   search a raw ingredient (USDA) without touching the AI at all.
7. **Home dashboard** — a calorie ring plus protein/carb/fat progress bars
   against your daily targets, and today's logged items.
8. **History** — full scrollable log with a confirm-before-delete step on
   each entry (deletes are permanent, so it asks first).
9. **Profile** — your name, a read-only summary of today's targets, an
   editor for manually overriding calories/macros, a shortcut to redo the
   onboarding survey, and log out.
10. **Friend Circles** — create a circle around a goal, share its
    6-character invite code, and each day every member's progress shows up
    to the group. A circle's goal can be **custom** (a free-text goal you
    check off manually), **workout** (auto-checks in the day you log any
    workout), or **calories** (auto-checks in once your logged calories
    reach a target you set) — members see each other's check-in status and
    day streak, but never each other's food logs. The circle's creator can
    edit the goal (type/target/description) at any time; RLS enforces that
    only the creator can.
11. **AI Workout Logging** — describe a workout in plain language ("45 min
    upper body lifting", "Ran 5k in 30 minutes") and Gemini estimates
    calories burned (using your saved bodyweight, if any) — editable before
    saving, same "AI estimates, you correct" pattern as food logging. Feeds
    the home dashboard's "Today's Workouts" list, any Friend Circle with a
    `workout` goal, and **adds back to today's calorie budget**
    (Remaining = Goal + Exercise − Food, same convention as most calorie
    trackers).
12. **Workout History** — full scrollable log of past workouts with delete,
    reachable from the home screen's "Today's Workouts" section or the
    workout logging screen.
13. **Weight Tracking** — log your weight (kg or lb, matching your
    onboarding unit choice) and see a trend line chart plus full history
    with delete, reachable from Profile.
14. **Promotions** — a sponsored-content slot at the bottom of the home
    screen, randomly picked each load from every approved + active sponsor.
    Anyone can submit a sponsor via [`sponsor_signup.html`](sponsor_signup.html)
    (a static public form); nothing they submit goes live until you approve
    it from Profile → Sponsor Requests, visible only to the `ADMIN_EMAIL`
    account. See "Sponsors: how they get submitted and approved" above.

## Notes & next steps

- `settings_view.py` (an older goals editor, since replaced by
  `profile_view.py`) is registered as a route but has no navigation entry
  point anywhere in the UI — it's superseded and not part of the current
  app flow. (`coach_view.py` *is* wired up — the chat-bubble icon on the
  home screen's top bar opens it.)
- `text_log_view.py`'s mic button records a short voice note and sends it
  straight to Gemini for transcription + macro parsing in one multimodal call
  (`ai_engine.analyze_audio`) — no on-device speech-to-text engine involved,
  same pattern as photo logging. Desktop and mobile builds get a real audio
  file Flet can read back; on web, Flet's `AudioRecorder` only hands back a
  browser-local `blob:` URL with no upload bridge to fetch it server-side, so
  the mic button is disabled there (tooltip explains why) rather than silently
  doing nothing.
- Supabase/Open Food Facts/USDA calls are genuinely live network calls made
  directly from your own device with your own keys. Gemini calls are also
  live, but go through the `gemini-proxy` Edge Function rather than
  straight from the device — see "Why a proxy in front of Gemini?" above.
