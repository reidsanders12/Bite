"""
Central Application State Engine.
Sitting in the Root Directory next to main.py.
"""
from datetime import date
from typing import Any, Optional

from app.database import Database
from app.models import UserGoals

class AppState:
    def __init__(self):
        """
        Main state engine instantiation hook.
        Requires zero positional arguments to comply with core routing architecture.
        """
        self.db: Database = Database()

        # Transient frontend staging pointers
        self.pending_breakdown: Optional[Any] = None
        self.pending_source: Optional[str] = None

        # Core tracking metric data caches
        self.daily_logs: list = []       # today only -- home dashboard + coach
        self.history_logs: list = []     # full history -- history screen
        self.user_goals: UserGoals = UserGoals()
        self.current_user_name: str = ""
        self.current_user_email: str = ""
        self.profile_data: dict = {}

        # In-memory only: the coach conversation isn't persisted to Supabase,
        # so it resets on app restart (no chat table exists yet).
        self.chat_history: list = []

    def refresh_logs(self) -> None:
        """Pulls today's food log entries from Supabase (for the home dashboard + coach)."""
        try:
            self.daily_logs = self.db.get_logs_for_date(date.today().isoformat())
        except Exception as err:
            print(f"[STATE ERROR] Timeline sync failed: {str(err)}")

    def refresh_history(self) -> None:
        """Pulls the full all-time food log history (for the history screen)."""
        try:
            self.history_logs = self.db.get_all_logs()
        except Exception as err:
            print(f"[STATE ERROR] History sync failed: {str(err)}")

    def refresh_goals(self) -> None:
        """Pulls the signed-in user's saved macro targets, falling back to defaults."""
        try:
            self.user_goals = self.db.get_goals() or UserGoals()
        except Exception as err:
            print(f"[STATE ERROR] Goal threshold sync failed: {str(err)}")
            self.user_goals = UserGoals()

    def refresh_profile(self) -> None:
        """Pulls the signed-in user's display name and saved biometrics from their auth metadata."""
        try:
            user_res = self.db.auth.get_user()
            if user_res and user_res.user:
                meta = user_res.user.user_metadata or {}
                self.current_user_email = user_res.user.email or ""
                self.current_user_name = (
                    meta.get("full_name") or self.current_user_email.split("@")[0] or "Bite User"
                )
                self.profile_data = meta
        except Exception as err:
            print(f"[STATE ERROR] Profile sync failed: {str(err)}")

    def get_profile_data(self) -> dict:
        """Returns cached biometric/location inputs from the last onboarding run, if any."""
        return self.profile_data

    def save_profile_data(self, data: dict) -> None:
        """Persists biometric/location inputs so onboarding can pre-fill next time."""
        self.db.update_profile_data(data)
        self.profile_data = {**self.profile_data, **data}

    def has_completed_onboarding(self) -> bool:
        """True once the signed-in user has a saved macro target row."""
        try:
            return self.db.get_goals() is not None
        except Exception as err:
            print(f"[STATE ERROR] Onboarding check failed: {str(err)}")
            return True

    def log_food(self, name: str, cal: int, pro: int, carb: int, fat: int) -> None:
        """Saves a new entry, scoped to the active user, to the cloud database."""
        self.db.log_food(name, cal, pro, carb, fat)

    def remove_log(self, entry_id) -> None:
        """Deletes a log entry from the cloud database and both local caches."""
        self.db.delete_log_entry(entry_id)

        def _without(logs):
            return [
                log for log in logs
                if (log.get("id") if isinstance(log, dict) else getattr(log, "id", None)) != entry_id
            ]

        self.daily_logs = _without(self.daily_logs)
        self.history_logs = _without(self.history_logs)

    def get_daily_logs(self) -> list:
        """Returns today's cached log entries (home dashboard + coach)."""
        return self.daily_logs

    def get_history_logs(self) -> list:
        """Returns the cached full log history (history screen)."""
        return self.history_logs

    def get_daily_totals(self) -> dict:
        """Sums today's cached logs into a {calories, protein, carbs, fat} dict."""
        totals = {"calories": 0, "protein": 0, "carbs": 0, "fat": 0}
        for log in self.daily_logs:
            for key in totals:
                try:
                    value = log.get(key, 0) if isinstance(log, dict) else getattr(log, key, 0)
                    totals[key] += int(value)
                except (TypeError, ValueError):
                    pass
        return totals

    def get_goals(self) -> UserGoals:
        """Returns the current synchronized macro targets cache layer."""
        return self.user_goals

    @property
    def goals(self) -> UserGoals:
        return self.user_goals

    def get_chat_history(self) -> list:
        """Returns this session's coach conversation (in-memory only)."""
        return self.chat_history

    def add_chat_message(self, text: str, is_user: bool) -> None:
        """Appends a message to this session's coach conversation (in-memory only)."""
        self.chat_history.append({"text": text, "is_user": is_user})

    def set_pending(self, breakdown: Any, source: str) -> None:
        """Stages an unconfirmed macro breakdown for the Confirm view."""
        self.pending_breakdown = breakdown
        self.pending_source = source

    def clear_pending(self) -> None:
        """Purges staging data cleanly upon workflow execution finishes."""
        self.pending_breakdown = None
        self.pending_source = None
