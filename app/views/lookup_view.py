"""
Barcode & Ingredient Lookup view with integrated Live Camera Barcode Scanning.
Exercises public Open Food Facts API and USDA FoodData Central pipelines.
"""

import asyncio
import logging

import flet as ft

from app import food_apis
from app import theme
from app.state import AppState
from app.views.widgets import error_banner, loading_view
from app.views.snap_view import camera_manager  # Centralized camera helper engine
from app.camera_engine import BLANK_FRAME_B64

logger = logging.getLogger(__name__)


def build_lookup_view(page: ft.Page, state: AppState) -> ft.View:
    # State tracking variables
    current_tab = [0]  # Scoped array reference pointer to avoid nonlocal binding mismatch
    camera_active = [False]

    # Persistent layout container targeting rendering segments
    tabs_content = ft.Container()
    results_area = ft.Column(spacing=8, scroll=ft.ScrollMode.HIDDEN)

    # 1. UI Declarations
    barcode_field = ft.TextField(
        label="Barcode (UPC/EAN)",
        hint_text="e.g. 3017620422003",
        **theme.styled_field(),
    )

    usda_field = ft.TextField(
        label="Ingredient name",
        hint_text="e.g. chicken breast, raw",
        **theme.styled_field(),
    )

    barcode_stream_view = ft.Image(
        src_base64=BLANK_FRAME_B64,
        width=320,
        height=200,
        fit=ft.ImageFit.COVER,
        border_radius=theme.RADIUS_MD,
        visible=False
    )

    scan_btn = theme.primary_button(
        "Live Scan Barcode",
        icon=ft.Icons.CAMERA_ALT_ROUNDED,
        on_click=lambda e: toggle_barcode_camera()
    )

    # 2. Execution Queries
    async def on_barcode_search(e):
        stop_barcode_camera()
        code = barcode_field.value.strip()
        if not code:
            return

        results_area.controls = [loading_view("Querying Open Food Facts database...")]
        page.update()
        try:
            product = await food_apis.lookup_barcode(code)
            if not product:
                results_area.controls = [error_banner("No matching retail product identified.")]
            else:
                results_area.controls = [_product_card(product, state, page)]
        except Exception as exc:
            results_area.controls = [error_banner(str(exc))]
        page.update()

    async def on_usda_search(e):
        query = usda_field.value.strip()
        if not query:
            return

        results_area.controls = [loading_view("Searching USDA FoodData Index...")]
        page.update()
        try:
            matches = await food_apis.search_usda(query)
            if not matches:
                results_area.controls = [error_banner("No standard biological ingredients found matching search query.")]
            else:
                results_area.controls = [_ingredient_card(m, state, page) for m in matches]
        except Exception as exc:
            results_area.controls = [error_banner(str(exc))]
        page.update()

    # Form Submission Wiring (Forwarding event argument e)
    barcode_field.on_submit = lambda e: page.run_task(on_barcode_search, e)
    usda_field.on_submit = lambda e: page.run_task(on_usda_search, e)

    # 3. Barcode Scanning Pipeline Runtime Hooks
    async def handle_detected_barcode(scanned_code: str):
        try:
            barcode_field.value = scanned_code
            # Reset the scan button/flag directly rather than calling
            # stop_barcode_camera() -- that would also hide
            # barcode_stream_view, which camera_engine just froze on the
            # exact frame the barcode was recognized in. Leaving it visible
            # gives a "captured this" confirmation while the lookup below
            # runs, instead of the preview vanishing with nothing to show
            # for it.
            camera_active[0] = False
            scan_btn.text = "Live Scan Barcode"
            scan_btn.style = ft.ButtonStyle(bgcolor=theme.ACCENT, color=theme.ACCENT_ON)
            page.update()
            await on_barcode_search(None)
        except Exception as exc:
            # Belt-and-suspenders: on_barcode_search already catches its own
            # lookup errors and shows a banner, so this only fires for
            # something unexpected (e.g. a UI update failing). Previously an
            # error here had nowhere to go and vanished silently, leaving a
            # stopped camera with no result and no explanation.
            logger.exception("Failed to process detected barcode %r", scanned_code)
            results_area.controls = [
                error_banner(f"Scanned {scanned_code}, but couldn't look it up: {exc}")
            ]
            page.update()

    def toggle_barcode_camera():
        if not camera_active[0]:
            camera_active[0] = True
            scan_btn.text = "Stop Scanner"
            scan_btn.style = ft.ButtonStyle(bgcolor=theme.ERROR, color=theme.TEXT_PRIMARY)
            barcode_stream_view.visible = True
            page.update()

            page.run_task(
                camera_manager.stream_views,
                barcode_stream_view,
                "barcode",
                handle_detected_barcode
            )
        else:
            stop_barcode_camera()

    def stop_barcode_camera():
        if camera_active[0]:
            camera_active[0] = False
            scan_btn.text = "Live Scan Barcode"
            scan_btn.style = ft.ButtonStyle(bgcolor=theme.ACCENT, color=theme.ACCENT_ON)
            barcode_stream_view.visible = False
            camera_manager.stop_camera()
            page.update()

    # 4. Content Block Generation Factory Primitives
    def build_barcode_tab():
        return ft.Column(
            [
                ft.Row([
                    ft.Container(barcode_field, expand=True),
                    ft.IconButton(
                        icon=ft.Icons.SEARCH_ROUNDED,
                        icon_color=theme.ACCENT,
                        on_click=lambda e: page.run_task(on_barcode_search, e)
                    )
                ], spacing=5),
                ft.Divider(color="transparent", height=5),
                ft.Row([scan_btn], alignment=ft.MainAxisAlignment.CENTER),
                ft.Row([barcode_stream_view], alignment=ft.MainAxisAlignment.CENTER),
                ft.Text(
                    "Looks up packaged products via Open Food Facts api mappings.",
                    size=11,
                    color=theme.TEXT_FAINT,
                ),
            ],
            spacing=10,
        )

    def build_usda_tab():
        return ft.Column(
            [
                ft.Row([
                    ft.Container(usda_field, expand=True),
                    ft.IconButton(
                        icon=ft.Icons.SEARCH_ROUNDED,
                        icon_color=theme.ACCENT,
                        on_click=lambda e: page.run_task(on_usda_search, e)
                    )
                ], spacing=5),
                ft.Text(
                    "Looks up raw ingredient databases via USDA FoodData Central (normalized values per 100g base sample scale).",
                    size=11,
                    color=theme.TEXT_FAINT,
                ),
            ],
            spacing=10,
        )

    tab_barcode_btn = ft.Container(expand=True)
    tab_usda_btn = ft.Container(expand=True)

    def update_tab_ui():
        stop_barcode_camera()
        results_area.controls = []

        if current_tab[0] == 0:
            tab_barcode_btn.bgcolor = theme.BG_SURFACE_ALT
            tab_barcode_btn.border = ft.border.all(1, theme.ACCENT)
            tab_barcode_btn.content.controls[0].color = theme.ACCENT

            tab_usda_btn.bgcolor = "transparent"
            tab_usda_btn.border = None
            tab_usda_btn.content.controls[0].color = theme.TEXT_MUTED
            tabs_content.content = build_barcode_tab()
        else:
            tab_usda_btn.bgcolor = theme.BG_SURFACE_ALT
            tab_usda_btn.border = ft.border.all(1, theme.ACCENT)
            tab_usda_btn.content.controls[0].color = theme.ACCENT

            tab_barcode_btn.bgcolor = "transparent"
            tab_barcode_btn.border = None
            tab_barcode_btn.content.controls[0].color = theme.TEXT_MUTED
            tabs_content.content = build_usda_tab()

    def switch_tabs(target_index: int):
        if current_tab[0] == target_index:
            return
        current_tab[0] = target_index
        update_tab_ui()
        page.update()

    # 5. Component Construction Wiring
    tab_barcode_btn.content = ft.Row([ft.Text("Barcode Product", weight="bold")], alignment=ft.MainAxisAlignment.CENTER)
    tab_barcode_btn.padding = 12
    tab_barcode_btn.border_radius = theme.RADIUS_SM
    tab_barcode_btn.on_click = lambda _: switch_tabs(0)

    tab_usda_btn.content = ft.Row([ft.Text("Ingredient Index", weight="bold")], alignment=ft.MainAxisAlignment.CENTER)
    tab_usda_btn.padding = 12
    tab_usda_btn.border_radius = theme.RADIUS_SM
    tab_usda_btn.on_click = lambda _: switch_tabs(1)

    custom_tabs_bar = ft.Container(
        content=ft.Row([tab_barcode_btn, tab_usda_btn], spacing=5),
        bgcolor=theme.BG_SURFACE,
        padding=6,
        border_radius=theme.RADIUS_SM,
    )

    update_tab_ui()

    return ft.View(
        route="/lookup",
        bgcolor=theme.BG_CANVAS,
        controls=[
            ft.AppBar(
                title=ft.Text("GLOBAL INDEX LOOKUP", size=16, weight="bold", font_family=theme.DISPLAY_FONT),
                bgcolor=theme.BG_CANVAS,
                elevation=0,
                leading=ft.IconButton(
                    icon=ft.Icons.ARROW_BACK_IOS_NEW_ROUNDED,
                    icon_color=theme.TEXT_MUTED,
                    on_click=lambda _: [
                        stop_barcode_camera(),
                        page.views.clear(),  # Destroys navigation route history references
                        page.go("/")         # Forces clean dashboard view rebuild pipeline
                    ]
                ),
            ),
            ft.Container(
                content=ft.Column(
                    [custom_tabs_bar, tabs_content, ft.Divider(color=theme.BORDER, height=20), results_area],
                    spacing=14,
                    scroll=ft.ScrollMode.HIDDEN,
                ),
                padding=24,
                expand=True,
            ),
        ],
    )


# --- ADAPTIVE ITEM VIEW CARDS ---

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
                    [ft.Text(product.name.upper(), weight=ft.FontWeight.BOLD, size=14), ft.Text(subtitle, size=12, color=theme.TEXT_MUTED)],
                    expand=True,
                    spacing=4
                ),
                ft.IconButton(
                    icon=ft.Icons.ADD_LINK_ROUNDED,
                    icon_color=theme.ACCENT,
                    on_click=on_log,
                    tooltip="Stage item parameters"
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
        ),
        padding=16,
        border_radius=theme.RADIUS_MD,
        bgcolor=theme.BG_SURFACE,
        border=ft.border.all(1, theme.BORDER)
    )


def _ingredient_card(breakdown, state: AppState, page: ft.Page) -> ft.Control:
    def on_log(e):
        state.set_pending(breakdown, source="usda")
        page.go("/confirm")

    return ft.Container(
        content=ft.Row(
            [
                ft.Column(
                    [
                        ft.Text(breakdown.meal_name.upper(), weight=ft.FontWeight.BOLD, size=14),
                        ft.Text(
                            f"Per 100g: {breakdown.calories} kcal • "
                            f"P: {breakdown.protein}g  C: {breakdown.carbs}g  F: {breakdown.fat}g",
                            size=12,
                            color=theme.TEXT_MUTED
                        ),
                    ],
                    expand=True,
                    spacing=4
                ),
                ft.IconButton(
                    icon=ft.Icons.ADD_LINK_ROUNDED,
                    icon_color=theme.ACCENT,
                    on_click=on_log,
                    tooltip="Stage biological matrix"
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
        ),
        padding=16,
        border_radius=theme.RADIUS_MD,
        bgcolor=theme.BG_SURFACE,
        border=ft.border.all(1, theme.BORDER)
    )
