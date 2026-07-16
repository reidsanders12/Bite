import os
from google import genai

# 1. Manually calculate the absolute path to your root folder
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, ".."))
env_path = os.path.join(root_dir, ".env")

print(f"[RAW ENV DEBUG] Checking path: {env_path}")

# 2. Raw File Inspection Loop
if os.path.exists(env_path):
    print("[RAW ENV DEBUG] File found! Reading lines manually...")
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            # Split lines manually to clear out spaces and hidden quotes
            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'").strip('"')
                
                # Dynamically force-inject it into the environment dictionary
                os.environ[key] = val
                print(f" -> Successfully parsed key manually: '{key}'")
else:
    print(f"[RAW ENV DEBUG] CRITICAL: .env file completely missing from {root_dir}")

# 3. Read back your key allocations
ai_key = os.getenv("GEMINI_API_KEY")
usda_key = os.getenv("USDA_API_KEY")

if not ai_key:
    raise ValueError(
        f"[Config Engine] CRITICAL ERROR: GEMINI_API_KEY is still not set!\n"
        f"Please verify that your file contains a line that looks exactly like:\n"
        f"GEMINI_API_KEY=your_actual_key_here\n"
        f"Current path checked: {env_path}"
    )

# Initialize your client cleanly
client = genai.Client(api_key=ai_key)

# 4. Read and validate your Supabase keys
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

print("[CONFIG DEBUG] All keys loaded and verified cleanly via manual parser fallback!")