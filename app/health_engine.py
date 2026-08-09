"""
Client-side wrapper around flet_health.Health() (Apple HealthKit / Google
Health Connect) -- styled like app/ai_engine.py. Read-only: Bite! never
writes health data back, it only displays what's already on the device.

flet_health.Health() is a non-visual control that must live in
page.overlay (see app/views/health_view.py, which creates and appends one
per view build) before any of its methods can be called.

Scope is "Activity basics" -- steps, walking/running distance, flights
climbed, active + total calories, and workouts. Deliberately not heart
rate, sleep, or any other vitals/body-measurement type: those are a more
sensitive HealthKit category, draw more App Review scrutiny per type
requested, and would need their own privacy-policy disclosure -- revisit
together if the app ever wants that data, don't just add a type here.
"""
import hashlib
import logging
from datetime import datetime
from typing import Optional

import flet_health as fh

logger = logging.getLogger(__name__)

# Every type below shares an identical name/value between
# HealthDataTypeAndroid and HealthDataTypeIOS (confirmed against
# flet-health's own example app) *except* distance -- Android's `health`
# plugin calls it DISTANCE_DELTA, iOS's calls it DISTANCE_WALKING_RUNNING --
# so HealthDataTypeAndroid's members are used unconditionally for
# everything else, and only distance needs the is_ios branch below.
_COMMON_READ_TYPES = [
    fh.HealthDataTypeAndroid.STEPS,
    fh.HealthDataTypeAndroid.ACTIVE_ENERGY_BURNED,
    fh.HealthDataTypeAndroid.TOTAL_CALORIES_BURNED,
    fh.HealthDataTypeAndroid.FLIGHTS_CLIMBED,
    fh.HealthDataTypeAndroid.WORKOUT,
]


def _distance_type(is_ios: bool):
    return fh.HealthDataTypeIOS.DISTANCE_WALKING_RUNNING if is_ios else fh.HealthDataTypeAndroid.DISTANCE_DELTA


def _distance_type_name(is_ios: bool) -> str:
    return "DISTANCE_WALKING_RUNNING" if is_ios else "DISTANCE_DELTA"


def read_types_for_platform(is_ios: bool) -> list:
    """The full read-scope list to pass to request_authorization_async, for
    whichever platform the caller is running on."""
    return _COMMON_READ_TYPES + [_distance_type(is_ios)]


class HealthEngineError(Exception):
    """Raised when a health data request fails."""


def get_health_control(page, state) -> fh.Health:
    """Returns a single shared fh.Health() control, creating it once and
    caching it on `state`. fh.Health() is non-visual and must live in
    page.overlay -- but page.overlay is global across the whole app, not
    scoped to whichever view created it, so appending a fresh one on every
    view build (home screen reruns this on every rerender, health screen on
    every visit) piles up duplicate controls in the same overlay Stack.
    Flutter renders one of the resulting duplicates as a broken gray
    placeholder instead of staying invisible -- reusing one instance for
    the app's whole session avoids that."""
    health = getattr(state, "_health_control", None)
    if health is None:
        health = fh.Health()
        page.overlay.append(health)
        state._health_control = health
    return health


async def request_permission(health: fh.Health, is_ios: bool) -> bool:
    """Requests read-only access to steps/distance/flights climbed/calories/
    workouts. Returns True if the permission prompt was shown without
    error. Per request_authorization's own docstring: on iOS, HealthKit's
    privacy model means this can't actually confirm the user granted
    access, only that they were asked -- so a True return doesn't guarantee
    data will come back on the next read."""
    try:
        return await health.request_authorization_async(types=read_types_for_platform(is_ios))
    except Exception as exc:
        raise HealthEngineError(f"Couldn't request Health access: {exc}") from exc


async def get_today_summary(health: fh.Health, is_ios: bool) -> dict:
    """Fetches today's activity so far.

    Returns {"steps": int|None, "active_calories": float|None,
    "total_calories": float|None, "distance_m": float|None,
    "flights_climbed": float|None}.

    Uses get_total_steps_in_interval_async for steps -- a dedicated call
    with a guaranteed plain-int return, per its source. Everything else goes
    through get_health_data_from_types_async (raw samples) and gets summed
    here by _sum_for_type() -- NOT get_health_aggregate_data_from_types_async,
    which sounds like the right call but isn't implemented on iOS at all:
    checked against the underlying `health` Flutter plugin's own Swift
    source (SwiftHealthPlugin.swift's `handle()` has no case for
    "getAggregateData", only Android's Kotlin side does), so it was always
    silently coming back empty on iOS regardless of what's authorized.
    distance_m is always in meters regardless of platform -- convert to
    km/mi at the display layer (see health_view.py), not here.
    """
    now = datetime.now()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

    try:
        steps = await health.get_total_steps_in_interval_async(start_of_day, now)
    except Exception as exc:
        raise HealthEngineError(f"Couldn't read steps: {exc}") from exc

    samples = []
    for t in (
        fh.HealthDataTypeAndroid.ACTIVE_ENERGY_BURNED,
        fh.HealthDataTypeAndroid.TOTAL_CALORIES_BURNED,
        fh.HealthDataTypeAndroid.FLIGHTS_CLIMBED,
        _distance_type(is_ios),
    ):
        # Queried one type at a time so a single type failing (e.g. never
        # granted -- HealthKit's permission sheet lets the user toggle each
        # type individually, and an app can never re-prompt for a type once
        # the user has responded once; Settings -> Health -> Data Access &
        # Devices -> Bite! is the only way to change that afterwards) only
        # blanks out that one metric instead of the whole summary.
        try:
            result = await health.get_health_data_from_types_async(
                types=[t],
                start_time=start_of_day,
                end_time=now,
            )
            samples += result
            if not result:
                logger.info("No samples back for %s -- check Settings > Health > Data Access & Devices > Bite!.", t)
        except Exception as exc:
            logger.warning("Sample fetch failed for %s: %s", t, exc)

    return {
        "steps": steps,
        "active_calories": _sum_for_type(samples, "ACTIVE_ENERGY_BURNED"),
        "total_calories": _sum_for_type(samples, "TOTAL_CALORIES_BURNED"),
        "flights_climbed": _sum_for_type(samples, "FLIGHTS_CLIMBED"),
        "distance_m": _sum_for_type(samples, _distance_type_name(is_ios)),
    }


def _sum_for_type(samples: list, type_name: str) -> Optional[float]:
    """Sums the numericValue of every raw HealthDataPoint sample matching
    type_name. Shape confirmed against the `health` pub.dev package's own
    generated JSON serializer (health.g.dart's _$HealthDataPointToJson /
    _$NumericHealthValueToJson): {"type": "ACTIVE_ENERGY_BURNED", "value":
    {"numericValue": 123.4}, ...}."""
    total = None
    for item in samples:
        if not isinstance(item, dict) or item.get("type") != type_name:
            continue
        value = item.get("value")
        numeric = value.get("numericValue") if isinstance(value, dict) else None
        if isinstance(numeric, (int, float)):
            total = (total or 0) + numeric
    return total


async def get_today_workouts(health: fh.Health, is_ios: bool) -> list[dict]:
    """Fetches today's raw workout samples (e.g. an Apple Watch workout)
    for import into workout_logs -- see database.import_health_workouts.

    Returns a list of {"name": str, "duration_minutes": int|None,
    "calories_burned": int|None, "external_id": str, "source": str}.
    Entries this couldn't confidently parse are skipped rather than
    raising, same defensive posture as _sum_for_type.
    """
    now = datetime.now()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    source = "apple_health" if is_ios else "health_connect"

    try:
        raw = await health.get_health_data_from_types_async(
            types=[fh.HealthDataTypeAndroid.WORKOUT],
            start_time=start_of_day,
            end_time=now,
        )
    except Exception as exc:
        raise HealthEngineError(f"Couldn't read workouts: {exc}") from exc

    workouts = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        parsed = _parse_workout(item, source)
        if parsed is None:
            logger.warning("Skipping unparsed workout sample: %r", item)
            continue
        workouts.append(parsed)
    return workouts


def _parse_iso(value) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    try:
        # dateFrom/dateTo come as Dart's DateTime.toIso8601String(), e.g.
        # "2026-08-08T14:32:00.000Z" -- Python's fromisoformat only started
        # accepting a bare "Z" suffix in 3.11, and the on-device interpreter
        # bundled by serious_python isn't guaranteed to be that new.
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_workout(item: dict, source: str) -> Optional[dict]:
    # Shape confirmed against the `health` pub.dev package's own generated
    # serializer (health.g.dart): {"uuid": ..., "type": "WORKOUT", "value":
    # {"workoutActivityType": "RUNNING", "totalEnergyBurned": 250, ...},
    # "dateFrom": "2026-08-08T...Z", "dateTo": "..."}.
    uuid = item.get("uuid")
    date_from = _parse_iso(item.get("dateFrom"))
    date_to = _parse_iso(item.get("dateTo"))

    value = item.get("value")
    value = value if isinstance(value, dict) else {}
    activity_type = value.get("workoutActivityType")
    calories = value.get("totalEnergyBurned")

    duration_minutes = None
    if date_from and date_to:
        duration_minutes = max(0, round((date_to - date_from).total_seconds() / 60))

    name = str(activity_type).replace("_", " ").title() if activity_type else "Workout"

    external_id = str(uuid) if uuid else None
    if external_id is None and date_from and date_to:
        # No uuid in this sample for some reason -- fall back to a stable
        # hash of start+end+type so re-syncing still dedupes instead of
        # re-importing the same workout every home screen load.
        external_id = hashlib.sha1(f"{date_from.isoformat()}:{date_to.isoformat()}:{name}".encode()).hexdigest()
    if external_id is None:
        return None

    return {
        "name": name,
        "duration_minutes": duration_minutes,
        "calories_burned": round(calories) if isinstance(calories, (int, float)) else None,
        "external_id": external_id,
        "source": source,
    }
