import flet as ft
from app import theme
from app.state import AppState
from app.ai_engine import chat_with_coach

# Local aliases kept so the rest of this file reads the same as before,
# now backed by the app-wide tokens in app/theme.py instead of one-off hex.
BG_CANVAS = theme.BG_CANVAS
BG_SURFACE = theme.BG_SURFACE
BG_INPUT = theme.BG_SURFACE_ALT
COLOR_ACCENT = theme.ACCENT
COLOR_PROTEIN = theme.PROTEIN
COLOR_CARBS = theme.CARBS
COLOR_FAT = theme.FAT

def create_macro_ring(label: str, consumed: int, target: int, color: str) -> ft.Container:
    """Renders a modern, flat dashboard indicator metric card."""
    percent = min(consumed / max(target, 1), 1.0)
    return ft.Container(
        content=ft.Column([
            ft.Text(label, size=12, color=theme.TEXT_MUTED, weight=ft.FontWeight.W_600),
            ft.Stack([
                ft.ProgressRing(value=percent, stroke_width=6, color=color, bgcolor=theme.BG_SURFACE_ALT, width=64, height=64),
                ft.Container(
                    content=ft.Text(f"{consumed}g", size=11, weight="bold", color=theme.TEXT_PRIMARY),
                    alignment=ft.alignment.center,
                    width=64, height=64
                )
            ]),
            ft.Text(f"Target: {target}g", size=10, color=theme.TEXT_MUTED)
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        bgcolor=BG_SURFACE,
        padding=14,
        border_radius=theme.RADIUS_MD,
        expand=True
    )

def build_coach_view(page: ft.Page, state: AppState) -> ft.Container:
    """Generates the premium Cyber-Athlete AI Fitness Coach interface."""
    
    # Extract current real data parameters from local engine
    totals = state.db.get_totals_for_date()
    goals = state.goals
    
    chat_list = ft.ListView(expand=True, spacing=12, padding=10, auto_scroll=True)
    chat_input = ft.TextField(
        hint_text="Ask about programming, recovery, recipes...",
        hint_style=ft.TextStyle(color=theme.TEXT_MUTED),
        bgcolor=BG_INPUT,
        border_color=ft.Colors.TRANSPARENT,
        focused_border_color=COLOR_ACCENT,
        border_radius=theme.RADIUS_SM,
        expand=True,
        text_style=ft.TextStyle(color=theme.TEXT_PRIMARY),
    )

    # Load past database logs to keep current session preserved
    saved_history = state.db.get_chat_history()

    def render_bubble(text: str, is_user: bool):
        return ft.Row(
            controls=[
                ft.Container(
                    content=ft.Text(text, color=theme.TEXT_PRIMARY, size=14),
                    bgcolor=BG_INPUT if is_user else BG_SURFACE,
                    padding=14,
                    border_radius=ft.border_radius.only(
                        top_left=16, top_right=16, 
                        bottom_left=4 if is_user else 16, 
                        bottom_right=16 if is_user else 4
                    ),
                    border=None if is_user else ft.border.only(left=ft.BorderSide(3, COLOR_ACCENT)),
                    max_width=420 * 0.75, # Keeps bubble sizing perfect for the locked width viewport
                )
            ],
            alignment=ft.MainAxisAlignment.END if is_user else ft.MainAxisAlignment.START
        )

    for msg in saved_history:
        chat_list.controls.append(render_bubble(msg["text"], msg["is_user"]))

    async def send_message(e):
        user_txt = chat_input.value.strip()
        if not user_txt:
            return
            
        chat_input.value = ""
        chat_list.controls.append(render_bubble(user_txt, is_user=True))
        state.db.add_chat_message(user_txt, is_user=True)
        
        # Add modern visual loading ring inside chat queue
        loader = ft.Row([ft.ProgressRing(width=20, height=20, color=COLOR_ACCENT)], alignment=ft.MainAxisAlignment.START)
        chat_list.controls.append(loader)
        page.update()
        
        try:
            # Process response on device with structural contextual awareness
            history_payload = state.db.get_chat_history()
            reply = await chat_with_coach(user_txt, history_payload, totals, goals)
            
            chat_list.controls.remove(loader)
            chat_list.controls.append(render_bubble(reply, is_user=False))
            state.db.add_chat_message(reply, is_user=False)
        except Exception as err:
            if loader in chat_list.controls:
                chat_list.controls.remove(loader)
            chat_list.controls.append(render_bubble(f"Coach Link Failure: {err}", is_user=False))
            
        page.update()

    chat_input.on_submit = send_message

    # Core Page Container Layout
    return ft.Container(
        expand=True,
        bgcolor=BG_CANVAS,
        padding=20,
        content=ft.Column([
            # Dashboard Title Header
            ft.Row([
                ft.Column([
                    ft.Text("MIND COACH", size=24, weight=ft.FontWeight.W_900, color=theme.TEXT_PRIMARY),
                    ft.Text("On-device AI Nutritionist & Trainer", size=12, color=theme.TEXT_MUTED, italic=True),
                ]),
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK_IOS_NEW_ROUNDED,
                    icon_color=COLOR_ACCENT,
                    on_click=lambda _: page.go("/")
                )
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),

            ft.Divider(color=theme.BORDER, height=10),

            # Interactive Macro Context Rows pulled from local state
            ft.Row([
                create_macro_ring("PROTEIN", totals["protein"], goals.daily_protein, COLOR_PROTEIN),
                create_macro_ring("CARBS", totals["carbs"], goals.daily_carbs, COLOR_CARBS),
                create_macro_ring("FAT", totals["fat"], goals.daily_fat, COLOR_FAT),
            ], spacing=10),

            ft.Divider(color=theme.BORDER, height=15),

            # Main Message Thread Frame
            ft.Container(
                content=chat_list,
                expand=True,
                bgcolor=theme.BG_CANVAS,
                border=ft.border.all(1, theme.BORDER),
                border_radius=theme.RADIUS_MD,
                padding=10,
            ),

            # Message Input Section
            ft.Row([
                chat_input,
                ft.FloatingActionButton(
                    bgcolor=COLOR_ACCENT,
                    content=ft.Icon(ft.Icons.SEND, color=theme.ACCENT_ON, size=16),
                    on_click=send_message
                )
            ], spacing=10)
        ])
    )