"""
Water Tracker: set a daily water intake goal and log entries throughout the
day. Goal + today's log are pulled fresh on every visit (see
app/database.py's WATER TRACKER section) rather than cached across app
restarts client-side, same as Weight Tracking.

Data loading and every mutation (quick add, custom add, goal change,
delete) round-trip to Supabase, so content_area shows a small spinner
while that's in flight instead of the screen looking frozen/unresponsive --
same reasoning as home_view.py's async health section, just applied to a
whole screen instead of one section of it.
"""
import flet as ft

from app import theme

_GOAL_PRESETS_ML = [1500, 2000, 2500, 3000]
_QUICK_ADD_ML = [(250, "Glass"), (500, "Bottle"), (1000, "Large Bottle")]


def build_water_view(page: ft.Page, state) -> ft.View:
    content_area = ft.Container(alignment=ft.alignment.center, expand=True)

    def _spinner(message: str) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                [
                    ft.ProgressRing(width=28, height=28, stroke_width=3, color=theme.ACCENT),
                    ft.Text(message, size=12, color=theme.TEXT_MUTED),
                ],
                spacing=12, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.only(top=80),
            alignment=ft.alignment.center,
        )

    async def reload(busy_message: str = None) -> None:
        if busy_message:
            content_area.content = _spinner(busy_message)
            page.update()
        if hasattr(state, "refresh_water_goal"):
            state.refresh_water_goal()
        if hasattr(state, "refresh_water_logs_today"):
            state.refresh_water_logs_today()
        content_area.content = _build_content()
        page.update()

    def _build_content() -> ft.Control:
        goal_ml = state.get_water_goal() if hasattr(state, "get_water_goal") else 2000
        today_logs = state.get_water_logs_today() if hasattr(state, "get_water_logs_today") else []
        total_ml = state.get_water_total_today_ml() if hasattr(state, "get_water_total_today_ml") else 0

        status_txt = ft.Text("", size=12)

        # --- Progress meter ---

        progress = min(1.0, total_ml / max(1, goal_ml))
        progress_ring = ft.Stack(
            [
                ft.ProgressRing(
                    value=progress, width=132, height=132, stroke_width=12,
                    color=theme.ACCENT, bgcolor=theme.BG_SURFACE_ALT, stroke_cap=ft.StrokeCap.ROUND,
                ),
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text(f"{total_ml:,}", size=26, weight="bold", color=theme.TEXT_PRIMARY),
                            ft.Text(f"of {goal_ml:,}mL", size=12, color=theme.TEXT_MUTED),
                        ],
                        spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    width=132, height=132, alignment=ft.alignment.center,
                ),
            ],
            width=132, height=132,
        )

        # --- Quick add / custom amount ---

        async def on_quick_add(amount_ml: int, e) -> None:
            state.log_water(amount_ml)
            await reload(f"Adding {amount_ml:,}mL...")

        def make_quick_add_handler(amount_ml: int):
            return lambda e: page.run_task(on_quick_add, amount_ml, e)

        quick_add_row = ft.Row(
            [
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.WATER_DROP_ROUNDED, color=theme.ACCENT, size=20),
                            ft.Text(f"+{amount}mL", size=12, weight="w600", color=theme.TEXT_PRIMARY),
                            ft.Text(label, size=10, color=theme.TEXT_MUTED),
                        ],
                        spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    bgcolor=theme.BG_SURFACE_ALT, border=ft.border.all(1, theme.BORDER),
                    border_radius=theme.RADIUS_LG, padding=ft.padding.symmetric(10, 12),
                    on_click=make_quick_add_handler(amount), expand=True,
                )
                for amount, label in _QUICK_ADD_ML
            ],
            spacing=10,
        )

        custom_field = ft.TextField(
            label="Custom amount (mL)",
            keyboard_type=ft.KeyboardType.NUMBER,
            input_filter=ft.InputFilter(regex_string=r"[0-9]", allow=True, replacement_string=""),
            **theme.styled_field(),
        )

        async def on_add_custom(e) -> None:
            try:
                amount = int((custom_field.value or "").strip())
            except ValueError:
                status_txt.value = "Enter a valid whole number."
                status_txt.color = theme.ERROR
                page.update()
                return
            if amount <= 0:
                status_txt.value = "Amount must be greater than zero."
                status_txt.color = theme.ERROR
                page.update()
                return
            state.log_water(amount)
            await reload(f"Adding {amount:,}mL...")

        custom_row = ft.Row(
            [
                ft.Container(custom_field, expand=True),
                theme.primary_button("Add", icon=ft.Icons.ADD, on_click=lambda e: page.run_task(on_add_custom, e)),
            ],
            spacing=10,
        )

        # --- Goal editor ---

        async def on_set_goal(daily_ml: int, e) -> None:
            success, err = state.set_water_goal(daily_ml)
            if success:
                await reload("Saving goal...")
            else:
                status_txt.value = f"Couldn't save goal: {err}"
                status_txt.color = theme.ERROR
                page.update()

        def make_goal_handler(daily_ml: int):
            return lambda e: page.run_task(on_set_goal, daily_ml, e)

        goal_chips = ft.Row(
            [
                ft.Container(
                    content=ft.Text(f"{preset:,}mL", size=13, weight="bold" if preset == goal_ml else "w500",
                                     color=theme.ACCENT_ON if preset == goal_ml else theme.TEXT_MUTED),
                    bgcolor=theme.ACCENT if preset == goal_ml else theme.BG_SURFACE_ALT,
                    border_radius=theme.RADIUS_SM,
                    padding=ft.padding.symmetric(horizontal=14, vertical=8),
                    on_click=None if preset == goal_ml else make_goal_handler(preset),
                )
                for preset in _GOAL_PRESETS_ML
            ],
            spacing=8, wrap=True,
        )

        # --- Today's entries ---

        async def on_delete(entry_id, e) -> None:
            state.remove_water_log(entry_id)
            await reload("Deleting...")

        def make_delete_handler(entry_id):
            return lambda e: page.run_task(on_delete, entry_id, e)

        entries_list = ft.Column(spacing=10)
        if not today_logs:
            entries_list.controls.append(
                ft.Text("No water logged today yet.", color=theme.TEXT_FAINT, italic=True, size=13)
            )
        else:
            for row in today_logs:
                entry_id = row.get("id") if isinstance(row, dict) else getattr(row, "id", None)
                amount = row.get("amount_ml", 0) if isinstance(row, dict) else getattr(row, "amount_ml", 0)
                created_at = row.get("created_at", "") if isinstance(row, dict) else getattr(row, "created_at", "")
                time_str = created_at[11:16] if len(created_at) >= 16 else ""

                entries_list.controls.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Icon(ft.Icons.WATER_DROP_ROUNDED, color=theme.ACCENT, size=16),
                                ft.Text(f"{amount:,}mL", size=14, weight="w600", color=theme.TEXT_PRIMARY, expand=True),
                                ft.Text(time_str, size=12, color=theme.TEXT_MUTED),
                                ft.IconButton(
                                    icon=ft.Icons.DELETE_OUTLINE, icon_color=theme.ERROR, icon_size=18,
                                    tooltip="Delete entry",
                                    on_click=make_delete_handler(entry_id),
                                ),
                            ],
                            spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=ft.padding.symmetric(horizontal=14, vertical=6),
                        border_radius=theme.RADIUS_MD, bgcolor=theme.BG_SURFACE,
                        border=ft.border.all(1, theme.BORDER),
                    )
                )

        return ft.Column(
            [
                ft.Row([progress_ring], alignment=ft.MainAxisAlignment.CENTER),
                ft.Text("QUICK ADD", size=11, color=theme.TEXT_FAINT, weight="w700"),
                quick_add_row,
                custom_row,
                status_txt,
                ft.Divider(color=theme.BORDER, height=20),
                ft.Text("DAILY GOAL", size=11, color=theme.TEXT_FAINT, weight="w700"),
                goal_chips,
                ft.Divider(color=theme.BORDER, height=20),
                ft.Text("Today", size=14, weight="bold", color=theme.TEXT_PRIMARY),
                entries_list,
            ],
            spacing=14,
            scroll=ft.ScrollMode.HIDDEN,
        )

    content_area.content = _spinner("Loading...")
    page.run_task(reload)

    return ft.View(
        route="/water",
        bgcolor=theme.BG_CANVAS,
        controls=[
            theme.app_bar("Water Tracker", on_back=lambda e: page.go("/")),
            ft.Container(content=content_area, padding=20, expand=True),
        ],
    )
