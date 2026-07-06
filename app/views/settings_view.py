"""Settings: dedicated to configuring daily macro and calorie tracking targets."""

import flet as ft

from app.models import UserGoals
from app.state import AppState


def build_settings_view(page: ft.Page, state: AppState) -> ft.View:
    goals = state.goals

    calories_field = ft.TextField(label="Daily calories", value=str(goals.daily_calories), border_radius=10)
    protein_field = ft.TextField(label="Daily protein (g)", value=str(goals.daily_protein), border_radius=10)
    carbs_field = ft.TextField(label="Daily carbs (g)", value=str(goals.daily_carbs), border_radius=10)
    fat_field = ft.TextField(label="Daily fat (g)", value=str(goals.daily_fat), border_radius=10)

    save_status = ft.Text("", color=ft.Colors.GREEN, size=12)

    def on_save(e):
        try:
            new_goals = UserGoals(
                daily_calories=int(calories_field.value or 0),
                daily_protein=int(protein_field.value or 0),
                daily_carbs=int(carbs_field.value or 0),
                daily_fat=int(fat_field.value or 0),
            )
        except ValueError:
            save_status.value = "Goals must be whole numbers."
            save_status.color = ft.Colors.ERROR
            page.update()
            return

        state.db.save_goals(new_goals)
        state.refresh_goals()
        save_status.value = "Saved!"
        save_status.color = ft.Colors.GREEN
        page.update()

    return ft.View(
        route="/settings",
        controls=[
            ft.AppBar(
                title=ft.Text("Settings"),
                leading=ft.IconButton(
                    icon=ft.Icons.ARROW_BACK, 
                    on_click=lambda e: page.go("/")
                ),
            ),
            ft.Container(
                content=ft.Column(
                    [
                        ft.Text("Daily Macro Targets", weight=ft.FontWeight.W_600, size=16),
                        ft.Text(
                            "Configure your nutritional baselines here. These goals will automatically "
                            "feed context directly into your dashboard trackers and AI fitness coach calculations.",
                            size=12,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Divider(height=10),
                        calories_field,
                        protein_field,
                        carbs_field,
                        fat_field,
                        ft.Divider(height=10),
                        ft.FilledButton(
                            text="Save Targets", 
                            icon=ft.Icons.SAVE, 
                            on_click=on_save
                        ),
                        save_status,
                    ],
                    spacing=14,
                    scroll=ft.ScrollMode.AUTO,
                ),
                padding=20,
                expand=True,
            ),
        ],
    )