"""
Unit tests for the pure date-arithmetic parts of app/database.py that don't
require a live Supabase connection. Bypasses Database.__init__ (which builds
a real supabase Client) via __new__, then stubs just the .client attribute
and get_current_user_id() -- everything else is real Database code.
"""
from datetime import date, timedelta
from types import SimpleNamespace

from app.database import Database


class _FakeQuery:
    def __init__(self, data):
        self._data = data

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def gte(self, *a, **k):
        return self

    def execute(self):
        return SimpleNamespace(data=self._data)


class _FakeClient:
    def __init__(self, data):
        self._data = data

    def table(self, name):
        return _FakeQuery(self._data)


def _make_db(log_dates, uid="u1"):
    db = Database.__new__(Database)
    db.client = _FakeClient([{"created_at": f"{d.isoformat()}T12:00:00"} for d in log_dates])
    db.get_current_user_id = lambda: uid
    return db


def test_streak_counts_consecutive_days_ending_today():
    today = date.today()
    dates = [today, today - timedelta(days=1), today - timedelta(days=2)]

    streak = _make_db(dates).get_log_streak()

    assert streak.current_streak == 3
    assert streak.logged_today is True


def test_streak_still_counts_through_yesterday_if_today_not_logged_yet():
    today = date.today()
    dates = [today - timedelta(days=1), today - timedelta(days=2)]

    streak = _make_db(dates).get_log_streak()

    assert streak.current_streak == 2
    assert streak.logged_today is False


def test_streak_stops_at_a_gap():
    today = date.today()
    # Today logged, yesterday missing, day before logged -- the gap breaks it.
    dates = [today, today - timedelta(days=2)]

    streak = _make_db(dates).get_log_streak()

    assert streak.current_streak == 1
    assert streak.logged_today is True


def test_streak_is_zero_with_no_logs():
    streak = _make_db([]).get_log_streak()

    assert streak.current_streak == 0
    assert streak.logged_today is False


def test_streak_is_zero_with_no_signed_in_user():
    streak = _make_db([date.today()], uid=None).get_log_streak()

    assert streak.current_streak == 0
    assert streak.logged_today is False
