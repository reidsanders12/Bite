"""
Icon-name -> Flet icon mapping for sponsor rows fetched from Supabase's
`sponsors` table (see supabase_circles_schema.sql).

Sponsors are managed entirely through the Supabase Table Editor -- there is
no admin UI in this codebase and no write path from the app. `icon_name` in
that table is a plain string (e.g. "fitness_center") so editing rows in the
Dashboard doesn't require knowing Flet's icon enum; this maps it to the
actual ft.Icons value the home screen renders.
"""
import flet as ft

_ICON_MAP = {
    "fitness_center": ft.Icons.FITNESS_CENTER_ROUNDED,
    "restaurant": ft.Icons.RESTAURANT_ROUNDED,
    "local_offer": ft.Icons.LOCAL_OFFER_ROUNDED,
    "shopping_bag": ft.Icons.SHOPPING_BAG_ROUNDED,
    "spa": ft.Icons.SPA_ROUNDED,
    "campaign": ft.Icons.CAMPAIGN_ROUNDED,
}
_DEFAULT_ICON = ft.Icons.CAMPAIGN_ROUNDED


def icon_for(icon_name: str):
    """Looks up a sponsor row's icon_name against the known set, falling
    back to a generic megaphone icon for anything unrecognized."""
    return _ICON_MAP.get((icon_name or "").strip().lower(), _DEFAULT_ICON)
