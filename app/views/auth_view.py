"""
Authentication Portal View.
Handles user registration and secure session login validation via Supabase Auth services.
"""
import flet as ft
from app import theme
from app.state import AppState

def build_auth_view(page: ft.Page, state: AppState) -> ft.View:
    # 1. UI Control Nodes Initialization
    email_field = ft.TextField(
        label="Email Address",
        hint_text="e.g. you@example.com",
        prefix_icon=ft.Icons.EMAIL_OUTLINED,
        keyboard_type=ft.KeyboardType.EMAIL,
        **theme.styled_field(),
    )

    password_field = ft.TextField(
        label="Password",
        prefix_icon=ft.Icons.LOCK_OUTLINED,
        password=True,
        can_reveal_password=True,
        **theme.styled_field(),
    )

    status_msg = ft.Text("", color=theme.ERROR, size=13, weight="w500", text_align=ft.TextAlign.CENTER)

    # 2. Authentication Submit Pipelines
    async def handle_login(e):
        email = email_field.value.strip()
        password = password_field.value.strip()

        if not email or not password:
            status_msg.value = "Please enter your email and password."
            status_msg.color = theme.ERROR
            page.update()
            return

        status_msg.value = "Signing you in..."
        status_msg.color = theme.TEXT_MUTED
        page.update()

        try:
            credentials = {"email": email, "password": password}
            response = state.db.auth.sign_in_with_password(credentials)

            if response and response.user:
                status_msg.value = ""
                page.update()

                # Clear standard route views history tracking stacks and advance to home
                page.views.clear()
                page.go("/")
            else:
                raise Exception("We couldn't sign you in. Please try again.")

        except Exception as err:
            status_msg.value = f"Sign in failed: {str(err)}"
            status_msg.color = theme.ERROR
            page.update()

    async def handle_register(e):
        email = email_field.value.strip()
        password = password_field.value.strip()

        if not email or len(password) < 6:
            status_msg.value = "Please enter a valid email and a password with at least 6 characters."
            status_msg.color = theme.ERROR
            page.update()
            return

        status_msg.value = "Creating your account..."
        status_msg.color = theme.TEXT_MUTED
        page.update()

        try:
            credentials = {"email": email, "password": password}
            response = state.db.auth.sign_up(credentials)

            if response and response.user:
                status_msg.value = "Account created! Check your inbox to confirm your email."
                status_msg.color = theme.SUCCESS
            else:
                raise Exception("We couldn't create your account. Please try again.")
            page.update()

        except Exception as err:
            status_msg.value = f"Registration failed: {str(err)}"
            status_msg.color = theme.ERROR
            page.update()

    # Form submissions wired into the text blocks directly for quick access
    email_field.on_submit = lambda e: page.run_task(handle_login, e)
    password_field.on_submit = lambda e: page.run_task(handle_login, e)

    # 3. Layout Node Container Tree Structures
    return ft.View(
        route="/auth",
        bgcolor=theme.BG_CANVAS,
        vertical_alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Container(
                content=ft.Column([
                    # Title Header Branding Element
                    ft.Column([
                        ft.Container(
                            content=ft.Icon(ft.Icons.RESTAURANT_ROUNDED, color=theme.ACCENT_ON, size=28),
                            width=56, height=56, bgcolor=theme.ACCENT, border_radius=16,
                            alignment=ft.alignment.center,
                        ),
                        ft.Divider(color="transparent", height=8),
                        ft.Text(
                            "Bite",
                            size=28,
                            weight="bold",
                            color=theme.TEXT_PRIMARY,
                        ),
                        ft.Text(
                            "Track your meals in seconds",
                            size=13,
                            color=theme.TEXT_MUTED,
                        ),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),

                    ft.Divider(color="transparent", height=20),

                    # Form Fields Container Box
                    ft.Container(
                        content=ft.Column([
                            email_field,
                            password_field,
                        ], spacing=16),
                        padding=6
                    ),

                    ft.Divider(color="transparent", height=5),
                    status_msg,
                    ft.Divider(color="transparent", height=5),

                    # Action Execution Trigger Panels
                    ft.Column([
                        theme.primary_button(
                            "Sign In",
                            width=float("inf"),
                            height=50,
                            on_click=lambda e: page.run_task(handle_login, e)
                        ),
                        ft.TextButton(
                            "Create an account",
                            style=ft.ButtonStyle(color=theme.TEXT_MUTED),
                            on_click=lambda e: page.run_task(handle_register, e)
                        )
                    ], spacing=10, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
                width=360,
                padding=32,
                bgcolor=theme.BG_SURFACE,
                border_radius=theme.RADIUS_LG,
                border=ft.border.all(1, theme.BORDER),
                shadow=theme.CARD_SHADOW,
            )
        ]
    )
