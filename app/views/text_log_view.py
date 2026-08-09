"""
Natural Language Voice/Text Log view.

Text-only Gemini calls are far cheaper than multimodal image calls, so this
is the most "free-tier friendly" logging path. The mic button records a
short voice note and sends it straight to Gemini for transcription +
macro parsing in one multimodal call (see ai_engine.analyze_audio) -- no
separate on-device speech-to-text engine involved.

Voice logging only works on desktop/mobile builds. On web, Flet's
AudioRecorder hands back a browser-local blob: URL that this Python
process has no way to fetch (there's no upload bridge for it, unlike
FilePicker), so the mic button is disabled there with an explanatory
tooltip instead of silently doing nothing.
"""

import asyncio
import os
import tempfile

import flet as ft
import flet_audio_recorder as far

from app import ai_engine
from app import theme
from app.state import AppState
from app.views.widgets import error_banner, loading_view

# Module-level singleton (same pattern as snap_view.camera_manager) -- a
# fresh AudioRecorder was previously created on every visit to this view and
# swapped into page.overlay, tearing down and re-requesting the native mic
# resource each time. After a few open/close cycles that repeated
# create/destroy churn left the platform-side recorder in a bad state
# (start_recording_async silently failing). Reusing one instance for the
# life of the app avoids the churn entirely.
_audio_recorder = far.AudioRecorder(audio_encoder=far.AudioEncoder.WAV)


def build_text_log_view(page: ft.Page, state: AppState) -> ft.View:
    text_field = ft.TextField(
        label="Describe what you ate",
        hint_text='e.g. "Had a scoop of whey, 100g oats, and 1 tbsp peanut butter"',
        multiline=True,
        min_lines=3,
        max_lines=6,
        autofocus=True,
        **theme.styled_field(),
    )
    status_area = ft.Container()
    submit_button = theme.primary_button("Parse with AI", icon=ft.Icons.AUTO_AWESOME)

    voice_supported = not page.web
    is_recording = {"value": False}
    recording_path = {"value": None}

    mic_button = ft.IconButton(
        ft.Icons.MIC_NONE,
        icon_color=theme.TEXT_MUTED,
        tooltip=(
            "Record a voice log"
            if voice_supported
            else "Voice log isn't available in the web app -- type or use Snap & Log instead"
        ),
        disabled=not voice_supported,
    )

    audio_recorder = _audio_recorder
    if voice_supported and audio_recorder not in page.overlay:
        # page.overlay is page-scoped and survives across rebuilds of this
        # view -- add the shared recorder once and leave it there rather
        # than recreating/swapping a new native recorder on every visit.
        page.overlay.append(audio_recorder)

    def reset_mic_button():
        mic_button.icon = ft.Icons.MIC_NONE
        mic_button.icon_color = theme.TEXT_MUTED
        mic_button.tooltip = "Record a voice log"

    async def process_recording(path: str):
        status_area.content = loading_view("Transcribing your meal...")
        submit_button.disabled = True
        page.update()
        try:
            with open(path, "rb") as f:
                audio_bytes = f.read()
            breakdown = await ai_engine.analyze_audio(
                audio_bytes, access_token=state.db.get_access_token(), mime_type="audio/wav"
            )
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
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

        state.set_pending(breakdown, source="voice")
        page.go("/confirm")

    async def on_mic_click(e):
        if not voice_supported:
            return

        if is_recording["value"]:
            is_recording["value"] = False
            reset_mic_button()
            status_area.content = None
            page.update()

            stopped_path = await audio_recorder.stop_recording_async()
            path = stopped_path or recording_path["value"]
            if not path or not os.path.exists(path):
                status_area.content = error_banner("Recording didn't produce any audio -- try again.")
                page.update()
                return
            await process_recording(path)
            return

        has_permission = await audio_recorder.has_permission_async()
        if not has_permission:
            status_area.content = error_banner(
                "Microphone permission is off -- enable it in your device/OS settings to use voice log."
            )
            page.update()
            return

        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        recording_path["value"] = path

        # start_recording() is a synchronous method that blocks on
        # threading.Event.wait() internally, waiting for the platform's
        # response -- called directly from this async handler, that wait
        # blocks the very event loop thread that needs to run to process
        # that response, so it always stalls until it times out. Running it
        # in a worker thread via asyncio.to_thread frees the event loop to
        # actually deliver the result.
        started = await asyncio.to_thread(audio_recorder.start_recording, output_path=path)
        if not started:
            status_area.content = error_banner("Couldn't start recording -- try again.")
            page.update()
            return

        is_recording["value"] = True
        mic_button.icon = ft.Icons.STOP_CIRCLE
        mic_button.icon_color = theme.ERROR
        mic_button.tooltip = "Stop recording"
        status_area.content = ft.Row(
            [
                ft.Icon(ft.Icons.FIBER_MANUAL_RECORD, color=theme.ERROR, size=14),
                ft.Text("Listening...", size=13, color=theme.TEXT_MUTED),
            ],
            spacing=8,
        )
        page.update()

    mic_button.on_click = on_mic_click

    async def on_submit(e):
        text = text_field.value.strip()
        if not text:
            return
        submit_button.disabled = True
        status_area.content = loading_view("Parsing your meal log...")
        page.update()
        try:
            breakdown = await ai_engine.analyze_text(text, access_token=state.db.get_access_token())
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
        route="/text_log",
        bgcolor=theme.BG_CANVAS,
        controls=[
            theme.app_bar("Describe a Meal", on_back=lambda e: page.go("/")),
            ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Container(text_field, expand=True),
                                mic_button,
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
