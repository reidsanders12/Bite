"""
Sponsor Requests: review sponsor submissions (from sponsor_signup.html or
anywhere else that posts to the `sponsors` table) and approve/reject them
before they can ever show on the home screen.

Only reachable if state.is_admin() is True (your email matches ADMIN_EMAIL
in .env) -- everyone else never sees the nav link, and even if they guessed
the route, the sponsors_select_owner RLS policy means the query just comes
back empty for them.
"""
import flet as ft

from app import promotions
from app import theme


def build_sponsor_requests_view(page: ft.Page, state) -> ft.View:
    if hasattr(state, "refresh_sponsor_requests"):
        state.refresh_sponsor_requests()

    requests = state.get_sponsor_requests() if hasattr(state, "get_sponsor_requests") else []
    status_txt = ft.Text("", size=12)

    def rerender() -> None:
        page.views[-1] = build_sponsor_requests_view(page, state)
        page.update()

    def show_status(message: str, ok: bool) -> None:
        status_txt.value = message
        status_txt.color = theme.SUCCESS if ok else theme.ERROR
        page.update()

    def make_approve_handler(sponsor_id):
        def handler(e):
            success, err = state.approve_sponsor(sponsor_id)
            if success:
                rerender()
            else:
                show_status(f"Couldn't approve: {err}", ok=False)
        return handler

    def make_reject_handler(sponsor_id):
        def handler(e):
            success, err = state.reject_sponsor(sponsor_id)
            if success:
                rerender()
            else:
                show_status(f"Couldn't reject: {err}", ok=False)
        return handler

    def make_toggle_active_handler(sponsor_id):
        def handler(e):
            success, err = state.set_sponsor_active(sponsor_id, e.control.value)
            if not success:
                show_status(f"Couldn't update: {err}", ok=False)
                rerender()
        return handler

    # --- Manage Menu (Gold-tier native integration: menu items / classes) ---

    menu_dialog = ft.AlertDialog(modal=True)

    def open_menu_dialog(sponsor: dict):
        sponsor_id = sponsor["id"]
        items_column = ft.Column(spacing=6)

        name_field = ft.TextField(label="Item name", **theme.styled_field())
        type_dropdown = ft.Dropdown(
            label="Type",
            value="meal",
            options=[
                ft.dropdown.Option("meal", "Meal (one-tap log)"),
                ft.dropdown.Option("workout", "Workout (suggested class)"),
            ],
            **theme.styled_dropdown(),
        )
        cal_field = ft.TextField(label="Calories", keyboard_type=ft.KeyboardType.NUMBER, **theme.styled_field())
        protein_field = ft.TextField(label="Protein (g)", keyboard_type=ft.KeyboardType.NUMBER, **theme.styled_field())
        carbs_field = ft.TextField(label="Carbs (g)", keyboard_type=ft.KeyboardType.NUMBER, **theme.styled_field())
        fat_field = ft.TextField(label="Fat (g)", keyboard_type=ft.KeyboardType.NUMBER, **theme.styled_field())
        meal_fields_row = ft.Row([cal_field, protein_field, carbs_field, fat_field], spacing=6, wrap=True)

        duration_field = ft.TextField(label="Duration (min)", keyboard_type=ft.KeyboardType.NUMBER, **theme.styled_field())
        cal_burned_field = ft.TextField(label="Calories burned", keyboard_type=ft.KeyboardType.NUMBER, **theme.styled_field())
        workout_fields_row = ft.Row([duration_field, cal_burned_field], spacing=6, visible=False)

        add_status = ft.Text("", size=12)

        def on_type_change(e):
            is_meal = type_dropdown.value == "meal"
            meal_fields_row.visible = is_meal
            workout_fields_row.visible = not is_meal
            page.update()
        type_dropdown.on_change = on_type_change

        def load_items():
            items = state.get_sponsor_menu_items_admin(sponsor_id)
            if not items:
                items_column.controls = [ft.Text("No items yet.", size=12, color=theme.TEXT_FAINT, italic=True)]
                return
            rows = []
            for item in items:
                if item.get("item_type") == "workout":
                    detail = f"{item.get('duration_minutes') or 0} min • {item.get('calories_burned') or 0} kcal burned"
                else:
                    detail = (
                        f"{item.get('calories') or 0} kcal • P{item.get('protein') or 0} "
                        f"C{item.get('carbs') or 0} F{item.get('fat') or 0}"
                    )
                rows.append(
                    ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Text(item.get("name", ""), size=13, weight="bold", color=theme.TEXT_PRIMARY),
                                    ft.Text(detail, size=11, color=theme.TEXT_MUTED),
                                ],
                                expand=True, spacing=0,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE, icon_color=theme.ERROR, icon_size=18,
                                on_click=make_delete_item_handler(item["id"]),
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    )
                )
            items_column.controls = rows

        def make_delete_item_handler(item_id):
            def handler(e):
                success, err = state.delete_sponsor_menu_item(item_id)
                if success:
                    load_items()
                    page.update()
                else:
                    add_status.value = err
                    add_status.color = theme.ERROR
                    page.update()
            return handler

        def parse_int(field: ft.TextField) -> int:
            raw = (field.value or "").strip()
            return int(raw) if raw else None

        def on_add_item(e):
            name = (name_field.value or "").strip()
            if not name:
                add_status.value = "Item name is required."
                add_status.color = theme.ERROR
                page.update()
                return
            try:
                if type_dropdown.value == "meal":
                    fields = {
                        "calories": parse_int(cal_field), "protein": parse_int(protein_field),
                        "carbs": parse_int(carbs_field), "fat": parse_int(fat_field),
                    }
                else:
                    fields = {
                        "duration_minutes": parse_int(duration_field),
                        "calories_burned": parse_int(cal_burned_field),
                    }
            except ValueError:
                add_status.value = "Numbers only, please."
                add_status.color = theme.ERROR
                page.update()
                return

            success, err = state.add_sponsor_menu_item(sponsor_id, type_dropdown.value, name, **fields)
            if success:
                name_field.value = ""
                for f in (cal_field, protein_field, carbs_field, fat_field, duration_field, cal_burned_field):
                    f.value = ""
                add_status.value = "Added."
                add_status.color = theme.SUCCESS
                load_items()
            else:
                add_status.value = err
                add_status.color = theme.ERROR
            page.update()

        def close_dialog(e):
            page.close(menu_dialog)

        load_items()
        menu_dialog.title = ft.Text(f"Manage Menu -- {sponsor.get('title', '')}")
        menu_dialog.content = ft.Container(
            content=ft.Column(
                [
                    items_column,
                    ft.Divider(color=theme.BORDER, height=20),
                    ft.Text("Add item", size=12, weight="bold", color=theme.TEXT_PRIMARY),
                    type_dropdown,
                    name_field,
                    meal_fields_row,
                    workout_fields_row,
                    theme.primary_button("Add Item", icon=ft.Icons.ADD, on_click=on_add_item),
                    add_status,
                ],
                spacing=10, scroll=ft.ScrollMode.HIDDEN, tight=True,
            ),
            width=380, height=420,
        )
        menu_dialog.actions = [ft.TextButton("Done", on_click=close_dialog)]
        page.open(menu_dialog)

    def make_manage_menu_handler(sponsor):
        def handler(e):
            open_menu_dialog(sponsor)
        return handler

    def sponsor_row(s: dict, actions: ft.Control) -> ft.Control:
        contact_bits = [s.get("contact_name") or "", s.get("contact_email") or ""]
        contact_line = " • ".join(b for b in contact_bits if b)
        category = (s.get("category") or "").strip()
        return theme.surface_card(
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(promotions.icon_for(s.get("icon_name")), size=22, color=theme.ACCENT),
                            ft.Column(
                                [
                                    ft.Text(s.get("title", ""), size=15, weight="bold", color=theme.TEXT_PRIMARY),
                                    ft.Text(s.get("subtitle", ""), size=12, color=theme.TEXT_MUTED),
                                ],
                                expand=True,
                                spacing=2,
                            ),
                            theme.sponsor_level_badge(s.get("level")),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    ),
                    ft.Text(f"Category: {category}", size=11, color=theme.TEXT_FAINT) if category else ft.Container(),
                    ft.Text(f"CTA: \"{s.get('cta_text', '')}\"", size=11, color=theme.TEXT_FAINT),
                    ft.Text(s["website_url"], size=11, color=theme.ACCENT) if s.get("website_url") else ft.Container(),
                    ft.Text(contact_line, size=11, color=theme.TEXT_FAINT) if contact_line else ft.Container(),
                    actions,
                ],
                spacing=8,
            )
        )

    pending = [s for s in requests if s.get("status") == "pending"]
    approved = [s for s in requests if s.get("status") == "approved"]
    rejected = [s for s in requests if s.get("status") == "rejected"]

    pending_cards = ft.Column(spacing=12)
    if not pending:
        pending_cards.controls.append(ft.Text("No pending requests.", color=theme.TEXT_FAINT, italic=True, size=13))
    else:
        for s in pending:
            actions = ft.Row(
                [
                    theme.primary_button("Approve", icon=ft.Icons.CHECK, on_click=make_approve_handler(s["id"])),
                    ft.TextButton("Reject", style=ft.ButtonStyle(color=theme.ERROR), on_click=make_reject_handler(s["id"])),
                ],
                spacing=10,
            )
            pending_cards.controls.append(sponsor_row(s, actions))

    approved_cards = ft.Column(spacing=12)
    if not approved:
        approved_cards.controls.append(ft.Text("No approved sponsors.", color=theme.TEXT_FAINT, italic=True, size=13))
    else:
        for s in approved:
            action_controls = [
                ft.Text("Live on home screen", size=12, color=theme.TEXT_MUTED, expand=True),
                ft.Switch(value=bool(s.get("active")), active_color=theme.ACCENT, on_change=make_toggle_active_handler(s["id"])),
            ]
            # Menu items only ever surface for Gold sponsors (see
            # sponsor_menu_items_select_gold_active RLS) -- hide the button
            # for other tiers so it can't create rows that never show.
            if s.get("level") == "gold":
                action_controls.insert(
                    0,
                    ft.TextButton(
                        "Manage Menu", icon=ft.Icons.RESTAURANT_MENU_ROUNDED,
                        style=ft.ButtonStyle(color=theme.ACCENT),
                        on_click=make_manage_menu_handler(s),
                    ),
                )
            actions = ft.Row(action_controls)
            approved_cards.controls.append(sponsor_row(s, actions))

    rejected_cards = ft.Column(spacing=12)
    if not rejected:
        rejected_cards.controls.append(ft.Text("No rejected requests.", color=theme.TEXT_FAINT, italic=True, size=13))
    else:
        for s in rejected:
            rejected_cards.controls.append(sponsor_row(s, ft.Text("Rejected", size=12, color=theme.ERROR)))

    return ft.View(
        route="/sponsor_requests",
        bgcolor=theme.BG_CANVAS,
        controls=[
            theme.app_bar("Sponsor Requests", on_back=lambda e: page.go("/profile")),
            ft.Container(
                content=ft.Column(
                    [
                        status_txt,
                        ft.Text(f"PENDING ({len(pending)})", size=11, color=theme.TEXT_FAINT, weight="w700"),
                        pending_cards,
                        ft.Divider(color=theme.BORDER, height=28),
                        ft.Text(f"APPROVED ({len(approved)})", size=11, color=theme.TEXT_FAINT, weight="w700"),
                        approved_cards,
                        ft.Divider(color=theme.BORDER, height=28),
                        ft.Text(f"REJECTED ({len(rejected)})", size=11, color=theme.TEXT_FAINT, weight="w700"),
                        rejected_cards,
                    ],
                    spacing=12,
                    scroll=ft.ScrollMode.HIDDEN,
                ),
                padding=20,
                expand=True,
            ),
        ],
    )
