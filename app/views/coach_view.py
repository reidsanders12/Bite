"""
AI Coach: a chat-based trainer/nutritionist that already knows your remaining
macro budget for today and (optionally) what you've told it about your
fitness goals, so it can suggest a meal that fits or build you a workout.
"""
import flet as ft
from app import theme
from app.state import AppState
from app.ai_engine import chat_with_coach, AIEngineError


def _remaining_tile(label: str, remaining: int, unit: str, color: str) -> ft.Control:
    return ft.Container(
        content=ft.Column(
            [
                ft.Text(f"{remaining:,}{unit}", size=17, weight="bold", color=color),
                ft.Text(label, size=11, color=theme.TEXT_MUTED),
            ],
            spacing=2,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=theme.BG_SURFACE_ALT,
        border_radius=theme.RADIUS_SM,
        padding=ft.padding.symmetric(vertical=10, horizontal=8),
        expand=True,
        alignment=ft.alignment.center,
    )


def build_coach_view(page: ft.Page, state: AppState) -> ft.View:
    totals = state.get_daily_totals()
    goals = state.goals
    profile = state.get_profile_data() if hasattr(state, "get_profile_data") else {}

    remaining_cal = goals.daily_calories - totals["calories"]
    remaining_pro = goals.daily_protein - totals["protein"]
    remaining_carb = goals.daily_carbs - totals["carbs"]
    remaining_fat = goals.daily_fat - totals["fat"]

    goals_field = ft.TextField(
        value=profile.get("workout_goals", ""),
        hint_text="e.g. Build muscle, gym access 4x/week, avoid leg day on Fridays",
        multiline=True,
        min_lines=1,
        max_lines=3,
        **theme.styled_field(),
    )
    goals_status = ft.Text("", size=11, color=theme.SUCCESS)

    def save_goals_text(e):
        text = (goals_field.value or "").strip()
        if hasattr(state, "save_profile_data"):
            state.save_profile_data({"workout_goals": text})
        goals_status.value = "Saved"
        page.update()

    chat_list = ft.ListView(expand=True, spacing=12, padding=10, auto_scroll=True)
    chat_input = ft.TextField(
        hint_text="Ask about programming, recovery, recipes...",
        expand=True,
        **theme.styled_field(),
    )

    def render_bubble(text: str, is_user: bool) -> ft.Control:
        return ft.Row(
            controls=[
                ft.Container(
                    content=ft.Text(text, color=theme.TEXT_PRIMARY, size=14),
                    bgcolor=theme.BG_SURFACE_ALT if is_user else theme.BG_SURFACE,
                    padding=14,
                    border_radius=ft.border_radius.only(
                        top_left=16, top_right=16,
                        bottom_left=4 if is_user else 16,
                        bottom_right=16 if is_user else 4,
                    ),
                    border=None if is_user else ft.border.only(left=ft.BorderSide(3, theme.ACCENT)),
                    width=280,
                )
            ],
            alignment=ft.MainAxisAlignment.END if is_user else ft.MainAxisAlignment.START,
        )

    for msg in state.get_chat_history():
        chat_list.controls.append(render_bubble(msg["text"], msg["is_user"]))

    async def send_text(text: str):
        text = text.strip()
        if not text:
            return

        chat_input.value = ""
        chat_list.controls.append(render_bubble(text, is_user=True))
        state.add_chat_message(text, is_user=True)

        loader = ft.Row([ft.ProgressRing(width=20, height=20, color=theme.ACCENT)], alignment=ft.MainAxisAlignment.START)
        chat_list.controls.append(loader)
        page.update()

        try:
            reply = await chat_with_coach(
                text,
                state.get_chat_history(),
                totals,
                goals,
                workout_goals=goals_field.value or "",
            )
            chat_list.controls.remove(loader)
            chat_list.controls.append(render_bubble(reply, is_user=False))
            state.add_chat_message(reply, is_user=False)
        except AIEngineError as err:
            chat_list.controls.remove(loader)
            chat_list.controls.append(render_bubble(f"Coach couldn't respond: {err}", is_user=False))
        except Exception as err:
            chat_list.controls.remove(loader)
            chat_list.controls.append(render_bubble(f"Coach link failure: {err}", is_user=False))

        page.update()

    async def on_send_click(e):
        await send_text(chat_input.value or "")

    async def on_suggest_meal(e):
        await send_text("Suggest a meal I can eat right now that fits within my remaining macros for today.")

    async def on_suggest_workout(e):
        await send_text("Based on my stated fitness goals, suggest a workout for today.")

    chat_input.on_submit = lambda e: page.run_task(on_send_click, e)

    return ft.View(
        route="/coach",
        bgcolor=theme.BG_CANVAS,
        controls=[
            theme.app_bar("AI Coach", on_back=lambda e: page.go("/")),
            ft.Container(
                expand=True,
                padding=20,
                content=ft.Column(
                    [
                        theme.surface_card(
                            ft.Column(
                                [
                                    ft.Text("Still available today", size=13, weight="bold", color=theme.TEXT_PRIMARY),
                                    ft.Row(
                                        [
                                            _remaining_tile("kcal", remaining_cal, "", theme.ACCENT),
                                            _remaining_tile("protein", remaining_pro, "g", theme.PROTEIN),
                                            _remaining_tile("carbs", remaining_carb, "g", theme.CARBS),
                                            _remaining_tile("fat", remaining_fat, "g", theme.FAT),
                                        ],
                                        spacing=8,
                                    ),
                                ],
                                spacing=10,
                            ),
                            padding=16,
                        ),
                        theme.surface_card(
                            ft.Column(
                                [
                                    ft.Text("Your fitness goals", size=13, weight="bold", color=theme.TEXT_PRIMARY),
                                    ft.Text(
                                        "Tell the coach once — it'll remember this for every meal and workout suggestion.",
                                        size=11, color=theme.TEXT_MUTED,
                                    ),
                                    goals_field,
                                    ft.Row(
                                        [
                                            goals_status,
                                            ft.TextButton(
                                                "Save goals",
                                                style=ft.ButtonStyle(color=theme.ACCENT),
                                                on_click=save_goals_text,
                                            ),
                                        ],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    ),
                                ],
                                spacing=6,
                            ),
                            padding=16,
                        ),
                        ft.Row(
                            [
                                ft.OutlinedButton(
                                    "Suggest a meal",
                                    icon=ft.Icons.RESTAURANT_MENU,
                                    on_click=lambda e: page.run_task(on_suggest_meal, e),
                                    expand=True,
                                ),
                                ft.OutlinedButton(
                                    "Suggest a workout",
                                    icon=ft.Icons.FITNESS_CENTER,
                                    on_click=lambda e: page.run_task(on_suggest_workout, e),
                                    expand=True,
                                ),
                            ],
                            spacing=10,
                        ),
                        ft.Container(
                            content=chat_list,
                            expand=True,
                            bgcolor=theme.BG_SURFACE,
                            border=ft.border.all(1, theme.BORDER),
                            border_radius=theme.RADIUS_MD,
                            padding=10,
                        ),
                        ft.Row(
                            [
                                chat_input,
                                ft.IconButton(
                                    icon=ft.Icons.SEND,
                                    icon_color=theme.ACCENT,
                                    on_click=lambda e: page.run_task(on_send_click, e),
                                ),
                            ],
                            spacing=10,
                        ),
                    ],
                    spacing=14,
                    expand=True,
                ),
            ),
        ],
    )
