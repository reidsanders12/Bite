"""
Workout History view -- same shape as history_view.py, for workout_logs.
"""
import flet as ft

from app import theme


def build_workout_history_view(page: ft.Page, state) -> ft.View:
    if hasattr(state, "refresh_workout_history"):
        state.refresh_workout_history()

    workouts = state.get_workout_history() if hasattr(state, "get_workout_history") else []

    history_list = ft.Column(spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)
    confirm_dialog = ft.AlertDialog(modal=True)
    error_banner = ft.Text("", color=theme.ERROR, size=12)

    def delete_item(entry_id, card_control, workout_name):
        def do_delete(e):
            success, err = state.remove_workout_log(entry_id) if hasattr(state, "remove_workout_log") else (False, "")

            if success:
                history_list.controls.remove(card_control)
                if not history_list.controls:
                    history_list.controls.append(ft.Text("No workouts logged yet.", color=theme.TEXT_MUTED, size=13))
                error_banner.value = ""
                page.close(confirm_dialog)
            else:
                error_banner.value = f"Couldn't delete: {err}"
                page.close(confirm_dialog)

            page.update()

        def cancel(e):
            page.close(confirm_dialog)

        confirm_dialog.title = ft.Text("Delete this entry?")
        confirm_dialog.content = ft.Text(f"\"{workout_name}\" will be permanently removed from your log.")
        confirm_dialog.actions = [
            ft.TextButton("Cancel", style=ft.ButtonStyle(color=theme.TEXT_MUTED), on_click=cancel),
            ft.TextButton("Delete", style=ft.ButtonStyle(color=theme.ERROR), on_click=do_delete),
        ]
        page.open(confirm_dialog)

    if not workouts:
        history_list.controls.append(ft.Text("No workouts logged yet.", color=theme.TEXT_MUTED, size=13))
    else:
        for log in workouts:
            entry_id = log.get("id") if isinstance(log, dict) else getattr(log, "id", None)
            name = log.get("workout_name") if isinstance(log, dict) else getattr(log, "workout_name", "Workout")
            duration = log.get("duration_minutes") if isinstance(log, dict) else getattr(log, "duration_minutes", 0)
            calories = log.get("calories_burned") if isinstance(log, dict) else getattr(log, "calories_burned", 0)

            item_card = ft.Container(
                padding=14, border_radius=theme.RADIUS_MD,
                bgcolor=theme.BG_SURFACE, border=ft.border.all(1, theme.BORDER),
            )
            item_card.content = ft.Row([
                ft.Column([
                    ft.Text(name, weight="bold", size=15, color=theme.TEXT_PRIMARY),
                    ft.Text(f"{duration or 0} min • {calories or 0} kcal burned", size=12, color=theme.TEXT_MUTED),
                ], expand=True),
                ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE,
                    icon_color=theme.ERROR,
                    tooltip="Delete workout entry",
                    on_click=lambda e, eid=entry_id, card=item_card, n=name: delete_item(eid, card, n),
                ),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

            history_list.controls.append(item_card)

    return ft.View(
        route="/workout_history",
        bgcolor=theme.BG_CANVAS,
        controls=[
            theme.app_bar("Workout History", on_back=lambda e: page.go("/")),
            ft.Container(
                content=ft.Column([
                    ft.Text("Manage Your Workouts", size=18, weight="bold", color=theme.TEXT_PRIMARY),
                    error_banner,
                    ft.Divider(color=theme.BORDER, height=20),
                    history_list,
                ], expand=True),
                padding=20,
                expand=True,
            ),
        ],
    )
