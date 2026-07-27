"""
Sponsor Requests: review sponsor submissions (from sponsor_signup.html or
anywhere else that posts to the `sponsors` table) and approve/reject them
before they can ever show on the home screen.

Only reachable if state.is_admin() is True (your email matches ADMIN_EMAIL
in .env) -- everyone else never sees the nav link, and even if they guessed
the route, the sponsors_select_owner RLS policy means the query just comes
back empty for them.
"""
import flet as ft

from app import promotions
from app import theme


def build_sponsor_requests_view(page: ft.Page, state) -> ft.View:
    if hasattr(state, "refresh_sponsor_requests"):
        state.refresh_sponsor_requests()

    requests = state.get_sponsor_requests() if hasattr(state, "get_sponsor_requests") else []
    status_txt = ft.Text("", size=12)

    def rerender() -> None:
        page.views[-1] = build_sponsor_requests_view(page, state)
        page.update()

    def show_status(message: str, ok: bool) -> None:
        status_txt.value = message
        status_txt.color = theme.SUCCESS if ok else theme.ERROR
        page.update()

    def make_approve_handler(sponsor_id):
        def handler(e):
            success, err = state.approve_sponsor(sponsor_id)
            if success:
                rerender()
            else:
                show_status(f"Couldn't approve: {err}", ok=False)
        return handler

    def make_reject_handler(sponsor_id):
        def handler(e):
            success, err = state.reject_sponsor(sponsor_id)
            if success:
                rerender()
            else:
                show_status(f"Couldn't reject: {err}", ok=False)
        return handler

    def make_toggle_active_handler(sponsor_id):
        def handler(e):
            success, err = state.set_sponsor_active(sponsor_id, e.control.value)
            if not success:
                show_status(f"Couldn't update: {err}", ok=False)
                rerender()
        return handler

    def sponsor_row(s: dict, actions: ft.Control) -> ft.Control:
        contact_bits = [s.get("contact_name") or "", s.get("contact_email") or ""]
        contact_line = " • ".join(b for b in contact_bits if b)
        return theme.surface_card(
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(promotions.icon_for(s.get("icon_name")), size=22, color=theme.ACCENT),
                            ft.Column(
                                [
                                    ft.Text(s.get("title", ""), size=15, weight="bold", color=theme.TEXT_PRIMARY),
                                    ft.Text(s.get("subtitle", ""), size=12, color=theme.TEXT_MUTED),
                                ],
                                expand=True,
                                spacing=2,
                            ),
                        ],
                        spacing=10,
                    ),
                    ft.Text(f"CTA: \"{s.get('cta_text', '')}\"", size=11, color=theme.TEXT_FAINT),
                    ft.Text(s["website_url"], size=11, color=theme.ACCENT) if s.get("website_url") else ft.Container(),
                    ft.Text(contact_line, size=11, color=theme.TEXT_FAINT) if contact_line else ft.Container(),
                    actions,
                ],
                spacing=8,
            )
        )

    pending = [s for s in requests if s.get("status") == "pending"]
    approved = [s for s in requests if s.get("status") == "approved"]
    rejected = [s for s in requests if s.get("status") == "rejected"]

    pending_cards = ft.Column(spacing=12)
    if not pending:
        pending_cards.controls.append(ft.Text("No pending requests.", color=theme.TEXT_FAINT, italic=True, size=13))
    else:
        for s in pending:
            actions = ft.Row(
                [
                    theme.primary_button("Approve", icon=ft.Icons.CHECK, on_click=make_approve_handler(s["id"])),
                    ft.TextButton("Reject", style=ft.ButtonStyle(color=theme.ERROR), on_click=make_reject_handler(s["id"])),
                ],
                spacing=10,
            )
            pending_cards.controls.append(sponsor_row(s, actions))

    approved_cards = ft.Column(spacing=12)
    if not approved:
        approved_cards.controls.append(ft.Text("No approved sponsors.", color=theme.TEXT_FAINT, italic=True, size=13))
    else:
        for s in approved:
            actions = ft.Row(
                [
                    ft.Text("Live on home screen", size=12, color=theme.TEXT_MUTED, expand=True),
                    ft.Switch(value=bool(s.get("active")), active_color=theme.ACCENT, on_change=make_toggle_active_handler(s["id"])),
                ],
            )
            approved_cards.controls.append(sponsor_row(s, actions))

    rejected_cards = ft.Column(spacing=12)
    if not rejected:
        rejected_cards.controls.append(ft.Text("No rejected requests.", color=theme.TEXT_FAINT, italic=True, size=13))
    else:
        for s in rejected:
            rejected_cards.controls.append(sponsor_row(s, ft.Text("Rejected", size=12, color=theme.ERROR)))

    return ft.View(
        route="/sponsor_requests",
        bgcolor=theme.BG_CANVAS,
        controls=[
            theme.app_bar("Sponsor Requests", on_back=lambda e: page.go("/profile")),
            ft.Container(
                content=ft.Column(
                    [
                        status_txt,
                        ft.Text(f"PENDING ({len(pending)})", size=11, color=theme.TEXT_FAINT, weight="w700"),
                        pending_cards,
                        ft.Divider(color=theme.BORDER, height=28),
                        ft.Text(f"APPROVED ({len(approved)})", size=11, color=theme.TEXT_FAINT, weight="w700"),
                        approved_cards,
                        ft.Divider(color=theme.BORDER, height=28),
                        ft.Text(f"REJECTED ({len(rejected)})", size=11, color=theme.TEXT_FAINT, weight="w700"),
                        rejected_cards,
                    ],
                    spacing=12,
                    scroll=ft.ScrollMode.HIDDEN,
                ),
                padding=20,
                expand=True,
            ),
        ],
    )
