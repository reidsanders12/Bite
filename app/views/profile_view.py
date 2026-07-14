"""
Profile Account and Macro Targets View.
"""
import flet as ft

from app import theme

def build_profile_view(page: ft.Page, state) -> ft.View:
    goals = state.get_goals() if hasattr(state, "get_goals") else None

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
            # Save right to state and database
            if hasattr(state, "db") and hasattr(state.db, "save_goals"):
                state.db.save_goals(new_goals)
            if hasattr(state, "refresh_goals"):
                state.refresh_goals()

            status_txt.value = "Goals updated successfully!"
            status_txt.color = theme.SUCCESS
            page.update()
        except ValueError:
            status_txt.value = "Please enter valid numbers for all fields."
            status_txt.color = theme.ERROR
            page.update()

    return ft.View(
        route="/profile",
        bgcolor=theme.BG_CANVAS,
        controls=[
            theme.app_bar("Your Profile", on_back=lambda e: page.go("/")),
            ft.Container(
                content=ft.Column([
                    ft.CircleAvatar(
                        content=ft.Icon(ft.Icons.PERSON, size=40, color=theme.ACCENT),
                        radius=40,
                        bgcolor=theme.BG_SURFACE_ALT,
                    ),
                    ft.Text(
                        f"Logged in as: {getattr(state, 'current_user', 'Local User')}",
                        size=16, weight="w600", color=theme.TEXT_PRIMARY,
                    ),
                    ft.Divider(color=theme.BORDER),
                    ft.Text("Adjust Daily Macro Targets Manually", size=14, weight="bold", color=theme.TEXT_PRIMARY),
                    cal_field,
                    pro_field,
                    carb_field,
                    fat_field,
                    status_txt,
                    theme.primary_button("Save Macro Targets", icon=ft.Icons.SAVE, on_click=save_custom_goals),
                    ft.TextButton(
                        "Redo Onboarding Survey & Find Local Sponsors",
                        icon=ft.Icons.ASSIGNMENT,
                        style=ft.ButtonStyle(color=theme.TEXT_MUTED),
                        on_click=lambda _: page.go("/survey")
                    )
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=15, scroll=ft.ScrollMode.AUTO), # Moved scroll here!
                padding=20,
                expand=True
            )
        ]
    )