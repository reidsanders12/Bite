"""
Main Home Dashboard View.
Displays daily macro progress and provides navigation shortcuts for logging,
lookup, and profile-contained preferences management.
"""

import flet as ft
from app.state import AppState


def build_home_view(page: ft.Page, state: AppState) -> ft.View:
    # 1. Force state to fetch the absolute latest records from the DB right now
    if hasattr(state, "refresh_logs"):
        state.refresh_logs()

    daily_logs = []
    if hasattr(state, "get_daily_logs"):
        daily_logs = state.get_daily_logs()
    elif hasattr(state, "logs"):
        daily_logs = state.logs

    goals = None
    if hasattr(state, "get_goals"):
        goals = state.get_goals()
    elif hasattr(state, "goals"):
        goals = state.goals

    # 2. Extract values defensively supporting both Class Objects and Dictionaries
    consumed_cal = 0
    consumed_protein = 0
    consumed_carbs = 0
    consumed_fat = 0

    for log in (daily_logs or []):
        try:
            # Try parsing as an object attribute first, fallback to dictionary key lookup
            c = getattr(log, "calories", None) if not isinstance(log, dict) else log.get("calories")
            p = getattr(log, "protein", None) if not isinstance(log, dict) else log.get("protein")
            ch = getattr(log, "carbs", None) if not isinstance(log, dict) else log.get("carbs")
            f = getattr(log, "fat", None) if not isinstance(log, dict) else log.get("fat")

            # Force parse values to integers to handle numeric string records safely
            consumed_cal += int(c or 0)
            consumed_protein += int(p or 0)
            consumed_carbs += int(ch or 0)
            consumed_fat += int(f or 0)
        except Exception:
            pass # Skip corrupted rows cleanly

    # Parse target metrics defensively
    target_cal = int(getattr(goals, "daily_calories", 2000) if not isinstance(goals, dict) else goals.get("daily_calories", 2000))
    target_protein = int(getattr(goals, "daily_protein", 150) if not isinstance(goals, dict) else goals.get("daily_protein", 150))
    target_carbs = int(getattr(goals, "daily_carbs", 200) if not isinstance(goals, dict) else goals.get("daily_carbs", 200))
    target_fat = int(getattr(goals, "daily_fat", 65) if not isinstance(goals, dict) else goals.get("daily_fat", 65))

    # Calculate current visual progress percentage
    cal_progress = min(1.0, consumed_cal / max(1, target_cal))

    # Action Shortcuts Buttons
    logging_shortcuts = ft.Row([
        ft.ElevatedButton(
            text="Scan Barcode",
            icon=getattr(ft.Icons, "BARCODE_READER", getattr(ft.Icons, "UPC_SCAN", ft.Icons.CAMERA)),
            style=ft.ButtonStyle(bgcolor="#222A35", color=ft.Colors.WHITE),
            on_click=lambda e: page.go("/lookup"),
            expand=True
        ),
        ft.ElevatedButton(
            text="Snap Meal",
            icon=ft.Icons.CAMERA_ALT,
            style=ft.ButtonStyle(bgcolor="#00E5FF", color="#181D26"),
            on_click=lambda e: page.go("/snap"),
            expand=True
        )
    ], spacing=10)

    # Progress Ring UI Card Component Block
    progress_rings = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Text("Daily Progress", weight="bold", size=16),
                ft.Text(f"{consumed_cal} / {target_cal} kcal", color="#00E5FF", weight="semibold")
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.ProgressBar(value=cal_progress, color="#00E5FF", bgcolor="#222A35", height=10),
            ft.Row([
                _macro_indicator("Protein", consumed_protein, target_protein, "#FF5252"),
                _macro_indicator("Carbs", consumed_carbs, target_carbs, "#4CAF50"),
                _macro_indicator("Fat", consumed_fat, target_fat, "#FFC107"),
            ], alignment=ft.MainAxisAlignment.SPACE_AROUND)
        ], spacing=14),
        padding=16,
        border_radius=12,
        bgcolor="#181D26"
    )

    return ft.View(
        route="/",
        controls=[
            ft.AppBar(
                title=ft.Text("Bite Tracker", weight="bold"),
                leading=ft.IconButton(
                    content=ft.Icon(ft.Icons.ACCOUNT_CIRCLE, color="#00E5FF"),
                    on_click=lambda e: page.go("/profile")
                ),
                actions=[
                    ft.IconButton(
                        content=ft.Icon(ft.Icons.HISTORY),
                        on_click=lambda e: page.go("/history")
                    )
                ],
                bgcolor="#181D26"
            ),
            ft.Container(
                content=ft.Column([
                    logging_shortcuts,
                    progress_rings,
                    ft.Divider(color="#222A35"),
                    ft.Text("Today's Timeline", weight="semibold", size=14),
                    ft.Column(
                        controls=[
                            ft.Text("No items logged yet today.", size=12, color="#7A8B9E")
                        ] if not daily_logs else [
                            ft.ListTile(
                                title=ft.Text(
                                    getattr(log, "meal_name", "Logged Food") if not isinstance(log, dict) else log.get("meal_name", "Logged Food")
                                ),
                                subtitle=ft.Text(
                                    f"{getattr(log, 'calories', 0) if not isinstance(log, dict) else log.get('calories', 0)} kcal • "
                                    f"P{getattr(log, 'protein', 0) if not isinstance(log, dict) else log.get('protein', 0)}g "
                                    f"C{getattr(log, 'carbs', 0) if not isinstance(log, dict) else log.get('carbs', 0)}g "
                                    f"F{getattr(log, 'fat', 0) if not isinstance(log, dict) else log.get('fat', 0)}g"
                                )
                            ) for log in daily_logs
                        ]
                    )
                ], spacing=18, scroll=ft.ScrollMode.AUTO),
                padding=20,
                expand=True
            )
        ]
    )


def _macro_indicator(label: str, current: float, target: float, color: str) -> ft.Control:
    percentage = current / max(1, target)
    return ft.Column([
        ft.Text(label, size=11, color="#7A8B9E"),
        ft.Container(
            content=ft.Text(f"{int(current)}g", size=12, weight="bold"),
            padding=4
        ),
        ft.Container(
            width=50,
            height=4,
            bgcolor="#222A35",
            border_radius=2,
            content=ft.Row([
                ft.Container(width=max(2, 50 * min(1.0, percentage)), height=4, bgcolor=color, border_radius=2)
            ])
        ),
        ft.Text(f"of {int(target)}g", size=10, color="#506173")
    ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER)