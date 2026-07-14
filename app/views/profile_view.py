"""
Profile Account and Macro Targets View.
"""
import flet as ft

from app import theme

def build_profile_view(page: ft.Page, state) -> ft.View:
    goals = state.get_goals() if hasattr(state, "get_goals") else None
    name = getattr(state, "current_user_name", "") or "Bite User"
    email = getattr(state, "current_user_email", "")
    initials = "".join(part[0] for part in name.split()[:2]).upper() or "B"

    def stat_tile(label: str, value: str, color: str) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(value, size=18, weight="bold", color=color, font_family=theme.DISPLAY_FONT),
                    ft.Text(label, size=11, color=theme.TEXT_MUTED),
                ],
                spacing=2,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=theme.BG_SURFACE_ALT,
            border_radius=theme.RADIUS_SM,
            padding=ft.padding.symmetric(vertical=12, horizontal=8),
            expand=True,
            alignment=ft.alignment.center,
        )

    summary_card = theme.surface_card(
        ft.Column(
            [
                ft.Text("Your Daily Targets", size=14, weight="bold", color=theme.TEXT_PRIMARY),
                ft.Row(
                    [
                        stat_tile("kcal", f"{getattr(goals, 'daily_calories', 2000):,}", theme.ACCENT),
                        stat_tile("protein", f"{getattr(goals, 'daily_protein', 150)}g", theme.PROTEIN),
                        stat_tile("carbs", f"{getattr(goals, 'daily_carbs', 200)}g", theme.CARBS),
                        stat_tile("fat", f"{getattr(goals, 'daily_fat', 65)}g", theme.FAT),
                    ],
                    spacing=8,
                ),
            ],
            spacing=12,
        )
    )

    # Target Input Fields
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

    status_txt = ft.Text("", color=theme.ACCENT, size=12)

    def save_custom_goals(e):
        try:
            from app.models import UserGoals
            new_goals = UserGoals(
                daily_calories=int(cal_field.value),
                daily_protein=int(pro_field.value),
                daily_carbs=int(carb_field.value),
                daily_fat=int(fat_field.value)
            )
            saved_ok, save_err = True, ""
            if hasattr(state, "db") and hasattr(state.db, "save_goals"):
                saved_ok, save_err = state.db.save_goals(new_goals)
            if saved_ok and hasattr(state, "refresh_goals"):
                state.refresh_goals()

            if saved_ok:
                status_txt.value = "Goals updated successfully!"
                status_txt.color = theme.SUCCESS
            else:
                status_txt.value = f"Couldn't save: {save_err}"
                status_txt.color = theme.ERROR
            page.update()
        except ValueError:
            status_txt.value = "Please enter valid numbers for all fields."
            status_txt.color = theme.ERROR
            page.update()

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

                    ft.Divider(color=theme.BORDER, height=28),
                    ft.Text("Edit Daily Macro Targets", size=14, weight="bold", color=theme.TEXT_PRIMARY),
                    cal_field,
                    pro_field,
                    carb_field,
                    fat_field,
                    status_txt,
                    theme.primary_button("Save Macro Targets", icon=ft.Icons.SAVE, on_click=save_custom_goals),
                    ft.TextButton(
                        "Redo Onboarding Survey",
                        icon=ft.Icons.ASSIGNMENT,
                        style=ft.ButtonStyle(color=theme.TEXT_MUTED),
                        on_click=lambda _: page.go("/survey")
                    ),
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
