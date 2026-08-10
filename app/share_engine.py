"""
Lightweight "share to contacts" flow. No native share-sheet plugin is
bundled (there's no `flet-share`/`share_plus` equivalent published for
Flet -- see README) -- this offers the same practical destinations one
would give you (Messages, Mail, or copy-to-clipboard) via a small in-app
dialog and the `sms:`/`mailto:` URL schemes `page.launch_url` already uses
elsewhere (profile_view.py's Contact Support). Messages lets the user pick
a contact once it opens, same end result as a real share sheet's contact
picker for this app's purposes.
"""
import urllib.parse

import flet as ft

from app import theme


def open_share_sheet(page: ft.Page, text: str, subject: str = "Bite!") -> None:
    dialog = ft.AlertDialog(modal=True)
    encoded_body = urllib.parse.quote(text)
    encoded_subject = urllib.parse.quote(subject)

    def close(e=None):
        page.close(dialog)

    def via_message(e):
        close()
        page.launch_url(f"sms:&body={encoded_body}")

    def via_email(e):
        close()
        page.launch_url(f"mailto:?subject={encoded_subject}&body={encoded_body}")

    def via_copy(e):
        page.set_clipboard(text)
        close()
        page.open(ft.SnackBar(ft.Text("Copied to clipboard.")))

    def _row(icon: str, label: str, on_click) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(icon, color=theme.ACCENT, size=20),
                    ft.Text(label, size=14, color=theme.TEXT_PRIMARY),
                ],
                spacing=14,
            ),
            padding=ft.padding.symmetric(vertical=10),
            on_click=on_click,
        )

    dialog.title = ft.Text("Share")
    dialog.content = ft.Column(
        [
            _row(ft.Icons.SMS_OUTLINED, "Message", via_message),
            _row(ft.Icons.EMAIL_OUTLINED, "Email", via_email),
            _row(ft.Icons.CONTENT_COPY_OUTLINED, "Copy", via_copy),
        ],
        tight=True, spacing=0, width=280,
    )
    dialog.actions = [
        ft.TextButton("Cancel", style=ft.ButtonStyle(color=theme.TEXT_MUTED), on_click=lambda e: close()),
    ]
    page.open(dialog)
