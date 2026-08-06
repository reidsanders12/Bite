"""
Post a Meal view: capture a photo and share it to the public feed or one of
your Friend Circles, with an optional caption and optional macros. No AI
analysis here -- this is a lightweight social share, separate from the "AI
estimates, you correct" logging flow (Snap & Log). If a Snap & Log estimate
is still staged on state.pending_breakdown, its macros are used to prefill
the fields here, but they stay fully editable and may be cleared.

Public posts are anonymous by default ("Show my name" is opt-in); circle
posts always show your name since a circle is your friend group.
"""
import flet as ft

from app import moderation, theme
from app.ai_engine import AIEngineError, analyze_image
from app.camera_engine import BLANK_FRAME_B64, CameraEngine

camera_manager = CameraEngine()


def build_post_meal_view(page: ft.Page, state) -> ft.View:
    if hasattr(state, "refresh_circles"):
        state.refresh_circles()
    circles = state.get_circles() if hasattr(state, "get_circles") else []

    view_stream = ft.Image(
        src_base64=BLANK_FRAME_B64, width=320, height=320,
        fit=ft.ImageFit.COVER, border_radius=theme.RADIUS_MD,
    )
    status_txt = ft.Text("Camera Ready", size=12, color=theme.TEXT_MUTED)
    captured_bytes = {"value": None}
    visibility_state = {"value": "public"}

    pending = getattr(state, "pending_breakdown", None)
    pending_items = getattr(pending, "identified_items", None) or []

    title_field = ft.TextField(
        label="Meal name (optional)", value=getattr(pending, "meal_name", "") or "",
        **theme.styled_field(),
    )
    ingredients_field = ft.TextField(
        label="Ingredients (optional, one per line)",
        value="\n".join(f"{item.name} ({item.portion_size})" for item in pending_items),
        multiline=True, min_lines=2, max_lines=6,
        **theme.styled_field(),
    )
    caption_field = ft.TextField(
        label="Notes (optional)", multiline=True, min_lines=1, max_lines=3,
        **theme.styled_field(),
    )

    def _macro_field(label: str, color: str, value=None) -> ft.TextField:
        return ft.TextField(
            label=label, value=str(value) if value is not None else "",
            keyboard_type=ft.KeyboardType.NUMBER, text_align=ft.TextAlign.CENTER,
            color=color, expand=True, **theme.styled_field(),
        )

    calories_field = _macro_field("Calories", theme.ACCENT, getattr(pending, "calories", None))
    protein_field = _macro_field("Protein (g)", theme.PROTEIN, getattr(pending, "protein", None))
    carbs_field = _macro_field("Carbs (g)", theme.CARBS, getattr(pending, "carbs", None))
    fat_field = _macro_field("Fat (g)", theme.FAT, getattr(pending, "fat", None))
    macros_row = ft.Row(
        [calories_field, protein_field, carbs_field, fat_field], spacing=8,
    )

    analyze_status = ft.Text("", size=11, color=theme.TEXT_MUTED)
    analyze_button = ft.TextButton(
        "Analyze with AI", icon=ft.Icons.AUTO_AWESOME,
        style=ft.ButtonStyle(color=theme.ACCENT),
    )

    async def on_analyze(e):
        if not captured_bytes["value"]:
            return
        access_token = state.db.get_access_token() if hasattr(state, "db") else None
        analyze_button.disabled = True
        analyze_status.value = "Analyzing photo..."
        analyze_status.color = theme.TEXT_MUTED
        page.update()
        try:
            breakdown = await analyze_image(captured_bytes["value"], access_token)
            calories_field.value = str(breakdown.calories)
            protein_field.value = str(breakdown.protein)
            carbs_field.value = str(breakdown.carbs)
            fat_field.value = str(breakdown.fat)
            if not (title_field.value or "").strip():
                title_field.value = breakdown.meal_name
            if not (ingredients_field.value or "").strip() and breakdown.identified_items:
                ingredients_field.value = "\n".join(
                    f"{item.name} ({item.portion_size})" for item in breakdown.identified_items
                )
            analyze_status.value = "Macros filled in -- feel free to adjust."
            analyze_status.color = theme.SUCCESS
        except AIEngineError as err:
            analyze_status.value = f"Couldn't analyze: {err}"
            analyze_status.color = theme.ERROR
        except Exception as err:
            analyze_status.value = f"Couldn't analyze: {err}"
            analyze_status.color = theme.ERROR
        analyze_button.disabled = False
        page.update()

    analyze_button.on_click = lambda e: page.run_task(on_analyze, e)

    macros_header = ft.Row(
        [
            ft.Text("Macros (optional)", size=12, color=theme.TEXT_MUTED, expand=True),
            analyze_button,
        ],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    circle_options = [ft.dropdown.Option(str(c.id), c.name) for c in circles]
    circle_dropdown = ft.Dropdown(
        label="Circle", options=circle_options,
        value=circle_options[0].key if circle_options else None,
        disabled=not circle_options, visible=False, **theme.styled_dropdown(),
    )

    # Public posts are anonymous by default -- your name only shows if you
    # opt in. Circle posts always show your name since circles are your
    # friends, so there's no toggle for those.
    show_name_switch = ft.Switch(value=False, active_color=theme.ACCENT)
    show_name_row = ft.Row(
        [
            ft.Text("Show my name", size=13, color=theme.TEXT_MUTED, expand=True),
            show_name_switch,
        ],
        visible=True,
    )

    def set_visibility(value: str):
        def handler(e):
            if value == "circle" and not circle_options:
                return
            visibility_state["value"] = value
            public_pill.bgcolor = theme.ACCENT if value == "public" else None
            public_pill.content.color = theme.ACCENT_ON if value == "public" else theme.TEXT_MUTED
            circle_pill.bgcolor = theme.ACCENT if value == "circle" else None
            circle_pill.content.color = theme.ACCENT_ON if value == "circle" else theme.TEXT_MUTED
            circle_dropdown.visible = value == "circle"
            show_name_row.visible = value == "public"
            page.update()
        return handler

    public_pill = ft.Container(
        content=ft.Text("Public", size=13, weight="bold", color=theme.ACCENT_ON),
        bgcolor=theme.ACCENT, border_radius=theme.RADIUS_SM,
        padding=ft.padding.symmetric(horizontal=16, vertical=8),
        on_click=set_visibility("public"),
    )
    circle_pill = ft.Container(
        content=ft.Text(
            "Circle" if circle_options else "Circle (join one first)",
            size=13, weight="w500", color=theme.TEXT_MUTED,
        ),
        border_radius=theme.RADIUS_SM,
        padding=ft.padding.symmetric(horizontal=16, vertical=8),
        on_click=set_visibility("circle"),
    )
    visibility_toggle = ft.Container(
        content=ft.Row([public_pill, circle_pill], spacing=4),
        bgcolor=theme.BG_SURFACE_ALT, border_radius=theme.RADIUS_SM, padding=4,
    )

    review_section = ft.Column(
        [
            title_field, ingredients_field,
            macros_header, macros_row, analyze_status,
            caption_field, visibility_toggle, show_name_row, circle_dropdown,
        ],
        spacing=14, visible=False,
    )
    post_button = theme.primary_button("Share", icon=ft.Icons.SEND_ROUNDED, visible=False)
    capture_button = theme.primary_button("Capture Photo", icon=ft.Icons.CAMERA_ALT)
    retake_button = ft.TextButton(
        "Retake", icon=ft.Icons.REPLAY, style=ft.ButtonStyle(color=theme.TEXT_MUTED), visible=False,
    )

    def start_capture_loop():
        page.run_task(camera_manager.stream_views, view_stream, "snap")

    async def on_capture(e):
        photo_bytes = camera_manager.get_captured_photo()
        if not photo_bytes:
            status_txt.value = "Failed to capture frame from viewport."
            page.update()
            return
        camera_manager.stop_camera()
        captured_bytes["value"] = photo_bytes
        status_txt.value = "Photo captured"
        capture_button.visible = False
        retake_button.visible = True
        review_section.visible = True
        post_button.visible = True
        page.update()

    def on_retake(e):
        captured_bytes["value"] = None
        status_txt.value = "Camera Ready"
        status_txt.color = theme.TEXT_MUTED
        capture_button.visible = True
        retake_button.visible = False
        review_section.visible = False
        post_button.visible = False
        page.update()
        start_capture_loop()

    def _parse_macro(value: str):
        value = (value or "").strip()
        if not value:
            return None
        try:
            return int(round(float(value)))
        except ValueError:
            return None

    def on_post(e):
        if not captured_bytes["value"]:
            return
        visibility = visibility_state["value"]
        circle_id = int(circle_dropdown.value) if visibility == "circle" and circle_dropdown.value else None
        if visibility == "circle" and not circle_id:
            status_txt.value = "Pick a circle to share to."
            status_txt.color = theme.ERROR
            page.update()
            return

        text_fields = (caption_field.value, title_field.value, ingredients_field.value)
        if not all(moderation.is_caption_allowed(text or "") for text in text_fields):
            status_txt.value = "Something you wrote isn't allowed -- please revise it."
            status_txt.color = theme.ERROR
            page.update()
            return

        post_button.disabled = True
        status_txt.value = "Sharing..."
        status_txt.color = theme.TEXT_MUTED
        page.update()

        show_name = True if visibility == "circle" else bool(show_name_switch.value)
        success, err = state.post_meal(
            captured_bytes["value"], (caption_field.value or "").strip(), visibility, circle_id,
            _parse_macro(calories_field.value), _parse_macro(protein_field.value),
            _parse_macro(carbs_field.value), _parse_macro(fat_field.value),
            show_name,
            (title_field.value or "").strip(), (ingredients_field.value or "").strip(),
        )
        if success:
            page.go("/meal_feed")
        else:
            status_txt.value = f"Couldn't share: {err}"
            status_txt.color = theme.ERROR
            post_button.disabled = False
            page.update()

    capture_button.on_click = on_capture
    retake_button.on_click = on_retake
    post_button.on_click = on_post

    def handle_back(e):
        camera_manager.stop_camera()
        page.go("/meal_feed")

    start_capture_loop()

    return ft.View(
        route="/post_meal",
        bgcolor=theme.BG_CANVAS,
        controls=[
            theme.app_bar("Post a Meal", on_back=handle_back),
            ft.Container(
                content=ft.Column(
                    [
                        ft.Container(
                            content=view_stream, alignment=ft.alignment.center,
                            bgcolor=theme.BG_SURFACE, border=ft.border.all(1, theme.BORDER),
                            border_radius=theme.RADIUS_MD,
                        ),
                        status_txt,
                        ft.Row([capture_button, retake_button], alignment=ft.MainAxisAlignment.CENTER, spacing=10),
                        review_section,
                        post_button,
                    ],
                    spacing=16, scroll=ft.ScrollMode.HIDDEN, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=20, expand=True,
            ),
        ],
    )
