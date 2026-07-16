"""
Survey and Onboarding Target Calculator View.
Calculates macro baseline targets from biometrics (Mifflin-St Jeor + TDEE).
"""

import flet as ft
from app import theme
from app.models import UserGoals

LB_PER_KG = 2.20462
CM_PER_IN = 2.54


def _to_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_survey_view(page: ft.Page, state) -> ft.View:
    saved = state.get_profile_data() if hasattr(state, "get_profile_data") else {}

    # Track the active wizard step: 0=Biometrics, 1=Activity & Goals
    current_step = 0

    # Step 1 Controls: Biometrics
    age_field = ft.TextField(
        label="Age (years)", hint_text="e.g. 28",
        value=str(saved.get("age", "")) if saved.get("age") else "",
        **theme.styled_field(),
    )
    gender_radio = ft.RadioGroup(
        content=ft.Row([
            ft.Radio(value="male", label="Male"),
            ft.Radio(value="female", label="Female")
        ], alignment=ft.MainAxisAlignment.CENTER),
        value=saved.get("gender"),
    )

    unit_toggle = ft.RadioGroup(
        content=ft.Row([
            ft.Radio(value="metric", label="Metric (kg / cm)"),
            ft.Radio(value="imperial", label="Imperial (lb / ft+in)"),
        ], alignment=ft.MainAxisAlignment.CENTER),
        value=saved.get("unit_system", "metric"),
    )

    weight_kg_field = ft.TextField(
        label="Current Weight (kg)", hint_text="e.g. 75",
        value=str(saved.get("weight_kg", "")) if saved.get("weight_kg") else "",
        **theme.styled_field(),
    )
    height_cm_field = ft.TextField(
        label="Height (cm)", hint_text="e.g. 178",
        value=str(saved.get("height_cm", "")) if saved.get("height_cm") else "",
        **theme.styled_field(),
    )
    weight_lb_field = ft.TextField(
        label="Current Weight (lb)", hint_text="e.g. 165",
        value=str(saved.get("weight_lb", "")) if saved.get("weight_lb") else "",
        **theme.styled_field(),
    )
    height_ft_field = ft.TextField(
        label="Height (ft)", hint_text="e.g. 5", expand=True,
        value=str(saved.get("height_ft", "")) if saved.get("height_ft") else "",
        **theme.styled_field(),
    )
    height_in_field = ft.TextField(
        label="Height (in)", hint_text="e.g. 10", expand=True,
        value=str(saved.get("height_in", "")) if saved.get("height_in") else "",
        **theme.styled_field(),
    )

    # Step 2 Controls: Activity & Goals
    activity_dropdown = ft.Dropdown(
        label="Activity Level",
        **theme.styled_dropdown(),
        options=[
            ft.dropdown.Option("1.2", "Sedentary (Little or no exercise)"),
            ft.dropdown.Option("1.375", "Lightly Active (1-3 days/week)"),
            ft.dropdown.Option("1.55", "Moderately Active (3-5 days/week)"),
            ft.dropdown.Option("1.725", "Very Active (6-7 days/week)"),
            ft.dropdown.Option("1.9", "Extremely Active (hard exercise + physical job)"),
        ],
        value=str(saved.get("activity", "1.375")),
    )
    fitness_goal_radio = ft.RadioGroup(
        content=ft.Column([
            ft.Radio(value="cut", label="Lose Weight (-300 to -500 kcal)"),
            ft.Radio(value="maintain", label="Maintain"),
            ft.Radio(value="bulk", label="Build Muscle (+200 to +300 kcal)")
        ], spacing=4),
        value=saved.get("goal", "maintain"),
    )

    wizard_content = ft.Container()
    status_msg = ft.Text("", color=theme.ERROR, size=12)

    def calculate_macro_targets():
        """Mifflin-St Jeor BMR -> TDEE -> goal-adjusted calories -> macros.

        Macros are derived in priority order (protein, then fat, then carbs)
        rather than as a flat calorie-percentage split, per the standard
        recomp/cut/bulk guidance: protein is set first from bodyweight to
        protect muscle, fat gets a fixed slice for hormone health, and carbs
        fill whatever calorie budget is left.
        """
        try:
            age = int(age_field.value)
            activity = float(activity_dropdown.value)

            if unit_toggle.value == "imperial":
                weight_lb = float(weight_lb_field.value)
                weight_kg = weight_lb / LB_PER_KG
                feet = float(height_ft_field.value)
                inches = _to_float(height_in_field.value, 0) or 0
                height_cm = (feet * 12 + inches) * CM_PER_IN
            else:
                weight_kg = float(weight_kg_field.value)
                height_cm = float(height_cm_field.value)
        except (ValueError, TypeError):
            return None

        # Mifflin-St Jeor BMR formulation model
        if gender_radio.value == "male":
            bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) + 5
        else:
            bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) - 161

        tdee = bmr * activity

        # Goal adjustment: midpoint of the recommended range
        # (weight loss: -300 to -500 kcal, muscle gain: +200 to +300 kcal)
        goal = fitness_goal_radio.value
        if goal == "cut":
            target_calories = tdee - 400
        elif goal == "bulk":
            target_calories = tdee + 250
        else:
            target_calories = tdee
        target_calories = max(1200, int(target_calories))  # Floor limit to maintain baseline safety margins

        # Protein first: 1.0 g per pound of bodyweight, the midpoint of the
        # recommended 0.8-1.2 g/lb range. Protein/Carbs = 4 kcal/g.
        weight_lb_total = weight_kg * LB_PER_KG
        protein_g = round(weight_lb_total * 1.0)
        protein_cal = protein_g * 4

        # Fat next: 25% of total calories, the midpoint of the 20-30% range.
        # Fat = 9 kcal/g.
        fat_cal = target_calories * 0.25
        fat_g = round(fat_cal / 9)

        # Carbs fill whatever calorie budget remains.
        carb_cal = max(0, target_calories - protein_cal - fat_cal)
        carbs_g = round(carb_cal / 4)

        return UserGoals(
            daily_calories=target_calories,
            daily_protein=max(50, protein_g),
            daily_carbs=max(50, carbs_g),
            daily_fat=max(30, fat_g)
        )

    def biometrics_fields_ok() -> bool:
        if not age_field.value or not gender_radio.value:
            return False
        if unit_toggle.value == "imperial":
            return bool(weight_lb_field.value and height_ft_field.value)
        return bool(weight_kg_field.value and height_cm_field.value)

    def render_step_view():
        """Updates layout configurations across onboarding phases dynamically."""
        status_msg.value = ""
        if current_step == 0:
            if unit_toggle.value == "imperial":
                weight_height_controls = [
                    weight_lb_field,
                    ft.Row([height_ft_field, height_in_field], spacing=10),
                ]
            else:
                weight_height_controls = [weight_kg_field, height_cm_field]

            wizard_content.content = ft.Column([
                ft.Text("Step 1: Your Biometrics", size=18, weight="bold"),
                unit_toggle,
                age_field,
                ft.Text("Gender:", size=12, color=theme.TEXT_MUTED),
                gender_radio,
                *weight_height_controls,
            ], spacing=14)
        elif current_step == 1:
            wizard_content.content = ft.Column([
                ft.Text("Step 2: Activity & Objectives", size=18, weight="bold"),
                activity_dropdown,
                ft.Text("Primary Fitness Target Direction:", size=12, color=theme.TEXT_MUTED),
                fitness_goal_radio,
            ], spacing=14)

    def on_next(e):
        nonlocal current_step
        if current_step == 0:
            if not biometrics_fields_ok():
                status_msg.value = "Please complete all fields to proceed."
                page.update()
                return
            current_step = 1
        elif current_step == 1:
            # Complete the survey flow: calculate + save goals, then remember
            # every input so this screen can pre-fill itself next time.
            calculated_goals = calculate_macro_targets()
            if calculated_goals is None:
                status_msg.value = "Couldn't calculate your targets — please check your biometric entries."
                status_msg.color = theme.ERROR
                page.update()
                return

            saved_ok, save_err = state.db.save_goals(calculated_goals)
            if not saved_ok:
                status_msg.value = f"Couldn't save your targets: {save_err}"
                status_msg.color = theme.ERROR
                page.update()
                return

            state.refresh_goals()

            profile_snapshot = {
                "age": _to_float(age_field.value),
                "gender": gender_radio.value,
                "unit_system": unit_toggle.value,
                "activity": activity_dropdown.value,
                "goal": fitness_goal_radio.value,
            }
            if unit_toggle.value == "imperial":
                profile_snapshot["weight_lb"] = _to_float(weight_lb_field.value)
                profile_snapshot["height_ft"] = _to_float(height_ft_field.value)
                profile_snapshot["height_in"] = _to_float(height_in_field.value, 0)
            else:
                profile_snapshot["weight_kg"] = _to_float(weight_kg_field.value)
                profile_snapshot["height_cm"] = _to_float(height_cm_field.value)

            if hasattr(state, "save_profile_data"):
                state.save_profile_data(profile_snapshot)

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

    def on_unit_change(e):
        render_step_view()
        page.update()

    unit_toggle.on_change = on_unit_change

    # Seed the initial wizard layout view configuration
    render_step_view()

    return ft.View(
        route="/survey",
        bgcolor=theme.BG_CANVAS,
        controls=[
            theme.app_bar("Setup Onboarding Engine", on_back=lambda e: page.go("/")),
            ft.Container(
                content=ft.Column([
                    wizard_content,
                    status_msg,
                    ft.Row([
                        ft.TextButton("Back", style=ft.ButtonStyle(color=theme.TEXT_MUTED), on_click=on_prev),
                        theme.primary_button("Continue", icon=ft.Icons.NAVIGATE_NEXT, on_click=on_next)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                ], spacing=20, scroll=ft.ScrollMode.AUTO),
                padding=20,
                expand=True
            )
        ]
    )
