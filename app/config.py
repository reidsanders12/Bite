import os
from dotenv import load_dotenv
from google import genai

root_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
env_path = os.path.join(root_dir, ".env")
load_dotenv(env_path)

ai_key = os.getenv("GEMINI_API_KEY")
usda_key = os.getenv("USDA_API_KEY")

if not ai_key:
    raise ValueError(
        f"[Config Engine] CRITICAL ERROR: GEMINI_API_KEY is still not set!\n"
        f"Please verify that your file contains a line that looks exactly like:\n"
        f"GEMINI_API_KEY=your_actual_key_here\n"
        f"Current path checked: {env_path}"
    )

client = genai.Client(api_key=ai_key)

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