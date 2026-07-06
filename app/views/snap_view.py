"""Camera snapshot layout module."""
import flet as ft
import asyncio
from app.camera_engine import CameraEngine
from app import ai_engine

camera_manager = CameraEngine()

def build_snap_view(page: ft.Page, state) -> ft.View:
    # Placeholder asset text while camera warmups trigger
    view_stream = ft.Image(
        src_base64="",
        width=320,
        height=320,
        fit=ft.ImageFit.COVER,
        border_radius=12
    )

    status_txt = ft.Text("Camera Ready", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
    
    # Context loop handler wrapping the async execution thread
# Pass the stream function directly into Flet's background task runner
    def start_capture_loop():
        page.run_task(camera_manager.stream_views, view_stream, "snap")

    async def on_snap_click(e):
            # 1. Grab the raw un-nested binary frame sequence from your Camera manager
            photo_bytes = camera_manager.get_captured_photo()
            if not photo_bytes:
                status_txt.value = "Failed to capture frame from viewport."
                page.update()
                return
                
            camera_manager.stop_camera()
            status_txt.value = "Analyzing meal with Gemini AI..."
            page.update()
            
            try:
                # 2. Pass the raw bytes straight into the exact keyword parameter name required
                macro_breakdown = await ai_engine.analyze_image(photo_bytes=photo_bytes)
                
                # 3. Stage the result model cleanly in global state and proceed
                state.set_pending(macro_breakdown, source="snap")
                page.go("/confirm")
                
            except Exception as err:
                status_txt.value = f"Analysis Error: {err}"
                page.update()

    def handle_back(e):
        camera_manager.stop_camera()
        page.go("/")

    # Fire capture stream immediately upon route load pipeline execution
    start_capture_loop()

    return ft.View(
        route="/snap",
        controls=[
            ft.AppBar(title=ft.Text("Snap Meal Photo"), leading=ft.IconButton(content=ft.Icon(ft.Icons.ARROW_BACK), on_click=handle_back)),
            ft.Container(
                content=ft.Column([
                    ft.Container(content=view_stream, alignment=ft.alignment.center, bgcolor="#11151C", border_radius=12),
                    status_txt,
                    ft.Row([
                        ft.FilledButton(text="Capture Photo", icon=ft.Icons.CAMERA_ALT, on_click=on_snap_click)
                    ], alignment=ft.MainAxisAlignment.CENTER)
                ], spacing=20),
                padding=20
            )
        ]
    )