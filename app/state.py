"""
Central Application State Engine.
Sitting in the Root Directory next to main.py.
"""
import logging
from datetime import date
from typing import Any, Optional

from app.database import Database
from app.models import Circle, LogStreak, UserGoals
from app import age_gate, moderation

logger = logging.getLogger(__name__)

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
        self.log_streak: LogStreak = LogStreak()  # consecutive-day food-logging streak -- home dashboard
        self.user_goals: UserGoals = UserGoals()
        self.current_user_name: str = ""
        self.current_user_email: str = ""
        self.profile_data: dict = {}
        self.circles: list[Circle] = []
        self.circle_status_cache: dict = {}  # circle_id -> list[CircleMemberStatus]
        self.daily_workouts: list = []  # today's workout entries -- home dashboard
        self.workout_history: list = []  # full workout history -- workout history screen
        self.weight_history: list = []  # full weight history, oldest first -- weight screen
        self.sponsors: list = []  # active sponsor rows -- home screen promo slot
        self.sponsor_meal_items: list = []  # Gold sponsors' one-tap meal log options -- lookup screen
        self.sponsor_workout_items: list = []  # Gold sponsors' suggested classes -- log workout screen
        self.meal_feed: list = []  # posts visible to the caller -- meal feed screen
        self.meal_post_like_counts: dict = {}  # post_id -> like count -- meal feed screen
        self.my_liked_post_ids: set = set()  # post ids the caller has liked -- meal feed screen
        self.progress_photos: list = []  # newest first, each with a signed `url` -- progress photos screen
        self.progress_photo_reminder: Optional[dict] = None  # {"remind_at": ...} or None
        self.water_goal_ml: int = 2000  # daily water goal -- water tracker screen + home
        self.water_logs_today: list = []  # today's water entries, newest first -- water tracker screen + home
        # Last-fetched Health summary (steps/active_calories/etc, see
        # health_engine.get_today_summary) -- home_view.py's async health
        # sync writes here so a SYNCHRONOUS rebuild (e.g. right after that
        # sync triggers rerender()) has an immediately-available value for
        # the "calories allowed" math instead of starting back at zero on
        # every rebuild. Never fetched this session == every value None.
        self.health_summary_cache: dict = {
            "steps": None, "active_calories": None, "total_calories": None,
            "flights_climbed": None, "distance_m": None,
        }

        # In-memory only: the coach conversation isn't persisted to Supabase,
        # so it resets on app restart (no chat table exists yet).
        self.chat_history: list = []

    def refresh_logs(self) -> None:
        """Pulls today's food log entries from Supabase (for the home dashboard + coach)."""
        try:
            self.daily_logs = self.db.get_logs_for_date(date.today().isoformat())
        except Exception as err:
            logger.error("Timeline sync failed: %s", err)

    def refresh_history(self) -> None:
        """Pulls the full all-time food log history (for the history screen)."""
        try:
            self.history_logs = self.db.get_all_logs()
        except Exception as err:
            logger.error("History sync failed: %s", err)

    def refresh_log_streak(self) -> None:
        """Pulls the caller's current consecutive-day food-logging streak (home dashboard)."""
        try:
            self.log_streak = self.db.get_log_streak()
        except Exception as err:
            logger.error("Streak sync failed: %s", err)
            self.log_streak = LogStreak()

    def get_log_streak(self) -> LogStreak:
        """Returns the cached current food-logging streak."""
        return self.log_streak

    def refresh_goals(self) -> None:
        """Pulls the signed-in user's saved macro targets, falling back to defaults."""
        try:
            self.user_goals = self.db.get_goals() or UserGoals()
        except Exception as err:
            logger.error("Goal threshold sync failed: %s", err)
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
            logger.error("Profile sync failed: %s", err)

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
            logger.error("Onboarding check failed: %s", err)
            return True

    def log_food(self, name: str, cal: int, pro: int, carb: int, fat: int) -> None:
        """Saves a new entry, scoped to the active user, to the cloud database."""
        self.db.log_food(name, cal, pro, carb, fat)
        self.refresh_logs()
        self.refresh_log_streak()
        self._auto_checkin_circles("calories")

    def refresh_workouts(self) -> None:
        """Pulls today's workout entries from Supabase (for the home dashboard)."""
        try:
            self.daily_workouts = self.db.get_workout_logs_for_date(date.today().isoformat())
        except Exception as err:
            logger.error("Workout sync failed: %s", err)

    def get_daily_workouts(self) -> list:
        """Returns today's cached workout entries."""
        return self.daily_workouts

    def log_workout(self, name: str, duration_minutes: int, calories_burned: int) -> None:
        """Saves a new workout entry and auto-checks-in any matching circles."""
        self.db.log_workout(name, duration_minutes, calories_burned)
        self.refresh_workouts()
        self._auto_checkin_circles("workout")

    def sync_health_workouts(self, workouts: list) -> int:
        """Imports Apple Health / Health Connect workouts (see
        app.health_engine.get_today_workouts) so a watch workout shows up
        exactly like a manually-logged one -- home screen tally, workout
        history list, and circle auto-checkin all read from the same
        workout_logs table. Safe to call on every home screen load: rows
        already imported are silently skipped (see
        database.import_health_workouts's upsert). Returns the number of
        genuinely new workouts added, so the caller only needs to
        re-render/refresh when that's nonzero."""
        added = self.db.import_health_workouts(workouts)
        if added:
            self.refresh_workouts()
            self._auto_checkin_circles("workout")
        return added

    def refresh_workout_history(self) -> None:
        """Pulls the full all-time workout history (for the workout history screen)."""
        try:
            self.workout_history = self.db.get_all_workout_logs()
        except Exception as err:
            logger.error("Workout history sync failed: %s", err)

    def get_workout_history(self) -> list:
        """Returns the cached full workout history."""
        return self.workout_history

    def remove_workout_log(self, entry_id) -> tuple[bool, str]:
        """Deletes a workout entry from the cloud database and local caches."""
        success, err = self.db.delete_workout_log(entry_id)
        if not success:
            return False, err

        def _without(logs):
            return [
                log for log in logs
                if (log.get("id") if isinstance(log, dict) else getattr(log, "id", None)) != entry_id
            ]

        self.daily_workouts = _without(self.daily_workouts)
        self.workout_history = _without(self.workout_history)
        return True, ""

    def log_weight(self, weight_kg: float) -> None:
        """Saves a new weight entry (always stored in kg) and refreshes the history cache."""
        self.db.log_weight(weight_kg)
        self.refresh_weight_history()

    def refresh_weight_history(self) -> None:
        """Pulls the full weight history, oldest first (for the weight trend screen)."""
        try:
            self.weight_history = self.db.get_weight_history()
        except Exception as err:
            logger.error("Weight history sync failed: %s", err)

    def get_weight_history(self) -> list:
        """Returns the cached weight history, oldest first."""
        return self.weight_history

    def remove_weight_log(self, entry_id) -> tuple[bool, str]:
        """Deletes a weight entry from the cloud database and the local cache."""
        success, err = self.db.delete_weight_log(entry_id)
        if not success:
            return False, err

        self.weight_history = [
            log for log in self.weight_history
            if (log.get("id") if isinstance(log, dict) else getattr(log, "id", None)) != entry_id
        ]
        return True, ""

    def refresh_water_goal(self) -> None:
        """Pulls the signed-in user's daily water goal, falling back to 2000mL."""
        try:
            self.water_goal_ml = self.db.get_water_goal()
        except Exception as err:
            logger.error("Water goal sync failed: %s", err)
            self.water_goal_ml = 2000

    def get_water_goal(self) -> int:
        """Returns the cached daily water goal, in mL."""
        return self.water_goal_ml

    def set_water_goal(self, daily_ml: int) -> tuple[bool, str]:
        """Saves a new daily water goal and updates the local cache."""
        success, err = self.db.set_water_goal(daily_ml)
        if success:
            self.water_goal_ml = daily_ml
        return success, err

    def refresh_water_logs_today(self) -> None:
        """Pulls today's water entries (local date), for the water tracker
        screen and home dashboard's water progress meter."""
        try:
            self.water_logs_today = self.db.get_water_logs_for_date(date.today().isoformat())
        except Exception as err:
            logger.error("Water log sync failed: %s", err)
            self.water_logs_today = []

    def get_water_logs_today(self) -> list:
        """Returns the cached list of today's water entries, newest first."""
        return self.water_logs_today

    def get_water_total_today_ml(self) -> int:
        """Sums today's cached water entries -- the running total shown
        against the daily goal."""
        return sum(
            (log.get("amount_ml", 0) if isinstance(log, dict) else getattr(log, "amount_ml", 0))
            for log in self.water_logs_today
        )

    def log_water(self, amount_ml: int) -> None:
        """Saves a new water entry, refreshes today's cache, and
        auto-checks-in any matching circles."""
        self.db.log_water(amount_ml)
        self.refresh_water_logs_today()
        self._auto_checkin_circles("water")

    def remove_water_log(self, entry_id) -> tuple[bool, str]:
        """Deletes a water entry from the cloud database and the local cache."""
        success, err = self.db.delete_water_log(entry_id)
        if not success:
            return False, err

        self.water_logs_today = [
            log for log in self.water_logs_today
            if (log.get("id") if isinstance(log, dict) else getattr(log, "id", None)) != entry_id
        ]
        return True, ""

    def refresh_sponsors(self) -> None:
        """Pulls active sponsor rows for the home screen promo slot."""
        try:
            self.sponsors = self.db.get_active_sponsors()
        except Exception as err:
            logger.error("Sponsor sync failed: %s", err)
            self.sponsors = []

    def get_sponsors(self) -> list:
        """Returns the cached list of active sponsor rows."""
        return self.sponsors

    def can_access_meal_feed(self) -> bool:
        """True unless the signed-in account is a known minor (see
        app/age_gate.py) -- gates the /meal_feed and /post_meal routes
        (main.py) and hides their nav entry points (home_view.py)."""
        return age_gate.can_access_meal_feed(self.profile_data.get("signup_age"))

    # --- SPONSOR MENU ITEMS (Gold-tier native integration) ---

    def refresh_sponsor_meal_items(self) -> None:
        """Pulls active Gold-sponsor meal items for the lookup screen's
        one-tap log options."""
        try:
            self.sponsor_meal_items = self.db.get_gold_sponsor_menu_items("meal")
        except Exception as err:
            logger.error("Sponsor meal item sync failed: %s", err)
            self.sponsor_meal_items = []

    def get_sponsor_meal_items(self) -> list:
        """Returns the cached list of active Gold-sponsor meal items."""
        return self.sponsor_meal_items

    def refresh_sponsor_workout_items(self) -> None:
        """Pulls active Gold-sponsor classes for the log workout screen's
        suggested-workout section."""
        try:
            self.sponsor_workout_items = self.db.get_gold_sponsor_menu_items("workout")
        except Exception as err:
            logger.error("Sponsor workout item sync failed: %s", err)
            self.sponsor_workout_items = []

    def get_sponsor_workout_items(self) -> list:
        """Returns the cached list of active Gold-sponsor classes."""
        return self.sponsor_workout_items

    def get_or_create_sponsor_redemption(self, sponsor_id: int) -> tuple[Optional[dict], str]:
        """This user's redemption code for a sponsor card's "Redeem" dialog
        (see home_view.py) -- created on first request, stable after that."""
        return self.db.get_or_create_sponsor_redemption(sponsor_id)

    def get_cached_health_summary(self) -> dict:
        """Returns the last-fetched Health summary (see health_summary_cache
        in __init__) -- every value is None until home_view.py's async
        health sync has resolved at least once this session."""
        return self.health_summary_cache

    def set_cached_health_summary(self, summary: dict) -> None:
        self.health_summary_cache = summary

    def _auto_checkin_circles(self, trigger_type: str, value: Optional[int] = None) -> None:
        """Marks today's goal done for any circle whose goal_type matches what
        was just logged -- a workout, hitting today's calorie target, hitting
        today's water target, or (via `value`, e.g. today's Health step
        count) hitting a step goal -- so members with those goal types never
        need to tap the check-in button manually. 'custom' circles are
        untouched; those stay manual.
        """
        self.refresh_circles()
        for circle in self.circles:
            if circle.goal_type != trigger_type:
                continue
            if trigger_type == "calories" and self.get_daily_totals()["calories"] < (circle.goal_value or 0):
                continue
            if trigger_type == "steps" and (value or 0) < (circle.goal_value or 0):
                continue
            if trigger_type == "water" and self.get_water_total_today_ml() < (circle.goal_value or 0):
                continue
            self.db.check_in(circle.id)
            self.circle_status_cache.pop(circle.id, None)

    def remove_log(self, entry_id) -> tuple[bool, str]:
        """Deletes a log entry from the cloud database and both local caches.

        Only updates the local caches if the remote delete actually
        succeeded -- otherwise the UI would show the entry as gone while it
        silently persists in Supabase (e.g. a missing DELETE RLS policy).
        """
        success, err = self.db.delete_log_entry(entry_id)
        if not success:
            return False, err

        def _without(logs):
            return [
                log for log in logs
                if (log.get("id") if isinstance(log, dict) else getattr(log, "id", None)) != entry_id
            ]

        self.daily_logs = _without(self.daily_logs)
        self.history_logs = _without(self.history_logs)
        return True, ""

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

    def add_chat_message(self, text: str, is_user: bool, kind: str = None, data: dict = None) -> None:
        """Appends a message to this session's coach conversation (in-memory only).

        `kind`/`data` let a message carry a structured card payload (e.g. a meal
        or workout suggestion) alongside its plain-text fallback, so revisiting
        the coach screen can rebuild the same card instead of falling back to a
        plain text bubble.
        """
        entry = {"text": text, "is_user": is_user}
        if kind:
            entry["kind"] = kind
            entry["data"] = data
        self.chat_history.append(entry)

    def refresh_circles(self) -> None:
        """Pulls every circle the signed-in user belongs to (circles screen)."""
        try:
            self.circles = self.db.get_my_circles()
        except Exception as err:
            logger.error("Circle sync failed: %s", err)
            self.circles = []

    def get_circles(self) -> list:
        """Returns the cached list of circles the user belongs to."""
        return self.circles

    def create_circle(
        self, name: str, goal_description: str, goal_type: str = "custom", goal_value: Optional[int] = None,
    ) -> tuple:
        """Creates a circle and refreshes the local cache."""
        circle, err = self.db.create_circle(
            name, goal_description, self.current_user_name or "Bite User", goal_type, goal_value,
        )
        if circle:
            self.refresh_circles()
        return circle, err

    def join_circle(self, invite_code: str) -> tuple:
        """Joins a circle by invite code and refreshes the local cache."""
        circle, err = self.db.join_circle(invite_code, self.current_user_name or "Bite User")
        if circle:
            self.refresh_circles()
        return circle, err

    def update_circle_goal(
        self, circle_id: int, goal_description: str, goal_type: str = "custom", goal_value: Optional[int] = None,
    ) -> tuple[bool, str]:
        """Updates a circle's goal (creator-only, enforced by RLS) and refreshes the cache."""
        success, err = self.db.update_circle_goal(circle_id, goal_description, goal_type, goal_value)
        if success:
            self.refresh_circles()
        return success, err

    def leave_circle(self, circle_id: int) -> None:
        """Leaves a circle and refreshes the local cache."""
        self.db.leave_circle(circle_id)
        self.refresh_circles()
        self.circle_status_cache.pop(circle_id, None)

    def delete_circle(self, circle_id: int) -> tuple[bool, str]:
        """Deletes a circle outright (creator-only) and refreshes the local cache."""
        success, err = self.db.delete_circle(circle_id)
        if success:
            self.refresh_circles()
            self.circle_status_cache.pop(circle_id, None)
        return success, err

    def check_in_circle(self, circle_id: int) -> tuple[bool, str]:
        """Marks today's goal as met for the given circle and refreshes its
        status. Returns (success, error_message) -- see db.check_in for why
        that matters now."""
        success, err = self.db.check_in(circle_id)
        if success:
            self.get_circle_status(circle_id, force_refresh=True)
        return success, err

    def undo_checkin_circle(self, circle_id: int) -> tuple[bool, str]:
        """Reverses today's check-in for an accidental tap. Only meaningful
        for manual (goal_type == 'custom') circles -- auto-checkin circles
        derive today's status from calories/workout data instead of a
        direct check-in row, so there's nothing here to undo for those."""
        success, err = self.db.undo_check_in(circle_id)
        if success:
            self.get_circle_status(circle_id, force_refresh=True)
        return success, err

    def get_circle_status(self, circle_id: int, force_refresh: bool = False) -> list:
        """Returns (and caches) member check-in/streak status for one circle."""
        if force_refresh or circle_id not in self.circle_status_cache:
            self.circle_status_cache[circle_id] = self.db.get_circle_status(circle_id)
        return self.circle_status_cache[circle_id]

    def get_pr_summary(self) -> dict:
        """Computes and returns personal records across workouts,
        food-logging streaks, and weight -- recomputed fresh on each call
        (a read-only screen with no other consumer, so there's nothing to
        gain from caching it in a state field)."""
        try:
            return self.db.get_pr_summary()
        except Exception as err:
            logger.error("PR summary sync failed: %s", err)
            return {}

    def refresh_meal_feed(self) -> None:
        """Pulls every meal post visible to the caller (own + public +
        circle posts), plus anonymous like counts and which of those posts
        the caller has liked."""
        try:
            self.meal_feed = self.db.get_meal_feed()
            post_ids = [p.get("id") for p in self.meal_feed if p.get("id") is not None]
            self.meal_post_like_counts = self.db.get_like_counts(post_ids)
            self.my_liked_post_ids = self.db.get_my_liked_post_ids()
        except Exception as err:
            logger.error("Meal feed sync failed: %s", err)
            self.meal_feed = []
            self.meal_post_like_counts = {}
            self.my_liked_post_ids = set()

    def get_meal_feed(self) -> list:
        """Returns the cached meal feed."""
        return self.meal_feed

    def get_like_count(self, post_id) -> int:
        """Returns the cached like count for a post."""
        return self.meal_post_like_counts.get(post_id, 0)

    def has_liked(self, post_id) -> bool:
        """True if the caller has liked this post."""
        return post_id in self.my_liked_post_ids

    def toggle_meal_post_like(self, post_id) -> tuple[bool, str]:
        """Likes or unlikes a post and updates the local cache once the
        round trip succeeds (not optimistically before)."""
        if post_id in self.my_liked_post_ids:
            success, err = self.db.unlike_meal_post(post_id)
            if success:
                self.my_liked_post_ids.discard(post_id)
                self.meal_post_like_counts[post_id] = max(0, self.meal_post_like_counts.get(post_id, 1) - 1)
            return success, err

        success, err = self.db.like_meal_post(post_id)
        if success:
            self.my_liked_post_ids.add(post_id)
            self.meal_post_like_counts[post_id] = self.meal_post_like_counts.get(post_id, 0) + 1
        return success, err

    def block_user(self, blocked_id: str) -> tuple[bool, str]:
        """Blocks a user and refreshes the feed so their posts disappear immediately."""
        success, err = self.db.block_user(blocked_id)
        if success:
            self.refresh_meal_feed()
        return success, err

    def report_meal_post(self, post_id: int, reason: str, category: str = "other") -> tuple[bool, str]:
        """Flags a post for moderation review. Doesn't remove it from the
        reporter's own feed -- that's what Block is for. A reason is
        mandatory (also enforced by the DB check constraint) so the
        moderation queue (reviewed directly in Supabase, not in-app) always
        has something concrete to act on."""
        reason = (reason or "").strip()
        if not reason:
            return False, "Please tell us why you're reporting this post."
        return self.db.report_meal_post(post_id, reason, category)

    def post_meal(
        self, photo_bytes: bytes, caption: str, visibility: str = "public", circle_id: Optional[int] = None,
        calories: Optional[int] = None, protein: Optional[int] = None,
        carbs: Optional[int] = None, fat: Optional[int] = None, show_name: bool = True,
        meal_name: str = "", ingredients: str = "",
    ) -> tuple[bool, str, bool]:
        """Uploads a meal photo and creates the post, then refreshes the feed
        cache. show_name=False stores the post under "Anonymous" instead of
        the caller's real display name.

        Returns (success, error_message, was_flagged). was_flagged is True
        when app/moderation.py's ed_screening_flags() matched the caption/
        meal name/ingredients -- the post is still created (never blocked,
        see that module's docstring), just auto-filed into the admin review
        queue via db.auto_flag_post(). post_meal_view.py uses was_flagged to
        show the poster a support-resource dialog."""
        for text in (caption, meal_name, ingredients):
            if not moderation.is_caption_allowed(text):
                return False, "Something you wrote isn't allowed -- please revise it.", False

        display_name = (self.current_user_name or "Bite User") if show_name else "Anonymous"
        photo_url, err = self.db.upload_meal_photo(photo_bytes)
        if not photo_url:
            return False, err, False
        post_id, err = self.db.create_meal_post(
            photo_url, caption, display_name, visibility, circle_id,
            calories, protein, carbs, fat, meal_name, ingredients,
        )
        if not post_id:
            return False, err, False

        self.refresh_meal_feed()

        matched = set()
        for text in (caption, meal_name, ingredients):
            matched.update(moderation.ed_screening_flags(text))
        was_flagged = bool(matched)
        if was_flagged:
            self.db.auto_flag_post(
                post_id, category="pro_ed_content",
                reason=f"Automated screening matched: {', '.join(sorted(matched))}",
            )
        return True, "", was_flagged

    def remove_meal_post(self, post_id) -> tuple[bool, str]:
        """Deletes a meal post from the cloud database and the local cache."""
        success, err = self.db.delete_meal_post(post_id)
        if not success:
            return False, err

        self.meal_feed = [
            p for p in self.meal_feed
            if (p.get("id") if isinstance(p, dict) else getattr(p, "id", None)) != post_id
        ]
        self.meal_post_like_counts.pop(post_id, None)
        self.my_liked_post_ids.discard(post_id)
        return True, ""

    # --- PROGRESS PHOTOS ---

    def refresh_progress_photos(self) -> None:
        try:
            self.progress_photos = self.db.get_progress_photos()
        except Exception as err:
            logger.error("Progress photos sync failed: %s", err)
            self.progress_photos = []

    def get_progress_photos(self) -> list:
        return self.progress_photos

    def add_progress_photo(self, photo_bytes: bytes, note: str = "") -> tuple[bool, str]:
        """Uploads to the private progress-photos bucket, saves the row,
        then refreshes the cache so the new photo shows up immediately."""
        storage_path, err = self.db.upload_progress_photo(photo_bytes)
        if not storage_path:
            return False, err
        photo_id, err = self.db.create_progress_photo(storage_path, note)
        if not photo_id:
            return False, err
        self.refresh_progress_photos()
        return True, ""

    def remove_progress_photo(self, photo_id: int) -> tuple[bool, str]:
        photo = next((p for p in self.progress_photos if p.get("id") == photo_id), None)
        storage_path = photo.get("storage_path") if photo else None
        if not storage_path:
            return False, "Photo not found."
        success, err = self.db.delete_progress_photo(photo_id, storage_path)
        if success:
            self.progress_photos = [p for p in self.progress_photos if p.get("id") != photo_id]
        return success, err

    def refresh_progress_photo_reminder(self) -> None:
        try:
            self.progress_photo_reminder = self.db.get_progress_photo_reminder()
        except Exception as err:
            logger.error("Progress photo reminder sync failed: %s", err)
            self.progress_photo_reminder = None

    def get_progress_photo_reminder(self) -> Optional[dict]:
        return self.progress_photo_reminder

    def set_progress_photo_reminder(self, remind_at_iso: str) -> tuple[bool, str]:
        success, err = self.db.set_progress_photo_reminder(remind_at_iso)
        if success:
            self.refresh_progress_photo_reminder()
        return success, err

    def clear_progress_photo_reminder(self) -> None:
        self.db.clear_progress_photo_reminder()
        self.progress_photo_reminder = None

    def set_pending(self, breakdown: Any, source: str) -> None:
        """Stages an unconfirmed macro breakdown for the Confirm view."""
        self.pending_breakdown = breakdown
        self.pending_source = source

    def clear_pending(self) -> None:
        """Purges staging data cleanly upon workflow execution finishes."""
        self.pending_breakdown = None
        self.pending_source = None

