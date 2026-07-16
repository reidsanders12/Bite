"""
Workout Logging view: describe a workout in plain language and let Gemini
estimate calories burned (using the user's saved bodyweight, if any) --
then edit the estimate before saving, same "AI estimates, you correct"
pattern as the food logging flow.
"""
import flet as ft

from app import ai_engine
from app import theme
from app.views.widgets import error_banner, loading_view

LB_PER_KG = 2.20462


def _saved_weight_kg(state) -> float:
    """Reads the user's onboarding-survey weight (either unit) as kg, if any."""
    profile = state.get_profile_data() if hasattr(state, "get_profile_data") else {}
    if profile.get("weight_kg"):
        try:
            return float(profile["weight_kg"])
        except (TypeError, ValueError):
            pass
    if profile.get("weight_lb"):
        try:
            return float(profile["weight_lb"]) / LB_PER_KG
        except (TypeError, ValueError):
            pass
    return None


def build_log_workout_view(page: ft.Page, state) -> ft.View:
    description_field = ft.TextField(
        label="Describe your workout",
        hint_text='e.g. "45 min upper body lifting" or "Ran 5k in 30 minutes"',
        multiline=True,
        min_lines=2,
        max_lines=4,
        autofocus=True,
        **theme.styled_field(),
    )
    status_area = ft.Container()
    estimate_button = theme.primary_button("Estimate with AI", icon=ft.Icons.AUTO_AWESOME)

    name_field = ft.TextField(label="Workout", **theme.styled_field())
    duration_field = ft.TextField(
        label="Duration (minutes)", keyboard_type=ft.KeyboardType.NUMBER, **theme.styled_field(),
    )
    calories_field = ft.TextField(
        label="Calories burned", keyboard_type=ft.KeyboardType.NUMBER, **theme.styled_field(),
    )
    review_section = ft.Column(
        [
            ft.Text("Review before saving", size=13, weight="bold", color=theme.TEXT_PRIMARY),
            name_field,
            duration_field,
            calories_field,
        ],
        spacing=12,
        visible=False,
    )
    save_status = ft.Text("", size=12)

    async def on_estimate(e):
        text = (description_field.value or "").strip()
        if not text:
            return
        estimate_button.disabled = True
        status_area.content = loading_view("Estimating calories burned...")
        page.update()
        try:
            estimate = await ai_engine.analyze_workout(text, weight_kg=_saved_weight_kg(state))
        except ai_engine.AIEngineError as exc:
            status_area.content = error_banner(str(exc))
            estimate_button.disabled = False
            page.update()
            return
        except Exception as exc:  # noqa: BLE001
            status_area.content = error_banner(f"Unexpected error: {exc}")
            estimate_button.disabled = False
            page.update()
            return

        name_field.value = estimate.workout_name
        duration_field.value = str(estimate.duration_minutes)
        calories_field.value = str(estimate.calories_burned)
        review_section.visible = True
        status_area.content = None
        estimate_button.disabled = False
        page.update()

    estimate_button.on_click = on_estimate

    def save_workout(e):
        name = (name_field.value or "").strip()
        if not name:
            save_status.value = "Enter a workout name."
            save_status.color = theme.ERROR
            page.update()
            return

        try:
            duration = int((duration_field.value or "0").strip() or 0)
            calories = int((calories_field.value or "0").strip() or 0)
        except ValueError:
            save_status.value = "Duration and calories must be whole numbers."
            save_status.color = theme.ERROR
            page.update()
            return

        state.log_workout(name, duration, calories)

        if len(page.views) > 1:
            page.views.pop()
        page.go("/")

    return ft.View(
        route="/log_workout",
        bgcolor=theme.BG_CANVAS,
        controls=[
            theme.app_bar(
                "Log a Workout",
                on_back=lambda e: page.go("/"),
                actions=[
                    ft.IconButton(
                        icon=ft.Icons.HISTORY_ROUNDED,
                        icon_color=theme.TEXT_MUTED,
                        tooltip="Workout History",
                        on_click=lambda e: page.go("/workout_history"),
                    ),
                ],
            ),
            ft.Container(
                content=ft.Column(
                    [
                        description_field,
                        estimate_button,
                        status_area,
                        ft.Divider(color=theme.BORDER, height=1),
                        review_section,
                        save_status,
                        theme.primary_button(
                            "Log Workout", icon=ft.Icons.FITNESS_CENTER_ROUNDED, on_click=save_workout,
                        ),
                    ],
                    spacing=16,
                    scroll=ft.ScrollMode.AUTO,
                ),
                padding=20,
                expand=True,
            ),
        ],
    )
