"""
Main Home Dashboard View - Modern Minimalist Edition.
"""
import flet as ft
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
                ft.Icon(ft.Icons.SUBTITLES_OUTLINED, size=15), 
                ft.Text("Text Log", size=12, weight="w600")
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=6),
            bgcolor="#141923", 
            border=ft.border.all(1, "#222C3F"), 
            border_radius=24, 
            padding=ft.padding.symmetric(12, 10),
            on_click=lambda _: page.go("/text_log"), 
            expand=True
        ),
        ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.SEARCH_ROUNDED, size=15), 
                ft.Text("Lookup", size=12, weight="w600")
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=6),
            bgcolor="#141923", 
            border=ft.border.all(1, "#222C3F"), 
            border_radius=24, 
            padding=ft.padding.symmetric(12, 10),
            on_click=lambda _: page.go("/lookup"), 
            expand=True
        ),
        ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.CAMERA_ALT_OUTLINED, size=15, color="#0A0E17"), 
                ft.Text("Snap", size=12, weight="bold", color="#0A0E17")
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=6),
            bgcolor="#00E5FF", 
            border_radius=24, 
            padding=ft.padding.symmetric(12, 10),
            on_click=lambda _: page.go("/snap"), 
            expand=True
        )
    ], spacing=10)

    # Clean Glassmorphic Progress Overview Box
    progress_card = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Column([
                    ft.Text("ENERGY CONSUMED", size=11, color="#7A8B9E", weight="w700"),
                    ft.Text(f"{consumed_cal} kcal", size=32, weight="bold"),
                ]),
                ft.Container(
                    content=ft.Text(f"Target: {target_cal}", size=11, color="#00E5FF", weight="w600"),
                    bgcolor="#0A2F35", border_radius=8, padding=ft.padding.symmetric(6, 10)
                )
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.END),
            ft.ProgressBar(value=cal_progress, color="#00E5FF", bgcolor="#141923", height=6),
            ft.Divider(color="#1C2431", height=10),
            ft.Row([
                _modern_macro("PROTEIN", consumed_pro, target_pro, "#FF5252"),
                _modern_macro("CARBS", consumed_carb, target_carb, "#4CAF50"),
                _modern_macro("FAT", consumed_fat, target_fat, "#FFC107"),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        ], spacing=16),
        padding=24, border_radius=20, bgcolor="#0A0E17", border=ft.border.all(1, "#1C2431")
    )

    # Clean Timeline Build List
    timeline_items = ft.Column(spacing=10)
    if not daily_logs:
        timeline_items.controls.append(
            ft.Container(
                content=ft.Text("No entries recorded for today.", color="#506173", size=13, italic=True),
                padding=10
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
                            ft.Text(name, size=14, weight="w600"),
                            ft.Text(f"P {p}g   C {ch}g   F {f}g", size=11, color="#7A8B9E")
                        ], expand=True),
                        ft.Text(f"+{c} kcal", size=14, weight="bold", color="#00E5FF")
                    ]),
                    padding=16, border_radius=14, bgcolor="#0A0E17", border=ft.border.all(1, "#141923")
                )
            )

    return ft.View(
        route="/",
        bgcolor="#06090F", # Absolute Midnight Background
        controls=[
            ft.AppBar(
                title=ft.Text("Bite Profile", size=18, weight="bold"),
                leading=ft.IconButton(icon=ft.Icons.ACCOUNT_CIRCLE_OUTLINED, icon_color="#7A8B9E", on_click=lambda _: page.go("/profile")),
                actions=[ft.IconButton(icon=ft.Icons.TUNE_ROUNDED, icon_color="#7A8B9E", on_click=lambda _: page.go("/history"))],                
                bgcolor="#06090F", elevation=0
            ),
            ft.Container(
                content=ft.Column([
                    progress_card,
                    ft.Divider(color="transparent", height=10),
                    logging_shortcuts,
                    ft.Divider(color="transparent", height=10),
                    ft.Text("TODAY'S LINEUP", size=11, color="#506173", weight="w700"),
                    timeline_items
                ], spacing=12, scroll=ft.ScrollMode.AUTO),
                padding=20, expand=True
            )
        ]
    )

def _modern_macro(label: str, cur: int, tgt: int, accent_color: str) -> ft.Control:
    return ft.Column([
        ft.Text(label, size=10, color="#506173", weight="bold"),
        ft.Text(f"{cur}/{tgt}g", size=13, weight="w600"),
        ft.Container(width=40, height=3, bgcolor="#141923", border_radius=2, 
                     content=ft.Row([ft.Container(width=min(40, 40*(cur/max(1,tgt))), height=3, bgcolor=accent_color)]))
    ], spacing=4)