from app.models import Circle, LogStreak


def _calorie_circle(goal_value=1500, circle_id=1):
    return Circle(
        id=circle_id, name="Cut Crew", goal_description="Hit calorie target",
        goal_type="calories", goal_value=goal_value, invite_code="ABC123", created_by="u1",
    )


def _workout_circle(circle_id=2):
    return Circle(
        id=circle_id, name="Gym Rats", goal_description="Log a workout",
        goal_type="workout", goal_value=None, invite_code="XYZ789", created_by="u1",
    )


# --- get_daily_totals ---

def test_get_daily_totals_sums_dict_and_object_logs(state):
    class ObjLog:
        calories, protein, carbs, fat = 200, 10, 20, 5

    state.daily_logs = [
        {"calories": 500, "protein": 30, "carbs": 40, "fat": 10},
        ObjLog(),
    ]
    assert state.get_daily_totals() == {"calories": 700, "protein": 40, "carbs": 60, "fat": 15}


def test_get_daily_totals_skips_unparseable_values_instead_of_raising(state):
    state.daily_logs = [{"calories": "not-a-number", "protein": 10, "carbs": 0, "fat": 0}]
    totals = state.get_daily_totals()
    assert totals == {"calories": 0, "protein": 10, "carbs": 0, "fat": 0}


def test_get_daily_totals_with_no_logs_is_all_zero(state):
    state.daily_logs = []
    assert state.get_daily_totals() == {"calories": 0, "protein": 0, "carbs": 0, "fat": 0}


# --- log_food / auto check-in on calorie circles ---

def test_log_food_auto_checks_in_calorie_circle_once_target_is_hit(state):
    state.db.get_logs_for_date.return_value = [{"calories": 2000, "protein": 0, "carbs": 0, "fat": 0}]
    state.db.get_my_circles.return_value = [_calorie_circle(goal_value=1500)]

    state.log_food("Big meal", 500, 20, 60, 10)

    state.db.log_food.assert_called_once_with("Big meal", 500, 20, 60, 10)
    state.db.check_in.assert_called_once_with(1)


def test_log_food_does_not_check_in_calorie_circle_below_target(state):
    state.db.get_logs_for_date.return_value = [{"calories": 500, "protein": 0, "carbs": 0, "fat": 0}]
    state.db.get_my_circles.return_value = [_calorie_circle(goal_value=1500)]

    state.log_food("Snack", 500, 5, 10, 2)

    state.db.check_in.assert_not_called()


def test_log_food_refreshes_log_streak(state):
    state.db.get_logs_for_date.return_value = []
    state.db.get_my_circles.return_value = []
    state.db.get_log_streak.return_value = LogStreak(current_streak=3, logged_today=True)

    state.log_food("Snack", 100, 5, 10, 2)

    state.db.get_log_streak.assert_called_once()
    assert state.get_log_streak() == LogStreak(current_streak=3, logged_today=True)


def test_refresh_log_streak_falls_back_to_zero_on_db_error(state):
    state.db.get_log_streak.side_effect = Exception("boom")

    state.refresh_log_streak()

    assert state.get_log_streak() == LogStreak()


def test_log_food_ignores_workout_circles(state):
    state.db.get_logs_for_date.return_value = [{"calories": 2000, "protein": 0, "carbs": 0, "fat": 0}]
    state.db.get_my_circles.return_value = [_workout_circle()]

    state.log_food("Big meal", 2000, 100, 200, 50)

    state.db.check_in.assert_not_called()


def test_log_workout_checks_in_workout_circle_regardless_of_calories(state):
    state.db.get_logs_for_date.return_value = []
    state.db.get_my_circles.return_value = [_workout_circle(circle_id=7)]

    state.log_workout("Run", 30, 300)

    state.db.log_workout.assert_called_once_with("Run", 30, 300)
    state.db.check_in.assert_called_once_with(7)


# --- delete flows only touch local caches when the remote delete actually succeeds ---

def test_remove_log_leaves_caches_untouched_when_db_delete_is_blocked(state):
    entry = {"id": 1, "calories": 100, "protein": 0, "carbs": 0, "fat": 0}
    state.daily_logs = [entry]
    state.history_logs = [entry]
    state.db.delete_log_entry.return_value = (False, "RLS blocked the delete")

    success, err = state.remove_log(1)

    assert success is False
    assert err == "RLS blocked the delete"
    assert state.daily_logs == [entry]
    assert state.history_logs == [entry]


def test_remove_log_updates_both_caches_on_success(state):
    entry = {"id": 1, "calories": 100, "protein": 0, "carbs": 0, "fat": 0}
    state.daily_logs = [entry]
    state.history_logs = [entry]
    state.db.delete_log_entry.return_value = (True, "")

    success, err = state.remove_log(1)

    assert success is True
    assert state.daily_logs == []
    assert state.history_logs == []


def test_remove_workout_log_blocked_delete_keeps_entry_in_history(state):
    entry = {"id": 5, "workout_name": "Run"}
    state.daily_workouts = [entry]
    state.workout_history = [entry]
    state.db.delete_workout_log.return_value = (False, "blocked")

    success, err = state.remove_workout_log(5)

    assert success is False
    assert state.workout_history == [entry]


# --- is_admin ---

def test_is_admin_true_when_email_matches_case_insensitively(state, monkeypatch):
    monkeypatch.setattr("app.state.ADMIN_EMAIL", "admin@example.com")
    state.current_user_email = "Admin@Example.com"
    assert state.is_admin() is True


def test_is_admin_false_when_email_differs(state, monkeypatch):
    monkeypatch.setattr("app.state.ADMIN_EMAIL", "admin@example.com")
    state.current_user_email = "someone-else@example.com"
    assert state.is_admin() is False


def test_is_admin_false_when_admin_email_unset(state, monkeypatch):
    monkeypatch.setattr("app.state.ADMIN_EMAIL", "")
    state.current_user_email = "anyone@example.com"
    assert state.is_admin() is False


# --- circle status caching ---

def test_get_circle_status_caches_until_force_refresh(state):
    state.db.get_circle_status.return_value = ["status-v1"]

    first = state.get_circle_status(1)
    second = state.get_circle_status(1)

    assert first == ["status-v1"] == second
    state.db.get_circle_status.assert_called_once_with(1)

    state.db.get_circle_status.return_value = ["status-v2"]
    refreshed = state.get_circle_status(1, force_refresh=True)

    assert refreshed == ["status-v2"]
    assert state.db.get_circle_status.call_count == 2
