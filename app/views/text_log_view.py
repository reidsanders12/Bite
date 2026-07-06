"""
Natural Language Voice/Text Log view.

Text-only Gemini calls are far cheaper than multimodal image calls, so this
is the most "free-tier friendly" logging path. A mic button is included as a
hook for native speech-to-text (wiring up an actual on-device STT engine is
platform-specific and left as a TODO -- see comment below).
"""

import flet as ft

from app import ai_engine
from app.state import AppState
from app.views.widgets import error_banner, loading_view


def build_text_log_view(page: ft.Page, state: AppState) -> ft.View:
    text_field = ft.TextField(
        label="Describe what you ate",
        hint_text='e.g. "Had a scoop of whey, 100g oats, and 1 tbsp peanut butter"',
        multiline=True,
        min_lines=3,
        max_lines=6,
        border_radius=12,
        autofocus=True,
    )
    status_area = ft.Container()
    submit_button = ft.FilledButton("Parse with AI", icon=ft.Icons.AUTO_AWESOME)

    def on_mic_click(e):
        # Hook point for native speech-to-text (e.g. platform channel / plugin).
        # Wiring an actual STT engine is device/OS specific, so for now this
        # just focuses the text field for manual dictation via the keyboard's
        # built-in mic if the OS provides one.
        text_field.focus()
        page.update()

    async def on_submit(e):
        text = text_field.value.strip()
        if not text:
            return
        submit_button.disabled = True
        status_area.content = loading_view("Parsing your meal log...")
        page.update()
        try:
            breakdown = await ai_engine.analyze_text(text)
        except ai_engine.AIEngineError as exc:
            status_area.content = error_banner(str(exc))
            submit_button.disabled = False
            page.update()
            return
        except Exception as exc:  # noqa: BLE001
            status_area.content = error_banner(f"Unexpected error: {exc}")
            submit_button.disabled = False
            page.update()
            return

        state.set_pending(breakdown, source="text")
        page.go("/confirm")

    submit_button.on_click = on_submit

    return ft.View(
        route="/text-log",
        controls=[
            ft.AppBar(
                title=ft.Text("Describe a Meal"),
                leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda e: page.go("/")),
            ),
            ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Container(text_field, expand=True),
                                ft.IconButton(
                                    ft.Icons.MIC_NONE,
                                    tooltip="Dictate (uses your keyboard's mic)",
                                    on_click=on_mic_click,
                                ),
                            ]
                        ),
                        submit_button,
                        status_area,
                    ],
                    spacing=16,
                ),
                padding=20,
                expand=True,
            ),
        ],
    )
