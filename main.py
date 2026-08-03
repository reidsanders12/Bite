import logging

import flet as ft

from app.logging_config import configure_logging

configure_logging()

# 1. IMPORT CONFIG FIRST (It loads everything into the environment automatically on import)
from app import config
from app import theme

from app.state import AppState
from app.views.auth_view import build_auth_view
from app.views.circles_view import build_circles_view
from app.views.coach_view import build_coach_view
from app.views.confirm_view import build_confirm_view
from app.views.history_view import build_history_view
from app.views.home_view import build_home_view
from app.views.log_workout_view import build_log_workout_view
from app.views.lookup_view import build_lookup_view
from app.views.meal_feed_view import build_meal_feed_view
from app.views.post_meal_view import build_post_meal_view
from app.views.pr_tracker_view import build_pr_tracker_view
from app.views.reported_posts_view import build_reported_posts_view
from app.views.settings_view import build_settings_view
from app.views.snap_view import build_snap_view
from app.views.survey_view import build_survey_view
from app.views.text_log_view import build_text_log_view
from app.views.profile_view import build_profile_view
from app.views.sponsor_requests_view import build_sponsor_requests_view
from app.views.weight_view import build_weight_view
from app.views.workout_history_view import build_workout_history_view

# 2. Append it cleanly inside your VIEW_BUILDERS map allocation table
logger = logging.getLogger(__name__)

VIEW_BUILDERS = {
    "/auth": build_auth_view,
    "/": build_home_view,
    "/profile": build_profile_view,
    "/circles": build_circles_view,
    "/log_workout": build_log_workout_view,
    "/workout_history": build_workout_history_view,
    "/weight": build_weight_view,
    "/pr_tracker": build_pr_tracker_view,
    "/meal_feed": build_meal_feed_view,
    "/post_meal": build_post_meal_view,
    "/sponsor_requests": build_sponsor_requests_view,
    "/reported_posts": build_reported_posts_view,
    "/snap": build_snap_view,
    "/confirm": build_confirm_view,
    "/history": build_history_view,
    "/lookup": build_lookup_view,
    "/settings": build_settings_view,
    "/survey": build_survey_view,
    "/text_log": build_text_log_view,
    "/coach": build_coach_view,
}

def main(page: ft.Page):
    page.title = "Bite"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.fonts = {theme.DISPLAY_FONT: theme.DISPLAY_FONT_URL}
    page.theme = theme.build_theme()
    page.bgcolor = theme.BG_CANVAS

    # 3. INITIALIZE STATE CORRECTLY
    state = AppState()

    def route_change(e):
            page.views.clear()

            try:
                if hasattr(state, "refresh_logs"):
                    state.refresh_logs()
                if hasattr(state, "refresh_goals"):
                    state.refresh_goals()
                if hasattr(state, "refresh_profile"):
                    state.refresh_profile()

                # Dynamically look up and rebuild the requested view layout
                builder = VIEW_BUILDERS.get(page.route)

                # /sponsor_requests is only ever surfaced via a nav link
                # that's hidden for non-admins, but the route itself must
                # also refuse to render for anyone who navigates there
                # directly (e.g. by URL on web) -- the sponsors_select_owner
                # RLS policy would just hand back an empty list either way,
                # but gating the route too means that's belt-and-suspenders
                # rather than the only thing standing between a random user
                # and the admin screen.
                if page.route in ("/sponsor_requests", "/reported_posts") and not (
                    hasattr(state, "is_admin") and state.is_admin()
                ):
                    builder = build_home_view

                if builder:
                    page.views.append(builder(page, state))
                else:
                    page.views.append(build_home_view(page, state))
                    
            except Exception:
                logger.exception("Routing crash while building view for route %r", page.route)

                page.views.append(
                    ft.View(
                        route="/error",
                        controls=[
                            ft.AppBar(title=ft.Text("App Initialization Error")),
                            ft.Container(
                                content=ft.Column([
                                    ft.Text("Failed to build view component safely.", color=ft.Colors.ERROR, weight="bold"),
                                    # Generic message only -- the real exception (already
                                    # printed to the console above via traceback.print_exc())
                                    # can include internal details we don't want to hand to
                                    # whoever's looking at this screen.
                                    ft.Text("Something went wrong loading this screen. Please try again.", size=12),
                                    ft.ElevatedButton("Force Reset to Auth Screen", on_click=lambda _: page.go("/auth"))
                                ]),
                                padding=20
                            )
                        ]
                    )
                )
                
            page.update()

    def view_pop(e):
        if len(page.views) > 1:
            page.views.pop()
            top_view = page.views[-1]
            page.go(top_view.route)

    # Wire navigation state pipeline notification hooks
    page.on_route_change = route_change
    page.on_view_pop = view_pop
    
    # Boots directly to /auth so users can sign in or create an account.
    page.go(page.route if page.route and page.route != "/" else "/auth")


if __name__ == "__main__":
    ft.app(target=main)