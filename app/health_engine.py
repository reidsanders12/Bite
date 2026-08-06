"""
Client-side wrapper around flet_health.Health() (Apple HealthKit / Google
Health Connect) -- styled like app/ai_engine.py. Read-only: Bite never
writes health data back, it only displays what's already on the device.

flet_health.Health() is a non-visual control that must live in
page.overlay (see app/views/health_view.py, which creates and appends one
per view build) before any of its methods can be called.

Only steps, active calories, total calories, and workouts are requested --
not the much longer list flet-health itself supports -- matching this
app's existing pattern of requesting only the scope a feature actually
uses (Whoop's OAuth scopes, gemini-proxy's model allow-list). STEPS/
WORKOUT/ACTIVE_ENERGY_BURNED/TOTAL_CALORIES_BURNED share identical values
between HealthDataTypeAndroid and HealthDataTypeIOS (confirmed against
flet-health's own example app), so HealthDataTypeAndroid's members are used
unconditionally for both platforms -- no platform branching needed for this
scope.
"""
from datetime import datetime
from typing import Optional

import flet_health as fh

READ_TYPES = [
    fh.HealthDataTypeAndroid.STEPS,
    fh.HealthDataTypeAndroid.ACTIVE_ENERGY_BURNED,
    fh.HealthDataTypeAndroid.TOTAL_CALORIES_BURNED,
    fh.HealthDataTypeAndroid.WORKOUT,
]


class HealthEngineError(Exception):
    """Raised when a health data request fails."""


async def request_permission(health: fh.Health) -> bool:
    """Requests read-only access to steps/calories/workouts. Returns True if
    the permission prompt was shown without error. Per request_authorization's
    own docstring: on iOS, HealthKit's privacy model means this can't
    actually confirm the user granted access, only that they were asked --
    so a True return doesn't guarantee data will come back on the next read."""
    try:
        return await health.request_authorization_async(types=READ_TYPES)
    except Exception as exc:
        raise HealthEngineError(f"Couldn't request Health access: {exc}") from exc


async def get_today_summary(health: fh.Health) -> dict:
    """Fetches today's steps and calories burned so far.

    Returns {"steps": int|None, "active_calories": float|None, "total_calories": float|None}.

    Uses get_total_steps_in_interval_async for steps -- a dedicated call
    with a guaranteed plain-int return, per its source. Calories go through
    get_health_aggregate_data_from_types_async, whose per-item dict shape
    isn't pinned down in flet-health's docs (its own README never shows a
    parsed example) -- _sum_for_type() below parses it defensively rather
    than assuming a shape, and should be simplified once the real shape is
    confirmed against a live device run.
    """
    now = datetime.now()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

    try:
        steps = await health.get_total_steps_in_interval_async(start_of_day, now)
    except Exception as exc:
        raise HealthEngineError(f"Couldn't read steps: {exc}") from exc

    try:
        aggregates = await health.get_health_aggregate_data_from_types_async(
            types=[fh.HealthDataTypeAndroid.ACTIVE_ENERGY_BURNED, fh.HealthDataTypeAndroid.TOTAL_CALORIES_BURNED],
            start_time=start_of_day,
            end_time=now,
        )
    except Exception as exc:
        raise HealthEngineError(f"Couldn't read calories: {exc}") from exc

    return {
        "steps": steps,
        "active_calories": _sum_for_type(aggregates, "ACTIVE_ENERGY_BURNED"),
        "total_calories": _sum_for_type(aggregates, "TOTAL_CALORIES_BURNED"),
    }


def _sum_for_type(aggregates: list, type_name: str) -> Optional[float]:
    """Sums the numeric value(s) for one data type out of an aggregate
    response, trying the shapes the underlying `health` Flutter package is
    known to use (a flat "value", or a nested "value"."numeric_value") and
    skipping anything unparseable rather than raising."""
    total = None
    for item in aggregates:
        if not isinstance(item, dict) or item.get("type") != type_name:
            continue
        raw_value = item.get("value")
        numeric = raw_value if isinstance(raw_value, (int, float)) else (
            raw_value.get("numeric_value") if isinstance(raw_value, dict) else None
        )
        if isinstance(numeric, (int, float)):
            total = (total or 0) + numeric
    return total
