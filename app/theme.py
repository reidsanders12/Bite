"""Shared design tokens for Bite's warm, editorial UI.

Every view should import its colors from here instead of hardcoding hex
strings, so the whole app reads as one consistent design instead of a
patchwork of slightly-different surfaces.
"""

import flet as ft

# Backgrounds: warm paper tones instead of clinical white/gray
BG_CANVAS = "#FAF3EA"      # page/view background (warm cream)
BG_SURFACE = "#FFFDF9"     # cards, panels (barely-off-white paper)
BG_SURFACE_ALT = "#F1E9DC"  # inputs, chips, nested surfaces, unfilled meter tracks

# Borders — editorial style leans on hairlines instead of shadow for structure
BORDER = "#E4D9C7"
BORDER_STRONG = "#CBB99E"

# Text
TEXT_PRIMARY = "#2B2622"  # warm ink, not pure black
TEXT_MUTED = "#75695A"    # secondary text, labels, captions
TEXT_FAINT = "#A79880"    # tertiary text, placeholders, section eyebrows

# Accent + semantic colors
ACCENT = "#C1652F"        # terracotta
ACCENT_ON = "#FFFDF9"     # text/icon color when placed on top of ACCENT
# Protein/Carbs/Fat as a warm rust/olive/mustard set. Distinguishable by both
# hue and lightness (rust is darkest, mustard lightest) so the pairing still
# holds up even before the text labels every view shows beside them kick in.
PROTEIN = "#A8432E"       # rust
CARBS = "#5B7B45"         # olive
FAT = "#D19A3D"           # mustard
ERROR = "#B3261E"
SUCCESS = "#4F7942"

# Sponsor tier colors -- kept in the same warm/muted family as the rest of
# the palette rather than literal metal tones, so a Gold/Category Exclusive
# badge doesn't clash against BG_SURFACE_ALT the way a bright yellow would.
SPONSOR_LEVEL_COLORS = {
    "bronze": "#9C6B44",
    "silver": "#8C8578",
    "gold": FAT,
    "category_exclusive": ACCENT,
}
SPONSOR_LEVEL_LABELS = {
    "bronze": "Bronze",
    "silver": "Silver",
    "gold": "Gold",
    "category_exclusive": "Category Exclusive",
}

RADIUS_SM = 6
RADIUS_MD = 8
RADIUS_LG = 12

# Serif display face for headlines/big numbers; body text stays on the
# platform sans default for readability at small sizes. Registered as a web
# font in main.py (Flet's canvaskit renderer can't use system fonts by name).
DISPLAY_FONT = "Lora"
DISPLAY_FONT_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/lora/Lora%5Bwght%5D.ttf"

CARD_SHADOW = ft.BoxShadow(
    spread_radius=0,
    blur_radius=10,
    color=ft.Colors.with_opacity(0.05, "#6B4F2E"),
    offset=ft.Offset(0, 3),
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
            foreground_color=TEXT_PRIMARY,
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
        title=ft.Text(
            title,
            weight=ft.FontWeight.BOLD,
            size=19,
            color=TEXT_PRIMARY,
            font_family=DISPLAY_FONT,
        ),
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


def macro_tile(value: str, label: str, color: str) -> ft.Container:
    """Small stat tile: bold colored value over a muted label on a chip
    background. Matches the AI Coach's macro tiles (coach_view._remaining_tile)
    so macros read consistently wherever they're shown."""
    return ft.Container(
        content=ft.Column(
            [
                ft.Text(value, size=17, weight="bold", color=color),
                ft.Text(label, size=11, color=TEXT_MUTED),
            ],
            spacing=2,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=BG_SURFACE_ALT,
        border_radius=RADIUS_SM,
        padding=ft.padding.symmetric(vertical=10, horizontal=8),
        expand=True,
        alignment=ft.alignment.center,
    )


def sponsor_level_badge(level: str) -> ft.Container:
    """Small pill showing a sponsor's tier (Bronze/Silver/Gold/Category
    Exclusive), colored via SPONSOR_LEVEL_COLORS. Unrecognized/missing
    levels fall back to Bronze's styling rather than erroring."""
    color = SPONSOR_LEVEL_COLORS.get(level, SPONSOR_LEVEL_COLORS["bronze"])
    label = SPONSOR_LEVEL_LABELS.get(level, "Bronze")
    return ft.Container(
        content=ft.Text(label.upper(), size=10, weight="bold", color=color),
        bgcolor=BG_SURFACE_ALT,
        border=ft.border.all(1, color),
        border_radius=RADIUS_SM,
        padding=ft.padding.symmetric(vertical=3, horizontal=8),
    )


def surface_card(content: ft.Control, **overrides) -> ft.Container:
    """Standard card: paper surface, hairline border, minimal shadow."""
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
    """Terracotta filled button matching the rest of the app."""
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
