"""
Connect Health App: Profile section that requests read-only access to
Apple Health (iOS) / Health Connect (Android) and displays today's steps
and calories burned. See app/health_engine.py for the actual data calls.

Not available on web/desktop -- HealthKit/Health Connect only exist on
iOS/Android, so the whole screen renders a short explanation there instead
of a broken Connect button.
"""
import flet as ft

from app import theme
from app.health_engine import (
    HEALTH_AVAILABLE,
    HealthEngineError,
    get_health_control,
    get_today_summary,
    get_today_workouts,
    request_permission,
)


def build_health_view(page: ft.Page, state) -> ft.View:
    supported = HEALTH_AVAILABLE and page.platform in (ft.PagePlatform.IOS, ft.PagePlatform.ANDROID)

    if not supported:
        message = (
            "Connect Health App isn't available in this build."
            if not HEALTH_AVAILABLE else
            "Connect Health App is only available in the iOS or Android app -- "
            "Apple Health and Health Connect don't exist on this platform."
        )
        body = ft.Column(
            [
                ft.Icon(ft.Icons.FAVORITE_BORDER_ROUNDED, color=theme.TEXT_FAINT, size=28),
                ft.Text(
                    message,
                    size=13, color=theme.TEXT_FAINT, text_align=ft.TextAlign.CENTER,
                ),
            ],
            spacing=10, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
        return ft.View(
            route="/health",
            bgcolor=theme.BG_CANVAS,
            controls=[
                theme.app_bar("Connect Health App", on_back=lambda e: page.go("/profile")),
                ft.Container(content=body, padding=40, alignment=ft.alignment.center, expand=True),
            ],
        )

    health = get_health_control(page, state)

    is_ios = page.platform == ft.PagePlatform.IOS
    label = "Apple Health" if is_ios else "Health Connect"
    # Distance is stored in meters regardless of platform (see
    # health_engine.py) -- displayed in miles for an iOS device (matches
    # Apple's own Activity/Fitness app units) and km everywhere else.
    METERS_PER_MILE = 1609.344

    status_txt = ft.Text("", size=12, color=theme.TEXT_MUTED)
    summary_section = ft.Column(spacing=12)
    connect_button = theme.primary_button(f"Connect {label}", icon=ft.Icons.FAVORITE_ROUNDED)

    async def refresh_summary(silent: bool = False) -> bool:
        """Loads today's summary + syncs workouts. Returns True only if any
        real data came back (meaning access was already granted on a past
        visit) -- NOT just "the calls didn't raise", since HealthKit returns
        empty/None for unauthorized types rather than an error (Apple's
        privacy model hides *why* a read came back empty), so an
        unauthorized first-ever visit looks identical to a successful-but-
        quiet one unless tiles is actually checked. Getting this wrong
        previously hid the Connect button on literally every visit,
        including the very first, before the user ever got a chance to
        grant access. silent=True suppresses the error status text -- used
        for the on-open auto-check below, so a first-ever visit (nothing
        granted yet) fails quietly instead of greeting the user with a red
        error message before they've even tapped Connect."""
        try:
            summary = await get_today_summary(health, is_ios)
        except HealthEngineError as exc:
            if not silent:
                status_txt.value = f"Couldn't load data: {exc}"
                status_txt.color = theme.ERROR
            return False

        tiles = []
        if summary["steps"] is not None:
            tiles.append(theme.macro_tile(f"{summary['steps']:,}", "steps", theme.ACCENT))
        if summary["distance_m"] is not None:
            if is_ios:
                dist_value = f"{summary['distance_m'] / METERS_PER_MILE:,.1f}mi"
            else:
                dist_value = f"{summary['distance_m'] / 1000:,.1f}km"
            tiles.append(theme.macro_tile(dist_value, "distance", theme.SUCCESS))
        if summary["flights_climbed"] is not None:
            tiles.append(theme.macro_tile(f"{summary['flights_climbed']:,.0f}", "floors", theme.FAT))
        if summary["active_calories"] is not None:
            tiles.append(theme.macro_tile(f"{summary['active_calories']:,.0f}", "active kcal", theme.PROTEIN))
        if summary["total_calories"] is not None:
            tiles.append(theme.macro_tile(f"{summary['total_calories']:,.0f}", "total kcal", theme.CARBS))

        summary_section.controls = [
            ft.Text("TODAY", size=11, color=theme.TEXT_FAINT, weight="w700"),
            # No wrap=True here -- macro_tile() sets expand=True on every
            # tile (wraps it in Flutter's Expanded), and Expanded is only
            # legal as a direct child of a Flex (Row/Column); wrap=True
            # turns this Row into a Wrap, which isn't one, so it threw a
            # layout error that rendered as a blank gray box instead of the
            # tiles. Every other macro_tile() row in the app (e.g.
            # meal_feed_view.py) already omits wrap for the same reason.
            ft.Row(tiles, spacing=8) if tiles else ft.Text(
                "No data came back for today. If you already have Health data, this "
                "usually means access wasn't actually granted for these types -- check "
                "Settings > Health > Data Access & Devices > Bite! and make sure Steps, "
                "Active Energy, Total (Resting) Energy, Flights Climbed, Walking + "
                "Running Distance, and Workouts are all toggled on (iOS lets you deny "
                "individual types in the permission sheet, and the app can't tell which "
                "ones were denied or re-ask once you've responded once).",
                size=12, color=theme.TEXT_FAINT, italic=True,
            ),
        ]

        # Also pulls today's workouts (e.g. an Apple Watch workout) into
        # workout_logs -- same import state.sync_health_workouts drives
        # from the home screen, surfaced here since this screen is where
        # the user is actively looking at Health data. Failure here
        # shouldn't blank out the tiles above, so it's a separate
        # try/except rather than folded into the block above.
        try:
            workouts = await get_today_workouts(health, is_ios)
            added = state.sync_health_workouts(workouts)
        except HealthEngineError:
            added = 0
        status_txt.color = theme.TEXT_MUTED
        status_txt.value = f"Synced {added} workout{'s' if added != 1 else ''} from {label}." if added else ""
        return bool(tiles)

    async def _load_if_already_connected():
        # Runs once on every visit to this screen, before the user touches
        # anything. If access was already granted on a previous visit, this
        # loads the data straight away and hides the Connect button --
        # otherwise HealthKit auth doesn't persist across app.py's view
        # rebuilds the way state.py's own caches do, since every visit to
        # /health starts a brand new view with a fresh, unconnected-looking
        # default state even though the OS-level permission is still valid.
        if await refresh_summary(silent=True):
            connect_button.visible = False
            page.update()

    page.run_task(_load_if_already_connected)

    async def on_connect(e):
        connect_button.disabled = True
        status_txt.value = "Requesting access..."
        status_txt.color = theme.TEXT_MUTED
        page.update()

        try:
            granted = await request_permission(health, is_ios)
        except HealthEngineError as exc:
            status_txt.value = f"Couldn't request access: {exc}"
            status_txt.color = theme.ERROR
            connect_button.disabled = False
            page.update()
            return

        if not granted:
            status_txt.value = "Permission wasn't granted."
            status_txt.color = theme.ERROR
            connect_button.disabled = False
            page.update()
            return

        connect_button.visible = False
        await refresh_summary()
        page.update()

    connect_button.on_click = lambda e: page.run_task(on_connect, e)

    explanation = ft.Text(
        f"Bite! reads your steps, distance, flights climbed, calories burned, and "
        f"workouts from {label} to show them here. Read-only -- nothing is ever "
        "written back.",
        size=12, color=theme.TEXT_MUTED,
    )

    return ft.View(
        route="/health",
        bgcolor=theme.BG_CANVAS,
        controls=[
            theme.app_bar("Connect Health App", on_back=lambda e: page.go("/profile")),
            ft.Container(
                content=ft.Column(
                    [explanation, connect_button, status_txt, summary_section],
                    spacing=16, scroll=ft.ScrollMode.HIDDEN,
                ),
                padding=20, expand=True,
            ),
        ],
    )
