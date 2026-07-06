"""
Historical Consumption Logging Workspace View.
Displays structural row timelines with inline item deletion triggers.
"""
import flet as ft

def build_history_view(page: ft.Page, state) -> ft.View:
    # 1. Force state to grab fresh database timelines
    if hasattr(state, "refresh_logs"):
        state.refresh_logs()
        
    daily_logs = state.get_daily_logs() if hasattr(state, "get_daily_logs") else getattr(state, "logs", [])

    # Container container reference layout to refresh list state dynamically
    history_list = ft.Column(spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)

    def delete_item(entry_id, card_control):
        # 1. Fire execution block against SQLite/AppState layer
        if hasattr(state, "remove_log"):
            state.remove_log(entry_id)
            
        # 2. Animate out or immediately drop control from active visual layout tree
        history_list.controls.remove(card_control)
        if not history_list.controls:
            history_list.controls.append(ft.Text("No historical logging events saved.", color="#7A8B9E", size=13))
            
        page.update()

    # 2. Map row cards into control stacks dynamically
    if not daily_logs:
        history_list.controls.append(ft.Text("No historical logging events saved.", color="#7A8B9E", size=13))
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
            item_card = ft.Container(padding=12, border_radius=10, bgcolor="#181D26", border=ft.border.all(1, "#222A35"))
            
            item_card.content = ft.Row([
                ft.Column([
                    ft.Text(meal_name, weight="bold", size=15),
                    ft.Text(f"{cal} kcal • P{pro}g C{carb}g F{fat}g", size=12, color="#7A8B9E")
                ], expand=True),
                ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE,
                    icon_color="#FF5252",
                    tooltip="Delete log entry",
                    # Pass context reference hooks into execution pipeline click handlers
                    on_click=lambda e, eid=entry_id, card=item_card: delete_item(eid, card)
                )
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            
            history_list.controls.append(item_card)

    return ft.View(
        route="/history",
        controls=[
            ft.AppBar(
                title=ft.Text("Logging History", weight="bold"),
                leading=ft.IconButton(content=ft.Icon(ft.Icons.ARROW_BACK), on_click=lambda e: page.go("/")),
                bgcolor="#181D26"
            ),
            ft.Container(
                content=ft.Column([
                    ft.Text("Manage Your Logs", size=18, weight="bold"),
                    ft.Text("Review or remove consumption track items recorded to your SQL local instance profile.", size=12, color="#7A8B9E"),
                    ft.Divider(color="#222A35", height=20),
                    history_list
                ], expand=True),
                padding=20,
                expand=True
            )
        ]
    )