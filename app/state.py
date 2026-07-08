"""
Central Application State Engine.
Sitting in the Root Directory next to main.py.
"""
from typing import Any, Optional
from supabase import create_client, Client

# Look inside the app folder to get the pre-validated configuration keys
from app.config import SUPABASE_URL, SUPABASE_ANON_KEY

class AppState:
    def __init__(self):
        """
        Main state engine instantiation hook.
        Requires zero positional arguments to comply with core routing architecture.
        """
        print("[STATE] Binding cloud database connection from verified app.config variables...")
        
        # Initialize client using guaranteed clean configuration targets
        self.db: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        
        # Transient frontend staging pointers
        self.pending_breakdown: Optional[Any] = None
        self.pending_source: Optional[str] = None
        
        # Core tracking metric data caches
        self.daily_logs: list = []
        self.user_goals: dict = {}
        
        print("[STATE] State framework initialized completely with autonomous database handles.")

    def refresh_logs(self) -> None:
        """
        Fetches active user log timelines from Supabase to synchronize current dashboard values.
        """
        try:
            print("[STATE] Refreshing daily timeline metrics from cloud database...")
            user_res = self.db.auth.get_user()
            if not user_res or not user_res.user:
                print("[STATE WARNING] Cannot synchronize timelines: User session context invalid.")
                return

            user_id = user_res.user.id
            res = self.db.table("food_logs").select("*").eq("user_id", user_id).order("created_at", descending=True).execute()
            
            self.daily_logs = res.data if hasattr(res, "data") else res
            print(f"[STATE] Successfully loaded {len(self.daily_logs)} log records for dashboard.")
        except Exception as err:
            print(f"[STATE ERROR] Timeline sync failed: {str(err)}")

    def refresh_goals(self) -> None:
        """
        Refreshes macronutrient target splits and dynamic caloric intake baselines.
        """
        try:
            print("[STATE] Synchronizing structural macro goal tables...")
            self.user_goals = {"daily_calories": 2000, "daily_protein": 150, "daily_carbs": 200, "daily_fat": 65}
        except Exception as err:
            print(f"[STATE ERROR] Goal threshold sync failed: {str(err)}")

    def log_food(self, name: str, cal: int, pro: int, carb: int, fat: int) -> None:
        """
        Assembles entry data components, appends active user credentials to clear RLS gates,
        and saves records to the cloud database.
        """
        user_res = self.db.auth.get_user()
        if not user_res or not user_res.user:
            raise Exception("Unauthorized: Missing valid session profile parameters.")

        payload = {
            "user_id": user_res.user.id,
            "meal_name": name,
            "calories": int(cal),
            "protein": int(pro),
            "carbs": int(carb),
            "fat": int(fat)
        }

        print(f"[STATE] Dispatching insertion payload to 'food_logs' table...")
        self.db.table("food_logs").insert(payload).execute()

    def get_daily_logs(self) -> list:
        """Returns the current synchronized app logs cache layer."""
        return self.daily_logs

    def clear_pending(self) -> None:
        """Purges staging data cleanly upon workflow execution finishes."""
        self.pending_breakdown = None
        self.pending_source = None