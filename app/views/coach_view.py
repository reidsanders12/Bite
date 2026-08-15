"""
AI Coach: a chat-based trainer/nutritionist that already knows your remaining
macro budget for today and (optionally) what you've told it about your
fitness goals, so it can suggest a meal that fits or build you a workout.
"""
import asyncio

import flet as ft
from app import theme
from app.state import AppState
from app.ai_engine import chat_with_coach, suggest_meal, suggest_workout, AIEngineError
from app.models import MealSuggestion, WorkoutPlan

LB_PER_KG = 2.20462


def _summarize_workouts(daily_workouts: list) -> str:
    if not daily_workouts:
        return "none logged today"
    parts = []
    for w in daily_workouts:
        name = w.get("workout_name") if isinstance(w, dict) else getattr(w, "workout_name", "Workout")
        duration = w.get("duration_minutes", 0) if isinstance(w, dict) else getattr(w, "duration_minutes", 0)
        calories = w.get("calories_burned", 0) if isinstance(w, dict) else getattr(w, "calories_burned", 0)
        parts.append(f"{name} ({duration or 0} min, {calories or 0} kcal burned)")
    return "; ".join(parts)


def _summarize_weight_trend(weight_history: list, is_imperial: bool) -> str:
    if not weight_history:
        return "no weight logged yet"

    def to_display(weight_kg: float) -> float:
        return weight_kg * LB_PER_KG if is_imperial else weight_kg

    unit = "lb" if is_imperial else "kg"
    latest_kg = weight_history[-1].get("weight_kg", 0) if isinstance(weight_history[-1], dict) else getattr(weight_history[-1], "weight_kg", 0)
    if len(weight_history) == 1:
        return f"{to_display(latest_kg):.1f}{unit} (only one entry logged so far)"

    first_kg = weight_history[0].get("weight_kg", 0) if isinstance(weight_history[0], dict) else getattr(weight_history[0], "weight_kg", 0)
    delta = to_display(latest_kg) - to_display(first_kg)
    direction = "up" if delta > 0 else ("down" if delta < 0 else "flat")
    return f"currently {to_display(latest_kg):.1f}{unit}, {direction} {abs(delta):.1f}{unit} over {len(weight_history)} logged entries"


def _remaining_tile(label: str, remaining: int, unit: str, color: str) -> ft.Control:
    value_text = ft.Text(f"{remaining:,}{unit}", size=17, weight="bold", color=color)
    tile = ft.Container(
        content=ft.Column(
            [
                value_text,
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
    tile.value_text = value_text  # exposed so the "Still available today" tiles can be refreshed live after a log action
    return tile


def build_coach_view(page: ft.Page, state: AppState) -> ft.View:
    if hasattr(state, "refresh_workouts"):
        state.refresh_workouts()
    if hasattr(state, "refresh_weight_history"):
        state.refresh_weight_history()

    totals = state.get_daily_totals()
    goals = state.goals
    profile = state.get_profile_data() if hasattr(state, "get_profile_data") else {}

    daily_workouts = state.get_daily_workouts() if hasattr(state, "get_daily_workouts") else []
    weight_history = state.get_weight_history() if hasattr(state, "get_weight_history") else []
    workouts_summary = _summarize_workouts(daily_workouts)
    weight_trend_summary = _summarize_weight_trend(weight_history, profile.get("unit_system") == "imperial")

    remaining_cal = goals.daily_calories - totals["calories"]
    remaining_pro = goals.daily_protein - totals["protein"]
    remaining_carb = goals.daily_carbs - totals["carbs"]
    remaining_fat = goals.daily_fat - totals["fat"]

    kcal_tile = _remaining_tile("kcal", remaining_cal, "", theme.ACCENT)
    protein_tile = _remaining_tile("protein", remaining_pro, "g", theme.PROTEIN)
    carbs_tile = _remaining_tile("carbs", remaining_carb, "g", theme.CARBS)
    fat_tile = _remaining_tile("fat", remaining_fat, "g", theme.FAT)

    def _refresh_remaining_tiles():
        """Re-pulls today's totals and updates the summary tiles in place, so
        logging a suggested meal reflects immediately without leaving the screen."""
        fresh_totals = state.get_daily_totals()
        kcal_tile.value_text.value = f"{goals.daily_calories - fresh_totals['calories']:,}"
        protein_tile.value_text.value = f"{goals.daily_protein - fresh_totals['protein']:,}g"
        carbs_tile.value_text.value = f"{goals.daily_carbs - fresh_totals['carbs']:,}g"
        fat_tile.value_text.value = f"{goals.daily_fat - fresh_totals['fat']:,}g"

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

    # Scrolls within its own bounded-height container below (unlike the
    # expand=True ListView this used to be, which had no bounded height of
    # its own -- see the height comment on that container). body_column
    # being scrollable too is what actually fixes the keyboard bug: if the
    # "still available today"/goals cards plus the keyboard inset ever
    # leave less room than the fixed layout needs, the whole page scrolls
    # instead of overflowing and clipping chat_input off-screen.
    chat_list = ft.Column(spacing=12, scroll=ft.ScrollMode.ADAPTIVE)
    chat_input = ft.TextField(
        hint_text="Ask about programming, recovery, recipes...",
        expand=True,
        **theme.styled_field(),
    )

    # Gemini's free-form chat replies (chat_with_coach) come back as
    # markdown prose -- **bold** exercise names, numbered/bulleted steps,
    # the odd heading -- since that's just how it writes, not something we
    # explicitly ask for (suggest_meal/suggest_workout sidestep this by
    # forcing a JSON response_schema instead of free text). Rendering AI
    # bubbles with ft.Markdown instead of plain ft.Text is what actually
    # turns that into bold text/real lists rather than showing the raw
    # "**"/"-" characters. User messages stay plain Text -- they're typed,
    # not markdown, and don't need parsing.
    _coach_markdown_style = ft.MarkdownStyleSheet(
        p_text_style=ft.TextStyle(color=theme.TEXT_PRIMARY, size=14),
        strong_text_style=ft.TextStyle(color=theme.TEXT_PRIMARY, size=14, weight=ft.FontWeight.BOLD),
        em_text_style=ft.TextStyle(color=theme.TEXT_PRIMARY, size=14, italic=True),
        h1_text_style=ft.TextStyle(color=theme.TEXT_PRIMARY, size=17, weight=ft.FontWeight.BOLD),
        h2_text_style=ft.TextStyle(color=theme.TEXT_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
        h3_text_style=ft.TextStyle(color=theme.TEXT_PRIMARY, size=15, weight=ft.FontWeight.BOLD),
        list_bullet_text_style=ft.TextStyle(color=theme.ACCENT, size=14, weight=ft.FontWeight.BOLD),
        code_text_style=ft.TextStyle(color=theme.TEXT_PRIMARY, size=13, font_family="monospace"),
        block_spacing=6,
    )

    def render_bubble(text: str, is_user: bool) -> ft.Control:
        bubble_content = (
            ft.Text(text, color=theme.TEXT_PRIMARY, size=14)
            if is_user
            else ft.Markdown(
                text,
                selectable=True,
                soft_line_break=True,
                md_style_sheet=_coach_markdown_style,
            )
        )
        return ft.Row(
            controls=[
                ft.Container(
                    content=bubble_content,
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

    def _stat_pair(exercise) -> ft.Control:
        detail = f"{exercise.sets} × {exercise.reps}"
        return ft.Column(
            [
                ft.Text(exercise.name, size=13, weight="w600", color=theme.TEXT_PRIMARY),
                ft.Text(detail, size=12, color=theme.TEXT_MUTED),
                *([ft.Text(exercise.notes, size=11, color=theme.TEXT_FAINT)] if exercise.notes else []),
            ],
            spacing=2,
        )

    def render_meal_card(suggestion) -> ft.Control:
        log_status = ft.Text("", size=11, color=theme.SUCCESS)
        log_button = ft.TextButton(
            "Log this meal",
            icon=ft.Icons.ADD_CIRCLE_OUTLINE,
            style=ft.ButtonStyle(color=theme.ACCENT),
        )

        def on_log_click(e):
            try:
                state.log_food(
                    name=suggestion.meal_name,
                    cal=suggestion.calories,
                    pro=suggestion.protein,
                    carb=suggestion.carbs,
                    fat=suggestion.fat,
                )
                log_button.disabled = True
                log_status.value = "Logged to today's timeline"
                _refresh_remaining_tiles()
            except Exception as err:
                log_status.value = f"Couldn't log: {err}"
                log_status.color = theme.ERROR
            page.update()

        log_button.on_click = on_log_click

        return theme.surface_card(
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.RESTAURANT_MENU, color=theme.ACCENT, size=18),
                            ft.Text(suggestion.meal_name, size=15, weight="bold", color=theme.TEXT_PRIMARY, expand=True),
                        ],
                        spacing=8,
                    ),
                    ft.Text(suggestion.rationale, size=12, color=theme.TEXT_MUTED),
                    ft.Row(
                        [
                            _remaining_tile("kcal", suggestion.calories, "", theme.ACCENT),
                            _remaining_tile("protein", suggestion.protein, "g", theme.PROTEIN),
                            _remaining_tile("carbs", suggestion.carbs, "g", theme.CARBS),
                            _remaining_tile("fat", suggestion.fat, "g", theme.FAT),
                        ],
                        spacing=8,
                    ),
                    ft.Column(
                        [ft.Text(f"• {item}", size=13, color=theme.TEXT_PRIMARY) for item in suggestion.ingredients],
                        spacing=4,
                    ),
                    ft.Text("How to make it", size=12, weight="bold", color=theme.TEXT_MUTED),
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(f"{i + 1}.", size=13, weight="bold", color=theme.TEXT_MUTED, width=18),
                                    ft.Text(step, size=13, color=theme.TEXT_PRIMARY, expand=True),
                                ],
                                spacing=8,
                                vertical_alignment=ft.CrossAxisAlignment.START,
                            )
                            for i, step in enumerate(suggestion.instructions)
                        ],
                        spacing=6,
                    ),
                    ft.Row([log_button, log_status], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ],
                spacing=12,
            ),
            padding=16,
        )

    def render_workout_card(plan) -> ft.Control:
        log_status = ft.Text("", size=11, color=theme.SUCCESS)
        log_button = ft.TextButton(
            "Log this workout",
            icon=ft.Icons.ADD_CIRCLE_OUTLINE,
            style=ft.ButtonStyle(color=theme.ACCENT),
        )

        def on_log_click(e):
            try:
                state.log_workout(
                    name=plan.workout_name,
                    duration_minutes=plan.estimated_duration_minutes,
                    calories_burned=plan.estimated_calories_burned,
                )
                log_button.disabled = True
                log_status.value = "Logged to today's workouts"
            except Exception as err:
                log_status.value = f"Couldn't log: {err}"
                log_status.color = theme.ERROR
            page.update()

        log_button.on_click = on_log_click

        return theme.surface_card(
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.FITNESS_CENTER, color=theme.ACCENT, size=18),
                            ft.Text(plan.workout_name, size=15, weight="bold", color=theme.TEXT_PRIMARY, expand=True),
                        ],
                        spacing=8,
                    ),
                    ft.Text(plan.rationale, size=12, color=theme.TEXT_MUTED),
                    ft.Row(
                        [
                            _remaining_tile("min", plan.estimated_duration_minutes, "", theme.ACCENT),
                            _remaining_tile("kcal burned", plan.estimated_calories_burned, "", theme.CARBS),
                        ],
                        spacing=8,
                    ),
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(f"{i + 1}.", size=13, weight="bold", color=theme.TEXT_MUTED, width=18),
                                    _stat_pair(exercise),
                                ],
                                spacing=8,
                                vertical_alignment=ft.CrossAxisAlignment.START,
                            )
                            for i, exercise in enumerate(plan.exercises)
                        ],
                        spacing=10,
                    ),
                    ft.Row([log_button, log_status], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ],
                spacing=12,
            ),
            padding=16,
        )

    for msg in state.get_chat_history():
        kind = msg.get("kind")
        if kind == "meal":
            chat_list.controls.append(render_meal_card(MealSuggestion(**msg["data"])))
        elif kind == "workout":
            chat_list.controls.append(render_workout_card(WorkoutPlan(**msg["data"])))
        else:
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
        _scroll_chat_into_view()

        try:
            reply = await chat_with_coach(
                text,
                state.get_chat_history(),
                totals,
                goals,
                access_token=state.db.get_access_token(),
                workout_goals=goals_field.value or "",
                workouts_summary=workouts_summary,
                weight_trend_summary=weight_trend_summary,
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
        _scroll_chat_into_view()

    async def on_send_click(e):
        await send_text(chat_input.value or "")

    async def on_suggest_meal(e):
        user_label = "Suggest a meal"
        chat_list.controls.append(render_bubble(user_label, is_user=True))
        state.add_chat_message(user_label, is_user=True)

        loader = ft.Row([ft.ProgressRing(width=20, height=20, color=theme.ACCENT)], alignment=ft.MainAxisAlignment.START)
        chat_list.controls.append(loader)
        page.update()
        _scroll_chat_into_view()

        try:
            suggestion = await suggest_meal(
                totals, goals, access_token=state.db.get_access_token(), workout_goals=goals_field.value or ""
            )
            chat_list.controls.remove(loader)
            chat_list.controls.append(render_meal_card(suggestion))
            state.add_chat_message(
                f"Suggested meal: {suggestion.meal_name} ({suggestion.calories} kcal, "
                f"{suggestion.protein}g protein, {suggestion.carbs}g carbs, {suggestion.fat}g fat). "
                f"{suggestion.rationale}",
                is_user=False,
                kind="meal",
                data=suggestion.model_dump(),
            )
        except AIEngineError as err:
            chat_list.controls.remove(loader)
            chat_list.controls.append(render_bubble(f"Coach couldn't respond: {err}", is_user=False))
        except Exception as err:
            chat_list.controls.remove(loader)
            chat_list.controls.append(render_bubble(f"Coach link failure: {err}", is_user=False))

        page.update()
        _scroll_chat_into_view()

    async def on_suggest_workout(e):
        user_label = "Suggest a workout"
        chat_list.controls.append(render_bubble(user_label, is_user=True))
        state.add_chat_message(user_label, is_user=True)

        loader = ft.Row([ft.ProgressRing(width=20, height=20, color=theme.ACCENT)], alignment=ft.MainAxisAlignment.START)
        chat_list.controls.append(loader)
        page.update()
        _scroll_chat_into_view()

        try:
            plan = await suggest_workout(
                totals,
                goals,
                access_token=state.db.get_access_token(),
                workout_goals=goals_field.value or "",
                workouts_summary=workouts_summary,
                weight_trend_summary=weight_trend_summary,
            )
            chat_list.controls.remove(loader)
            chat_list.controls.append(render_workout_card(plan))
            state.add_chat_message(
                f"Suggested workout: {plan.workout_name} ({plan.estimated_duration_minutes} min, "
                f"~{plan.estimated_calories_burned} kcal burned). {plan.rationale}",
                is_user=False,
                kind="workout",
                data=plan.model_dump(),
            )
        except AIEngineError as err:
            chat_list.controls.remove(loader)
            chat_list.controls.append(render_bubble(f"Coach couldn't respond: {err}", is_user=False))
        except Exception as err:
            chat_list.controls.remove(loader)
            chat_list.controls.append(render_bubble(f"Coach link failure: {err}", is_user=False))

        page.update()
        _scroll_chat_into_view()

    chat_input.on_submit = lambda e: page.run_task(on_send_click, e)

    def _scroll_chat_into_view():
        # Called after every new bubble/card: chat_list scrolls to its own
        # bottom so the newest message is visible within the chat box, and
        # body_column scrolls to ITS bottom so the input row (and, while
        # typing, chat_input itself) stays visible above the on-screen
        # keyboard rather than getting clipped off-screen behind it.
        chat_list.scroll_to(offset=-1, duration=200)
        body_column.scroll_to(offset=-1, duration=200)

    body_column = ft.Column(
        [
            theme.surface_card(
                ft.Column(
                    [
                        ft.Text("Still available today", size=13, weight="bold", color=theme.TEXT_PRIMARY),
                        ft.Row(
                            [kcal_tile, protein_tile, carbs_tile, fat_tile],
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
                # expand=True doesn't work here the way it used to -- inside
                # body_column's own scroll (needed for the keyboard fix,
                # see the comment on chat_list above), an expand child has
                # no bounded height to expand into, so it collapsed down to
                # its content's intrinsic size instead of filling the
                # screen like before. An explicit height, sized off the
                # device's actual viewport, gets back the "fills most of
                # the screen" feel without needing an unbounded expand.
                content=chat_list,
                height=max(280, int((page.height or 700) - 340)),
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
        scroll=ft.ScrollMode.ADAPTIVE,
        # Explicit stretch, not relied-on default behavior: the chat box's
        # scrollable content (chat_list) otherwise has no width of its own
        # to size against and was rendering skinny -- shrink-wrapped to
        # roughly a bubble's width instead of filling the screen -- once it
        # stopped being an expand=True child (see the height comment below).
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )

    if chat_list.controls:
        async def _jump_to_bottom_on_mount():
            # Mirrors the old ListView(auto_scroll=True)'s behavior of
            # opening already scrolled to the newest message -- needs a
            # beat after mount before body_column has a real scroll extent
            # to jump to.
            await asyncio.sleep(0.05)
            chat_list.scroll_to(offset=-1, duration=0)

        page.run_task(_jump_to_bottom_on_mount)

    return ft.View(
        route="/coach",
        bgcolor=theme.BG_CANVAS,
        controls=[
            theme.app_bar("AI Coach", on_back=lambda e: page.go("/")),
            ft.Container(
                content=theme.ai_disclaimer("AI-generated suggestions -- not medical or nutrition advice."),
                padding=ft.padding.only(left=20, right=20, top=4),
            ),
            ft.Container(
                expand=True,
                padding=20,
                content=body_column,
            ),
        ],
    )
