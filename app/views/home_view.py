"""
Main Home Dashboard View - Modern Minimalist Edition.
"""
import flet as ft
from app import theme
from app.state import AppState

def build_home_view(page: ft.Page, state: AppState) -> ft.View:
    if hasattr(state, "refresh_logs"):
        state.refresh_logs()

    daily_logs = state.get_daily_logs() if hasattr(state, "get_daily_logs") else getattr(state, "logs", [])
    goals = state.get_goals() if hasattr(state, "get_goals") else getattr(state, "goals", None)

    # Defensively compute macros
    consumed_cal, consumed_pro, consumed_carb, consumed_fat = 0, 0, 0, 0
    for log in (daily_logs or []):
        try:
            consumed_cal += int(log.get("calories", 0) if isinstance(log, dict) else getattr(log, "calories", 0))
            consumed_pro += int(log.get("protein", 0) if isinstance(log, dict) else getattr(log, "protein", 0))
            consumed_carb += int(log.get("carbs", 0) if isinstance(log, dict) else getattr(log, "carbs", 0))
            consumed_fat += int(log.get("fat", 0) if isinstance(log, dict) else getattr(log, "fat", 0))
        except: pass

    target_cal = int(getattr(goals, "daily_calories", 2000) if not isinstance(goals, dict) else goals.get("daily_calories", 2000))
    target_pro = int(getattr(goals, "daily_protein", 150) if not isinstance(goals, dict) else goals.get("daily_protein", 150))
    target_carb = int(getattr(goals, "daily_carbs", 200) if not isinstance(goals, dict) else goals.get("daily_carbs", 200))
    target_fat = int(getattr(goals, "daily_fat", 65) if not isinstance(goals, dict) else goals.get("daily_fat", 65))

    cal_progress = min(1.0, consumed_cal / max(1, target_cal))

    # --- NEW MODERN UI ELEMENTS ---
    
    # Sleek Pill-Shaped Action Controls - Three Column Layout
    logging_shortcuts = ft.Row([
        ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.SUBTITLES_OUTLINED, size=15, color=theme.TEXT_PRIMARY),
                ft.Text("Text Log", size=12, weight="w600")
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=6),
            bgcolor=theme.BG_SURFACE_ALT,
            border=ft.border.all(1, theme.BORDER),
            border_radius=24,
            padding=ft.padding.symmetric(12, 10),
            on_click=lambda _: page.go("/text_log"),
            expand=True
        ),
        ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.SEARCH_ROUNDED, size=15, color=theme.TEXT_PRIMARY),
                ft.Text("Lookup", size=12, weight="w600")
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=6),
            bgcolor=theme.BG_SURFACE_ALT,
            border=ft.border.all(1, theme.BORDER),
            border_radius=24,
            padding=ft.padding.symmetric(12, 10),
            on_click=lambda _: page.go("/lookup"),
            expand=True
        ),
        ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.CAMERA_ALT_OUTLINED, size=15, color=theme.ACCENT_ON),
                ft.Text("Snap", size=12, weight="bold", color=theme.ACCENT_ON)
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=6),
            bgcolor=theme.ACCENT,
            border_radius=24,
            padding=ft.padding.symmetric(12, 10),
            on_click=lambda _: page.go("/snap"),
            expand=True
        )
    ], spacing=10)

    # Progress Overview Box: calorie ring gauge + macro meters
    remaining_cal = max(0, target_cal - consumed_cal)
    calorie_ring = ft.Stack(
        [
            ft.ProgressRing(
                value=cal_progress, width=132, height=132, stroke_width=12,
                color=theme.ACCENT, bgcolor=theme.BG_SURFACE_ALT, stroke_cap=ft.StrokeCap.ROUND,
            ),
            ft.Container(
                content=ft.Column(
                    [
                        ft.Text(f"{remaining_cal:,}", size=26, weight="bold", color=theme.TEXT_PRIMARY),
                        ft.Text("Remaining", size=11, color=theme.TEXT_MUTED),
                    ],
                    spacing=0,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                width=132, height=132, alignment=ft.alignment.center,
            ),
        ],
        width=132, height=132,
    )

    calorie_breakdown = ft.Column(
        [
            ft.Row(
                [ft.Icon(ft.Icons.FLAG_OUTLINED, size=16, color=theme.TEXT_MUTED),
                 ft.Text("Goal", size=13, color=theme.TEXT_MUTED, expand=True),
                 ft.Text(f"{target_cal:,}", size=13, weight="w600", color=theme.TEXT_PRIMARY)],
                spacing=8,
            ),
            ft.Row(
                [ft.Icon(ft.Icons.RESTAURANT_OUTLINED, size=16, color=theme.TEXT_MUTED),
                 ft.Text("Food", size=13, color=theme.TEXT_MUTED, expand=True),
                 ft.Text(f"{consumed_cal:,}", size=13, weight="w600", color=theme.TEXT_PRIMARY)],
                spacing=8,
            ),
        ],
        spacing=12,
        width=150,
    )

    progress_card = ft.Container(
        content=ft.Column([
            ft.Text("Calories", size=17, weight="bold", color=theme.TEXT_PRIMARY),
            ft.Text("Remaining = Goal − Food", size=12, color=theme.TEXT_FAINT),
            ft.Row(
                [calorie_ring, calorie_breakdown],
                alignment=ft.MainAxisAlignment.SPACE_AROUND,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Divider(color=theme.BORDER, height=1),
            ft.Row([
                _modern_macro("PROTEIN", consumed_pro, target_pro, theme.PROTEIN),
                _modern_macro("CARBS", consumed_carb, target_carb, theme.CARBS),
                _modern_macro("FAT", consumed_fat, target_fat, theme.FAT),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        ], spacing=18),
        padding=26, border_radius=theme.RADIUS_LG, bgcolor=theme.BG_SURFACE,
        border=ft.border.all(1, theme.BORDER), shadow=theme.CARD_SHADOW,
    )

    # Timeline Build List
    timeline_items = ft.Column(spacing=12)
    if not daily_logs:
        timeline_items.controls.append(
            ft.Container(
                content=ft.Column(
                    [
                        ft.Icon(ft.Icons.RESTAURANT_ROUNDED, color=theme.TEXT_FAINT, size=28),
                        ft.Text("No entries recorded for today.", color=theme.TEXT_FAINT, size=13, italic=True),
                    ],
                    spacing=10,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=28,
                alignment=ft.alignment.center,
            )
        )
    else:
        for log in daily_logs:
            name = log.get("meal_name", "Logged Food") if isinstance(log, dict) else getattr(log, "meal_name", "Logged Food")
            c = log.get("calories", 0) if isinstance(log, dict) else getattr(log, "calories", 0)
            p = log.get("protein", 0) if isinstance(log, dict) else getattr(log, "protein", 0)
            ch = log.get("carbs", 0) if isinstance(log, dict) else getattr(log, "carbs", 0)
            f = log.get("fat", 0) if isinstance(log, dict) else getattr(log, "fat", 0)

            timeline_items.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Column([
                            ft.Text(name, size=15, weight="w600"),
                            ft.Row(
                                [
                                    _macro_chip("P", p, theme.PROTEIN),
                                    _macro_chip("C", ch, theme.CARBS),
                                    _macro_chip("F", f, theme.FAT),
                                ],
                                spacing=10,
                            ),
                        ], expand=True, spacing=6),
                        ft.Text(f"+{c:,}", size=16, weight="bold", color=theme.ACCENT)
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=18, border_radius=theme.RADIUS_MD, bgcolor=theme.BG_SURFACE,
                    border=ft.border.all(1, theme.BORDER), shadow=theme.CARD_SHADOW,
                )
            )

    return ft.View(
        route="/",
        bgcolor=theme.BG_CANVAS,
        controls=[
            ft.AppBar(
                title=ft.Text("Bite Profile", size=18, weight="bold"),
                leading=ft.IconButton(icon=ft.Icons.ACCOUNT_CIRCLE_OUTLINED, icon_color=theme.TEXT_MUTED, on_click=lambda _: page.go("/profile")),
                actions=[ft.IconButton(icon=ft.Icons.TUNE_ROUNDED, icon_color=theme.TEXT_MUTED, on_click=lambda _: page.go("/history"))],
                bgcolor=theme.BG_CANVAS, elevation=0
            ),
            ft.Container(
                content=ft.Column([
                    progress_card,
                    ft.Divider(color="transparent", height=4),
                    logging_shortcuts,
                    ft.Divider(color="transparent", height=4),
                    ft.Text("TODAY'S LINEUP", size=11, color=theme.TEXT_FAINT, weight="w700"),
                    timeline_items
                ], spacing=18, scroll=ft.ScrollMode.AUTO),
                padding=ft.padding.symmetric(20, 24), expand=True
            )
        ]
    )

def _modern_macro(label: str, cur: int, tgt: int, accent_color: str) -> ft.Control:
    return ft.Column([
        ft.Text(label, size=10, color=theme.TEXT_FAINT, weight="bold"),
        ft.Text(f"{cur}g", size=15, weight="bold"),
        ft.Text(f"of {tgt}g", size=10, color=theme.TEXT_MUTED),
        ft.ProgressBar(
            value=min(1.0, cur / max(1, tgt)), width=76, height=6,
            color=accent_color, bgcolor=ft.Colors.with_opacity(0.15, accent_color),
            border_radius=3,
        ),
    ], spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER)


def _macro_chip(letter: str, grams: int, color: str) -> ft.Control:
    return ft.Row(
        [
            ft.Container(width=8, height=8, border_radius=4, bgcolor=color),
            ft.Text(f"{letter} {grams}g", size=11, color=theme.TEXT_MUTED),
        ],
        spacing=5,
    )