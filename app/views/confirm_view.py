"""
Log Confirmation View.
Tracks entries by fractional or whole serving units (multipliers) rather than raw grams,
and ensures a hard refresh layout sweep back to the primary dashboard.
"""
import logging

import flet as ft

from app import theme

logger = logging.getLogger(__name__)

def build_confirm_view(page: ft.Page, state) -> ft.View:
    # 1. Safely retrieve the staged Pydantic object from your updated AppState memory
    item = getattr(state, "pending_breakdown", None)

    if not item:
        return ft.View(
            route="/confirm",
            bgcolor=theme.BG_CANVAS,
            controls=[
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.WARNING_ROUNDED, color=theme.ERROR, size=48),
                        ft.Text("No meal to confirm yet.", color=theme.ERROR, size=14),
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

    # 3. Editable fields so the user can correct what the AI guessed
    name_field = ft.TextField(
        value=meal_name,
        text_align=ft.TextAlign.CENTER,
        text_size=20,
        text_style=ft.TextStyle(weight="bold"),
        **theme.styled_field(),
    )
    subtitle_txt = ft.Text(f"Estimated Base Unit: {serving_desc}", color=theme.TEXT_FAINT, size=12)

    def _numeric_field(value: int, color: str) -> ft.TextField:
        return ft.TextField(
            value=str(value),
            keyboard_type=ft.KeyboardType.NUMBER,
            text_align=ft.TextAlign.CENTER,
            width=110,
            color=color,
            **theme.styled_field(),
        )

    calories_field = _numeric_field(base_calories, theme.ACCENT)
    protein_field = _numeric_field(base_protein, theme.PROTEIN)
    carbs_field = _numeric_field(base_carbs, theme.CARBS)
    fat_field = _numeric_field(base_fat, theme.FAT)

    status_msg = ft.Text("", color=theme.ACCENT, size=12)

    def _parse_int(value: str, fallback: int) -> int:
        try:
            return int(round(float(value)))
        except (TypeError, ValueError):
            return fallback

    # 4. Slider mutation action scales nutritional vectors dynamically,
    # overwriting whatever is currently in the editable fields
    def slider_changed(e):
        servings_multiplier = slider.value
        slider_label.value = f"Quantity: {round(servings_multiplier, 2)} servings"

        # Multiply baseline numbers by the fractional metric slider positions
        calories_field.value = str(int(base_calories * servings_multiplier))
        protein_field.value = str(int(base_protein * servings_multiplier))
        carbs_field.value = str(int(base_carbs * servings_multiplier))
        fat_field.value = str(int(base_fat * servings_multiplier))
        page.update()

    # The slider handles fractional steps beautifully (0.1 increments)
    slider = ft.Slider(
        min=0.1,
        max=5.0,
        divisions=49,
        value=1.0,
        label="{value}x servings",
        on_change=slider_changed,
        thumb_color=theme.ACCENT,
        active_color=theme.ACCENT
    )
    slider_label = ft.Text("Quantity: 1.0 serving", weight="w500", color=theme.TEXT_MUTED, size=13)

    # 5. Async-wrapped database execution to prevent main event-loop thread blocking
    async def confirm_and_save(e):
        try:
            status_msg.value = "Saving..."
            page.update()

            # Read directly from the editable fields so manual corrections win
            final_cal = _parse_int(calories_field.value, base_calories)
            final_pro = _parse_int(protein_field.value, base_protein)
            final_carb = _parse_int(carbs_field.value, base_carbs)
            final_fat = _parse_int(fat_field.value, base_fat)

            display_name = name_field.value.strip() or meal_name

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

            status_msg.value = "Logged!"
            page.update()
            
            # --- FLUSH THE VIEW STACK TO FORCE FRESH INLINE RENDERING ---
            if len(page.views) > 1:
                page.views.pop()
                
            page.go("/")
            
        except Exception as err:
            logger.error("Couldn't save logged entry: %s", err)
            status_msg.value = "Couldn't save -- please try again."
            page.update()

    return ft.View(
        route="/confirm",
        bgcolor=theme.BG_CANVAS,
        controls=[
            ft.Container(
                content=ft.Column([
                    ft.Divider(color="transparent", height=20),
                    ft.Container(name_field, width=280),
                    subtitle_txt,
                    ft.Divider(color=theme.BORDER, height=30),

                    ft.Column(
                        [ft.Text("Calories (kcal)", size=11, color=theme.TEXT_MUTED), calories_field],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=4,
                    ),
                    ft.Divider(color="transparent", height=10),
                    ft.Row([
                        ft.Column(
                            [ft.Text("Protein (g)", size=11, color=theme.TEXT_MUTED), protein_field],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4,
                        ),
                        ft.Column(
                            [ft.Text("Carbs (g)", size=11, color=theme.TEXT_MUTED), carbs_field],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4,
                        ),
                        ft.Column(
                            [ft.Text("Fat (g)", size=11, color=theme.TEXT_MUTED), fat_field],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4,
                        ),
                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=20),

                    ft.Divider(color="transparent", height=30),

                    # Intermediary Slider Matrix Container
                    ft.Container(
                        content=ft.Column([
                            slider_label,
                            slider,
                        ], spacing=10, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        padding=20,
                        bgcolor=theme.BG_SURFACE,
                        border_radius=theme.RADIUS_MD,
                        border=ft.border.all(1, theme.BORDER)
                    ),

                    ft.Divider(color="transparent", height=10),
                    status_msg,
                    ft.Divider(color="transparent", height=10),

                    theme.primary_button(
                        "Log to Timeline",
                        icon=ft.Icons.CHECK,
                        on_click=lambda e: page.run_task(confirm_and_save, e),  # Explicitly forwarding event e
                        width=float("inf"),
                    ),
                    ft.TextButton(
                        "Cancel Entry",
                        style=ft.ButtonStyle(color=theme.TEXT_MUTED),
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