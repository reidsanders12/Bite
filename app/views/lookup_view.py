"""
Barcode / Ingredient Lookup view with integrated Live Camera Barcode Scanning.

Exercises two free public food-database pathways:
- Open Food Facts for packaged products (scan/type a barcode)
- USDA FoodData Central for raw ingredients (search by name)
"""

import asyncio
import flet as ft

from app import food_apis
from app.state import AppState
from app.views.widgets import error_banner, loading_view
from app.views.snap_view import camera_manager  # Reuses the same central camera engine


def build_lookup_view(page: ft.Page, state: AppState) -> ft.View:
    # State tracking
    # 0 = Barcode, 1 = Ingredient Search
    current_tab = 0  
    camera_active = False

    tabs_content = ft.Container()

    barcode_field = ft.TextField(
        label="Barcode (UPC/EAN)", hint_text="e.g. 3017620422003", border_radius=10
    )
    usda_field = ft.TextField(
        label="Ingredient name", hint_text="e.g. chicken breast, raw", border_radius=10
    )
    
    # Target preview layout container for the camera frame stream
    barcode_stream_view = ft.Image(
        width=320, 
        height=200, 
        fit=ft.ImageFit.COVER, 
        border_radius=8,
        visible=False
    )
    
    scan_btn = ft.ElevatedButton(
        text="Live Scan Barcode", 
        icon=ft.Icons.CAMERA, 
        on_click=lambda e: toggle_barcode_camera()
    )
    
    results_area = ft.Column(spacing=8)

    async def on_barcode_search(e):
        # Stop scanner if running when search is executed manually
        stop_barcode_camera()
        
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

    # Bind field submissions to execution hooks
    barcode_field.on_submit = on_barcode_search
    usda_field.on_submit = on_usda_search

    async def handle_detected_barcode(scanned_code: str):
        barcode_field.value = scanned_code
        stop_barcode_camera()
        page.update()
        # Automatically run search pipeline upon detection
        await on_barcode_search(None)

    def toggle_barcode_camera():
            nonlocal camera_active
            if not camera_active:
                camera_active = True
                scan_btn.text = "Stop Scanner"
                scan_btn.icon = ft.Icons.CAMERA_FRONT
                barcode_stream_view.visible = True
                page.update()
                
                # Use page.run_task to spawn the coroutine on Flet's main event loop
                page.run_task(
                    camera_manager.stream_views, 
                    barcode_stream_view, 
                    "barcode", 
                    handle_detected_barcode
                )
            else:
                stop_barcode_camera()


    def stop_barcode_camera():
        nonlocal camera_active
        camera_active = False
        scan_btn.text = "Live Scan Barcode"
        scan_btn.icon = ft.Icons.CAMERA
        barcode_stream_view.visible = False
        camera_manager.stop_camera()
        page.update()

    def build_barcode_tab():
        return ft.Column(
            [
                ft.Row([
                    ft.Container(barcode_field, expand=True), 
                    ft.IconButton(content=ft.Icon(ft.Icons.SEARCH), on_click=on_barcode_search)
                ]),
                ft.Row([scan_btn], alignment=ft.MainAxisAlignment.CENTER),
                ft.Row([barcode_stream_view], alignment=ft.MainAxisAlignment.CENTER),
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
                ft.Row([
                    ft.Container(usda_field, expand=True), 
                    ft.IconButton(content=ft.Icon(ft.Icons.SEARCH), on_click=on_usda_search)
                ]),
                ft.Text(
                    "Looks up raw ingredients via USDA FoodData Central (per 100g).",
                    size=11,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
            ],
            spacing=10,
        )

    # Placeholders for custom segment triggers
    tab_barcode_btn = ft.Container(expand=True)
    tab_usda_btn = ft.Container(expand=True)

    def update_tab_ui():
        nonlocal current_tab
        # Kill the camera feed cleanly whenever tabs are switched
        stop_barcode_camera()
        
        if current_tab == 0:
            tab_barcode_btn.bgcolor = "#222A35"
            tab_barcode_btn.border = ft.border.all(1, "#00E5FF")
            tab_barcode_btn.content.controls[0].color = "#00E5FF"
            
            tab_usda_btn.bgcolor = "transparent"
            tab_usda_btn.border = None
            tab_usda_btn.content.controls[0].color = "#7A8B9E"
            tabs_content.content = build_barcode_tab()
        else:
            tab_usda_btn.bgcolor = "#222A35"
            tab_usda_btn.border = ft.border.all(1, "#00E5FF")
            tab_usda_btn.content.controls[0].color = "#00E5FF"
            
            tab_barcode_btn.bgcolor = "transparent"
            tab_barcode_btn.border = None
            tab_barcode_btn.content.controls[0].color = "#7A8B9E"
            tabs_content.content = build_usda_tab()
            
        results_area.controls = []

    def switch_to_barcode(e):
        nonlocal current_tab
        if current_tab == 0:
            return
        current_tab = 0
        update_tab_ui()
        page.update()

    def switch_to_usda(e):
        nonlocal current_tab
        if current_tab == 1:
            return
        current_tab = 1
        update_tab_ui()
        page.update()

    # Custom tab decorations
    tab_barcode_btn.content = ft.Row([ft.Text("Barcode", weight="bold")], alignment=ft.MainAxisAlignment.CENTER)
    tab_barcode_btn.padding = 12
    tab_barcode_btn.border_radius = 10
    tab_barcode_btn.on_click = switch_to_barcode

    tab_usda_btn.content = ft.Row([ft.Text("Ingredient Search", weight="bold")], alignment=ft.MainAxisAlignment.CENTER)
    tab_usda_btn.padding = 12
    tab_usda_btn.border_radius = 10
    tab_usda_btn.on_click = switch_to_usda

    custom_tabs_bar = ft.Container(
        content=ft.Row([tab_barcode_btn, tab_usda_btn], spacing=5),
        bgcolor="#181D26",
        padding=6,
        border_radius=12,
    )

    def handle_back_navigation(e):
        stop_barcode_camera()
        page.go("/")

    # Seed UI elements
    update_tab_ui()

    return ft.View(
        route="/lookup",
        controls=[
            ft.AppBar(
                title=ft.Text("Lookup"),
                leading=ft.IconButton(
                    content=ft.Icon(ft.Icons.ARROW_BACK), 
                    on_click=handle_back_navigation
                ),
            ),
            ft.Container(
                content=ft.Column(
                    [custom_tabs_bar, tabs_content, ft.Divider(color="#222A35"), results_area],
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
                ft.IconButton(
                    content=ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE), 
                    on_click=on_log, 
                    tooltip="Log this"
                ),
            ]
        ),
        padding=12,
        border_radius=12,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
    )


def _ingredient_card(breakdown, state: AppState, page: ft.Page) -> ft.Control:
    def on_log(e):
        # 1. Correctly declare the source parameter as 'usda'
        state.set_pending(breakdown, source="usda")
        # 2. Head to the confirmation view to let the user choose grams consumed
        page.go("/confirm")

    return ft.Container(
        content=ft.Row(
            [
                ft.Column(
                    [
                        ft.Text(breakdown.meal_name, weight=ft.FontWeight.W_600),
                        ft.Text(
                            f"per 100g: {breakdown.calories} kcal • "
                            f"P{breakdown.protein}g C{breakdown.carbs}g F{breakdown.fat}g",
                            size=12,
                            color="#7A8B9E"
                        ),
                    ],
                    expand=True,
                ),
                ft.IconButton(
                    content=ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE, color="#00E5FF"), 
                    on_click=on_log, 
                    tooltip="Log this ingredient match"
                ),
            ]
        ),
        padding=12,
        border_radius=12,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
    )