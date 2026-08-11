"""
Barcode & Ingredient Lookup view with integrated Live Camera Barcode Scanning.
Exercises public Open Food Facts API and USDA FoodData Central pipelines.
"""

import asyncio
import logging

import flet as ft
import flet_native_camera as fnc

from app import food_apis
from app import promotions
from app import theme
from app.models import MacroBreakdown
from app.state import AppState
from app.views.widgets import error_banner, loading_view

logger = logging.getLogger(__name__)


def build_lookup_view(page: ft.Page, state: AppState) -> ft.View:
    if hasattr(state, "refresh_sponsor_meal_items"):
        state.refresh_sponsor_meal_items()

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

    scanner = fnc.BarcodeScanner(width=320, height=200)
    # BarcodeScanner has no border_radius of its own (unlike the old
    # ft.Image), so a clipping Container provides the rounded corners; its
    # visibility -- not scanner.visible -- is what's toggled on start/stop.
    scanner_container = ft.Container(
        content=scanner,
        width=320,
        height=200,
        border_radius=theme.RADIUS_MD,
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
        bgcolor=theme.BG_SURFACE,
        visible=False,
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
    async def handle_detected_barcode(e: fnc.BarcodeDetectEvent):
        scanned_code = e.code
        try:
            barcode_field.value = scanned_code
            # Reset the scan button/flag directly rather than calling
            # stop_barcode_camera() -- the scanner already released the
            # camera itself the instant it fired this event (see
            # flet_native_camera's barcode_scanner.dart), so there's nothing
            # left to stop here, just UI state to reconcile. Unlike the old
            # OpenCV-based camera, the preview goes blank rather than
            # freezing on the last frame -- mobile_scanner has no
            # freeze-frame API -- but the decoded value below still confirms
            # what was scanned.
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

    scanner.on_detect = lambda e: page.run_task(handle_detected_barcode, e)

    def on_scanner_error(e):
        camera_active[0] = False
        scan_btn.text = "Live Scan Barcode"
        scan_btn.style = ft.ButtonStyle(bgcolor=theme.ACCENT, color=theme.ACCENT_ON)
        scanner_container.visible = False
        results_area.controls = [error_banner(f"Camera error: {e.data}")]
        page.update()

    scanner.on_error = on_scanner_error

    async def start_barcode_camera():
        camera_active[0] = True
        scan_btn.text = "Stop Scanner"
        scan_btn.style = ft.ButtonStyle(bgcolor=theme.ERROR, color=theme.TEXT_PRIMARY)
        scanner_container.visible = True
        page.update()

        started = await scanner.start_async()
        if not started:
            camera_active[0] = False
            scan_btn.text = "Live Scan Barcode"
            scan_btn.style = ft.ButtonStyle(bgcolor=theme.ACCENT, color=theme.ACCENT_ON)
            scanner_container.visible = False
            results_area.controls = [
                error_banner("Couldn't start the camera. Check camera permission in Settings.")
            ]
            page.update()

    def toggle_barcode_camera():
        if not camera_active[0]:
            page.run_task(start_barcode_camera)
        else:
            stop_barcode_camera()

    def stop_barcode_camera():
        if camera_active[0]:
            camera_active[0] = False
            scan_btn.text = "Live Scan Barcode"
            scan_btn.style = ft.ButtonStyle(bgcolor=theme.ACCENT, color=theme.ACCENT_ON)
            scanner_container.visible = False
            scanner.stop()
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
                ft.Row([scanner_container], alignment=ft.MainAxisAlignment.CENTER),
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

    def build_sponsored_tab():
        items = state.get_sponsor_meal_items() if hasattr(state, "get_sponsor_meal_items") else []
        if not items:
            return ft.Column(
                [ft.Text("No sponsored menu items right now.", size=12, color=theme.TEXT_FAINT, italic=True)],
                spacing=10,
            )
        return ft.Column([_sponsor_item_card(item, state, page) for item in items], spacing=8)

    tab_barcode_btn = ft.Container(expand=True)
    tab_usda_btn = ft.Container(expand=True)
    tab_sponsored_btn = ft.Container(expand=True)

    tabs = [
        (tab_barcode_btn, build_barcode_tab),
        (tab_usda_btn, build_usda_tab),
        (tab_sponsored_btn, build_sponsored_tab),
    ]

    def update_tab_ui():
        stop_barcode_camera()
        results_area.controls = []

        for index, (btn, builder) in enumerate(tabs):
            active = index == current_tab[0]
            btn.bgcolor = theme.BG_SURFACE_ALT if active else "transparent"
            btn.border = ft.border.all(1, theme.ACCENT) if active else None
            btn.content.controls[0].color = theme.ACCENT if active else theme.TEXT_MUTED
        tabs_content.content = tabs[current_tab[0]][1]()

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

    tab_sponsored_btn.content = ft.Row([ft.Text("Sponsored", weight="bold")], alignment=ft.MainAxisAlignment.CENTER)
    tab_sponsored_btn.padding = 12
    tab_sponsored_btn.border_radius = theme.RADIUS_SM
    tab_sponsored_btn.on_click = lambda _: switch_tabs(2)

    custom_tabs_bar = ft.Container(
        content=ft.Row([tab_barcode_btn, tab_usda_btn, tab_sponsored_btn], spacing=5),
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


def _sponsor_item_card(item: dict, state: AppState, page: ft.Page) -> ft.Control:
    """A Gold sponsor's menu item -- the "native integration" promise from
    the sponsor tiers (see sponsor_requests_view.py's Manage Menu dialog).
    Tapping it stages the sponsor's own macro numbers exactly like a
    barcode/USDA hit, one tap into the same Confirm screen."""
    sponsor_name = (item.get("sponsors") or {}).get("title", "Sponsor")
    icon_name = (item.get("sponsors") or {}).get("icon_name")

    def on_log(e):
        breakdown = MacroBreakdown(
            meal_name=item.get("name", ""),
            calories=item.get("calories") or 0,
            protein=item.get("protein") or 0,
            carbs=item.get("carbs") or 0,
            fat=item.get("fat") or 0,
        )
        state.set_pending(breakdown, source="sponsor")
        page.go("/confirm")

    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(promotions.icon_for(icon_name), size=22, color=theme.ACCENT),
                ft.Column(
                    [
                        ft.Text(sponsor_name.upper(), size=10, weight="bold", color=theme.TEXT_FAINT),
                        ft.Text(item.get("name", "").upper(), weight=ft.FontWeight.BOLD, size=14),
                        ft.Text(
                            f"{item.get('calories') or 0} kcal • "
                            f"P: {item.get('protein') or 0}g  C: {item.get('carbs') or 0}g  F: {item.get('fat') or 0}g",
                            size=12,
                            color=theme.TEXT_MUTED,
                        ),
                    ],
                    expand=True,
                    spacing=2,
                ),
                ft.IconButton(
                    icon=ft.Icons.ADD_LINK_ROUNDED,
                    icon_color=theme.ACCENT,
                    on_click=on_log,
                    tooltip="Log this item",
                ),
            ],
            spacing=10,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        padding=16,
        border_radius=theme.RADIUS_MD,
        bgcolor=theme.BG_SURFACE,
        border=ft.border.all(1, theme.BORDER),
    )
