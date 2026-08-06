"""
Connect Health App: Profile section that requests read-only access to
Apple Health (iOS) / Health Connect (Android) and displays today's steps
and calories burned. See app/health_engine.py for the actual data calls.

Not available on web/desktop -- HealthKit/Health Connect only exist on
iOS/Android, so the whole screen renders a short explanation there instead
of a broken Connect button.
"""
import flet as ft
import flet_health as fh

from app import theme
from app.health_engine import HealthEngineError, get_today_summary, request_permission


def build_health_view(page: ft.Page, state) -> ft.View:
    supported = page.platform in (ft.PagePlatform.IOS, ft.PagePlatform.ANDROID)

    if not supported:
        body = ft.Column(
            [
                ft.Icon(ft.Icons.FAVORITE_BORDER_ROUNDED, color=theme.TEXT_FAINT, size=28),
                ft.Text(
                    "Connect Health App is only available in the iOS or Android app -- "
                    "Apple Health and Health Connect don't exist on this platform.",
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

    health = fh.Health()
    page.overlay.append(health)

    label = "Apple Health" if page.platform == ft.PagePlatform.IOS else "Health Connect"

    status_txt = ft.Text("", size=12, color=theme.TEXT_MUTED)
    summary_section = ft.Column(spacing=12)
    connect_button = theme.primary_button(f"Connect {label}", icon=ft.Icons.FAVORITE_ROUNDED)

    async def refresh_summary():
        try:
            summary = await get_today_summary(health)
        except HealthEngineError as exc:
            status_txt.value = f"Couldn't load data: {exc}"
            status_txt.color = theme.ERROR
            return

        tiles = []
        if summary["steps"] is not None:
            tiles.append(theme.macro_tile(f"{summary['steps']:,}", "steps", theme.ACCENT))
        if summary["active_calories"] is not None:
            tiles.append(theme.macro_tile(f"{summary['active_calories']:,.0f}", "active kcal", theme.PROTEIN))
        if summary["total_calories"] is not None:
            tiles.append(theme.macro_tile(f"{summary['total_calories']:,.0f}", "total kcal", theme.CARBS))

        summary_section.controls = [
            ft.Text("TODAY", size=11, color=theme.TEXT_FAINT, weight="w700"),
            ft.Row(tiles, spacing=8) if tiles else ft.Text(
                "No data yet -- log some activity in your Health app, then check back.",
                size=12, color=theme.TEXT_FAINT, italic=True,
            ),
        ]
        status_txt.value = ""

    async def on_connect(e):
        connect_button.disabled = True
        status_txt.value = "Requesting access..."
        status_txt.color = theme.TEXT_MUTED
        page.update()

        try:
            granted = await request_permission(health)
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
        f"Bite reads your steps, calories burned, and workouts from {label} to show "
        "them here. Read-only -- nothing is ever written back.",
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
