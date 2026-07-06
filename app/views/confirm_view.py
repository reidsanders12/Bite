"""
Confirmation screen with the Correction Slider.

AI portion-size estimation from a photo (or even a text description) can be
off. Rather than re-calling Gemini, the slider scales calories/protein/
carbs/fat *locally* by a 0.5x-2.0x factor -- instant feedback, zero API cost.
"""

import flet as ft

from app.models import MacroBreakdown
from app.state import AppState
from app.views.widgets import macro_stat_chip


def build_confirm_view(page: ft.Page, state: AppState) -> ft.View:
    original: MacroBreakdown = state.pending_breakdown

    if original is None:
        # Nothing pending (e.g. user refreshed / navigated here directly) -- bounce home.
        return ft.View(
            route="/confirm",
            controls=[
                ft.AppBar(title=ft.Text("Confirm")),
                ft.Container(
                    content=ft.Text("Nothing to confirm. Log a meal first."),
                    padding=20,
                ),
            ],
        )

    scale_state = {"factor": 1.0}

    stats_row = ft.Row(spacing=10)
    items_column = ft.Column(spacing=4)
    meal_name_field = ft.TextField(
        label="Meal name", value=original.meal_name, border_radius=10
    )

    def render(factor: float):
        scaled = original.scaled(factor)
        stats_row.controls = [
            macro_stat_chip("Calories", scaled.calories, ft.Colors.DEEP_ORANGE, unit=""),
            macro_stat_chip("Protein", scaled.protein, ft.Colors.BLUE),
            macro_stat_chip("Carbs", scaled.carbs, ft.Colors.AMBER),
            macro_stat_chip("Fat", scaled.fat, ft.Colors.PURPLE),
        ]
        items_column.controls = [
            ft.Row(
                [
                    ft.Icon(ft.Icons.FIBER_MANUAL_RECORD, size=8, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text(f"{item.name} — {item.portion_size}", size=13),
                ],
                spacing=8,
            )
            for item in original.identified_items
        ] or [ft.Text("No individual items identified.", size=13, italic=True)]

    render(1.0)

    def on_slider_change(e):
        scale_state["factor"] = round(e.control.value, 2)
        slider_label.value = f"Portion size: {scale_state['factor']:.2f}x"
        render(scale_state["factor"])
        page.update()

    slider_label = ft.Text(f"Portion size: {scale_state['factor']:.2f}x", weight=ft.FontWeight.W_600)

    slider = ft.Slider(
        min=0.5,
        max=2.0,
        value=1.0,
        divisions=30,
        label="{value}x",
        on_change=on_slider_change,
        active_color=ft.Colors.DEEP_ORANGE,
    )

    def on_discard(e):
        state.clear_pending()
        page.go("/")

    def on_save(e):
        final = original.scaled(scale_state["factor"])
        final.meal_name = meal_name_field.value.strip() or final.meal_name
        state.db.add_log(final, source=state.pending_source, scale_factor=scale_state["factor"])
        state.clear_pending()
        page.snack_bar = ft.SnackBar(content=ft.Text(f"Logged {final.meal_name}!"))
        page.snack_bar.open = True
        page.go("/")

    return ft.View(
        route="/confirm",
        controls=[
            ft.AppBar(
                title=ft.Text("Confirm Meal"),
                leading=ft.IconButton(ft.Icons.CLOSE, on_click=on_discard),
            ),
            ft.Container(
                content=ft.Column(
                    [
                        meal_name_field,
                        stats_row,
                        ft.Divider(),
                        slider_label,
                        slider,
                        ft.Text(
                            "Drag to scale the estimated portion up or down -- "
                            "macros recalculate instantly, no extra AI call needed.",
                            size=11,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Divider(),
                        ft.Text("Identified items", weight=ft.FontWeight.W_600, size=13),
                        items_column,
                        ft.Container(height=10),
                        ft.FilledButton(
                            "Save to Log",
                            icon=ft.Icons.CHECK,
                            on_click=on_save,
                        ),
                        ft.OutlinedButton(
                            "Discard",
                            on_click=on_discard,
                        ),
                    ],
                    spacing=14,
                    scroll=ft.ScrollMode.AUTO,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                ),
                padding=20,
                expand=True,
            ),
        ],
    )
