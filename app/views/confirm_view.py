"""
Log Confirmation View.
Tracks entries by fractional or whole serving units (multipliers) rather than raw grams,
and ensures a hard refresh layout sweep back to the primary dashboard.
"""
import flet as ft

def build_confirm_view(page: ft.Page, state) -> ft.View:
    # 1. Safely retrieve the staged Pydantic object from your updated AppState memory
    item = getattr(state, "pending_breakdown", None)
    
    if not item:
        return ft.View(
            route="/confirm",
            bgcolor="#06090F",
            controls=[
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.WARNING_ROUNDED, color="#FF5252", size=48),
                        ft.Text("No nutritional payload found staged for validation.", color="#FF5252", size=14),
                        ft.Divider(color="transparent", height=10),
                        ft.TextButton("Return to Dashboard", on_click=lambda _: page.go("/"))
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=20, alignment=ft.alignment.center, expand=True
                )
            ]
        )

    # 2. Extract base nutrient attributes directly using standard object property lookup syntax
    base_calories = getattr(item, "calories", 0) or 0
    base_protein = getattr(item, "protein", 0) or 0
    base_carbs = getattr(item, "carbs", 0) or 0
    base_fat = getattr(item, "fat", 0) or 0
    meal_name = getattr(item, "meal_name", "Logged Food Item")
    
    # Check if a specific portion breakdown array exists inside the structure
    portion_list = getattr(item, "identified_items", [])
    if portion_list and len(portion_list) > 0:
        serving_desc = portion_list[0].portion_size or "1 Standard Serving"
    else:
        serving_desc = "1 Standard Serving"

    # 3. Dynamic layout typography nodes matching the dark minimalist theme
    title_txt = ft.Text(meal_name.upper(), size=20, weight="bold")
    subtitle_txt = ft.Text(f"Estimated Base Unit: {serving_desc}", color="#506173", size=12)

    calc_calories = ft.Text(f"{base_calories} kcal", size=32, weight="bold", color="#00E5FF")
    calc_protein = ft.Text(f"Protein: {base_protein}g", size=13, weight="semibold", color="#FF5252")
    calc_carbs = ft.Text(f"Carbs: {base_carbs}g", size=13, weight="semibold", color="#4CAF50")
    calc_fat = ft.Text(f"Fat: {base_fat}g", size=13, weight="semibold", color="#FFC107")

    status_msg = ft.Text("", color="#00E5FF", size=12)

    # 4. Slider mutation action scales nutritional vectors dynamically
    def slider_changed(e):
        servings_multiplier = slider.value
        slider_label.value = f"Quantity: {round(servings_multiplier, 2)} servings"
        
        # Multiply baseline numbers by the fractional metric slider positions
        calc_calories.value = f"{int(base_calories * servings_multiplier)} kcal"
        calc_protein.value = f"Protein: {int(base_protein * servings_multiplier)}g"
        calc_carbs.value = f"Carbs: {int(base_carbs * servings_multiplier)}g"
        calc_fat.value = f"Fat: {int(base_fat * servings_multiplier)}g"
        page.update()

    # The slider handles fractional steps beautifully (0.1 increments)
    slider = ft.Slider(
        min=0.1, 
        max=5.0, 
        divisions=49,  
        value=1.0, 
        label="{value}x servings", 
        on_change=slider_changed,
        thumb_color="#00E5FF",
        active_color="#00E5FF"
    )
    slider_label = ft.Text("Quantity: 1.0 serving", weight="w500", color="#7A8B9E", size=13)

    # 5. Async-wrapped database execution to prevent main event-loop thread blocking
    async def confirm_and_save(e):
        try:
            status_msg.value = "Synchronizing encrypted database fields..."
            page.update()

            servings_multiplier = slider.value
            final_cal = int(base_calories * servings_multiplier)
            final_pro = int(base_protein * servings_multiplier)
            final_carb = int(base_carbs * servings_multiplier)
            final_fat = int(base_fat * servings_multiplier)
            
            # Format display string with serving multipliers for cleaner historical logs
            display_name = f"{meal_name} ({round(servings_multiplier, 1)}x)"

            # --- ENGINE WRITE TRANSACTIONS WITH ASYNC WORKER TASK HANDLING ---
            # Using state.log_food handles user auth parsing to clear RLS gates safely
            state.log_food(
                name=display_name,
                cal=final_cal,
                pro=final_pro,
                carb=final_carb,
                fat=final_fat
            )

            # --- HARD CACHE REFRESH LAYER ---
            # Trigger immediate background re-calculation of structural rolling data arrays
            state.refresh_logs()

            # --- PURGE TRANSIENT STAGING POINTERS ---
            state.pending_breakdown = None
            state.pending_source = None

            status_msg.value = "Food committed to cloud logs successfully!"
            page.update()
            
            # --- FLUSH THE VIEW STACK TO FORCE FRESH INLINE RENDERING ---
            if len(page.views) > 1:
                page.views.pop()
                
            page.go("/")
            
        except Exception as err:
            status_msg.value = f"Cloud Logging Error: {str(err)}"
            page.update()

    return ft.View(
        route="/confirm",
        bgcolor="#06090F",
        controls=[
            ft.Container(
                content=ft.Column([
                    ft.Divider(color="transparent", height=20),
                    title_txt,
                    subtitle_txt,
                    ft.Divider(color="#1C2431", height=30),
                    
                    calc_calories,
                    ft.Divider(color="transparent", height=10),
                    ft.Row([
                        calc_protein,
                        calc_carbs,
                        calc_fat
                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=20),
                    
                    ft.Divider(color="transparent", height=30),
                    
                    # Intermediary Slider Matrix Container
                    ft.Container(
                        content=ft.Column([
                            slider_label,
                            slider,
                        ], spacing=10, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        padding=20,
                        bgcolor="#0A0E17",
                        border_radius=16,
                        border=ft.border.all(1, "#1C2431")
                    ),
                    
                    ft.Divider(color="transparent", height=10),
                    status_msg,
                    ft.Divider(color="transparent", height=10),
                    
                    ft.FilledButton(
                        "Log to Timeline", 
                        icon=ft.Icons.CHECK, 
                        on_click=lambda e: page.run_task(confirm_and_save, e),  # Explicitly forwarding event e
                        width=float("inf"), 
                        style=ft.ButtonStyle(
                            bgcolor="#00E5FF", 
                            color="#0A0E17",
                            shape=ft.RoundedRectangleBorder(radius=12)
                        )
                    ),
                    ft.TextButton(
                        "Cancel Entry", 
                        style=ft.ButtonStyle(color="#7A8B9E"),
                        on_click=lambda _: [
                            setattr(state, "pending_breakdown", None),
                            page.go("/")
                        ]
                    )
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=24, alignment=ft.alignment.center, expand=True
            )
        ]
    )