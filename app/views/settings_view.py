"""Settings: bring-your-own free-tier API keys + personal daily macro goals."""

import flet as ft

from app import config
from app.models import UserGoals
from app.state import AppState


def build_settings_view(page: ft.Page, state: AppState) -> ft.View:
    goals = state.goals

    gemini_key_field = ft.TextField(
        label="Gemini API key",
        value=config.get_saved_key("GEMINI_API_KEY"),
        password=True,
        can_reveal_password=True,
        hint_text="Get a free key at aistudio.google.com",
        border_radius=10,
    )
    usda_key_field = ft.TextField(
        label="USDA FoodData Central API key (optional)",
        value=config.get_saved_key("USDA_API_KEY"),
        password=True,
        can_reveal_password=True,
        hint_text="Defaults to the shared DEMO_KEY if left blank",
        border_radius=10,
    )

    calories_field = ft.TextField(label="Daily calories", value=str(goals.daily_calories), border_radius=10)
    protein_field = ft.TextField(label="Daily protein (g)", value=str(goals.daily_protein), border_radius=10)
    carbs_field = ft.TextField(label="Daily carbs (g)", value=str(goals.daily_carbs), border_radius=10)
    fat_field = ft.TextField(label="Daily fat (g)", value=str(goals.daily_fat), border_radius=10)

    save_status = ft.Text("", color=ft.Colors.GREEN, size=12)

    def on_save(e):
        if gemini_key_field.value.strip():
            config.save_key("GEMINI_API_KEY", gemini_key_field.value.strip())
        if usda_key_field.value.strip():
            config.save_key("USDA_API_KEY", usda_key_field.value.strip())

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
                leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda e: page.go("/")),
            ),
            ft.Container(
                content=ft.Column(
                    [
                        ft.Text("API Keys", weight=ft.FontWeight.W_600),
                        ft.Text(
                            "Stored only on this device. Requests go directly from your "
                            "phone/computer to Google/USDA -- never through our servers.",
                            size=11,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        gemini_key_field,
                        usda_key_field,
                        ft.Divider(),
                        ft.Text("Daily Goals", weight=ft.FontWeight.W_600),
                        calories_field,
                        protein_field,
                        carbs_field,
                        fat_field,
                        ft.FilledButton("Save Settings", icon=ft.Icons.SAVE, on_click=on_save),
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
