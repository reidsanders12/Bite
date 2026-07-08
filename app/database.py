"""
Cloud Data Layer via Supabase PostgreSQL.
Handles multi-user row scoping utilizing authenticated user session identifiers.
"""
import os
from typing import List, Optional
from supabase import create_client, Client
from app.models import UserGoals

class Database:
    def __init__(self):
        self.url: str = os.getenv("SUPABASE_URL", "")
        self.key: str = os.getenv("SUPABASE_KEY", "")
        
        if not self.url or not self.key:
            print("[Database Engine] WARNING: Missing Supabase environment keys in .env!")
            
        self.client: Client = create_client(self.url, self.key)

    # --- AUTH MODULE INTERFACES ---

    def sign_up_user(self, email: str, password: str):
        """Registers a brand new account identity within the Supabase Auth cluster."""
        return self.client.auth.sign_up({"email": email, "password": password})

    def sign_in_user(self, email: str, password: str):
        """Authenticates credentials against GoTrue engine and issues a stateful token."""
        return self.client.auth.sign_in_with_password({"email": email, "password": password})

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

    def get_daily_logs(self) -> List[dict]:
        """Fetches logging timelines matching exclusively the active user session."""
        uid = self.get_current_user_id()
        if not uid:
            return []

        try:
            # Filters items utilizing explicit column row constraints (.eq)
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

    def save_goals(self, goals: UserGoals):
        """Upserts a custom target breakdown tied to the individual's user token."""
        uid = self.get_current_user_id()
        if not uid:
            return

        try:
            payload = {
                "user_id": uid, # Primary key constraint target identifier
                "daily_calories": int(goals.daily_calories),
                "daily_protein": int(goals.daily_protein),
                "daily_carbs": int(goals.daily_carbs),
                "daily_fat": int(goals.daily_fat)
            }
            self.client.table("user_goals").upsert(payload).execute()
            print(f"[Supabase Database Engine] Synchronized target goal parameters for UUID: {uid}")
        except Exception as e:
            print(f"[Supabase Sync Error] Failed to save goals: {e}")

    def get_goals(self) -> Optional[UserGoals]:
        """Retrieves targeted macro calculations for the individual user."""
        uid = self.get_current_user_id()
        if not uid:
            return None

        try:
            response = self.client.table("user_goals").select("*").eq("user_id", uid).execute()
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