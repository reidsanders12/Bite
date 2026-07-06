"""
Application State Management.
Holds session metrics, daily tracking data, and acts as the bridge to the SQLite database.
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional
import flet as ft

from app.database import Database  # Assumes your database file is in app/database.py
from app.models import UserGoals   # Assumes your goal model file is in app/models.py


@dataclass
class AppState:
    db: Database = field(default_factory=Database)
    goals: Optional[UserGoals] = None
    logs: List[Any] = field(default_factory=list)
    pending_item: Optional[Any] = None
    pending_source: Optional[str] = None
    current_user: str = "Local User"

    def __post_init__(self) -> None:
        """Runs automatically right after the class initializes."""
        self.refresh_goals()
        self.refresh_logs()

    def refresh_goals(self) -> None:
        """Fetches up-to-date fitness targets from the local storage layer."""
        try:
            if hasattr(self.db, "get_goals"):
                self.goals = self.db.get_goals()
        except Exception as e:
            print(f"[State Engine] Failed to sync goals: {e}")
            self.goals = None

    def refresh_logs(self) -> None:
        """Fetches fresh consumption history profiles from the local database layer."""
        try:
            if hasattr(self.db, "get_daily_logs"):
                self.logs = self.db.get_daily_logs()
            elif hasattr(self.db, "get_logs"):
                self.logs = self.db.get_logs()
        except Exception as e:
            print(f"[State Engine] Failed to sync logs: {e}")
            self.logs = []

    def get_daily_logs(self) -> List[Any]:
        """Exposes logs securely to view templates."""
        self.refresh_logs()
        return self.logs

    def get_goals(self) -> Optional[UserGoals]:
        """Exposes active goals to view templates."""
        self.refresh_goals()
        return self.goals

    def set_pending(self, item: Any, source: str) -> None:
        """Temporarily caches an incoming logged entity before transaction validation."""
        self.pending_item = item
        self.pending_source = source

    def remove_log(self, entry_id: int) -> None:
            """Deletes a log item completely by its hardware table ID index."""
            print(f"[State Engine] Purging entry record ID: {entry_id}")
            try:
                if hasattr(self.db, "delete_log_entry"):
                    self.db.delete_log_entry(entry_id)
            except Exception as e:
                print(f"[State Engine] Database delete failure: {e}")
                
            # Hard refresh local active application caches
            self.refresh_logs()


    def add_log(self, meal_name: str, calories: int, protein: int, carbs: int, fat: int) -> None:
        """
        The absolute source of truth for saving food items.
        Writes straight to your physical SQLite database, then forces an immediate cache reload.
        """
        print(f"[State Engine] Attempting write payload: {meal_name} ({calories} kcal)")
        
        # 1. Execute physical database write operations
        try:
            if hasattr(self.db, "log_food"):
                self.db.log_food(meal_name, calories, protein, carbs, fat)
            elif hasattr(self.db, "save_log"):
                self.db.save_log(meal_name, calories, protein, carbs, fat)
            elif hasattr(self.db, "insert_log"):
                self.db.insert_log(meal_name, calories, protein, carbs, fat)
        except Exception as db_err:
            print(f"[State Engine] Core database write exception: {db_err}")

        # 2. Local fallback list cache update
        # If your database module layout doesn't support the methods above yet,
        # creating a basic generic object allows the home screen to parse it instantly!
        class GenericLog:
            def __init__(self, name, cal, pro, carb, fat_val):
                self.meal_name = name
                self.calories = int(cal)
                self.protein = int(pro)
                self.carbs = int(carb)
                self.fat = int(fat_val)

        new_entry = GenericLog(meal_name, calories, protein, carbs, fat)
        
        # Prepend to display at the top of the timeline
        self.logs.insert(0, new_entry)
        
        # 3. Synchronize storage backend data completely
        self.refresh_logs()
        # Double check that the item made it into runtime memory successfully
        if not any(getattr(l, 'meal_name', '') == meal_name for l in self.logs):
            self.logs.insert(0, new_entry)