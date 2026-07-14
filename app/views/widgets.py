"""Small reusable Flet UI pieces shared across views."""

import flet as ft

from app import theme


def macro_ring(label: str, consumed: int, goal: int, color: str, unit: str = "g") -> ft.Control:
    """A progress ring with the macro name / consumed-vs-goal numbers stacked on top."""
    ratio = min(consumed / goal, 1.0) if goal > 0 else 0.0
    return ft.Column(
        [
            ft.Stack(
                [
                    ft.ProgressRing(
                        value=ratio,
                        width=90,
                        height=90,
                        stroke_width=8,
                        color=color,
                        bgcolor=ft.Colors.with_opacity(0.12, color),
                    ),
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Text(f"{consumed}", size=18, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
                                ft.Text(f"/ {goal}{unit}", size=10, color=theme.TEXT_MUTED),
                            ],
                            spacing=0,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        width=90,
                        height=90,
                        alignment=ft.alignment.center,
                    ),
                ],
                width=90,
                height=90,
            ),
            ft.Text(label, size=12, weight=ft.FontWeight.W_500, color=theme.TEXT_MUTED),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=6,
    )


def macro_stat_chip(label: str, value, color: str, unit: str = "g") -> ft.Control:
    return ft.Container(
        content=ft.Column(
            [
                ft.Text(f"{value}{unit}", size=20, weight=ft.FontWeight.BOLD, color=color),
                ft.Text(label, size=11, color=theme.TEXT_MUTED),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=2,
        ),
        bgcolor=ft.Colors.with_opacity(0.1, color),
        border_radius=theme.RADIUS_SM,
        padding=ft.padding.symmetric(vertical=10, horizontal=14),
        expand=True,
        alignment=ft.alignment.center,
    )


def loading_view(message: str) -> ft.Control:
    return ft.Column(
        [
            ft.ProgressRing(width=48, height=48, color=theme.ACCENT),
            ft.Container(height=16),
            ft.Text(message, size=14, color=theme.TEXT_MUTED),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True,
    )


def error_banner(message: str, on_dismiss=None) -> ft.Control:
    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.ERROR_OUTLINE, color=theme.ERROR),
                ft.Text(message, color=theme.TEXT_PRIMARY, expand=True, size=13),
                ft.IconButton(
                    ft.Icons.CLOSE,
                    icon_color=theme.ERROR,
                    icon_size=16,
                    on_click=on_dismiss,
                )
                if on_dismiss
                else ft.Container(),
            ]
        ),
        bgcolor=ft.Colors.with_opacity(0.12, theme.ERROR),
        border=ft.border.all(1, ft.Colors.with_opacity(0.3, theme.ERROR)),
        border_radius=theme.RADIUS_SM,
        padding=12,
    )
