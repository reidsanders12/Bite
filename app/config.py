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
# review screen (Profile -> Sponsor Requests). Left blank, that screen stays
# hidden for everyone -- this isn't a hard requirement like the keys above.
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "").strip().lower()