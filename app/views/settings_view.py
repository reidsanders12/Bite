"""Settings: dedicated to configuring daily macro and calorie tracking targets."""

import flet as ft

from app import theme
from app.models import UserGoals
from app.state import AppState


def build_settings_view(page: ft.Page, state: AppState) -> ft.View:
    goals = state.goals

    calories_field = ft.TextField(
        label="Daily calories", value=str(goals.daily_calories), **theme.styled_field()
    )
    protein_field = ft.TextField(
        label="Daily protein (g)", value=str(goals.daily_protein), **theme.styled_field()
    )
    carbs_field = ft.TextField(
        label="Daily carbs (g)", value=str(goals.daily_carbs), **theme.styled_field()
    )
    fat_field = ft.TextField(
        label="Daily fat (g)", value=str(goals.daily_fat), **theme.styled_field()
    )

    save_status = ft.Text("", color=theme.SUCCESS, size=12)

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
            save_status.color = theme.ERROR
            page.update()
            return

        state.db.save_goals(new_goals)
        state.refresh_goals()
        save_status.value = "Saved!"
        save_status.color = theme.SUCCESS
        page.update()

    return ft.View(
        route="/settings",
        bgcolor=theme.BG_CANVAS,
        controls=[
            theme.app_bar("Settings", on_back=lambda e: page.go("/")),
            ft.Container(
                content=ft.Column(
                    [
                        ft.Text("Daily Macro Targets", weight=ft.FontWeight.W_600, size=16, color=theme.TEXT_PRIMARY),
                        ft.Text(
                            "Configure your nutritional baselines here. These goals will automatically "
                            "feed context directly into your dashboard trackers and AI fitness coach calculations.",
                            size=12,
                            color=theme.TEXT_MUTED,
                        ),
                        ft.Divider(height=10, color=theme.BORDER),
                        calories_field,
                        protein_field,
                        carbs_field,
                        fat_field,
                        ft.Divider(height=10, color="transparent"),
                        theme.primary_button("Save Targets", icon=ft.Icons.SAVE, on_click=on_save),
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