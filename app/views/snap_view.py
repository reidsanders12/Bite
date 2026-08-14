"""Camera snapshot layout module."""
import base64

import flet as ft
import flet_native_camera as fnc
from app import theme
from app import ai_engine


def build_snap_view(page: ft.Page, state) -> ft.View:
    # SystemCamera hands the capture off to the OS's own Camera app instead
    # of rendering a live in-app preview (NativeCamera's CameraController
    # approach was unreliable on real devices) -- non-visual, so it lives in
    # page.overlay like FilePicker, not inline in the layout below.
    camera = fnc.SystemCamera()
    page.overlay.append(camera)

    status_txt = ft.Text("", size=12, color=theme.TEXT_MUTED)
    placeholder_icon = ft.Icon(ft.Icons.CAMERA_ALT, size=64, color=theme.TEXT_FAINT)
    photo_preview = ft.Image(
        width=320, height=320, fit=ft.ImageFit.COVER,
        border_radius=theme.RADIUS_MD, visible=False,
    )
    capture_button = theme.primary_button(
        "Open Camera", icon=ft.Icons.CAMERA_ALT, on_click=lambda e: page.run_task(on_snap_click, e)
    )

    def on_camera_error(e):
        status_txt.value = f"Camera error: {e.data}"
        status_txt.color = theme.ERROR
        capture_button.disabled = False
        page.update()

    camera.on_error = on_camera_error

    async def on_snap_click(e):
        capture_button.disabled = True
        status_txt.value = ""
        page.update()

        photo_bytes = await camera.take_picture_async()
        if not photo_bytes:
            # No error event fired (that's handled separately by
            # on_camera_error) -- this is the user backing out of the
            # system camera UI without taking a shot, not a failure.
            status_txt.value = ""
            capture_button.disabled = False
            page.update()
            return

        photo_preview.src_base64 = base64.b64encode(photo_bytes).decode("utf-8")
        photo_preview.visible = True
        placeholder_icon.visible = False
        capture_button.text = "Retake Photo"
        status_txt.value = "Analyzing meal with AI..."
        page.update()

        try:
            access_token = state.db.get_access_token()
            macro_breakdown = await ai_engine.analyze_image(
                photo_bytes=photo_bytes, access_token=access_token
            )
            state.set_pending(macro_breakdown, source="snap")
            page.go("/confirm")
        except Exception as err:
            status_txt.value = f"Analysis Error: {err}"
            status_txt.color = theme.ERROR
            capture_button.disabled = False
            page.update()

    def handle_back(e):
        page.go("/")

    return ft.View(
        route="/snap",
        bgcolor=theme.BG_CANVAS,
        controls=[
            theme.app_bar("Snap Meal Photo", on_back=handle_back),
            ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=ft.Stack([placeholder_icon, photo_preview], alignment=ft.alignment.center),
                        width=320,
                        height=320,
                        alignment=ft.alignment.center,
                        bgcolor=theme.BG_SURFACE,
                        border=ft.border.all(1, theme.BORDER),
                        border_radius=theme.RADIUS_MD,
                        clip_behavior=ft.ClipBehavior.HARD_EDGE,
                    ),
                    status_txt,
                    ft.Row([capture_button], alignment=ft.MainAxisAlignment.CENTER),
                ], spacing=20, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=20
            )
        ]
    )
