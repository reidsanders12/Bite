"""
Historical Consumption Logging Workspace View.
Displays structural row timelines with inline item deletion triggers.
"""
import flet as ft

from app import theme

def build_history_view(page: ft.Page, state) -> ft.View:
    # 1. Force state to grab the full all-time log history (not just today)
    if hasattr(state, "refresh_history"):
        state.refresh_history()

    daily_logs = state.get_history_logs() if hasattr(state, "get_history_logs") else getattr(state, "logs", [])

    # Container container reference layout to refresh list state dynamically
    history_list = ft.Column(spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)

    confirm_dialog = ft.AlertDialog(modal=True)
    error_banner = ft.Text("", color=theme.ERROR, size=12)

    def delete_item(entry_id, card_control, meal_name):
        def do_delete(e):
            success, err = state.remove_log(entry_id) if hasattr(state, "remove_log") else (False, "")

            if success:
                history_list.controls.remove(card_control)
                if not history_list.controls:
                    history_list.controls.append(ft.Text("No historical logging events saved.", color=theme.TEXT_MUTED, size=13))
                error_banner.value = ""
                page.close(confirm_dialog)
            else:
                error_banner.value = f"Couldn't delete: {err}"
                page.close(confirm_dialog)

            page.update()

        def cancel(e):
            page.close(confirm_dialog)

        confirm_dialog.title = ft.Text("Delete this entry?")
        confirm_dialog.content = ft.Text(f"\"{meal_name}\" will be permanently removed from your log.")
        confirm_dialog.actions = [
            ft.TextButton("Cancel", style=ft.ButtonStyle(color=theme.TEXT_MUTED), on_click=cancel),
            ft.TextButton("Delete", style=ft.ButtonStyle(color=theme.ERROR), on_click=do_delete),
        ]
        page.open(confirm_dialog)

    # 2. Map row cards into control stacks dynamically
    if not daily_logs:
        history_list.controls.append(ft.Text("No historical logging events saved.", color=theme.TEXT_MUTED, size=13))
    else:
        for log in daily_logs:
            # Handle class instance variables or dict mappings safely
            entry_id = log.get("id") if isinstance(log, dict) else getattr(log, "id", None)
            meal_name = log.get("meal_name") if isinstance(log, dict) else getattr(log, "meal_name", "Logged Item")
            cal = log.get("calories") if isinstance(log, dict) else getattr(log, "calories", 0)
            pro = log.get("protein") if isinstance(log, dict) else getattr(log, "protein", 0)
            carb = log.get("carbs") if isinstance(log, dict) else getattr(log, "carbs", 0)
            fat = log.get("fat") if isinstance(log, dict) else getattr(log, "fat", 0)

            # Build structural container reference closure block
            item_card = ft.Container(
                padding=14, border_radius=theme.RADIUS_MD,
                bgcolor=theme.BG_SURFACE, border=ft.border.all(1, theme.BORDER),
            )

            item_card.content = ft.Row([
                ft.Column([
                    ft.Text(meal_name, weight="bold", size=15, color=theme.TEXT_PRIMARY),
                    ft.Text(f"{cal} kcal • P{pro}g C{carb}g F{fat}g", size=12, color=theme.TEXT_MUTED)
                ], expand=True),
                ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE,
                    icon_color=theme.ERROR,
                    tooltip="Delete log entry",
                    # Pass context reference hooks into execution pipeline click handlers
                    on_click=lambda e, eid=entry_id, card=item_card, mn=meal_name: delete_item(eid, card, mn)
                )
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

            history_list.controls.append(item_card)

    return ft.View(
        route="/history",
        bgcolor=theme.BG_CANVAS,
        controls=[
            theme.app_bar("Logging History", on_back=lambda e: page.go("/")),
            ft.Container(
                content=ft.Column([
                    ft.Text("Manage Your Logs", size=18, weight="bold", color=theme.TEXT_PRIMARY),
                    ft.Text("Review or remove consumption track items recorded to your SQL local instance profile.", size=12, color=theme.TEXT_MUTED),
                    error_banner,
                    ft.Divider(color=theme.BORDER, height=20),
                    history_list
                ], expand=True),
                padding=20,
                expand=True
            )
        ]
    )