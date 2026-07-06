"""
Barcode / Ingredient Lookup view.

Exercises the two free public food-database pathways directly (no Gemini
call needed at all here, so it's the cheapest possible logging path):
- Open Food Facts for packaged products (scan/type a barcode)
- USDA FoodData Central for raw ingredients (search by name)
"""

import flet as ft

from app import food_apis
from app.state import AppState
from app.views.widgets import error_banner, loading_view


def build_lookup_view(page: ft.Page, state: AppState) -> ft.View:
    tabs_content = ft.Container()

    barcode_field = ft.TextField(
        label="Barcode (UPC/EAN)", hint_text="e.g. 3017620422003", border_radius=10
    )
    usda_field = ft.TextField(
        label="Ingredient name", hint_text="e.g. chicken breast, raw", border_radius=10
    )
    results_area = ft.Column(spacing=8)

    async def on_barcode_search(e):
        code = barcode_field.value.strip()
        if not code:
            return
        results_area.controls = [loading_view("Looking up Open Food Facts...")]
        page.update()
        try:
            product = await food_apis.lookup_barcode(code)
        except food_apis.FoodApiError as exc:
            results_area.controls = [error_banner(str(exc))]
            page.update()
            return
        results_area.controls = [_product_card(product, state, page)]
        page.update()

    async def on_usda_search(e):
        query = usda_field.value.strip()
        if not query:
            return
        results_area.controls = [loading_view("Searching USDA FoodData Central...")]
        page.update()
        try:
            matches = await food_apis.search_usda(query)
        except food_apis.FoodApiError as exc:
            results_area.controls = [error_banner(str(exc))]
            page.update()
            return
        results_area.controls = [_ingredient_card(m, state, page) for m in matches]
        page.update()

    def build_barcode_tab():
        return ft.Column(
            [
                ft.Row([ft.Container(barcode_field, expand=True), ft.IconButton(ft.Icons.SEARCH, on_click=on_barcode_search)]),
                ft.Text(
                    "Looks up packaged products via Open Food Facts (free, no key required).",
                    size=11,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
            ],
            spacing=10,
        )

    def build_usda_tab():
        return ft.Column(
            [
                ft.Row([ft.Container(usda_field, expand=True), ft.IconButton(ft.Icons.SEARCH, on_click=on_usda_search)]),
                ft.Text(
                    "Looks up raw ingredients via USDA FoodData Central (per 100g).",
                    size=11,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
            ],
            spacing=10,
        )

    def on_tab_change(e):
        tabs_content.content = build_barcode_tab() if e.control.selected_index == 0 else build_usda_tab()
        results_area.controls = []
        page.update()

    tabs = ft.Tabs(
        selected_index=0,
        on_change=on_tab_change,
        tabs=[ft.Tab(text="Barcode"), ft.Tab(text="Ingredient Search")],
    )
    tabs_content.content = build_barcode_tab()

    return ft.View(
        route="/lookup",
        controls=[
            ft.AppBar(
                title=ft.Text("Lookup"),
                leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda e: page.go("/")),
            ),
            ft.Container(
                content=ft.Column(
                    [tabs, tabs_content, ft.Divider(), results_area],
                    spacing=14,
                    scroll=ft.ScrollMode.AUTO,
                ),
                padding=20,
                expand=True,
            ),
        ],
    )


def _product_card(product, state: AppState, page: ft.Page) -> ft.Control:
    def on_log(e):
        state.set_pending(product.per_100g, source="barcode")
        page.go("/confirm")

    subtitle = f"{product.brand} • per 100g: {product.per_100g.calories} kcal" if product.brand else (
        f"per 100g: {product.per_100g.calories} kcal"
    )
    return ft.Container(
        content=ft.Row(
            [
                ft.Column(
                    [ft.Text(product.name, weight=ft.FontWeight.W_600), ft.Text(subtitle, size=12)],
                    expand=True,
                ),
                ft.IconButton(ft.Icons.ADD_CIRCLE_OUTLINE, on_click=on_log, tooltip="Log this"),
            ]
        ),
        padding=12,
        border_radius=12,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
    )


def _ingredient_card(breakdown, state: AppState, page: ft.Page) -> ft.Control:
    def on_log(e):
        state.set_pending(breakdown, source="barcode")
        page.go("/confirm")

    return ft.Container(
        content=ft.Row(
            [
                ft.Column(
                    [
                        ft.Text(breakdown.meal_name, weight=ft.FontWeight.W_600),
                        ft.Text(
                            f"per 100g: {breakdown.calories} kcal • "
                            f"P{breakdown.protein} C{breakdown.carbs} F{breakdown.fat}",
                            size=12,
                        ),
                    ],
                    expand=True,
                ),
                ft.IconButton(ft.Icons.ADD_CIRCLE_OUTLINE, on_click=on_log, tooltip="Log this"),
            ]
        ),
        padding=12,
        border_radius=12,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
    )
