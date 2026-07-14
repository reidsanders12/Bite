"""Shared design tokens for Bite's light, friendly UI.

Every view should import its colors from here instead of hardcoding hex
strings, so the whole app reads as one consistent design instead of a
patchwork of slightly-different surfaces.
"""

import flet as ft

# Backgrounds, lightest to a touch darker
BG_CANVAS = "#F5F6F8"       # page/view background
BG_SURFACE = "#FFFFFF"      # cards, panels
BG_SURFACE_ALT = "#F0F2F5"  # inputs, chips, nested surfaces, unfilled meter tracks

# Borders
BORDER = "#E7E9EC"
BORDER_STRONG = "#D5D9DE"

# Text
TEXT_PRIMARY = "#1A1D29"
TEXT_MUTED = "#6B7280"     # secondary text, labels, captions
TEXT_FAINT = "#9CA3AF"     # tertiary text, placeholders, section eyebrows

# Accent + semantic colors
ACCENT = "#2F86EB"
ACCENT_ON = "#FFFFFF"      # text/icon color when placed on top of ACCENT
# Protein/Carbs/Fat validated as a set for colorblind-safe separation on this
# light surface (the prior dark-theme red/green pairing was a near-worst-case
# deuteranopia confusion; these read fine paired with the direct text labels
# every view already shows beside them).
PROTEIN = "#E34948"
CARBS = "#1BAF7A"
FAT = "#EDA100"
ERROR = "#E5484D"
SUCCESS = "#1BAF7A"

RADIUS_SM = 10
RADIUS_MD = 14
RADIUS_LG = 20

CARD_SHADOW = ft.BoxShadow(
    spread_radius=0,
    blur_radius=16,
    color=ft.Colors.with_opacity(0.06, "#0B1220"),
    offset=ft.Offset(0, 4),
)


def build_theme() -> ft.Theme:
    """App-wide Material theme so default (unstyled) controls still match."""
    return ft.Theme(
        color_scheme_seed=ACCENT,
        use_material3=True,
        color_scheme=ft.ColorScheme(
            primary=ACCENT,
            on_primary=ACCENT_ON,
            surface=BG_SURFACE,
            on_surface=TEXT_PRIMARY,
            surface_variant=BG_SURFACE_ALT,
            on_surface_variant=TEXT_MUTED,
            background=BG_CANVAS,
            on_background=TEXT_PRIMARY,
            error=ERROR,
            on_error="#FFFFFF",
            outline=BORDER,
        ),
        scaffold_bgcolor=BG_CANVAS,
        canvas_color=BG_CANVAS,
        card_color=BG_SURFACE,
        divider_color=BORDER,
        appbar_theme=ft.AppBarTheme(
            bgcolor=BG_CANVAS,
            color=TEXT_PRIMARY,
            elevation=0,
        ),
        filled_button_theme=ft.FilledButtonTheme(
            bgcolor=ACCENT,
            foreground_color=ACCENT_ON,
            shape=ft.RoundedRectangleBorder(radius=RADIUS_SM),
        ),
        text_button_theme=ft.TextButtonTheme(
            foreground_color=TEXT_MUTED,
        ),
        card_theme=ft.CardTheme(
            color=BG_SURFACE,
            shape=ft.RoundedRectangleBorder(radius=RADIUS_MD),
        ),
    )


def styled_field(**overrides) -> dict:
    """Default kwargs to spread into a ft.TextField for on-brand styling."""
    base = dict(
        border_radius=RADIUS_SM,
        border_color=BORDER,
        focused_border_color=ACCENT,
        bgcolor=BG_SURFACE_ALT,
        cursor_color=ACCENT,
    )
    base.update(overrides)
    return base


def styled_dropdown(**overrides) -> dict:
    """Default kwargs to spread into a ft.Dropdown (no cursor_color support)."""
    base = dict(
        border_radius=RADIUS_SM,
        border_color=BORDER,
        focused_border_color=ACCENT,
        bgcolor=BG_SURFACE_ALT,
    )
    base.update(overrides)
    return base


def app_bar(title: str, on_back=None, actions=None) -> ft.AppBar:
    """Consistent AppBar: canvas background, back arrow, muted icon color."""
    return ft.AppBar(
        title=ft.Text(title, weight=ft.FontWeight.BOLD, size=18, color=TEXT_PRIMARY),
        bgcolor=BG_CANVAS,
        elevation=0,
        leading=ft.IconButton(
            icon=ft.Icons.ARROW_BACK,
            icon_color=TEXT_MUTED,
            on_click=on_back,
        )
        if on_back
        else None,
        actions=actions,
    )


def surface_card(content: ft.Control, **overrides) -> ft.Container:
    """Standard elevated card: white surface, soft shadow, rounded corners."""
    base = dict(
        content=content,
        bgcolor=BG_SURFACE,
        border=ft.border.all(1, BORDER),
        border_radius=RADIUS_MD,
        padding=16,
        shadow=CARD_SHADOW,
    )
    base.update(overrides)
    return ft.Container(**base)


def primary_button(text: str, on_click=None, icon=None, **overrides) -> ft.FilledButton:
    """Blue-on-white filled button matching the rest of the app."""
    base = dict(
        text=text,
        icon=icon,
        on_click=on_click,
        style=ft.ButtonStyle(
            bgcolor=ACCENT,
            color=ACCENT_ON,
            shape=ft.RoundedRectangleBorder(radius=RADIUS_SM),
        ),
    )
    base.update(overrides)
    return ft.FilledButton(**base)
