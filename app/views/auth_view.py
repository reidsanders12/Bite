"""
Authentication and Local Session Registration View.
"""
import flet as ft

def build_auth_view(page: ft.Page, state) -> ft.View:
    username_field = ft.TextField(label="Username", hint_text="e.g. reid_sanders", border_radius=10)
    password_field = ft.TextField(label="Password", password=True, can_reveal_password=True, border_radius=10)
    status_msg = ft.Text("", color="#FF5252", size=12)

    def handle_login(e):
        user = username_field.value.strip()
        pwd = password_field.value.strip()
        
        if not user or not pwd:
            status_msg.value = "Please enter both username and password."
            page.update()
            return
        
        # Connect to your DB login/registration helper hooks if available
        if hasattr(state, "db") and hasattr(state.db, "authenticate_user"):
            success = state.db.authenticate_user(user, pwd)
            if not success:
                status_msg.value = "Invalid credentials. Try again."
                page.update()
                return
        
        # Update session states and redirect to the dashboard
        if hasattr(state, "current_user"):
            state.current_user = user
            
        page.go("/")

    def handle_signup(e):
        user = username_field.value.strip()
        pwd = password_field.value.strip()
        
        if len(user) < 3 or len(pwd) < 4:
            status_msg.value = "Credentials too short! (Min: 3 char user, 4 char pass)"
            page.update()
            return

        if hasattr(state, "db") and hasattr(state.db, "create_user"):
            state.db.create_user(user, pwd)
        
        if hasattr(state, "current_user"):
            state.current_user = user
            
        page.go("/survey") # New signups get immediately channeled into your macro-sponsor wizard!

    return ft.View(
        route="/auth",
        controls=[
            ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.LOCK_PERSON_ROUNDED, color="#00E5FF", size=64),
                    ft.Text("Welcome to Bite", size=24, weight="bold"),
                    ft.Text("Log in or create a local account to track sync profiles safely.", size=12, color="#7A8B9E"),
                    ft.Divider(color="transparent", height=10),
                    username_field,
                    password_field,
                    status_msg,
                    ft.Divider(color="transparent", height=10),
                    ft.FilledButton("Log In", icon=ft.Icons.LOGIN, on_click=handle_login, width=200, style=ft.ButtonStyle(bgcolor="#00E5FF", color="#181D26")),
                    ft.TextButton("Don't have an account? Sign Up", on_click=handle_signup)
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                alignment=ft.alignment.center,
                padding=40,
                expand=True
            )
        ]
    )