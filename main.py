"""
Multimodal AI Macro Tracker -- entry point.

Run with:  flet run main.py          (desktop)
       or: flet run main.py --web    (browser)
       or: flet build apk/ipa        (native mobile, once you're ready to ship)

Architecture recap (see PRODUCT_BRIEF for the full rationale):
  - All AI calls (Gemini) and food-database lookups (Open Food Facts, USDA)
    happen directly from this client using the user's own free-tier keys.
  - All persistence (goals + food log history) is local SQLite.
  - There is no backend server anywhere in this codebase.
"""

import flet as ft

from app import config
from app.state import AppState
from app.views.confirm_view import build_confirm_view
from app.views.history_view import build_history_view
from app.views.home_view import build_home_view
from app.views.lookup_view import build_lookup_view
from app.views.settings_view import build_settings_view
from app.views.snap_view import build_snap_view
from app.views.text_log_view import build_text_log_view

VIEW_BUILDERS = {
    "/snap": build_snap_view,
    "/confirm": build_confirm_view,
    "/text-log": build_text_log_view,
    "/history": build_history_view,
    "/settings": build_settings_view,
    "/lookup": build_lookup_view,
}


def main(page: ft.Page):
    page.title = "Macro Tracker"
    page.theme_mode = ft.ThemeMode.SYSTEM
    page.window.width = 420
    page.window.height = 860

    config.load_into_environment()
    state = AppState()

    def route_change(e: ft.RouteChangeEvent):
        page.views.clear()
        page.views.append(build_home_view(page, state))

        if page.route != "/":
            builder = VIEW_BUILDERS.get(page.route)
            if builder is not None:
                page.views.append(builder(page, state))

        page.update()

    def view_pop(e: ft.ViewPopEvent):
        page.views.pop()
        top_view = page.views[-1]
        page.go(top_view.route)

    page.on_route_change = route_change
    page.on_view_pop = view_pop
    page.go(page.route)


if __name__ == "__main__":
    ft.app(target=main)
