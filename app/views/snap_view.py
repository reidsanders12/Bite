"""
Instant Snap & Log view.

Flow: user picks/takes a food photo -> bytes are encoded and sent straight
from this device to Gemini Flash (client-side AI processing, per the
"$0 infra" architecture) -> structured MacroBreakdown comes back -> we hand
off to the Correction Slider (confirm view) before anything is saved.
"""

import flet as ft

from app import ai_engine
from app.state import AppState
from app.views.widgets import error_banner, loading_view


def build_snap_view(page: ft.Page, state: AppState) -> ft.View:
    picked_path: dict = {"value": None}

    preview = ft.Container(
        content=ft.Column(
            [
                ft.Icon(ft.Icons.PHOTO_CAMERA_OUTLINED, size=56, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Text("No photo selected", color=ft.Colors.ON_SURFACE_VARIANT),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        height=280,
        border_radius=16,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        alignment=ft.alignment.center,
    )

    status_area = ft.Container()
    analyze_button = ft.FilledButton(
        "Analyze Photo",
        icon=ft.Icons.AUTO_AWESOME,
        disabled=True,
    )

    body = ft.Column(
        [
            ft.Text(
                "Snap or choose a clear photo of your meal. Gemini estimates the "
                "full macro breakdown in a few seconds.",
                size=13,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
            preview,
            ft.OutlinedButton(
                "Choose / Take Photo",
                icon=ft.Icons.ADD_A_PHOTO,
                on_click=lambda e: file_picker.pick_files(
                    file_type=ft.FilePickerFileType.IMAGE, allow_multiple=False
                ),
            ),
            analyze_button,
            status_area,
        ],
        spacing=16,
    )

    def on_pick_result(e: ft.FilePickerResultEvent):
        if not e.files:
            return
        picked_path["value"] = e.files[0].path
        preview.content = ft.Image(
            src=picked_path["value"],
            fit=ft.ImageFit.COVER,
            border_radius=16,
        )
        analyze_button.disabled = False
        status_area.content = None
        page.update()

    file_picker = ft.FilePicker(on_result=on_pick_result)
    page.overlay.append(file_picker)

    async def on_analyze(e):
        path = picked_path["value"]
        if not path:
            return
        analyze_button.disabled = True
        status_area.content = loading_view("Analyzing your meal with Gemini...")
        page.update()
        try:
            with open(path, "rb") as f:
                image_bytes = f.read()
            mime = "image/png" if path.lower().endswith(".png") else "image/jpeg"
            breakdown = await ai_engine.analyze_image(image_bytes, mime_type=mime)
        except ai_engine.AIEngineError as exc:
            status_area.content = error_banner(str(exc))
            analyze_button.disabled = False
            page.update()
            return
        except Exception as exc:  # noqa: BLE001
            status_area.content = error_banner(f"Unexpected error: {exc}")
            analyze_button.disabled = False
            page.update()
            return

        state.set_pending(breakdown, source="photo")
        page.go("/confirm")

    analyze_button.on_click = on_analyze

    return ft.View(
        route="/snap",
        controls=[
            ft.AppBar(
                title=ft.Text("Snap & Log"),
                leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda e: page.go("/")),
            ),
            ft.Container(content=body, padding=20, expand=True),
        ],
    )
