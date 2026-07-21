"""
Profile Account and Macro Targets View.
"""
import flet as ft

from app import theme
from app.models import UserGoals

LB_PER_KG = 2.20462
CM_PER_IN = 2.54

_MIN_CALORIES, _MAX_CALORIES = 500, 10000
_MIN_GRAMS, _MAX_GRAMS = 0, 500


def _bmi_category(bmi: float) -> tuple[str, str]:
    if bmi < 18.5:
        return "Underweight", theme.FAT
    if bmi < 25:
        return "Healthy weight", theme.SUCCESS
    if bmi < 30:
        return "Overweight", theme.FAT
    return "Obese", theme.ERROR


def _resolve_weight_kg(profile: dict, weight_history: list):
    if weight_history:
        latest = weight_history[-1]
        kg = latest.get("weight_kg") if isinstance(latest, dict) else getattr(latest, "weight_kg", None)
        if kg:
            return kg
    if profile.get("unit_system") == "imperial" and profile.get("weight_lb"):
        return profile["weight_lb"] / LB_PER_KG
    return profile.get("weight_kg")


def _resolve_height_cm(profile: dict):
    if profile.get("unit_system") == "imperial" and profile.get("height_ft") is not None:
        feet = profile.get("height_ft") or 0
        inches = profile.get("height_in") or 0
        return (feet * 12 + inches) * CM_PER_IN
    return profile.get("height_cm")


def build_profile_view(page: ft.Page, state) -> ft.View:
    if hasattr(state, "refresh_weight_history"):
        state.refresh_weight_history()

    goals = state.get_goals() if hasattr(state, "get_goals") else None
    profile = state.get_profile_data() if hasattr(state, "get_profile_data") else {}
    weight_history = state.get_weight_history() if hasattr(state, "get_weight_history") else []

    name = getattr(state, "current_user_name", "") or "Bite User"
    email = getattr(state, "current_user_email", "")
    initials = "".join(part[0] for part in name.split()[:2]).upper() or "B"

    def stat_tile(label: str, value: str, color: str) -> ft.Control:
        value_text = ft.Text(value, size=18, weight="bold", color=color, font_family=theme.DISPLAY_FONT)
        tile = ft.Container(
            content=ft.Column(
                [value_text, ft.Text(label, size=11, color=theme.TEXT_MUTED)],
                spacing=2,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=theme.BG_SURFACE_ALT,
            border_radius=theme.RADIUS_SM,
            padding=ft.padding.symmetric(vertical=12, horizontal=8),
            expand=True,
            alignment=ft.alignment.center,
        )
        tile.value_text = value_text
        return tile

    kcal_tile = stat_tile("kcal", f"{getattr(goals, 'daily_calories', 2000):,}", theme.ACCENT)
    pro_tile = stat_tile("protein", f"{getattr(goals, 'daily_protein', 150)}g", theme.PROTEIN)
    carb_tile = stat_tile("carbs", f"{getattr(goals, 'daily_carbs', 200)}g", theme.CARBS)
    fat_tile = stat_tile("fat", f"{getattr(goals, 'daily_fat', 65)}g", theme.FAT)
    tiles_row = ft.Row([kcal_tile, pro_tile, carb_tile, fat_tile], spacing=8)

    # Target Input Fields -- hidden until "Edit" is tapped, so the card doesn't
    # show the same four numbers twice (as read-only tiles AND editable fields).
    cal_field = ft.TextField(
        label="Daily Calories (kcal)", value=str(getattr(goals, "daily_calories", 2000)), **theme.styled_field()
    )
    pro_field = ft.TextField(
        label="Protein (g)", value=str(getattr(goals, "daily_protein", 150)), **theme.styled_field()
    )
    carb_field = ft.TextField(
        label="Carbs (g)", value=str(getattr(goals, "daily_carbs", 200)), **theme.styled_field()
    )
    fat_field = ft.TextField(
        label="Fats (g)", value=str(getattr(goals, "daily_fat", 65)), **theme.styled_field()
    )
    edit_fields_column = ft.Column([cal_field, pro_field, carb_field, fat_field], spacing=12, visible=False)

    status_txt = ft.Text("", size=12)

    edit_button = ft.TextButton("Edit", icon=ft.Icons.EDIT_OUTLINED, style=ft.ButtonStyle(color=theme.ACCENT))
    save_button = theme.primary_button("Save", icon=ft.Icons.CHECK)
    cancel_button = ft.TextButton("Cancel", style=ft.ButtonStyle(color=theme.TEXT_MUTED))
    edit_actions_row = ft.Row([save_button, cancel_button], spacing=10, visible=False)

    def enter_edit_mode(e):
        cal_field.value = str(getattr(goals, "daily_calories", 2000))
        pro_field.value = str(getattr(goals, "daily_protein", 150))
        carb_field.value = str(getattr(goals, "daily_carbs", 200))
        fat_field.value = str(getattr(goals, "daily_fat", 65))
        status_txt.value = ""
        tiles_row.visible = False
        edit_fields_column.visible = True
        edit_actions_row.visible = True
        edit_button.visible = False
        page.update()

    def cancel_edit(e):
        status_txt.value = ""
        tiles_row.visible = True
        edit_fields_column.visible = False
        edit_actions_row.visible = False
        edit_button.visible = True
        page.update()

    def save_custom_goals(e):
        try:
            cal = int(cal_field.value)
            pro = int(pro_field.value)
            carb = int(carb_field.value)
            fat = int(fat_field.value)
        except (TypeError, ValueError):
            status_txt.value = "Please enter whole numbers for all fields."
            status_txt.color = theme.ERROR
            page.update()
            return

        if not (_MIN_CALORIES <= cal <= _MAX_CALORIES):
            status_txt.value = f"Calories should be between {_MIN_CALORIES:,} and {_MAX_CALORIES:,}."
            status_txt.color = theme.ERROR
            page.update()
            return

        for field_label, value in (("Protein", pro), ("Carbs", carb), ("Fat", fat)):
            if not (_MIN_GRAMS <= value <= _MAX_GRAMS):
                status_txt.value = f"{field_label} should be between {_MIN_GRAMS} and {_MAX_GRAMS}g."
                status_txt.color = theme.ERROR
                page.update()
                return

        new_goals = UserGoals(daily_calories=cal, daily_protein=pro, daily_carbs=carb, daily_fat=fat)
        saved_ok, save_err = True, ""
        if hasattr(state, "db") and hasattr(state.db, "save_goals"):
            saved_ok, save_err = state.db.save_goals(new_goals)
        if saved_ok and hasattr(state, "refresh_goals"):
            state.refresh_goals()

        if saved_ok:
            kcal_tile.value_text.value = f"{cal:,}"
            pro_tile.value_text.value = f"{pro}g"
            carb_tile.value_text.value = f"{carb}g"
            fat_tile.value_text.value = f"{fat}g"
            status_txt.value = ""
            tiles_row.visible = True
            edit_fields_column.visible = False
            edit_actions_row.visible = False
            edit_button.visible = True
        else:
            status_txt.value = f"Couldn't save: {save_err}"
            status_txt.color = theme.ERROR
        page.update()

    edit_button.on_click = enter_edit_mode
    save_button.on_click = save_custom_goals
    cancel_button.on_click = cancel_edit

    summary_card = theme.surface_card(
        ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("Your Daily Targets", size=14, weight="bold", color=theme.TEXT_PRIMARY, expand=True),
                        edit_button,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                tiles_row,
                edit_fields_column,
                status_txt,
                edit_actions_row,
            ],
            spacing=12,
        )
    )

    # --- BMI: latest logged weight (falling back to the onboarding snapshot) + onboarding height ---
    weight_kg = _resolve_weight_kg(profile, weight_history)
    height_cm = _resolve_height_cm(profile)
    bmi = weight_kg / ((height_cm / 100) ** 2) if weight_kg and height_cm else None

    if bmi is not None:
        category, category_color = _bmi_category(bmi)
        bmi_card = theme.surface_card(
            ft.Row(
                [
                    ft.Column(
                        [
                            ft.Text(f"{bmi:.1f}", size=26, weight="bold", color=category_color, font_family=theme.DISPLAY_FONT),
                            ft.Text("BMI", size=11, color=theme.TEXT_MUTED),
                        ],
                        spacing=0,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.VerticalDivider(width=1, color=theme.BORDER),
                    ft.Column(
                        [
                            ft.Text(category, size=14, weight="bold", color=category_color),
                            ft.Text(
                                "Based on your latest logged weight and onboarding height",
                                size=11, color=theme.TEXT_MUTED,
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                ],
                spacing=16,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )
    else:
        bmi_card = theme.surface_card(
            ft.Column(
                [
                    ft.Text("BMI", size=14, weight="bold", color=theme.TEXT_PRIMARY),
                    ft.Text(
                        "Complete the onboarding survey and log a weight entry to see your BMI here.",
                        size=12, color=theme.TEXT_MUTED,
                    ),
                    ft.TextButton(
                        "Complete Survey",
                        icon=ft.Icons.ASSIGNMENT,
                        style=ft.ButtonStyle(color=theme.ACCENT),
                        on_click=lambda _: page.go("/survey"),
                    ),
                ],
                spacing=8,
            )
        )

    def sign_out(e):
        try:
            state.db.auth.sign_out()
        except Exception:
            pass
        page.views.clear()
        page.go("/auth")

    return ft.View(
        route="/profile",
        bgcolor=theme.BG_CANVAS,
        controls=[
            theme.app_bar("Your Profile", on_back=lambda e: page.go("/")),
            ft.Container(
                content=ft.Column([
                    ft.CircleAvatar(
                        content=ft.Text(initials, size=28, weight="bold", color=theme.ACCENT_ON),
                        radius=40,
                        bgcolor=theme.ACCENT,
                    ),
                    ft.Text(name, size=20, weight="bold", color=theme.TEXT_PRIMARY, font_family=theme.DISPLAY_FONT),
                    ft.Text(email, size=13, color=theme.TEXT_MUTED) if email else ft.Container(),

                    ft.Divider(color=theme.BORDER, height=28),
                    summary_card,
                    bmi_card,

                    ft.Divider(color=theme.BORDER, height=28),
                    ft.TextButton(
                        "Redo Onboarding Survey",
                        icon=ft.Icons.ASSIGNMENT,
                        style=ft.ButtonStyle(color=theme.TEXT_MUTED),
                        on_click=lambda _: page.go("/survey")
                    ),
                    ft.TextButton(
                        "Weight Tracking",
                        icon=ft.Icons.MONITOR_WEIGHT_OUTLINED,
                        style=ft.ButtonStyle(color=theme.TEXT_MUTED),
                        on_click=lambda _: page.go("/weight")
                    ),
                    ft.TextButton(
                        "Sponsor Requests",
                        icon=ft.Icons.CAMPAIGN_OUTLINED,
                        style=ft.ButtonStyle(color=theme.TEXT_MUTED),
                        on_click=lambda _: page.go("/sponsor_requests")
                    ) if hasattr(state, "is_admin") and state.is_admin() else ft.Container(),
                    ft.Divider(color=theme.BORDER, height=28),
                    ft.TextButton(
                        "Log Out",
                        icon=ft.Icons.LOGOUT,
                        style=ft.ButtonStyle(color=theme.ERROR),
                        on_click=sign_out
                    ),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=15, scroll=ft.ScrollMode.AUTO),
                padding=20,
                expand=True
            )
        ]
    )
