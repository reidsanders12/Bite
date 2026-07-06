"""
Profile Account and Macro Targets View.
"""
import flet as ft

def build_profile_view(page: ft.Page, state) -> ft.View:
    goals = state.get_goals() if hasattr(state, "get_goals") else None
    
    # Target Input Fields
    cal_field = ft.TextField(label="Daily Calories (kcal)", value=str(getattr(goals, "daily_calories", 2000)), border_radius=10)
    pro_field = ft.TextField(label="Protein (g)", value=str(getattr(goals, "daily_protein", 150)), border_radius=10)
    carb_field = ft.TextField(label="Carbs (g)", value=str(getattr(goals, "daily_carbs", 200)), border_radius=10)
    fat_field = ft.TextField(label="Fats (g)", value=str(getattr(goals, "daily_fat", 65)), border_radius=10)
    
    status_txt = ft.Text("", color="#00E5FF")

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
            page.update()
        except ValueError:
            status_txt.value = "Please enter valid numbers for all fields."
            page.update()

    return ft.View(
        route="/profile",
        controls=[
            ft.AppBar(
                title=ft.Text("Your Profile"),
                leading=ft.IconButton(content=ft.Icon(ft.Icons.ARROW_BACK), on_click=lambda e: page.go("/")),
            ),
            ft.Container(
                content=ft.Column([
                    ft.CircleAvatar(content=ft.Icon(ft.Icons.PERSON, size=40), radius=40, bgcolor="#222A35"),
                    ft.Text(f"Logged in as: {getattr(state, 'current_user', 'Local User')}", size=16, weight="semibold"),
                    ft.Divider(color="#222A35"),
                    ft.Text("Adjust Daily Macro Targets Manually", size=14, weight="bold"),
                    cal_field,
                    pro_field,
                    carb_field,
                    fat_field,
                    status_txt,
                    ft.FilledButton(
                        "Save Macro Targets", 
                        icon=ft.Icons.SAVE, 
                        on_click=save_custom_goals, 
                        style=ft.ButtonStyle(bgcolor="#00E5FF", color="#181D26")
                    ),
                    ft.TextButton(
                        "Redo Onboarding Survey & Find Local Sponsors", 
                        icon=ft.Icons.ASSIGNMENT, 
                        on_click=lambda _: page.go("/survey")
                    )
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=15, scroll=ft.ScrollMode.AUTO), # Moved scroll here!
                padding=20,
                expand=True
            )
        ]
    )