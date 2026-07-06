# Macro Tracker — Frictionless AI Photo Logging

A 100% free, open-source AI calorie/macro tracker. No subscriptions, no paywalls,
no backend server, no cloud database bill — ever. Every AI call and every food-database
lookup happens directly from your own device using your own free-tier API key, and
everything you log stays in a local SQLite file on your machine.

## Architecture

| Layer | Choice |
|---|---|
| UI | [Flet](https://flet.dev) (Python → native Flutter UI, one codebase for desktop/web/mobile) |
| AI | `google-genai` SDK, `gemini-2.5-flash`, called **client-side** with your own key |
| Structured output | `pydantic` — Gemini is forced into strict JSON via `response_schema` |
| Local storage | SQLite (`~/.macro_tracker/macro_tracker.db`) — goals + full log history |
| Barcode lookup | [Open Food Facts](https://world.openfoodfacts.org) (free, no key) |
| Ingredient lookup | [USDA FoodData Central](https://fdc.nal.usda.gov) (free key, `DEMO_KEY` works too) |

There is **no Flask/FastAPI backend anywhere** in this codebase. All network calls
(Gemini, Open Food Facts, USDA) go straight from this app to those services.

## Project layout

```
main.py                    # entry point, route-based navigation
app/
  models.py                 # Pydantic schemas (MacroBreakdown, FoodItem, UserGoals)
  database.py                # SQLite persistence (goals + logs)
  ai_engine.py                # Gemini Flash calls (image + text), structured output
  food_apis.py                 # Open Food Facts + USDA FoodData Central lookups
  config.py                     # local API-key persistence (~/.macro_tracker/config.json)
  state.py                       # shared in-memory app state passed between views
  views/
    home_view.py                 # dashboard: progress rings + quick actions
    snap_view.py                  # Instant Snap & Log (photo -> Gemini)
    confirm_view.py                # Correction Slider (0.5x-2.0x local rescaling)
    text_log_view.py                # Natural Language Voice/Text Log
    history_view.py                  # 7-day chart + full log history
    lookup_view.py                    # Barcode / ingredient search
    settings_view.py                   # API keys + daily macro goals
    widgets.py                          # shared small UI components
```

## Setup

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Get a **free Gemini API key** at https://aistudio.google.com/apikey (generous free
tier, no credit card required for `gemini-2.5-flash`). Optionally get a free USDA
key at https://fdc.nal.usda.gov/api-key-signup — or just leave it blank, the app
falls back to the shared `DEMO_KEY`.

You can either:
- Paste your Gemini key into **Settings** inside the running app (persisted to
  `~/.macro_tracker/config.json`), or
- Export it as an environment variable before launching:
  ```bash
  export GEMINI_API_KEY="your-key-here"
  ```

## Run it

```bash
flet run main.py          # desktop window
flet run main.py --web    # in your browser
```

To ship as a real mobile app later: `flet build apk` / `flet build ipa`
(see the [Flet packaging docs](https://flet.dev/docs/publish)).

## Core workflows implemented

1. **Instant Snap & Log** — pick/take a food photo, Gemini Flash returns a
   structured macro breakdown in a couple seconds.
2. **The Correction Slider** — confirmation screen lets you scale the estimated
   portion 0.5x–2.0x; calories/protein/carbs/fat recalculate instantly and
   entirely on-device (no extra API call).
3. **Natural Language Text Log** — type (or dictate via your keyboard's mic)
   something like *"100g oats, a scoop of whey, 1 tbsp peanut butter"* and get
   the same structured breakdown from a cheap text-only Gemini call.
4. **Barcode / Ingredient Lookup** — scan/type a barcode (Open Food Facts) or
   search a raw ingredient (USDA) without touching the AI at all.
5. **Local History & Aggregates** — daily progress rings vs. your goals, plus a
   7-day calorie chart and a full scrollable log, all read straight from SQLite.

## Notes & next steps

- `text_log_view.py`'s mic button is a hook, not a full speech-to-text
  integration — wiring a native STT engine is platform-specific and left as a
  clearly marked TODO in that file.
- All Gemini/Open Food Facts/USDA calls are genuinely live network calls; they
  were verified against the installed SDK's actual method signatures, but
  weren't exercised against the live services while generating this code (no
  outbound network access to those domains in the build sandbox). Test with
  your own key before you trust the numbers on a real meal.
