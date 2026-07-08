"""
Authentication Portal View.
Handles user registration and secure session login validation via Supabase Auth services.
"""
import flet as ft
from app.state import AppState

def build_auth_view(page: ft.Page, state: AppState) -> ft.View:
    # 1. UI Control Nodes Initialization
    email_field = ft.TextField(
        label="Email Address",
        hint_text="e.g. you@example.com",
        prefix_icon=ft.Icons.EMAIL_OUTLINED,
        border_radius=12,
        border_color="#1C2431",
        focused_border_color="#00E5FF",
        keyboard_type=ft.KeyboardType.EMAIL,
    )

    password_field = ft.TextField(
        label="Password",
        prefix_icon=ft.Icons.LOCK_OUTLINED,
        password=True,
        can_reveal_password=True,
        border_radius=12,
        border_color="#1C2431",
        focused_border_color="#00E5FF",
    )

    status_msg = ft.Text("", color="#FF5252", size=13, weight="w500", text_align=ft.TextAlign.CENTER)

    # 2. Authentication Submit Pipelines
    async def handle_login(e):
        email = email_field.value.strip()
        password = password_field.value.strip()

        if not email or not password:
            status_msg.value = "Please complete both required credentials fields."
            status_msg.color = "#FF5252"
            page.update()
            return

        status_msg.value = "Authenticating identity configuration tokens..."
        status_msg.color = "#00E5FF"
        page.update()

        try:
            credentials = {"email": email, "password": password}
            response = state.db.auth.sign_in_with_password(credentials)
            
            if response and response.user:
                status_msg.value = "Access verified. Syncing timeline arrays..."
                status_msg.color = "#4CAF50"
                page.update()
                
                # Clear standard route views history tracking stacks and advance to home
                page.views.clear()
                page.go("/")
            else:
                raise Exception("Empty session token configuration payload received.")

        except Exception as err:
            status_msg.value = f"Auth Error: {str(err)}"
            status_msg.color = "#FF5252"
            page.update()

    async def handle_register(e):
        email = email_field.value.strip()
        password = password_field.value.strip()

        if not email or len(password) < 6:
            status_msg.value = "Registration requires valid email and minimum 6-character password."
            status_msg.color = "#FF5252"
            page.update()
            return

        status_msg.value = "Provisioning secure account parameters on cloud index..."
        status_msg.color = "#00E5FF"
        page.update()

        try:
            credentials = {"email": email, "password": password}
            response = state.db.auth.sign_up(credentials)
            
            if response and response.user:
                status_msg.value = "Registration initialized! Check your inbox for confirmation info."
                status_msg.color = "#4CAF50"
            else:
                raise Exception("Account provisioning interface execution failed.")
            page.update()

        except Exception as err:
            status_msg.value = f"Registration Error: {str(err)}"
            status_msg.color = "#FF5252"
            page.update()

    # Form submissions wired into the text blocks directly for quick access
    email_field.on_submit = lambda e: page.run_task(handle_login, e)
    password_field.on_submit = lambda e: page.run_task(handle_login, e)

    # 3. Layout Node Container Tree Structures
    return ft.View(
        route="/auth",
        bgcolor="#06090F",
        vertical_alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Container(
                content=ft.Column([
                    # Title Header Branding Element
                    ft.Column([
                        ft.Text(
                            "BITE", 
                            size=36, 
                            weight="black", 
                            color="#FFFFFF", 
                            style=ft.TextStyle(letter_spacing=2)
                        ),
                        ft.Text(
                            "NUTRITIONAL INTEL SYSTEM", 
                            size=11, 
                            color="#506173", 
                            weight="bold", 
                            style=ft.TextStyle(letter_spacing=1)
                        ),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0),
                    
                    ft.Divider(color="transparent", height=15),
                    
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
                        ft.FilledButton(
                            "SIGN IN TO PROFILE",
                            icon=ft.Icons.LOGIN_ROUNDED,
                            width=float("inf"),
                            height=50,
                            style=ft.ButtonStyle(
                                bgcolor="#00E5FF",
                                color="#0A0E17",
                                shape=ft.RoundedRectangleBorder(radius=12)
                            ),
                            on_click=lambda e: page.run_task(handle_login, e)  # Forwarding event parameter e cleanly
                        ),
                        ft.TextButton(
                            "Create standard user account",
                            style=ft.ButtonStyle(color="#7A8B9E"),
                            on_click=lambda e: page.run_task(handle_register, e)  # Forwarding event parameter e cleanly
                        )
                    ], spacing=10, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
                    
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
                width=360,
                padding=28,
                bgcolor="#0A0E17",
                border_radius=24,
                border=ft.border.all(1, "#1C2431")
            )
        ]
    )