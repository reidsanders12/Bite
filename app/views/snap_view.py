"""Camera snapshot layout module."""
import base64

import flet as ft
import flet_native_camera as fnc
from app import theme
from app import ai_engine

def build_snap_view(page: ft.Page, state) -> ft.View:
    # Visible -- lives inline in the preview box below, not page.overlay,
    # since it renders a live viewfinder rather than just exposing methods.
    camera = fnc.NativeCamera(width=320, height=320)

    status_txt = ft.Text(
        "Starting camera...", size=12, color=theme.TEXT_MUTED
    )
    placeholder_icon = ft.Icon(ft.Icons.CAMERA_ALT, size=64, color=theme.TEXT_FAINT)
    photo_preview = ft.Image(
        width=320, height=320, fit=ft.ImageFit.COVER,
        border_radius=theme.RADIUS_MD, visible=False,
    )

    def on_camera_error(e):
        status_txt.value = f"Camera error: {e.data}"
        status_txt.color = theme.ERROR
        page.update()

    camera.on_error = on_camera_error

    async def start_camera():
        started = await camera.start_async()
        status_txt.value = "Ready." if started else "Couldn't start the camera."
        status_txt.color = theme.TEXT_MUTED if started else theme.ERROR
        page.update()

    async def on_snap_click(e):
        photo_bytes = await camera.take_picture_async()
        if not photo_bytes:
            status_txt.value = "No photo captured."
            page.update()
            return

        await camera.stop_async()
        photo_preview.src_base64 = base64.b64encode(photo_bytes).decode("utf-8")
        photo_preview.visible = True
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
            page.update()

    def handle_back(e):
        page.run_task(camera.stop_async)
        page.go("/")

    page.run_task(start_camera)

    return ft.View(
        route="/snap",
        bgcolor=theme.BG_CANVAS,
        controls=[
            theme.app_bar("Snap Meal Photo", on_back=handle_back),
            ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=ft.Stack([placeholder_icon, camera, photo_preview], alignment=ft.alignment.center),
                        width=320,
                        height=320,
                        alignment=ft.alignment.center,
                        bgcolor=theme.BG_SURFACE,
                        border=ft.border.all(1, theme.BORDER),
                        border_radius=theme.RADIUS_MD,
                        clip_behavior=ft.ClipBehavior.HARD_EDGE,
                    ),
                    status_txt,
                    ft.Row([
                        theme.primary_button("Capture Photo", icon=ft.Icons.CAMERA_ALT, on_click=on_snap_click)
                    ], alignment=ft.MainAxisAlignment.CENTER)
                ], spacing=20, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=20
            )
        ]
    )
