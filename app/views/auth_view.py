"""
Authentication Portal View.
Handles user registration and secure session login validation via Supabase Auth services.
"""
import asyncio
import logging

import flet as ft
from app import theme
from app.age_gate import MIN_ACCOUNT_AGE, is_account_age_allowed
from app.state import AppState

logger = logging.getLogger(__name__)

def build_auth_view(page: ft.Page, state: AppState) -> ft.View:
    mode = {"value": "login"}  # "login" | "register"

    # 1. UI Control Nodes Initialization
    name_field = ft.TextField(
        label="Full Name",
        hint_text="e.g. Jamie Rivera",
        prefix_icon=ft.Icons.PERSON_OUTLINE,
        **theme.styled_field(),
    )

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

    # COPPA account-creation floor (app/age_gate.py) -- self-attested, same
    # shape as the existing onboarding "age" field, but collected here so a
    # too-young signup is refused before any account exists at all rather
    # than after.
    age_field = ft.TextField(
        label="Age",
        hint_text=f"Must be {MIN_ACCOUNT_AGE} or older to create an account",
        prefix_icon=ft.Icons.CAKE_OUTLINED,
        keyboard_type=ft.KeyboardType.NUMBER,
        **theme.styled_field(),
    )

    status_msg = ft.Text("", color=theme.ERROR, size=13, weight="w500", text_align=ft.TextAlign.CENTER)

    name_slot = ft.Container(content=None, height=0)
    age_slot = ft.Container(content=None, height=0)
    primary_btn = theme.primary_button("Sign In", width=float("inf"), height=50)
    toggle_btn = ft.TextButton(style=ft.ButtonStyle(color=theme.TEXT_MUTED))

    def render_mode():
        is_register = mode["value"] == "register"
        name_slot.content = name_field if is_register else None
        name_slot.height = None if is_register else 0
        age_slot.content = age_field if is_register else None
        age_slot.height = None if is_register else 0
        primary_btn.text = "Create Account" if is_register else "Sign In"
        toggle_btn.text = "Already have an account? Sign in" if is_register else "New here? Create an account"
        status_msg.value = ""

    def toggle_mode(e):
        mode["value"] = "register" if mode["value"] == "login" else "login"
        render_mode()
        page.update()

    toggle_btn.on_click = toggle_mode

    # 2. Authentication Submit Pipelines
    async def route_after_auth():
        """New accounts (no saved macro goals yet) go through onboarding first."""
        page.views.clear()
        if state.has_completed_onboarding():
            page.go("/")
        else:
            page.go("/survey")

    async def handle_login(e):
        email = email_field.value.strip()
        # Not .strip()'d: a password field's leading/trailing whitespace may
        # be intentional, and silently discarding it narrows the effective
        # password space without the user knowing.
        password = password_field.value

        if not email or not password:
            status_msg.value = "Please enter your email and password."
            status_msg.color = theme.ERROR
            page.update()
            return

        status_msg.value = "Signing you in..."
        status_msg.color = theme.TEXT_MUTED
        page.update()

        try:
            response = state.db.sign_in_user(email, password)

            if response and response.user:
                status_msg.value = ""
                await route_after_auth()
            else:
                raise Exception("We couldn't sign you in. Please try again.")

        except Exception as err:
            # Generic message to the user -- the real exception (which can
            # include Supabase/GoTrue internals) goes to the console only.
            logger.error("Sign in failed: %s", err)
            status_msg.value = "Sign in failed. Please check your email and password and try again."
            status_msg.color = theme.ERROR
            page.update()

    async def handle_register(e):
        name = name_field.value.strip()
        email = email_field.value.strip()
        password = password_field.value  # not .strip()'d -- see handle_login

        if not name:
            status_msg.value = "Please tell us what to call you."
            status_msg.color = theme.ERROR
            page.update()
            return

        if not email or len(password) < 10:
            status_msg.value = "Please enter a valid email and a password with at least 10 characters."
            status_msg.color = theme.ERROR
            page.update()
            return

        age_raw = (age_field.value or "").strip()
        try:
            age = int(age_raw)
        except ValueError:
            age = None
        if age is None or age <= 0:
            status_msg.value = "Please enter your age."
            status_msg.color = theme.ERROR
            page.update()
            return
        # Refused here, before sign_up_user is ever called -- no account is
        # created for an under-13 signup. See app/age_gate.py.
        if not is_account_age_allowed(age):
            status_msg.value = f"You must be at least {MIN_ACCOUNT_AGE} years old to create a Bite! account."
            status_msg.color = theme.ERROR
            page.update()
            return

        status_msg.value = "Creating your account..."
        status_msg.color = theme.TEXT_MUTED
        page.update()

        try:
            response = state.db.sign_up_user(email, password, full_name=name, age=age)

            if not (response and response.user):
                raise Exception("We couldn't create your account. Please try again.")

            if getattr(response, "session", None):
                # Email confirmation is off for this project - session is live already.
                status_msg.value = ""
                await route_after_auth()
            else:
                mode["value"] = "login"
                render_mode()
                status_msg.value = "Account created! Check your inbox to confirm your email, then sign in."
                status_msg.color = theme.SUCCESS
                page.update()

        except Exception as err:
            logger.error("Registration failed: %s", err)
            status_msg.value = "Registration failed. Please double-check your details and try again."
            status_msg.color = theme.ERROR
            page.update()

    def on_submit(e):
        if mode["value"] == "register":
            page.run_task(handle_register, e)
        else:
            page.run_task(handle_login, e)

    primary_btn.on_click = on_submit

    # Form submissions wired into the text blocks directly for quick access
    email_field.on_submit = on_submit
    password_field.on_submit = on_submit

    render_mode()

    # Fades and scales up from just below full size on first paint -- this is
    # the first thing Flet renders after the native splash hands off, so a
    # quick entrance here bridges that handoff instead of a flat jump cut.
    brand_icon = ft.Container(
        content=ft.Icon(ft.Icons.RESTAURANT_ROUNDED, color=theme.ACCENT_ON, size=28),
        width=56, height=56, bgcolor=theme.ACCENT, border_radius=theme.RADIUS_LG,
        alignment=ft.alignment.center,
        opacity=0,
        scale=0.85,
        animate_opacity=250,
        animate_scale=ft.Animation(250, ft.AnimationCurve.EASE_OUT),
    )

    async def animate_brand_in():
        await asyncio.sleep(0.05)
        brand_icon.opacity = 1
        brand_icon.scale = 1
        page.update()

    page.run_task(animate_brand_in)

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
                        brand_icon,
                        ft.Divider(color="transparent", height=8),
                        ft.Text(
                            "Bite!",
                            size=30,
                            weight="bold",
                            color=theme.TEXT_PRIMARY,
                            font_family=theme.DISPLAY_FONT,
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
                            name_slot,
                            age_slot,
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
                        primary_btn,
                        toggle_btn,
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
