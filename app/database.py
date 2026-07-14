"""
Cloud Data Layer via Supabase PostgreSQL.
Handles multi-user row scoping utilizing authenticated user session identifiers.
"""
from typing import List, Optional
from supabase import create_client, Client
from app.config import SUPABASE_URL, SUPABASE_ANON_KEY
from app.models import UserGoals

class Database:
    def __init__(self):
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

    @property
    def auth(self):
        """Passthrough so callers can still reach the underlying GoTrue auth client."""
        return self.client.auth

    # --- AUTH MODULE INTERFACES ---

    def sign_up_user(self, email: str, password: str, full_name: Optional[str] = None):
        """Registers a brand new account identity within the Supabase Auth cluster."""
        payload = {"email": email, "password": password}
        if full_name:
            payload["options"] = {"data": {"full_name": full_name}}
        return self.client.auth.sign_up(payload)

    def sign_in_user(self, email: str, password: str):
        """Authenticates credentials against GoTrue engine and issues a stateful token."""
        return self.client.auth.sign_in_with_password({"email": email, "password": password})

    def update_profile_data(self, data: dict):
        """Merges arbitrary profile fields (biometrics, units, location) into
        the user's auth metadata, alongside full_name. GoTrue merges the
        `data` object into existing user_metadata rather than replacing it."""
        try:
            self.client.auth.update_user({"data": data})
        except Exception as e:
            print(f"[Supabase Sync Error] Failed to update profile metadata: {e}")

    def get_profile_data(self) -> dict:
        """Reads the signed-in user's full auth metadata blob."""
        try:
            user_res = self.client.auth.get_user()
            if user_res and user_res.user:
                return user_res.user.user_metadata or {}
        except Exception as e:
            print(f"[Supabase Sync Error] Failed to read profile metadata: {e}")
        return {}

    def get_current_user_id(self) -> Optional[str]:
        """Extracts the unique uuid primary key from the active user session context."""
        try:
            # Safely extract the session via GoTrue token memory state pointers
            session = self.client.auth.get_session()
            if session and session.user:
                return session.user.id
        except Exception:
            pass
        return None

    # --- SCOPED DATA OPERATIONS ---

    def log_food(self, name: str, cal: int, pro: int, carb: int, fat: int):
        """Inserts a new log entry explicitly scoped to the active signed-in user."""
        uid = self.get_current_user_id()
        if not uid:
            print("[Supabase Sync Error] Aborting write payload: No active user session.")
            return

        try:
            payload = {
                "user_id": uid, # Map relational row owner tracking identifier
                "meal_name": name,
                "calories": int(cal),
                "protein": int(pro),
                "carbs": int(carb),
                "fat": int(fat)
            }
            self.client.table("food_logs").insert(payload).execute()
            print(f"[Supabase Database Engine] Committed food entry cleanly for UUID: {uid}")
        except Exception as e:
            print(f"[Supabase Sync Error] Failed to log food: {e}")

    def get_all_logs(self) -> List[dict]:
        """Fetches the full logging history for the active user (all time)."""
        uid = self.get_current_user_id()
        if not uid:
            return []

        try:
            response = (
                self.client.table("food_logs")
                .select("*")
                .eq("user_id", uid)
                .order("id", desc=True) # Validated desc=True sorting parameter
                .execute()
            )
            return response.data or []
        except Exception as e:
            print(f"[Supabase Sync Error] Failed to fetch logs: {e}")
            return []

    def get_logs_for_date(self, date_iso: str) -> List[dict]:
        """Fetches only the logs created on the given local date (YYYY-MM-DD)."""
        uid = self.get_current_user_id()
        if not uid:
            return []

        try:
            response = (
                self.client.table("food_logs")
                .select("*")
                .eq("user_id", uid)
                .gte("created_at", f"{date_iso}T00:00:00")
                .lte("created_at", f"{date_iso}T23:59:59.999999")
                .order("id", desc=True)
                .execute()
            )
            return response.data or []
        except Exception as e:
            print(f"[Supabase Sync Error] Failed to fetch today's logs: {e}")
            return []

    def delete_log_entry(self, entry_id: int):
        """Deletes a target row verifying match parameters against entry id and user id."""
        uid = self.get_current_user_id()
        if not uid:
            return

        try:
            # Double check user ownership prior to processing structural database drop queries
            self.client.table("food_logs").delete().eq("id", entry_id).eq("user_id", uid).execute()
        except Exception as e:
            print(f"[Supabase Sync Error] Failed to purge remote row: {e}")

    def save_goals(self, goals: UserGoals) -> tuple[bool, str]:
        """Updates the existing goals row for this user, or inserts one if
        none exists yet. Deliberately does a manual select-then-write instead
        of `.upsert(on_conflict="user_id")`: that call errors out unless the
        table has a unique constraint on user_id, which isn't guaranteed --
        this way it works regardless of what constraints the table has.
        Matches on user_id rather than an `id` column, since user_goals has
        no surrogate id column (user_id is the key -- one row per user).
        Returns (success, error_message) so callers can show the user *why*
        it failed instead of silently falling back to default goals.
        """
        uid = self.get_current_user_id()
        if not uid:
            msg = "No active user session."
            print(f"[Supabase Sync Error] Aborting goal save: {msg}")
            return False, msg

        payload = {
            "user_id": uid,
            "daily_calories": int(goals.daily_calories),
            "daily_protein": int(goals.daily_protein),
            "daily_carbs": int(goals.daily_carbs),
            "daily_fat": int(goals.daily_fat)
        }
        try:
            existing = self.client.table("user_goals").select("user_id").eq("user_id", uid).execute()
            if existing.data:
                self.client.table("user_goals").update(payload).eq("user_id", uid).execute()
            else:
                self.client.table("user_goals").insert(payload).execute()
            print(f"[Supabase Database Engine] Synchronized target goal parameters for UUID: {uid}")
            return True, ""
        except Exception as e:
            print(f"[Supabase Sync Error] Failed to save goals: {e}")
            return False, str(e)

    def get_goals(self) -> Optional[UserGoals]:
        """Retrieves targeted macro calculations for the individual user."""
        uid = self.get_current_user_id()
        if not uid:
            return None

        try:
            # No `id` column on user_goals (user_id is the key), so no
            # order/limit needed -- there's at most one row per user.
            response = (
                self.client.table("user_goals")
                .select("*")
                .eq("user_id", uid)
                .execute()
            )
            if response.data:
                row = response.data[0]
                return UserGoals(
                    daily_calories=row["daily_calories"],
                    daily_protein=row["daily_protein"],
                    daily_carbs=row["daily_carbs"],
                    daily_fat=row["daily_fat"]
                )
            return None
        except Exception as e:
            print(f"[Supabase Sync Error] Failed to read remote goals: {e}")
            return None