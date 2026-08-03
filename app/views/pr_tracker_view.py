"""
Personal Records view: auto-computed bests across workouts, food-logging
streaks, and weight -- derived entirely from existing workout_logs,
food_logs, and weight_logs rows (see database.py's get_pr_summary), no new
table or manual entry required.
"""
import flet as ft

from app import theme

LB_PER_KG = 2.20462


def _record_card(icon: str, label: str, value: str, subtitle: str, color: str) -> ft.Control:
    return ft.Container(
        content=ft.Row(
            [
                ft.Container(
                    content=ft.Icon(icon, color=color, size=22),
                    width=44, height=44, border_radius=theme.RADIUS_MD,
                    bgcolor=ft.Colors.with_opacity(0.12, color),
                    alignment=ft.alignment.center,
                ),
                ft.Column(
                    [
                        ft.Text(label, size=13, weight="w600", color=theme.TEXT_PRIMARY),
                        ft.Text(subtitle, size=12, color=theme.TEXT_MUTED),
                    ],
                    expand=True, spacing=2,
                ),
                ft.Text(value, size=18, weight="bold", color=color, font_family=theme.DISPLAY_FONT),
            ],
            spacing=14, vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=16, border_radius=theme.RADIUS_MD, bgcolor=theme.BG_SURFACE,
        border=ft.border.all(1, theme.BORDER), shadow=theme.CARD_SHADOW,
    )


def build_pr_tracker_view(page: ft.Page, state) -> ft.View:
    summary = state.get_pr_summary() if hasattr(state, "get_pr_summary") else {}
    profile = state.get_profile_data() if hasattr(state, "get_profile_data") else {}
    is_imperial = profile.get("unit_system") == "imperial"
    weight_unit = "lb" if is_imperial else "kg"

    def to_display_weight(kg: float) -> float:
        return kg * LB_PER_KG if is_imperial else kg

    cards = ft.Column(spacing=12)

    food_best = summary.get("food_streak_best") or 0
    if food_best:
        food_current = summary.get("food_streak_current") or 0
        cards.controls.append(_record_card(
            ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED, "Best Logging Streak",
            f"{food_best}d", f"Current streak: {food_current}d", theme.ACCENT,
        ))

    workout_best = summary.get("workout_streak_best") or 0
    if workout_best:
        workout_current = summary.get("workout_streak_current") or 0
        cards.controls.append(_record_card(
            ft.Icons.WHATSHOT_ROUNDED, "Best Workout Streak",
            f"{workout_best}d", f"Current streak: {workout_current}d", theme.PROTEIN,
        ))

    longest_workout = summary.get("longest_workout")
    if longest_workout and (longest_workout.get("duration_minutes") or 0) > 0:
        name = longest_workout.get("workout_name") or "Workout"
        date_str = (longest_workout.get("created_at") or "")[:10]
        cards.controls.append(_record_card(
            ft.Icons.TIMER_OUTLINED, "Longest Workout",
            f"{longest_workout['duration_minutes']} min", f"{name} · {date_str}", theme.CARBS,
        ))

    most_cal_workout = summary.get("most_calories_workout")
    if most_cal_workout and (most_cal_workout.get("calories_burned") or 0) > 0:
        name = most_cal_workout.get("workout_name") or "Workout"
        date_str = (most_cal_workout.get("created_at") or "")[:10]
        cards.controls.append(_record_card(
            ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED, "Most Calories Burned",
            f"{most_cal_workout['calories_burned']:,} kcal", f"{name} · {date_str}", theme.FAT,
        ))

    total_workouts = summary.get("total_workouts") or 0
    if total_workouts:
        cards.controls.append(_record_card(
            ft.Icons.FITNESS_CENTER_ROUNDED, "Total Workouts Logged",
            f"{total_workouts:,}", "All-time count", theme.TEXT_PRIMARY,
        ))

    lowest_weight = summary.get("lowest_weight")
    if lowest_weight:
        date_str = (lowest_weight.get("created_at") or "")[:10]
        cards.controls.append(_record_card(
            ft.Icons.TRENDING_DOWN_ROUNDED, "Lowest Logged Weight",
            f"{to_display_weight(lowest_weight['weight_kg']):.1f} {weight_unit}", date_str, theme.SUCCESS,
        ))

    highest_weight = summary.get("highest_weight")
    if highest_weight:
        date_str = (highest_weight.get("created_at") or "")[:10]
        cards.controls.append(_record_card(
            ft.Icons.TRENDING_UP_ROUNDED, "Highest Logged Weight",
            f"{to_display_weight(highest_weight['weight_kg']):.1f} {weight_unit}", date_str, theme.TEXT_MUTED,
        ))

    if not cards.controls:
        cards.controls.append(
            ft.Container(
                content=ft.Column(
                    [
                        ft.Icon(ft.Icons.EMOJI_EVENTS_OUTLINED, color=theme.TEXT_FAINT, size=28),
                        ft.Text(
                            "Log meals, workouts, and weight to start earning records.",
                            color=theme.TEXT_FAINT, size=13, italic=True, text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                    spacing=10, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=28, alignment=ft.alignment.center,
            )
        )

    return ft.View(
        route="/pr_tracker",
        bgcolor=theme.BG_CANVAS,
        controls=[
            theme.app_bar("Personal Records", on_back=lambda e: page.go("/profile")),
            ft.Container(
                content=ft.Column([cards], spacing=14, scroll=ft.ScrollMode.HIDDEN, expand=True),
                padding=20, expand=True,
            ),
        ],
    )
