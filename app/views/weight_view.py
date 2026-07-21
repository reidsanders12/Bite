"""
Weight Tracking view: log your weight and see a trend chart over time.
Always stored in kg; displayed in whichever unit is selected here (defaults
to whatever the onboarding survey used, but can be switched on this screen).
"""
import math

import flet as ft

from app import theme

LB_PER_KG = 2.20462
_AXIS_STEP = 0.5


def _snap(value: float, round_up: bool) -> float:
    """Rounds an axis bound out to the nearest _AXIS_STEP, so min/max never
    land a fraction of a unit away from fl_chart's own auto-generated tick
    marks (that near-duplicate spacing is what caused overlapping axis labels)."""
    rounder = math.ceil if round_up else math.floor
    return rounder(value / _AXIS_STEP) * _AXIS_STEP


def build_weight_view(page: ft.Page, state) -> ft.View:
    if hasattr(state, "refresh_weight_history"):
        state.refresh_weight_history()

    history = state.get_weight_history() if hasattr(state, "get_weight_history") else []
    profile = state.get_profile_data() if hasattr(state, "get_profile_data") else {}
    is_imperial = profile.get("unit_system") == "imperial"
    unit_label = "lb" if is_imperial else "kg"

    def to_display(weight_kg: float) -> float:
        return weight_kg * LB_PER_KG if is_imperial else weight_kg

    def to_kg(display_weight: float) -> float:
        return display_weight / LB_PER_KG if is_imperial else display_weight

    def rerender() -> None:
        page.views[-1] = build_weight_view(page, state)
        page.update()

    def set_unit_system(unit: str):
        def handler(e):
            if hasattr(state, "save_profile_data"):
                state.save_profile_data({"unit_system": unit})
            rerender()
        return handler

    def _unit_pill(label: str, unit_value: str, active: bool) -> ft.Control:
        return ft.Container(
            content=ft.Text(
                label, size=13, weight="bold" if active else "w500",
                color=theme.ACCENT_ON if active else theme.TEXT_MUTED,
            ),
            bgcolor=theme.ACCENT if active else None,
            border_radius=theme.RADIUS_SM,
            padding=ft.padding.symmetric(horizontal=16, vertical=8),
            on_click=None if active else set_unit_system(unit_value),
        )

    unit_toggle = ft.Container(
        content=ft.Row(
            [_unit_pill("kg", "metric", not is_imperial), _unit_pill("lb", "imperial", is_imperial)],
            spacing=4,
        ),
        bgcolor=theme.BG_SURFACE_ALT,
        border_radius=theme.RADIUS_SM,
        padding=4,
    )

    weight_field = ft.TextField(
        label=f"Today's weight ({unit_label})",
        keyboard_type=ft.KeyboardType.NUMBER,
        input_filter=ft.InputFilter(regex_string=r"[0-9.]", allow=True, replacement_string=""),
        **theme.styled_field(),
    )
    status_txt = ft.Text("", size=12)

    def save_weight(e):
        try:
            display_value = float((weight_field.value or "").strip())
        except ValueError:
            status_txt.value = "Enter a valid number."
            status_txt.color = theme.ERROR
            page.update()
            return

        if display_value <= 0:
            status_txt.value = "Weight must be greater than zero."
            status_txt.color = theme.ERROR
            page.update()
            return

        state.log_weight(to_kg(display_value))
        rerender()

    def make_delete_handler(entry_id):
        def handler(e):
            state.remove_weight_log(entry_id)
            rerender()
        return handler

    # Trend chart -- only meaningful with 2+ points
    chart_section: ft.Control = ft.Container()
    if len(history) >= 2:
        display_weights = [to_display(
            row.get("weight_kg", 0) if isinstance(row, dict) else getattr(row, "weight_kg", 0)
        ) for row in history]
        points = [
            ft.LineChartDataPoint(i, w, tooltip=f"{w:.2f} {unit_label}")
            for i, w in enumerate(display_weights)
        ]
        min_w, max_w = min(display_weights), max(display_weights)
        # Generous, fixed headroom (not just a % of the span) so the tooltip
        # over the highest point always has room above it instead of
        # overlapping the axis labels in that corner. Bounds are then snapped
        # to round numbers so they never land a fraction of a unit away from
        # fl_chart's own auto tick marks -- that's what produced the
        # overlapping "85.2"/"85" labels before.
        padding = max(1.5, (max_w - min_w) * 0.25)
        min_y = _snap(min_w - padding, round_up=False)
        max_y = _snap(max_w + padding, round_up=True)

        chart_section = ft.Container(
            content=ft.LineChart(
                data_series=[
                    ft.LineChartData(
                        data_points=points,
                        curved=True,
                        color=theme.ACCENT,
                        stroke_width=3,
                        point=True,
                        below_line_gradient=ft.LinearGradient(
                            begin=ft.alignment.top_center,
                            end=ft.alignment.bottom_center,
                            colors=[ft.Colors.with_opacity(0.25, theme.ACCENT), ft.Colors.with_opacity(0, theme.ACCENT)],
                        ),
                    ),
                ],
                min_y=min_y,
                max_y=max_y,
                min_x=0,
                max_x=max(1, len(display_weights) - 1),
                left_axis=ft.ChartAxis(labels_size=54),
                bottom_axis=ft.ChartAxis(show_labels=False),
                tooltip_bgcolor=theme.BG_SURFACE_ALT,
                tooltip_fit_inside_horizontally=True,
                tooltip_fit_inside_vertically=True,
                interactive=True,
                expand=True,
            ),
            height=220,
            padding=16,
            border_radius=theme.RADIUS_LG,
            bgcolor=theme.BG_SURFACE,
            border=ft.border.all(1, theme.BORDER),
            shadow=theme.CARD_SHADOW,
        )

    trend_txt = ft.Container()
    if len(history) >= 2:
        first_kg = history[0].get("weight_kg", 0) if isinstance(history[0], dict) else getattr(history[0], "weight_kg", 0)
        last_kg = history[-1].get("weight_kg", 0) if isinstance(history[-1], dict) else getattr(history[-1], "weight_kg", 0)
        delta = to_display(last_kg) - to_display(first_kg)
        arrow = "▲" if delta > 0 else ("▼" if delta < 0 else "―")
        trend_txt = ft.Text(
            f"{arrow} {abs(delta):.2f} {unit_label} over {len(history)} entries",
            size=13, color=theme.TEXT_MUTED,
        )

    entries_list = ft.Column(spacing=10)
    if not history:
        entries_list.controls.append(
            ft.Text("No weight entries yet.", color=theme.TEXT_FAINT, italic=True, size=13)
        )
    else:
        for row in reversed(history):
            entry_id = row.get("id") if isinstance(row, dict) else getattr(row, "id", None)
            weight_kg = row.get("weight_kg", 0) if isinstance(row, dict) else getattr(row, "weight_kg", 0)
            created_at = row.get("created_at", "") if isinstance(row, dict) else getattr(row, "created_at", "")
            date_str = created_at[:10] if created_at else ""

            entries_list.controls.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Text(f"{to_display(weight_kg):.2f} {unit_label}", size=14, weight="w600", color=theme.TEXT_PRIMARY, expand=True),
                            ft.Text(date_str, size=12, color=theme.TEXT_MUTED),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE, icon_color=theme.ERROR, icon_size=18,
                                tooltip="Delete entry",
                                on_click=make_delete_handler(entry_id),
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.padding.symmetric(horizontal=14, vertical=6),
                    border_radius=theme.RADIUS_MD, bgcolor=theme.BG_SURFACE,
                    border=ft.border.all(1, theme.BORDER),
                )
            )

    return ft.View(
        route="/weight",
        bgcolor=theme.BG_CANVAS,
        controls=[
            theme.app_bar("Weight Tracking", on_back=lambda e: page.go("/")),
            ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [ft.Text("Units", size=12, color=theme.TEXT_MUTED), unit_toggle],
                            spacing=10,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.Row([weight_field, theme.primary_button("Log", icon=ft.Icons.ADD, on_click=save_weight)], spacing=10),
                        status_txt,
                        chart_section,
                        trend_txt,
                        ft.Divider(color=theme.BORDER, height=20),
                        ft.Text("History", size=14, weight="bold", color=theme.TEXT_PRIMARY),
                        entries_list,
                    ],
                    spacing=14,
                    scroll=ft.ScrollMode.AUTO,
                ),
                padding=20,
                expand=True,
            ),
        ],
    )
