import os
from dotenv import load_dotenv

root_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
env_path = os.path.join(root_dir, ".env")
load_dotenv(env_path)

# GEMINI_API_KEY intentionally does NOT live here (or anywhere in the app or
# its .env) anymore. AI calls go through the gemini-proxy Supabase Edge
# Function (see app/ai_engine.py + supabase/functions/gemini-proxy), which
# holds that key server-side -- a shipped client build should never contain
# an API key that costs real money per call, since anyone can extract it
# from the compiled app.
usda_key = os.getenv("USDA_API_KEY")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise ValueError(
        "[Config Engine] CRITICAL ERROR: SUPABASE_URL or SUPABASE_ANON_KEY missing."
    )

SUPABASE_URL = SUPABASE_URL.strip()
SUPABASE_ANON_KEY = SUPABASE_ANON_KEY.strip()

# 5. Optional: the email address that unlocks the in-app "Sponsor Requests"
# and "Reported Posts" review screens (Profile -> ...). Left blank, those
# screens stay hidden for everyone -- this isn't a hard requirement like the
# keys above.
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "").strip().lower()

# Optional: URLs for the hosted privacy_policy.html / account_deletion.html
# (repo root -- static pages, same "host it yourself" pattern as
# sponsor_signup.html, see the README). Profile only shows these links once
# set -- an unset URL hides the button rather than opening a dead link. Both
# are required by Apple/Google Play policy once an app collects account data
# and (for account_deletion.html specifically) lets users create accounts --
# see README's "App Store / Play Store compliance" section.
PRIVACY_POLICY_URL = os.getenv("PRIVACY_POLICY_URL", "").strip()
ACCOUNT_DELETION_URL = os.getenv("ACCOUNT_DELETION_URL", "").strip()

# Same "host it yourself" pattern as PRIVACY_POLICY_URL above --
# terms_of_service.html (repo root). Unset hides the Profile button rather
# than opening a dead link, same as the other two.
TERMS_OF_SERVICE_URL = os.getenv("TERMS_OF_SERVICE_URL", "").strip()