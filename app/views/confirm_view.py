"""
Log Confirmation View.
Tracks entries by fractional or whole serving units (multipliers) rather than raw grams,
and ensures a hard refresh layout sweep back to the primary dashboard.
"""
import flet as ft

def build_confirm_view(page: ft.Page, state) -> ft.View:
    # 1. Safely retrieve the staged item payload from state memory
    item = getattr(state, "pending_item", None)
    
    if not item:
        return ft.View(
            route="/confirm",
            controls=[
                ft.AppBar(title=ft.Text("Confirm Log")),
                ft.Container(
                    content=ft.Column([
                        ft.Text("No food item was found staged for logging.", color=ft.Colors.ERROR),
                        ft.ElevatedButton("Return Home", on_click=lambda _: page.go("/"))
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=20, alignment=ft.alignment.center, expand=True
                )
            ]
        )

    # 2. Extract base nutrient payloads from our pending object dictionary mapping
    base_calories = getattr(item, "calories", 0) or 0
    base_protein = getattr(item, "protein", 0) or 0
    base_carbs = getattr(item, "carbs", 0) or 0
    base_fat = getattr(item, "fat", 0) or 0
    meal_name = getattr(item, "meal_name", "Logged Food Context")
    
    # Try to extract a human-readable serving description if provided by the API (e.g., "1 cup (240g)")
    serving_desc = getattr(item, "serving_size_text", None) or getattr(item, "serving_description", "1 Standard Serving")

    # 3. Dynamic layout text nodes
    title_txt = ft.Text(meal_name, size=22, weight="bold")
    subtitle_txt = ft.Text(f"Base unit: {serving_desc}", color="#7A8B9E", size=13)

    calc_calories = ft.Text(f"{base_calories} kcal", size=28, weight="bold", color="#00E5FF")
    calc_protein = ft.Text(f"Protein: {base_protein}g", size=13, weight="semibold", color="#FF5252")
    calc_carbs = ft.Text(f"Carbs: {base_carbs}g", size=13, weight="semibold", color="#4CAF50")
    calc_fat = ft.Text(f"Fat: {base_fat}g", size=13, weight="semibold", color="#FFC107")

    status_msg = ft.Text("", color="#00E5FF")

    # 4. Slider action changes state based purely on fractional serving quantities
    def slider_changed(e):
        servings_multiplier = slider.value
        slider_label.value = f"Quantity: {round(servings_multiplier, 2)} servings"
        
        # Scale nutritional macros directly by the chosen number of servings
        calc_calories.value = f"{int(base_calories * servings_multiplier)} kcal"
        calc_protein.value = f"Protein: {int(base_protein * servings_multiplier)}g"
        calc_carbs.value = f"Carbs: {int(base_carbs * servings_multiplier)}g"
        calc_fat.value = f"Fat: {int(base_fat * servings_multiplier)}g"
        page.update()

    # The slider handles fractional iterations (e.g., 0.5 servings up to 5.0 packages)
    slider = ft.Slider(
        min=0.1, 
        max=5.0, 
        divisions=49,  # Steps neatly every 0.1 increments
        value=1.0, 
        label="{value}x servings", 
        on_change=slider_changed
    )
    slider_label = ft.Text("Quantity: 1.0 serving", weight="w500")

    def confirm_and_save(e):
        try:
            servings_multiplier = slider.value

            final_cal = int(base_calories * servings_multiplier)
            final_pro = int(base_protein * servings_multiplier)
            final_carb = int(base_carbs * servings_multiplier)
            final_fat = int(base_fat * servings_multiplier)
            
            # Format title string with serving context for timeline clarity
            display_name = f"{meal_name} ({round(servings_multiplier, 1)} serv)"

            # --- ENGINE WRITE ---
            # Call your application logging pipelines
            if hasattr(state, "add_log"):
                state.add_log(display_name, final_cal, final_pro, final_carb, final_fat)
            elif hasattr(state, "log_food"):
                state.log_food(display_name, final_cal, final_pro, final_carb, final_fat)
            elif hasattr(state, "db") and state.db:
                write_func = getattr(state.db, "log_food", getattr(state.db, "save_log", None))
                if write_func:
                    write_func(display_name, final_cal, final_pro, final_carb, final_fat)

            # --- HARD CACHE REFRESH LAYER ---
            # Re-pull database data right now before going back to the home view
            if hasattr(state, "refresh_logs"):
                state.refresh_logs()
            elif hasattr(state, "load_daily_logs"):
                state.load_daily_logs()

            status_msg.value = "Food successfully added!"
            page.update()
            
            # --- CLEAR VIEW STACK TO FORCE RE-RENDER ---
            # To prevent Flet from showing cached old timeline contents, pop the current view manually
            if len(page.views) > 1:
                page.views.pop()
                
            # Direct routing change back to home
            page.go("/")
            
        except Exception as err:
            status_msg.value = f"Failed to log item: {str(err)}"
            page.update()

    return ft.View(
        route="/confirm",
        controls=[
            ft.AppBar(title=ft.Text("Confirm Entry")),
            ft.Container(
                content=ft.Column([
                    title_txt,
                    subtitle_txt,
                    ft.Divider(color="#222A35", height=30),
                    
                    calc_calories,
                    ft.Row([
                        calc_protein,
                        calc_carbs,
                        calc_fat
                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=15),
                    
                    ft.Divider(color="transparent", height=20),
                    slider_label,
                    slider,
                    
                    status_msg,
                    ft.Divider(color="transparent", height=15),
                    
                    ft.FilledButton(
                        "Log to Timeline", 
                        icon=ft.Icons.CHECK, 
                        on_click=confirm_and_save, 
                        width=220, 
                        style=ft.ButtonStyle(bgcolor="#00E5FF", color="#181D26")
                    )
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=20, alignment=ft.alignment.center, expand=True
            )
        ]
    )