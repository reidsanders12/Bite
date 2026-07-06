"""Home / dashboard view -- daily progress + the three logging entry points."""

import flet as ft

from app.state import AppState
from app.views.widgets import macro_ring


def build_home_view(page: ft.Page, state: AppState) -> ft.View:
    totals = state.db.get_totals_for_date()
    goals = state.goals

    rings = ft.Row(
        [
            macro_ring("Calories", totals["calories"], goals.daily_calories, ft.Colors.DEEP_ORANGE, unit=""),
            macro_ring("Protein", totals["protein"], goals.daily_protein, ft.Colors.BLUE),
            macro_ring("Carbs", totals["carbs"], goals.daily_carbs, ft.Colors.AMBER),
            macro_ring("Fat", totals["fat"], goals.daily_fat, ft.Colors.PURPLE),
        ],
        alignment=ft.MainAxisAlignment.SPACE_EVENLY,
    )

    def action_card(icon, title, subtitle, route, color):
        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        content=ft.Icon(icon, color=color, size=26),
                        bgcolor=ft.Colors.with_opacity(0.12, color),
                        border_radius=12,
                        padding=12,
                    ),
                    ft.Column(
                        [
                            ft.Text(title, weight=ft.FontWeight.W_600, size=15),
                            ft.Text(subtitle, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ft.Icon(ft.Icons.CHEVRON_RIGHT, color=ft.Colors.ON_SURFACE_VARIANT),
                ],
                spacing=14,
            ),
            padding=16,
            border_radius=16,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            on_click=lambda e: page.go(route),
            ink=True,
        )

    recent = state.db.get_logs_for_date()
    recent_list = (
        ft.Column(
            [
                ft.ListTile(
                    leading=ft.Icon(
                        {
                            "photo": ft.Icons.PHOTO_CAMERA,
                            "text": ft.Icons.EDIT_NOTE,
                            "barcode": ft.Icons.QR_CODE_SCANNER,
                        }.get(entry.source, ft.Icons.RESTAURANT),
                    ),
                    title=ft.Text(entry.meal_name),
                    subtitle=ft.Text(
                        f"{entry.calories} kcal • P{entry.protein} C{entry.carbs} F{entry.fat} • "
                        f"{entry.logged_at[11:16]}"
                    ),
                )
                for entry in recent[:5]
            ]
        )
        if recent
        else ft.Container(
            content=ft.Text(
                "No meals logged yet today. Snap a photo to get started!",
                color=ft.Colors.ON_SURFACE_VARIANT,
                italic=True,
            ),
            padding=16,
        )
    )

    return ft.View(
        route="/",
        controls=[
            ft.AppBar(
                title=ft.Text("Macro Tracker", weight=ft.FontWeight.BOLD),
                center_title=False,
                bgcolor=ft.Colors.SURFACE,
                actions=[
                    ft.IconButton(ft.Icons.SETTINGS_OUTLINED, on_click=lambda e: page.go("/settings")),
                ],
            ),
            ft.Container(
                content=ft.Column(
                    [
                        ft.Text("Today", size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                        rings,
                        ft.Container(height=8),
                        action_card(
                            ft.Icons.PHOTO_CAMERA,
                            "Snap & Log",
                            "Take a photo, AI estimates macros instantly",
                            "/snap",
                            ft.Colors.DEEP_ORANGE,
                        ),
                        action_card(
                            ft.Icons.EDIT_NOTE,
                            "Describe a Meal",
                            'e.g. "100g oats, a scoop of whey"',
                            "/text-log",
                            ft.Colors.BLUE,
                        ),
                        action_card(
                            ft.Icons.QR_CODE_SCANNER,
                            "Barcode / Ingredient Lookup",
                            "Free databases: Open Food Facts, USDA",
                            "/lookup",
                            ft.Colors.TEAL,
                        ),
                        ft.Container(height=8),
                        ft.Row(
                            [
                                ft.Text("Today's Log", weight=ft.FontWeight.W_600),
                                ft.TextButton("Full history", on_click=lambda e: page.go("/history")),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        recent_list,
                    ],
                    spacing=14,
                    scroll=ft.ScrollMode.AUTO,
                ),
                padding=20,
                expand=True,
            ),
        ],
    )
