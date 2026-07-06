"""Local History & Aggregates view -- everything is read straight from SQLite."""

from datetime import date, timedelta

import flet as ft

from app.state import AppState


def build_history_view(page: ft.Page, state: AppState) -> ft.View:
    days = [date.today() - timedelta(days=i) for i in range(6, -1, -1)]
    daily_totals = [(d, state.db.get_totals_for_date(d)) for d in days]
    max_cal = max((t["calories"] for _, t in daily_totals), default=0) or state.goals.daily_calories

    bar_groups = []
    for i, (d, totals) in enumerate(daily_totals):
        is_today = d == date.today()
        bar_groups.append(
            ft.BarChartGroup(
                x=i,
                bar_rods=[
                    ft.BarChartRod(
                        from_y=0,
                        to_y=totals["calories"],
                        width=22,
                        color=ft.Colors.DEEP_ORANGE if is_today else ft.Colors.DEEP_ORANGE_200,
                        border_radius=6,
                        tooltip=f"{totals['calories']} kcal",
                    )
                ],
            )
        )

    chart = ft.BarChart(
        bar_groups=bar_groups,
        border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
        left_axis=ft.ChartAxis(labels_size=36),
        bottom_axis=ft.ChartAxis(
            labels=[
                ft.ChartAxisLabel(
                    value=i,
                    label=ft.Text(d.strftime("%a"), size=10),
                )
                for i, (d, _) in enumerate(daily_totals)
            ],
        ),
        horizontal_grid_lines=ft.ChartGridLines(
            interval=max(1, round(max_cal / 4)), color=ft.Colors.OUTLINE_VARIANT, width=1
        ),
        max_y=max_cal * 1.2 if max_cal else 100,
        interactive=True,
        height=180,
    )

    all_dates = state.db.get_recent_dates(limit=30)
    sections = []
    for d_str in all_dates:
        entries = state.db.get_logs_for_date(date.fromisoformat(d_str))
        totals = state.db.get_totals_for_date(date.fromisoformat(d_str))
        sections.append(
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(d_str, weight=ft.FontWeight.W_600, size=13),
                            ft.Text(
                                f"{totals['calories']} kcal  •  P{totals['protein']} C{totals['carbs']} F{totals['fat']}",
                                size=12,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    *[
                        ft.ListTile(
                            dense=True,
                            title=ft.Text(e.meal_name, size=13),
                            subtitle=ft.Text(
                                f"{e.calories} kcal • P{e.protein} C{e.carbs} F{e.fat}", size=11
                            ),
                            trailing=ft.IconButton(
                                ft.Icons.DELETE_OUTLINE,
                                icon_size=18,
                                on_click=lambda ev, log_id=e.id: on_delete(log_id),
                            ),
                        )
                        for e in entries
                    ],
                    ft.Divider(),
                ],
                spacing=2,
            )
        )

    log_list = ft.Column(sections, spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)

    def on_delete(log_id: int):
        state.db.delete_log(log_id)
        page.go("/history")  # rebuild the view with fresh data

    return ft.View(
        route="/history",
        controls=[
            ft.AppBar(
                title=ft.Text("History"),
                leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda e: page.go("/")),
            ),
            ft.Container(
                content=ft.Column(
                    [
                        ft.Text("Last 7 days", size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                        chart,
                        ft.Divider(),
                        ft.Text("All logged days", weight=ft.FontWeight.W_600),
                        log_list,
                    ],
                    spacing=12,
                    expand=True,
                ),
                padding=20,
                expand=True,
            ),
        ],
    )
