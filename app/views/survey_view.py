"""
Survey and Onboarding Target Calculator View.
Calculates macro baseline targets and maps localized regional sponsor parameters.
"""

import flet as ft
from app.models import UserGoals

def build_survey_view(page: ft.Page, state) -> ft.View:
    # Track the active wizard step: 0=Biometrics, 1=Goals, 2=Location & Sponsors
    current_step = 0

    # Step 1 Controls: Biometrics
    age_field = ft.TextField(label="Age (years)", hint_text="e.g. 28", border_radius=10)
    gender_radio = ft.RadioGroup(
        content=ft.Row([
            ft.Radio(value="male", label="Male"),
            ft.Radio(value="female", label="Female")
        ], alignment=ft.MainAxisAlignment.CENTER)
    )
    weight_field = ft.TextField(label="Current Weight (kg)", hint_text="e.g. 75", border_radius=10)
    height_field = ft.TextField(label="Height (cm)", hint_text="e.g. 178", border_radius=10)

    # Step 2 Controls: Goals & Activity
    activity_dropdown = ft.Dropdown(
        label="Activity Level",
        border_radius=10,
        options=[
            ft.dropdown.Option("1.2", "Sedentary (Little or no exercise)"),
            ft.dropdown.Option("1.375", "Lightly Active (1-3 days/week)"),
            ft.dropdown.Option("1.55", "Moderately Active (3-5 days/week)"),
            ft.dropdown.Option("1.725", "Very Active (6-7 days/week)"),
        ],
        value="1.375"
    )
    fitness_goal_radio = ft.RadioGroup(
        content=ft.Row([
            ft.Radio(value="cut", label="Lose Weight (-500 kcal)"),
            ft.Radio(value="maintain", label="Maintain"),
            ft.Radio(value="bulk", label="Build Muscle (+500 kcal)")
        ], alignment=ft.MainAxisAlignment.CENTER),
        value="maintain"
    )

    # Step 3 Controls: Location & Sponsors
    region_dropdown = ft.Dropdown(
        label="Select Your Region",
        border_radius=10,
        options=[
            ft.dropdown.Option("US_EAST", "United States (East Coast)"),
            ft.dropdown.Option("US_WEST", "United States (West Coast)"),
            ft.dropdown.Option("UK_MAIN", "United Kingdom"),
            ft.dropdown.Option("EU_CENTRAL", "Central Europe"),
        ],
        value="US_EAST"
    )
    
    sponsor_display = ft.Column(spacing=10, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    wizard_content = ft.Container()
    status_msg = ft.Text("", color=ft.Colors.ERROR, size=12)

    # Localized Sponsorship Mapping Data Store
    SPONSOR_REGIONS = {
        "US_EAST": [
            {"name": "Apex Fuel Meal Prep", "desc": "Get 15% off locally sourced macro-exact meals.", "promo": "BITE15"},
            {"name": "Metro Athletics", "desc": "Free day pass at any tri-state area facility.", "promo": "METROFIT"}
        ],
        "US_WEST": [
            {"name": "Pacific Clean Eats", "desc": "Free organic protein shake with your first delivery.", "promo": "PACIFICCLEAN"},
            {"name": "Vanguard Gyms", "desc": "Waived sign-up fees at all West Coast hubs.", "promo": "VANGUARD"}
        ],
        "UK_MAIN": [
            {"name": "British Beef Boxes", "desc": "£10 off high-protein grass-fed lean meat bundles.", "promo": "UKPROTEIN"}
        ],
        "EU_CENTRAL": [
            {"name": "EuroPrep Nutrition", "desc": "10% off high-protein local catering alternatives.", "promo": "EURO10"}
        ]
    }

    def calculate_macro_targets():
        """Executes client-side fitness formulation tracking algorithms."""
        try:
            age = int(age_field.value)
            weight = float(weight_field.value)
            height = float(height_field.value)
            activity = float(activity_dropdown.value)
        except (ValueError, TypeError):
            return None

        # Mifflin-St Jeor BMR formulation model
        if gender_radio.value == "male":
            bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
        else:
            bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161

        tdee = bmr * activity

        # Goal adjustment criteria offsets
        goal = fitness_goal_radio.value
        if goal == "cut":
            target_calories = int(tdee - 500)
        elif goal == "bulk":
            target_calories = int(tdee + 500)
        else:
            target_calories = int(tdee)

        # Standard Macro Distribution Split (40% Carbs / 30% Protein / 30% Fat)
        # Protein/Carbs = 4 kcal/g, Fat = 9 kcal/g
        protein_g = int((target_calories * 0.30) / 4)
        carbs_g = int((target_calories * 0.40) / 4)
        fat_g = int((target_calories * 0.30) / 9)

        return UserGoals(
            daily_calories=max(1200, target_calories),  # Floor limit to maintain baseline safety margins
            daily_protein=max(50, protein_g),
            daily_carbs=max(50, carbs_g),
            daily_fat=max(30, fat_g)
        )

    def render_step_view():
        """Updates layout configurations across onboarding phases dynamically."""
        status_msg.value = ""
        if current_step == 0:
            wizard_content.content = ft.Column([
                ft.Text("Step 1: Your Biometrics", size=18, weight="bold"),
                age_field,
                ft.Text("Gender:", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                gender_radio,
                weight_field,
                height_field,
            ], spacing=14)
        elif current_step == 1:
            wizard_content.content = ft.Column([
                ft.Text("Step 2: Activity & Objectives", size=18, weight="bold"),
                activity_dropdown,
                ft.Text("Primary Fitness Target Direction:", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                fitness_goal_radio,
            ], spacing=14)
        elif current_step == 2:
            # Query and display localized sponsorship matches based on region selection
            local_deals = SPONSOR_REGIONS.get(region_dropdown.value, [])
            sponsor_display.controls = [
                ft.Container(
                    content=ft.Column([
                        ft.Text(deal["name"], weight="bold", size=14, color="#00E5FF"),
                        ft.Text(deal["desc"], size=12),
                        ft.Container(
                            content=ft.Text(f"Code: {deal['promo']}", size=11, weight="bold", color="#181D26"),
                            bgcolor="#00E5FF", padding=4, border_radius=4
                        )
                    ]),
                    padding=12, border_radius=8, bgcolor="#222A35"
                ) for deal in local_deals
            ]
            
            wizard_content.content = ft.Column([
                ft.Text("Step 3: Location Matchmaking", size=18, weight="bold"),
                ft.Text("We leverage your high-level region parameters to populate local discounts.", size=12),
                region_dropdown,
                ft.Divider(color="#222A35"),
                ft.Text("Exclusive Local Partner Sponsors Available In Your Region:", size=13, weight="semibold"),
                sponsor_display,
            ], spacing=14)

    def on_next(e):
        nonlocal current_step
        if current_step == 0:
            if not age_field.value or not weight_field.value or not height_field.value or not gender_radio.value:
                status_msg.value = "Please complete all fields to proceed."
                page.update()
                return
            current_step = 1
        elif current_step == 1:
            current_step = 2
        elif current_step == 2:
            # Complete the survey flow and save values client-side
            calculated_goals = calculate_macro_targets()
            if calculated_goals:
                state.db.save_goals(calculated_goals)
                state.refresh_goals()
            
            # (Optional) Cache selected regional identifier into your local DB context here
            page.go("/")
            return
            
        render_step_view()
        page.update()

    def on_prev(e):
        nonlocal current_step
        if current_step > 0:
            current_step -= 1
            render_step_view()
            page.update()

    # Re-trigger data assembly rendering profiles dynamically upon dropdown changes
    region_dropdown.on_change = lambda e: render_step_view() or page.update()

    # Seed the initial wizard layout view configuration
    render_step_view()

    return ft.View(
        route="/survey",
        controls=[
            ft.AppBar(
                title=ft.Text("Setup Onboarding Engine"),
                leading=ft.IconButton(content=ft.Icon(ft.Icons.ARROW_BACK), on_click=lambda e: page.go("/")),
            ),
            ft.Container(
                content=ft.Column([
                    wizard_content,
                    status_msg,
                    ft.Row([
                        ft.TextButton("Back", on_click=on_prev),
                        ft.FilledButton("Continue", icon=ft.Icons.NAVIGATE_NEXT, on_click=on_next)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                ], spacing=20, scroll=ft.ScrollMode.AUTO),
                padding=20,
                expand=True
            )
        ]
    )