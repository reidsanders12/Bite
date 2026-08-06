"""
Reported Posts: the admin-only moderation queue for Meal Feed. This is what
turns "a mechanism to report offensive content" (Apple Guideline 1.2 /
Google Play's UGC policy) into something actually actionable instead of
reports piling up unread -- see the SQL comment above blocked_users in
supabase_circles_schema.sql for the full compliance rationale.

Only reachable if state.is_admin() is True (your email matches ADMIN_EMAIL
in .env) -- everyone else never sees the nav link, and even if they guessed
the route, meal_post_reports_select_owner RLS means the query just comes
back empty for them.
"""
import flet as ft

from app import theme


def build_reported_posts_view(page: ft.Page, state) -> ft.View:
    if hasattr(state, "refresh_reported_posts"):
        state.refresh_reported_posts()

    reports = state.get_reported_posts() if hasattr(state, "get_reported_posts") else []
    status_txt = ft.Text("", size=12)

    def rerender() -> None:
        page.views[-1] = build_reported_posts_view(page, state)
        page.update()

    def show_status(message: str, ok: bool) -> None:
        status_txt.value = message
        status_txt.color = theme.SUCCESS if ok else theme.ERROR
        page.update()

    def make_dismiss_handler(report_id):
        def handler(e):
            success, err = state.dismiss_report(report_id)
            if success:
                rerender()
            else:
                show_status(f"Couldn't dismiss: {err}", ok=False)
        return handler

    def make_remove_post_handler(post_id):
        def handler(e):
            success, err = state.admin_remove_meal_post(post_id)
            if success:
                rerender()
            else:
                show_status(f"Couldn't remove post: {err}", ok=False)
        return handler

    report_cards = ft.Column(spacing=12)
    if not reports:
        report_cards.controls.append(
            ft.Text("No open reports.", color=theme.TEXT_FAINT, italic=True, size=13)
        )
    else:
        for r in reports:
            post = r.get("post") or {}
            report_id = r.get("id")
            post_id = r.get("post_id")
            author = post.get("display_name", "Unknown user")
            meal_name = post.get("meal_name") or ""
            caption = post.get("caption") or ""
            photo_url = post.get("photo_url")
            reason = r.get("reason") or "No reason given"

            report_cards.controls.append(
                theme.surface_card(
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(f"Posted by {author}", size=13, weight="bold", color=theme.TEXT_PRIMARY, expand=True),
                                    ft.Text(r.get("created_at", "")[:10], size=11, color=theme.TEXT_FAINT),
                                ],
                            ),
                            ft.Image(
                                src=photo_url, fit=ft.ImageFit.COVER, height=160,
                                border_radius=theme.RADIUS_SM,
                            ) if photo_url else ft.Container(),
                            ft.Text(meal_name, size=13, weight="bold", color=theme.TEXT_PRIMARY) if meal_name else ft.Container(),
                            ft.Text(caption, size=12, color=theme.TEXT_PRIMARY) if caption else ft.Container(),
                            ft.Text(f"Reason: {reason}", size=12, color=theme.TEXT_MUTED, italic=True),
                            ft.Row(
                                [
                                    ft.TextButton(
                                        "Dismiss", style=ft.ButtonStyle(color=theme.TEXT_MUTED),
                                        on_click=make_dismiss_handler(report_id),
                                    ),
                                    ft.TextButton(
                                        "Remove Post", style=ft.ButtonStyle(color=theme.ERROR),
                                        on_click=make_remove_post_handler(post_id),
                                    ),
                                ],
                                spacing=10,
                            ),
                        ],
                        spacing=8,
                    )
                )
            )

    return ft.View(
        route="/reported_posts",
        bgcolor=theme.BG_CANVAS,
        controls=[
            theme.app_bar("Reported Posts", on_back=lambda e: page.go("/profile")),
            ft.Container(
                content=ft.Column(
                    [
                        status_txt,
                        ft.Text(f"OPEN REPORTS ({len(reports)})", size=11, color=theme.TEXT_FAINT, weight="w700"),
                        report_cards,
                    ],
                    spacing=12,
                    scroll=ft.ScrollMode.HIDDEN,
                ),
                padding=20,
                expand=True,
            ),
        ],
    )
