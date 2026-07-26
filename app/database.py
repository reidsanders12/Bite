"""
Cloud Data Layer via Supabase PostgreSQL.
Handles multi-user row scoping utilizing authenticated user session identifiers.
"""
import logging
import secrets
import string
from datetime import date, timedelta
from typing import List, Optional
from supabase import create_client, Client
from app.config import SUPABASE_URL, SUPABASE_ANON_KEY
from app.models import Circle, CircleMemberStatus, LogStreak, UserGoals

logger = logging.getLogger(__name__)

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
            logger.error(f"Failed to update profile metadata: {e}")

    def get_profile_data(self) -> dict:
        """Reads the signed-in user's full auth metadata blob."""
        try:
            user_res = self.client.auth.get_user()
            if user_res and user_res.user:
                return user_res.user.user_metadata or {}
        except Exception as e:
            logger.error(f"Failed to read profile metadata: {e}")
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

    def get_access_token(self) -> Optional[str]:
        """Returns the active session's access token (JWT), for calls that need
        to authenticate to something other than Supabase itself -- e.g. the
        gemini-proxy Edge Function, which verifies this same token to confirm
        the caller is a real signed-in user before spending any AI quota."""
        try:
            session = self.client.auth.get_session()
            if session:
                return session.access_token
        except Exception:
            pass
        return None

    # --- SCOPED DATA OPERATIONS ---

    def log_food(self, name: str, cal: int, pro: int, carb: int, fat: int):
        """Inserts a new log entry explicitly scoped to the active signed-in user."""
        uid = self.get_current_user_id()
        if not uid:
            logger.error("Aborting write payload: No active user session.")
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
            logger.info(f"Committed food entry cleanly for UUID: {uid}")
        except Exception as e:
            logger.error(f"Failed to log food: {e}")

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
            logger.error(f"Failed to fetch logs: {e}")
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
            logger.error(f"Failed to fetch today's logs: {e}")
            return []

    def get_log_streak(self) -> LogStreak:
        """Computes the caller's current consecutive-day food-logging streak.

        Same approach as get_circle_status: pull a bounded window of rows
        (last 400 days) and compute the streak in Python. If today has no
        entry yet, the streak still counts through yesterday rather than
        dropping to zero immediately -- `logged_today` tells the caller
        whether it's currently at risk of breaking.
        """
        uid = self.get_current_user_id()
        if not uid:
            return LogStreak()

        try:
            window_start = (date.today() - timedelta(days=400)).isoformat()
            response = (
                self.client.table("food_logs")
                .select("created_at")
                .eq("user_id", uid)
                .gte("created_at", f"{window_start}T00:00:00")
                .execute()
            )
            log_dates = {row["created_at"][:10] for row in (response.data or [])}

            today = date.today()
            logged_today = today.isoformat() in log_dates
            cursor = today if logged_today else today - timedelta(days=1)

            streak = 0
            while cursor.isoformat() in log_dates:
                streak += 1
                cursor -= timedelta(days=1)

            return LogStreak(current_streak=streak, logged_today=logged_today)
        except Exception as e:
            logger.error(f"Failed to compute log streak: {e}")
            return LogStreak()

    def delete_log_entry(self, entry_id: int) -> tuple[bool, str]:
        """Deletes a target row verifying match parameters against entry id and user id.

        Returns (success, error_message). Supabase's delete() doesn't raise
        when RLS blocks it -- it just deletes zero rows and reports success
        at the HTTP level -- so this checks response.data instead of trusting
        the absence of an exception.
        """
        uid = self.get_current_user_id()
        if not uid:
            return False, "No active user session."

        try:
            # Double check user ownership prior to processing structural database drop queries
            response = (
                self.client.table("food_logs").delete().eq("id", entry_id).eq("user_id", uid).execute()
            )
            if not response.data:
                logger.error("Delete was blocked (0 rows affected) -- check the DELETE RLS policy on food_logs.")
                return False, "Couldn't delete that entry -- please try again."
            return True, ""
        except Exception as e:
            logger.error(f"Failed to purge remote row: {e}")
            # Generic message for the UI -- the real exception is already
            # printed above (Supabase/Postgres internals shouldn't reach the
            # end user, who has no use for an RLS policy name or table name).
            return False, "Something went wrong -- please try again."

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
            logger.error(f"Aborting goal save: {msg}")
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
            logger.info(f"Synchronized target goal parameters for UUID: {uid}")
            return True, ""
        except Exception as e:
            logger.error(f"Failed to save goals: {e}")
            # Generic message for the UI -- the real exception is already
            # printed above (Supabase/Postgres internals shouldn't reach the
            # end user, who has no use for an RLS policy name or table name).
            return False, "Something went wrong -- please try again."

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
            logger.error(f"Failed to read remote goals: {e}")
            return None

    # --- FRIEND CIRCLES ---

    @staticmethod
    def _row_to_circle(row: dict) -> Circle:
        return Circle(
            id=row["id"], name=row["name"], goal_description=row["goal_description"],
            goal_type=row.get("goal_type", "custom"), goal_value=row.get("goal_value"),
            invite_code=row["invite_code"], created_by=row["created_by"],
        )

    def create_circle(
        self, name: str, goal_description: str, display_name: str,
        goal_type: str = "custom", goal_value: Optional[int] = None,
    ) -> tuple[Optional[Circle], str]:
        """Creates a new circle with a fresh invite code and joins the creator to it."""
        uid = self.get_current_user_id()
        if not uid:
            return None, "No active user session."

        invite_code = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
        try:
            response = (
                self.client.table("circles")
                .insert({
                    "name": name,
                    "goal_description": goal_description,
                    "goal_type": goal_type,
                    "goal_value": goal_value,
                    "invite_code": invite_code,
                    "created_by": uid,
                })
                .execute()
            )
            row = response.data[0]
            self.client.table("circle_members").insert({
                "circle_id": row["id"],
                "user_id": uid,
                "display_name": display_name,
            }).execute()
            return self._row_to_circle(row), ""
        except Exception as e:
            logger.error(f"Failed to create circle: {e}")
            return None, "Something went wrong -- please try again."

    def join_circle(self, invite_code: str, display_name: str) -> tuple[Optional[Circle], str]:
        """Looks up a circle by its invite code and adds the caller as a member.

        Uses the find_circle_by_invite_code() RPC rather than a plain table
        select: the circles table's RLS policy only allows a caller to read
        rows they created or already belong to, so a direct select here
        would never find the circle being joined. The RPC is a
        SECURITY DEFINER lookup scoped to an exact invite-code match --
        it doesn't reopen table-wide read access.
        """
        uid = self.get_current_user_id()
        if not uid:
            return None, "No active user session."

        try:
            found = self.client.rpc(
                "find_circle_by_invite_code", {"code": invite_code.strip().upper()}
            ).execute()
            if not found.data:
                return None, "No circle found with that invite code."
            row = found.data[0]

            self.client.table("circle_members").insert({
                "circle_id": row["id"],
                "user_id": uid,
                "display_name": display_name,
            }).execute()
            return self._row_to_circle(row), ""
        except Exception as e:
            logger.error(f"Failed to join circle: {e}")
            return None, "Something went wrong -- please try again."

    def get_my_circles(self) -> List[Circle]:
        """Returns every circle the caller is a member of."""
        uid = self.get_current_user_id()
        if not uid:
            return []

        try:
            memberships = (
                self.client.table("circle_members").select("circle_id").eq("user_id", uid).execute()
            )
            circle_ids = [m["circle_id"] for m in (memberships.data or [])]
            if not circle_ids:
                return []

            circles = self.client.table("circles").select("*").in_("id", circle_ids).execute()
            return [self._row_to_circle(row) for row in (circles.data or [])]
        except Exception as e:
            logger.error(f"Failed to fetch circles: {e}")
            return []

    def update_circle_goal(
        self, circle_id: int, goal_description: str, goal_type: str, goal_value: Optional[int],
    ) -> tuple[bool, str]:
        """Updates a circle's goal. RLS (circles_update_own) already restricts
        this to the circle's creator; the `.eq("created_by", uid)` below is a
        redundant, app-layer copy of that same check -- defense-in-depth so
        this write path doesn't rely solely on RLS never being misconfigured
        or accidentally disabled."""
        uid = self.get_current_user_id()
        if not uid:
            return False, "No active user session."

        try:
            response = (
                self.client.table("circles")
                .update({
                    "goal_description": goal_description,
                    "goal_type": goal_type,
                    "goal_value": goal_value,
                })
                .eq("id", circle_id)
                .eq("created_by", uid)
                .execute()
            )
            if not response.data:
                msg = "Update was blocked -- only the circle's creator can edit its goal."
                logger.error(msg)
                return False, msg
            return True, ""
        except Exception as e:
            logger.error(f"Failed to update circle goal: {e}")
            # Generic message for the UI -- the real exception is already
            # printed above (Supabase/Postgres internals shouldn't reach the
            # end user, who has no use for an RLS policy name or table name).
            return False, "Something went wrong -- please try again."

    def delete_circle(self, circle_id: int) -> tuple[bool, str]:
        """Deletes a circle outright (creator-only, enforced by both the
        circles_delete_own RLS policy and the redundant `.eq("created_by", uid)`
        check below -- see update_circle_goal for why). circle_members/
        circle_checkins rows cascade-delete automatically via their FK
        ON DELETE CASCADE."""
        uid = self.get_current_user_id()
        if not uid:
            return False, "No active user session."

        try:
            response = (
                self.client.table("circles").delete().eq("id", circle_id).eq("created_by", uid).execute()
            )
            if not response.data:
                msg = "Delete was blocked -- only the circle's creator can delete it."
                logger.error(msg)
                return False, msg
            return True, ""
        except Exception as e:
            logger.error(f"Failed to delete circle: {e}")
            # Generic message for the UI -- the real exception is already
            # printed above (Supabase/Postgres internals shouldn't reach the
            # end user, who has no use for an RLS policy name or table name).
            return False, "Something went wrong -- please try again."

    def leave_circle(self, circle_id: int) -> None:
        """Removes the caller's own membership row from a circle."""
        uid = self.get_current_user_id()
        if not uid:
            return

        try:
            self.client.table("circle_members").delete().eq("circle_id", circle_id).eq("user_id", uid).execute()
        except Exception as e:
            logger.error(f"Failed to leave circle: {e}")

    def check_in(self, circle_id: int) -> None:
        """Records that the caller met their circle's goal today (idempotent per day)."""
        uid = self.get_current_user_id()
        if not uid:
            return

        try:
            self.client.table("circle_checkins").insert({
                "circle_id": circle_id,
                "user_id": uid,
                "checkin_date": date.today().isoformat(),
            }).execute()
        except Exception as e:
            # Expected (and harmless) once today's row already exists --
            # the unique (circle_id, user_id, checkin_date) constraint blocks
            # a duplicate check-in for the same day.
            logger.error(f"Check-in not recorded (likely already checked in today): {e}")

    def get_circle_status(self, circle_id: int) -> List[CircleMemberStatus]:
        """Returns every member's today/streak status for one circle.

        Streaks are computed here in Python from raw checkin dates rather
        than in SQL -- keeps the RLS policies simple (plain row visibility,
        no security-definer function) at the cost of pulling a bounded
        window of rows (last 60 days) per call.
        """
        try:
            members = (
                self.client.table("circle_members")
                .select("user_id, display_name")
                .eq("circle_id", circle_id)
                .execute()
            )
            window_start = (date.today() - timedelta(days=60)).isoformat()
            checkins = (
                self.client.table("circle_checkins")
                .select("user_id, checkin_date")
                .eq("circle_id", circle_id)
                .gte("checkin_date", window_start)
                .execute()
            )

            dates_by_user: dict[str, set] = {}
            for row in (checkins.data or []):
                dates_by_user.setdefault(row["user_id"], set()).add(row["checkin_date"])

            today = date.today()
            statuses = []
            for member in (members.data or []):
                uid = member["user_id"]
                member_dates = dates_by_user.get(uid, set())

                streak = 0
                cursor = today
                while cursor.isoformat() in member_dates:
                    streak += 1
                    cursor -= timedelta(days=1)

                statuses.append(CircleMemberStatus(
                    user_id=uid,
                    display_name=member["display_name"],
                    checked_in_today=today.isoformat() in member_dates,
                    streak_days=streak,
                ))
            return statuses
        except Exception as e:
            logger.error(f"Failed to fetch circle status: {e}")
            return []

    # --- WORKOUT LOGS ---

    def log_workout(self, name: str, duration_minutes: int, calories_burned: int) -> None:
        """Inserts a new workout entry scoped to the active signed-in user."""
        uid = self.get_current_user_id()
        if not uid:
            logger.error("Aborting workout write: No active user session.")
            return

        try:
            self.client.table("workout_logs").insert({
                "user_id": uid,
                "workout_name": name,
                "duration_minutes": int(duration_minutes),
                "calories_burned": int(calories_burned),
            }).execute()
        except Exception as e:
            logger.error(f"Failed to log workout: {e}")

    def get_workout_logs_for_date(self, date_iso: str) -> List[dict]:
        """Fetches the caller's workout entries created on the given local date."""
        uid = self.get_current_user_id()
        if not uid:
            return []

        try:
            response = (
                self.client.table("workout_logs")
                .select("*")
                .eq("user_id", uid)
                .gte("created_at", f"{date_iso}T00:00:00")
                .lte("created_at", f"{date_iso}T23:59:59.999999")
                .order("id", desc=True)
                .execute()
            )
            return response.data or []
        except Exception as e:
            logger.error(f"Failed to fetch today's workouts: {e}")
            return []

    def get_all_workout_logs(self) -> List[dict]:
        """Fetches the caller's full all-time workout history."""
        uid = self.get_current_user_id()
        if not uid:
            return []

        try:
            response = (
                self.client.table("workout_logs")
                .select("*")
                .eq("user_id", uid)
                .order("id", desc=True)
                .execute()
            )
            return response.data or []
        except Exception as e:
            logger.error(f"Failed to fetch workout history: {e}")
            return []

    def delete_workout_log(self, entry_id: int) -> tuple[bool, str]:
        """Deletes a workout entry. See delete_log_entry for why response.data
        is checked instead of trusting the absence of an exception."""
        uid = self.get_current_user_id()
        if not uid:
            return False, "No active user session."

        try:
            response = (
                self.client.table("workout_logs").delete().eq("id", entry_id).eq("user_id", uid).execute()
            )
            if not response.data:
                logger.error("Delete was blocked (0 rows affected) -- check the DELETE RLS policy on workout_logs.")
                return False, "Couldn't delete that entry -- please try again."
            return True, ""
        except Exception as e:
            logger.error(f"Failed to delete workout: {e}")
            # Generic message for the UI -- the real exception is already
            # printed above (Supabase/Postgres internals shouldn't reach the
            # end user, who has no use for an RLS policy name or table name).
            return False, "Something went wrong -- please try again."

    # --- WEIGHT LOGS ---

    def log_weight(self, weight_kg: float) -> None:
        """Inserts a new weight entry (always stored in kg) for the active user."""
        uid = self.get_current_user_id()
        if not uid:
            logger.error("Aborting weight write: No active user session.")
            return

        try:
            self.client.table("weight_logs").insert({
                "user_id": uid,
                "weight_kg": float(weight_kg),
            }).execute()
        except Exception as e:
            logger.error(f"Failed to log weight: {e}")

    def get_weight_history(self) -> List[dict]:
        """Fetches the caller's full weight history, oldest first (for a trend chart)."""
        uid = self.get_current_user_id()
        if not uid:
            return []

        try:
            response = (
                self.client.table("weight_logs")
                .select("*")
                .eq("user_id", uid)
                .order("created_at", desc=False)
                .execute()
            )
            return response.data or []
        except Exception as e:
            logger.error(f"Failed to fetch weight history: {e}")
            return []

    def delete_weight_log(self, entry_id: int) -> tuple[bool, str]:
        """Deletes a weight entry. See delete_log_entry for why response.data
        is checked instead of trusting the absence of an exception."""
        uid = self.get_current_user_id()
        if not uid:
            return False, "No active user session."

        try:
            response = (
                self.client.table("weight_logs").delete().eq("id", entry_id).eq("user_id", uid).execute()
            )
            if not response.data:
                logger.error("Delete was blocked (0 rows affected) -- check the DELETE RLS policy on weight_logs.")
                return False, "Couldn't delete that entry -- please try again."
            return True, ""
        except Exception as e:
            logger.error(f"Failed to delete weight entry: {e}")
            # Generic message for the UI -- the real exception is already
            # printed above (Supabase/Postgres internals shouldn't reach the
            # end user, who has no use for an RLS policy name or table name).
            return False, "Something went wrong -- please try again."

    # --- SPONSORS ---

    def get_active_sponsors(self) -> List[dict]:
        """Fetches approved + active sponsor rows for the home screen promo slot."""
        try:
            response = (
                self.client.table("sponsors")
                .select("*")
                .eq("active", True)
                .eq("status", "approved")
                .order("sort_order", desc=False)
                .execute()
            )
            return response.data or []
        except Exception as e:
            logger.error(f"Failed to fetch sponsors: {e}")
            return []

    def get_all_sponsors(self) -> List[dict]:
        """Fetches every sponsor row regardless of status, for the in-app
        Sponsor Requests review screen. Only returns rows if the caller's
        email matches the sponsors_select_owner RLS policy -- everyone else
        gets an empty list back (silently, not an error)."""
        try:
            response = (
                self.client.table("sponsors")
                .select("*")
                .order("created_at", desc=True)
                .execute()
            )
            return response.data or []
        except Exception as e:
            logger.error(f"Failed to fetch sponsor requests: {e}")
            return []

    def update_sponsor_status(self, sponsor_id: int, status: str, active: bool) -> tuple[bool, str]:
        """Approves/rejects a sponsor request. Restricted to the owner email
        by the sponsors_update_owner RLS policy."""
        try:
            response = (
                self.client.table("sponsors")
                .update({"status": status, "active": active})
                .eq("id", sponsor_id)
                .execute()
            )
            if not response.data:
                msg = "Update was blocked -- only the configured admin account can review sponsors."
                logger.error(msg)
                return False, msg
            return True, ""
        except Exception as e:
            logger.error(f"Failed to update sponsor status: {e}")
            # Generic message for the UI -- the real exception is already
            # printed above (Supabase/Postgres internals shouldn't reach the
            # end user, who has no use for an RLS policy name or table name).
            return False, "Something went wrong -- please try again."