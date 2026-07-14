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
| AI | `google-genai` SDK, `gemini-2.5-flash`, called **client-side** with your own key |
| Structured output | `pydantic` — Gemini is forced into strict JSON via `response_schema` |
| Auth + cloud storage | [Supabase](https://supabase.com) — auth, food logs, macro goals, and profile metadata |
| Barcode lookup | [Open Food Facts](https://world.openfoodfacts.org) (free, no key) |
| Ingredient lookup | [USDA FoodData Central](https://fdc.nal.usda.gov) (free key, `DEMO_KEY` works too) |

There is **no Flask/FastAPI backend anywhere** in this codebase. All network
calls (Gemini, Supabase, Open Food Facts, USDA) go straight from this app to
those services.

## Project layout

```
main.py                      # entry point, route-based navigation
app/
  models.py                  # Pydantic schemas (MacroBreakdown, FoodItem, UserGoals)
  database.py                 # Supabase data layer (auth, food_logs, user_goals, profile metadata)
  state.py                     # shared app state passed between views; caches logs/goals/profile
  ai_engine.py                  # Gemini Flash calls (image + text), structured output
  food_apis.py                   # Open Food Facts + USDA FoodData Central lookups
  camera_engine.py                 # photo capture helpers for Snap & Log
  config.py                         # loads .env (Gemini/USDA/Supabase keys) into the environment
  theme.py                           # shared design tokens (colors, radii, fonts, shared widgets)
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
    coach_view.py                             # AI coach chat (in progress, not yet wired up)
    settings_view.py                          # legacy goals editor, superseded by profile_view
    widgets.py                                 # shared small UI components
```

## Setup

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the project root with:

```bash
GEMINI_API_KEY="your-gemini-key"        # https://aistudio.google.com/apikey (free tier)
USDA_API_KEY="your-usda-key"            # https://fdc.nal.usda.gov/api-key-signup (or leave blank for DEMO_KEY)
SUPABASE_URL="https://xxxx.supabase.co"
SUPABASE_ANON_KEY="your-supabase-anon-key"
```

Your Supabase project needs two tables: `food_logs` and `user_goals`, both
scoped by `user_id` (matching `auth.users.id`), with Row Level Security
restricting each user to their own rows. `user_goals` needs a **unique
constraint on `user_id`** — the app upserts against it.

## Run it

```bash
flet run main.py          # desktop window
flet run main.py --web    # in your browser
```

To ship as a real mobile app later: `flet build apk` / `flet build ipa`
(see the [Flet packaging docs](https://flet.dev/docs/publish)).

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

## Notes & next steps

- `coach_view.py` (an AI chat coach) and `settings_view.py` (an older goals
  editor, since replaced by `profile_view.py`) are registered as routes but
  have no navigation entry point anywhere in the UI — they're unfinished/
  superseded and not part of the current app flow.
- `text_log_view.py`'s mic button is a hook, not a full speech-to-text
  integration — wiring a native STT engine is platform-specific and left as a
  clearly marked TODO in that file.
- All Gemini/Supabase/Open Food Facts/USDA calls are genuinely live network
  calls made from your own device with your own keys.
