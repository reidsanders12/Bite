"""
Friend Circles: shared, custom accountability goals with invite-code joining.
"""
import flet as ft

from app import theme

GOAL_TYPE_LABELS = {
    "custom": "Off (check in manually)",
    "workout": "Auto: when I log a workout",
    "calories": "Auto: when I hit a calorie target",
}
GOAL_TYPE_BY_LABEL = {label: key for key, label in GOAL_TYPE_LABELS.items()}


def build_circles_view(page: ft.Page, state) -> ft.View:
    if hasattr(state, "refresh_circles"):
        state.refresh_circles()

    circles = state.get_circles() if hasattr(state, "get_circles") else []
    my_uid = state.db.get_current_user_id() if hasattr(state, "db") else None

    def rerender() -> None:
        # Rebuilds this view fresh from current state and swaps it into the
        # stack in place. More reliable than page.go("/circles") for
        # reflecting a just-made change immediately: navigating to the
        # route you're already on doesn't reliably force every control to
        # re-read fresh state on this Flet version.
        page.views[-1] = build_circles_view(page, state)
        page.update()

    status_txt = ft.Text("", size=12)

    name_field = ft.TextField(label="Circle name", **theme.styled_field())
    goal_field = ft.TextField(label="Goal (e.g. 'Log a workout 4x/week')", **theme.styled_field())
    code_field = ft.TextField(label="Invite code", **theme.styled_field())

    goal_type_dropdown = ft.Dropdown(
        label="Auto check-in",
        value=GOAL_TYPE_LABELS["custom"],
        options=[ft.dropdown.Option(label) for label in GOAL_TYPE_LABELS.values()],
        **theme.styled_dropdown(),
    )
    calorie_target_field = ft.TextField(
        label="Calorie target (kcal)", keyboard_type=ft.KeyboardType.NUMBER,
        visible=False, **theme.styled_field(),
    )

    def on_goal_type_change(e):
        calorie_target_field.visible = goal_type_dropdown.value == GOAL_TYPE_LABELS["calories"]
        page.update()

    goal_type_dropdown.on_change = on_goal_type_change

    create_dialog = ft.AlertDialog(modal=True)
    dialog_error = ft.Text("", color=theme.ERROR, size=12)

    def show_status(message: str, ok: bool) -> None:
        status_txt.value = message
        status_txt.color = theme.SUCCESS if ok else theme.ERROR
        page.update()

    def open_create_dialog(e):
        name_field.value = ""
        goal_field.value = ""
        goal_type_dropdown.value = GOAL_TYPE_LABELS["custom"]
        calorie_target_field.value = ""
        calorie_target_field.visible = False
        dialog_error.value = ""
        page.open(create_dialog)

    def create_circle(e):
        name = (name_field.value or "").strip()
        goal = (goal_field.value or "").strip()
        goal_type = GOAL_TYPE_BY_LABEL.get(goal_type_dropdown.value, "custom")

        goal_value = None
        if goal_type == "calories":
            try:
                goal_value = int((calorie_target_field.value or "").strip())
            except ValueError:
                dialog_error.value = "Enter a whole number for the calorie target."
                page.update()
                return

        if not name or not goal:
            dialog_error.value = "Enter a name and a goal."
            page.update()
            return

        circle, err = state.create_circle(name, goal, goal_type, goal_value)
        if circle:
            page.close(create_dialog)
            rerender()
        else:
            dialog_error.value = f"Couldn't create circle: {err}"
            page.update()

    create_dialog.title = ft.Text("New Circle")
    create_dialog.content = ft.Column(
        [name_field, goal_field, goal_type_dropdown, calorie_target_field, dialog_error],
        spacing=12,
        tight=True,
        width=340,
    )
    create_dialog.actions = [
        ft.TextButton("Cancel", style=ft.ButtonStyle(color=theme.TEXT_MUTED), on_click=lambda e: page.close(create_dialog)),
        ft.TextButton("Create", style=ft.ButtonStyle(color=theme.ACCENT), on_click=create_circle),
    ]

    # --- Edit an existing circle's goal (creator-only; enforced server-side
    # too via the circles_update_own RLS policy) ---
    editing_circle_id = None

    edit_goal_field = ft.TextField(label="Goal", **theme.styled_field())
    edit_goal_type_dropdown = ft.Dropdown(
        label="Auto check-in",
        options=[ft.dropdown.Option(label) for label in GOAL_TYPE_LABELS.values()],
        **theme.styled_dropdown(),
    )
    edit_calorie_target_field = ft.TextField(
        label="Calorie target (kcal)", keyboard_type=ft.KeyboardType.NUMBER,
        visible=False, **theme.styled_field(),
    )
    edit_dialog_error = ft.Text("", color=theme.ERROR, size=12)
    edit_dialog = ft.AlertDialog(modal=True)

    def on_edit_goal_type_change(e):
        edit_calorie_target_field.visible = edit_goal_type_dropdown.value == GOAL_TYPE_LABELS["calories"]
        page.update()

    edit_goal_type_dropdown.on_change = on_edit_goal_type_change

    def make_open_edit_handler(circle):
        def handler(e):
            nonlocal editing_circle_id
            editing_circle_id = circle.id
            edit_goal_field.value = circle.goal_description
            edit_goal_type_dropdown.value = GOAL_TYPE_LABELS.get(circle.goal_type, GOAL_TYPE_LABELS["custom"])
            edit_calorie_target_field.value = str(circle.goal_value) if circle.goal_value else ""
            edit_calorie_target_field.visible = circle.goal_type == "calories"
            edit_dialog_error.value = ""
            page.open(edit_dialog)
        return handler

    def save_edit_goal(e):
        goal = (edit_goal_field.value or "").strip()
        goal_type = GOAL_TYPE_BY_LABEL.get(edit_goal_type_dropdown.value, "custom")

        goal_value = None
        if goal_type == "calories":
            try:
                goal_value = int((edit_calorie_target_field.value or "").strip())
            except ValueError:
                edit_dialog_error.value = "Enter a whole number for the calorie target."
                page.update()
                return

        if not goal:
            edit_dialog_error.value = "Enter a goal."
            page.update()
            return

        success, err = state.update_circle_goal(editing_circle_id, goal, goal_type, goal_value)
        if success:
            page.close(edit_dialog)
            rerender()
        else:
            edit_dialog_error.value = f"Couldn't save: {err}"
            page.update()

    edit_dialog.title = ft.Text("Edit Circle Goal")
    edit_dialog.content = ft.Column(
        [edit_goal_field, edit_goal_type_dropdown, edit_calorie_target_field, edit_dialog_error],
        spacing=12,
        tight=True,
        width=340,
    )
    edit_dialog.actions = [
        ft.TextButton("Cancel", style=ft.ButtonStyle(color=theme.TEXT_MUTED), on_click=lambda e: page.close(edit_dialog)),
        ft.TextButton("Save", style=ft.ButtonStyle(color=theme.ACCENT), on_click=save_edit_goal),
    ]

    def join_circle(e):
        code = (code_field.value or "").strip()
        if not code:
            show_status("Enter an invite code.", ok=False)
            return
        circle, err = state.join_circle(code)
        if circle:
            rerender()
        else:
            show_status(f"Couldn't join: {err}", ok=False)

    def make_checkin_handler(circle_id, was_checked_in):
        # Toggles rather than only ever checking in -- an accidental tap
        # used to be permanent (disabled=already_checked_in, no way back)
        # until undo_checkin_circle existed.
        def handler(e):
            if was_checked_in:
                success, err = state.undo_checkin_circle(circle_id)
                verb = "undo check-in"
            else:
                success, err = state.check_in_circle(circle_id)
                verb = "check in"
            if success:
                rerender()
            else:
                show_status(f"Couldn't {verb}: {err}", ok=False)
        return handler

    def make_leave_handler(circle_id):
        def handler(e):
            state.leave_circle(circle_id)
            rerender()
        return handler

    # Creators delete the whole circle rather than "leave" it -- leaving as
    # creator would orphan the circle (still in the DB, invite code still
    # works, but with no owner able to edit/delete it afterward).
    delete_confirm_dialog = ft.AlertDialog(modal=True)

    def make_delete_handler(circle_id, circle_name):
        def open_confirm(e):
            def do_delete(e2):
                success, err = state.delete_circle(circle_id)
                page.close(delete_confirm_dialog)
                if success:
                    rerender()
                else:
                    show_status(f"Couldn't delete: {err}", ok=False)

            def cancel(e2):
                page.close(delete_confirm_dialog)

            delete_confirm_dialog.title = ft.Text("Delete this circle?")
            delete_confirm_dialog.content = ft.Text(
                f"\"{circle_name}\" will be permanently deleted for every member, "
                "including everyone's check-in history."
            )
            delete_confirm_dialog.actions = [
                ft.TextButton("Cancel", style=ft.ButtonStyle(color=theme.TEXT_MUTED), on_click=cancel),
                ft.TextButton("Delete", style=ft.ButtonStyle(color=theme.ERROR), on_click=do_delete),
            ]
            page.open(delete_confirm_dialog)
        return open_confirm

    circle_cards = ft.Column(spacing=14)
    if not circles:
        circle_cards.controls.append(
            ft.Container(
                content=ft.Text("You're not in any circles yet.", color=theme.TEXT_FAINT, italic=True),
                padding=20,
                alignment=ft.alignment.center,
            )
        )
    else:
        for circle in circles:
            members = state.get_circle_status(circle.id) if hasattr(state, "get_circle_status") else []

            member_rows = []
            for m in members:
                is_me = m.user_id == my_uid
                icon = ft.Icons.CHECK_CIRCLE if m.checked_in_today else ft.Icons.RADIO_BUTTON_UNCHECKED
                icon_color = theme.SUCCESS if m.checked_in_today else theme.TEXT_FAINT
                member_rows.append(
                    ft.Row(
                        [
                            ft.Icon(icon, color=icon_color, size=18),
                            ft.Text(
                                f"{m.display_name}{' (you)' if is_me else ''}",
                                size=13,
                                color=theme.TEXT_PRIMARY,
                                expand=True,
                            ),
                            ft.Text(f"{m.streak_days}d streak", size=11, color=theme.TEXT_MUTED),
                        ]
                    )
                )

            already_checked_in = any(m.user_id == my_uid and m.checked_in_today for m in members)
            is_auto = circle.goal_type != "custom"

            goal_line_parts = [circle.goal_description]
            if circle.goal_type == "workout":
                goal_line_parts.append("(auto: logs a workout)")
            elif circle.goal_type == "calories":
                goal_line_parts.append(f"(auto: hits {circle.goal_value or 0} kcal)")

            circle_cards.controls.append(
                theme.surface_card(
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(circle.name, size=16, weight="bold", color=theme.TEXT_PRIMARY, expand=True),
                                    ft.IconButton(
                                        icon=ft.Icons.EDIT_OUTLINED,
                                        icon_color=theme.TEXT_MUTED,
                                        icon_size=18,
                                        tooltip="Edit goal",
                                        on_click=make_open_edit_handler(circle),
                                    ) if circle.created_by == my_uid else ft.Container(),
                                    ft.TextButton(
                                        "Delete",
                                        style=ft.ButtonStyle(color=theme.ERROR),
                                        on_click=make_delete_handler(circle.id, circle.name),
                                    ) if circle.created_by == my_uid else ft.TextButton(
                                        "Leave",
                                        style=ft.ButtonStyle(color=theme.ERROR),
                                        on_click=make_leave_handler(circle.id),
                                    ),
                                ]
                            ),
                            ft.Text(" ".join(goal_line_parts), size=13, color=theme.TEXT_MUTED),
                            ft.Divider(color=theme.BORDER, height=1),
                            ft.Column(member_rows, spacing=8) if member_rows else ft.Container(),
                            ft.Text(f"Invite code: {circle.invite_code}", size=11, color=theme.TEXT_FAINT),
                            theme.primary_button(
                                "Checked in -- tap to undo" if already_checked_in else "Mark today's goal done",
                                icon=ft.Icons.UNDO if already_checked_in else ft.Icons.CHECK,
                                on_click=make_checkin_handler(circle.id, already_checked_in),
                            ) if not is_auto else ft.Text(
                                "Checked in for today" if already_checked_in else "Not yet today -- checks in automatically",
                                size=12, color=theme.SUCCESS if already_checked_in else theme.TEXT_FAINT,
                            ),
                        ],
                        spacing=10,
                    )
                )
            )

    return ft.View(
        route="/circles",
        bgcolor=theme.BG_CANVAS,
        floating_action_button=ft.FloatingActionButton(
            icon=ft.Icons.ADD,
            tooltip="New Circle",
            bgcolor=theme.ACCENT,
            foreground_color=theme.ACCENT_ON,
            on_click=open_create_dialog,
        ),
        controls=[
            theme.app_bar("Friend Circles", on_back=lambda e: page.go("/")),
            ft.Container(
                content=ft.Column(
                    [
                        circle_cards,
                        ft.Divider(color=theme.BORDER, height=28),
                        ft.Text("Join a circle", size=14, weight="bold", color=theme.TEXT_PRIMARY),
                        code_field,
                        theme.primary_button("Join Circle", icon=ft.Icons.GROUP_ADD, on_click=join_circle),
                        status_txt,
                    ],
                    spacing=12,
                    scroll=ft.ScrollMode.HIDDEN,
                ),
                padding=20,
                expand=True,
            ),
        ],
    )
