"""
Progress Photos: a private per-user photo timeline (not shared anywhere,
unlike Meal Feed's public/circle posts -- see the progress-photos Storage
bucket's public=false in supabase_circles_schema.sql). Also lets you pick
a date for your next photo; the Home screen surfaces a reminder banner
once that date has passed (see home_view.py's progress_photo_due check --
there's no OS-level push notification for this yet, see README).
"""
import base64
import datetime

import flet as ft
import flet_native_camera as fnc

from app import theme

_PRESETS = [
    ("1 week", 7),
    ("2 weeks", 14),
    ("1 month", 30),
    ("2 months", 60),
]


def _format_date(iso_value: str) -> str:
    try:
        dt = datetime.datetime.fromisoformat(iso_value.replace("Z", "+00:00"))
        return dt.strftime("%b %-d, %Y")
    except (ValueError, AttributeError):
        return iso_value or ""


def build_progress_photos_view(page: ft.Page, state) -> ft.View:
    if hasattr(state, "refresh_progress_photos"):
        state.refresh_progress_photos()
    if hasattr(state, "refresh_progress_photo_reminder"):
        state.refresh_progress_photo_reminder()

    photos = state.get_progress_photos() if hasattr(state, "get_progress_photos") else []
    reminder = state.get_progress_photo_reminder() if hasattr(state, "get_progress_photo_reminder") else None

    # SystemCamera hands the capture off to the OS's own Camera app instead
    # of rendering a live in-app preview (NativeCamera's CameraController
    # approach was unreliable on real devices) -- non-visual, so it lives in
    # page.overlay like FilePicker, not inline in the layout below.
    # lens_direction=FRONT is only a preference for which camera the system
    # app opens to -- the user can still flip it there.
    camera = fnc.SystemCamera(lens_direction=fnc.LensDirection.FRONT)
    page.overlay.append(camera)

    def rerender() -> None:
        page.views[-1] = build_progress_photos_view(page, state)
        page.update()

    status_txt = ft.Text("", size=12)

    def show_status(message: str, ok: bool) -> None:
        status_txt.value = message
        status_txt.color = theme.SUCCESS if ok else theme.ERROR
        page.update()

    # --- Reminder ---

    def set_reminder_days(days: int):
        def handler(e):
            remind_at = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)).isoformat()
            success, err = state.set_progress_photo_reminder(remind_at)
            if success:
                rerender()
            else:
                show_status(f"Couldn't set reminder: {err}", ok=False)
        return handler

    def clear_reminder(e):
        state.clear_progress_photo_reminder()
        rerender()

    date_picker = ft.DatePicker(
        first_date=datetime.datetime.now(),
        last_date=datetime.datetime.now() + datetime.timedelta(days=730),
    )

    def on_custom_date(e):
        if not date_picker.value:
            return
        remind_at = datetime.datetime.combine(
            date_picker.value, datetime.time.min, tzinfo=datetime.timezone.utc
        ).isoformat()
        success, err = state.set_progress_photo_reminder(remind_at)
        if success:
            rerender()
        else:
            show_status(f"Couldn't set reminder: {err}", ok=False)

    date_picker.on_change = on_custom_date
    page.overlay.append(date_picker)

    reminder_line = (
        f"Next photo: {_format_date(reminder['remind_at'])}" if reminder else "No reminder set."
    )
    preset_chips = ft.Row(
        [
            ft.TextButton(
                label, style=ft.ButtonStyle(color=theme.ACCENT), on_click=set_reminder_days(days),
            )
            for label, days in _PRESETS
        ]
        + [
            ft.TextButton(
                "Custom date", style=ft.ButtonStyle(color=theme.ACCENT),
                on_click=lambda e: page.open(date_picker),
            ),
        ],
        wrap=True, spacing=4,
    )

    reminder_card = theme.surface_card(
        ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.NOTIFICATIONS_OUTLINED, color=theme.ACCENT, size=20),
                        ft.Text(reminder_line, size=13, weight="w600", color=theme.TEXT_PRIMARY, expand=True),
                        ft.TextButton(
                            "Clear", style=ft.ButtonStyle(color=theme.TEXT_MUTED), on_click=clear_reminder,
                        ) if reminder else ft.Container(),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Text("Remind me to take my next photo in:", size=12, color=theme.TEXT_MUTED),
                preset_chips,
            ],
            spacing=8,
        )
    )

    # --- Capture ---

    captured_bytes = {"value": None}
    note_field = ft.TextField(label="Note (optional)", **theme.styled_field())
    photo_preview = ft.Image(width=280, height=280, fit=ft.ImageFit.COVER, border_radius=theme.RADIUS_MD, visible=False)
    placeholder_icon = ft.Icon(ft.Icons.CAMERA_ALT, size=64, color=theme.TEXT_FAINT)

    capture_button = theme.primary_button("Open Camera", icon=ft.Icons.CAMERA_ALT)
    retake_button = ft.TextButton(
        "Retake", icon=ft.Icons.REPLAY, style=ft.ButtonStyle(color=theme.TEXT_MUTED), visible=False,
    )
    save_button = theme.primary_button("Save Photo", icon=ft.Icons.CHECK, visible=False)
    review_section = ft.Column([note_field], visible=False, spacing=10)

    def on_camera_error(e):
        show_status(f"Camera error: {e.data}", ok=False)

    camera.on_error = on_camera_error

    async def on_capture(e):
        capture_button.disabled = True
        page.update()

        photo_bytes = await camera.take_picture_async()
        capture_button.disabled = False
        if not photo_bytes:
            # User backed out of the system camera UI without taking a
            # shot -- on_camera_error handles actual failures separately.
            page.update()
            return

        captured_bytes["value"] = photo_bytes
        photo_preview.src_base64 = base64.b64encode(photo_bytes).decode("utf-8")
        photo_preview.visible = True
        placeholder_icon.visible = False
        capture_button.visible = False
        retake_button.visible = True
        review_section.visible = True
        save_button.visible = True
        page.update()

    def on_retake(e):
        photo_preview.visible = False
        placeholder_icon.visible = True
        capture_button.visible = True
        retake_button.visible = False
        review_section.visible = False
        save_button.visible = False
        page.update()

    def on_save(e):
        if not captured_bytes["value"]:
            return
        save_button.disabled = True
        show_status("Saving...", ok=True)
        success, err = state.add_progress_photo(captured_bytes["value"], (note_field.value or "").strip())
        if success:
            rerender()
        else:
            save_button.disabled = False
            show_status(f"Couldn't save: {err}", ok=False)

    capture_button.on_click = on_capture
    retake_button.on_click = on_retake
    save_button.on_click = on_save

    # --- Timeline ---

    view_photo_dialog = ft.AlertDialog(modal=True)

    def make_view_handler(photo: dict):
        def handler(e):
            def do_delete(e2):
                page.close(view_photo_dialog)
                success, err = state.remove_progress_photo(photo["id"])
                if success:
                    rerender()
                else:
                    show_status(f"Couldn't delete: {err}", ok=False)

            view_photo_dialog.content = ft.Column(
                [
                    ft.Image(src=photo.get("url"), width=280, height=280, fit=ft.ImageFit.COVER, border_radius=theme.RADIUS_MD),
                    ft.Text(_format_date(photo.get("taken_at", "")), size=12, color=theme.TEXT_MUTED),
                    ft.Text(photo.get("note") or "", size=13, color=theme.TEXT_PRIMARY) if photo.get("note") else ft.Container(),
                ],
                tight=True, spacing=8, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            )
            view_photo_dialog.actions = [
                ft.TextButton("Delete", style=ft.ButtonStyle(color=theme.ERROR), on_click=do_delete),
                ft.TextButton("Close", style=ft.ButtonStyle(color=theme.TEXT_MUTED), on_click=lambda e2: page.close(view_photo_dialog)),
            ]
            page.open(view_photo_dialog)
        return handler

    thumbnails = ft.Row(wrap=True, spacing=8, run_spacing=8)
    for photo in photos:
        if not photo.get("url"):
            continue
        thumbnails.controls.append(
            ft.Container(
                content=ft.Image(src=photo["url"], width=104, height=104, fit=ft.ImageFit.COVER, border_radius=theme.RADIUS_SM),
                width=104, height=104, border_radius=theme.RADIUS_SM,
                on_click=make_view_handler(photo),
            )
        )
    if not photos:
        thumbnails.controls.append(
            ft.Text("No progress photos yet.", color=theme.TEXT_FAINT, italic=True, size=13)
        )

    def handle_back(e):
        page.go("/profile")

    return ft.View(
        route="/progress_photos",
        bgcolor=theme.BG_CANVAS,
        controls=[
            theme.app_bar("Progress Photos", on_back=handle_back),
            ft.Container(
                content=ft.Column(
                    [
                        reminder_card,
                        ft.Divider(color=theme.BORDER, height=1),
                        ft.Container(
                            content=ft.Stack([placeholder_icon, photo_preview], alignment=ft.alignment.center),
                            width=280, height=280, alignment=ft.alignment.center,
                            bgcolor=theme.BG_SURFACE, border=ft.border.all(1, theme.BORDER),
                            border_radius=theme.RADIUS_MD, clip_behavior=ft.ClipBehavior.HARD_EDGE,
                        ),
                        ft.Row([capture_button, retake_button], alignment=ft.MainAxisAlignment.CENTER, spacing=10),
                        review_section,
                        save_button,
                        status_txt,
                        ft.Divider(color=theme.BORDER, height=1),
                        ft.Text("Timeline", size=14, weight="bold", color=theme.TEXT_PRIMARY),
                        thumbnails,
                    ],
                    spacing=16, scroll=ft.ScrollMode.HIDDEN, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=20, expand=True,
            ),
        ],
    )
