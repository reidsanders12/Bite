"""
Meal Feed view: browse meal posts visible to you (your own, everyone's
public posts, and circle-only posts from circles you belong to), like a
post anonymously (see database.py's meal_post_likes RLS -- nobody, not even
the app, can see who liked what, only the total), and jump to Post a Meal.

Calorie/macro numbers are deliberately never rendered here for anyone else's
post -- only the author sees their own post's numbers, and only on their own
card. Meal Feed is a social feed, not a place to compare or rank food
between users (see the safety review this shipped with); your own personal
totals still live in History/Coach, unaffected by this.
"""
from datetime import datetime, timezone

import flet as ft

from app import theme

_REPORT_CATEGORIES = [
    ("harassment", "Harassment or bullying"),
    ("pro_ed_content", "Pro-eating-disorder content"),
    ("copyright", "Copyright / trademark infringement"),
    ("spam", "Spam or scam"),
    ("other", "Other"),
]

# Placeholder resource -- confirm the exact org/hotline/wording with product
# before shipping; see the safety review's Area 1 for why this exists (a
# lightweight "Get support" link next to reporting, similar to major
# platforms' self-harm-adjacent content flows).
_SUPPORT_RESOURCE_TEXT = (
    "If this is about your own relationship with food or your body, you're not alone. "
    "The National Eating Disorders Association (NEDA) Helpline: call/text 1-800-931-2237."
)


def _open_support_dialog(page: ft.Page) -> None:
    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Get support"),
        content=ft.Text(_SUPPORT_RESOURCE_TEXT, size=13),
        actions=[ft.TextButton("Close", on_click=lambda e: page.close(dialog))],
    )
    page.open(dialog)


def _relative_time(created_at: str) -> str:
    if not created_at:
        return ""
    try:
        ts = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        return created_at[:10]

    delta = datetime.now(timezone.utc) - ts
    seconds = delta.total_seconds()
    if seconds < 60:
        return "just now"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes}m ago"
    hours = int(minutes // 60)
    if hours < 24:
        return f"{hours}h ago"
    days = int(hours // 24)
    if days < 7:
        return f"{days}d ago"
    return ts.strftime("%b %d")


def _post_card(post: dict, circle_names: dict, my_uid, state, page: ft.Page, rerender) -> ft.Control:
    post_id = post.get("id")
    author_id = post.get("user_id")
    name = post.get("display_name") or "Bite User"
    caption = post.get("caption") or ""
    photo_url = post.get("photo_url")
    time_str = _relative_time(post.get("created_at") or "")
    visibility = post.get("visibility", "public")
    circle_id = post.get("circle_id")
    tag_text = circle_names.get(circle_id, "Circle") if visibility == "circle" else "Public"
    tag_icon = ft.Icons.GROUPS_OUTLINED if visibility == "circle" else ft.Icons.PUBLIC_ROUNDED
    is_own = author_id == my_uid
    liked = state.has_liked(post_id) if hasattr(state, "has_liked") else False
    like_count = state.get_like_count(post_id) if hasattr(state, "get_like_count") else 0

    def on_toggle_like(e):
        state.toggle_meal_post_like(post_id)
        rerender()

    def on_delete(e):
        state.remove_meal_post(post_id)
        rerender()

    report_dialog = ft.AlertDialog(modal=True)
    category_dropdown = ft.Dropdown(
        label="What's wrong with this post?",
        options=[ft.dropdown.Option(key, label) for key, label in _REPORT_CATEGORIES],
        value=_REPORT_CATEGORIES[0][0],
        **theme.styled_dropdown(),
    )
    reason_field = ft.TextField(
        label="Details (optional)", multiline=True, min_lines=2, max_lines=4,
        **theme.styled_field(),
    )

    def open_report_dialog(e):
        category_dropdown.value = _REPORT_CATEGORIES[0][0]
        reason_field.value = ""
        reason_field.error_text = None

        def submit_report(e2):
            category = category_dropdown.value or "other"
            label = dict(_REPORT_CATEGORIES).get(category, "Other")
            reason = (reason_field.value or "").strip() or label
            success, err = state.report_meal_post(post_id, reason, category)
            if success:
                page.close(report_dialog)
            else:
                reason_field.error_text = err
                page.update()

        def cancel(e2):
            page.close(report_dialog)

        def get_support(e2):
            page.close(report_dialog)
            _open_support_dialog(page)

        report_dialog.title = ft.Text("Report this post?")
        report_dialog.content = ft.Column(
            [category_dropdown, reason_field], spacing=10, tight=True,
        )
        report_dialog.actions = [
            ft.TextButton("Get support", style=ft.ButtonStyle(color=theme.ACCENT), on_click=get_support),
            ft.TextButton("Cancel", style=ft.ButtonStyle(color=theme.TEXT_MUTED), on_click=cancel),
            ft.TextButton("Report", style=ft.ButtonStyle(color=theme.ERROR), on_click=submit_report),
        ]
        page.open(report_dialog)

    block_dialog = ft.AlertDialog(modal=True)

    def open_block_dialog(e):
        def confirm_block(e2):
            state.block_user(author_id)
            page.close(block_dialog)
            rerender()

        def cancel(e2):
            page.close(block_dialog)

        block_dialog.title = ft.Text(f"Block {name}?")
        block_dialog.content = ft.Text(f"You won't see {name}'s posts in your feed anymore.")
        block_dialog.actions = [
            ft.TextButton("Cancel", style=ft.ButtonStyle(color=theme.TEXT_MUTED), on_click=cancel),
            ft.TextButton("Block", style=ft.ButtonStyle(color=theme.ERROR), on_click=confirm_block),
        ]
        page.open(block_dialog)

    trailing_action = ft.IconButton(
        icon=ft.Icons.DELETE_OUTLINE, icon_color=theme.ERROR, icon_size=18,
        tooltip="Delete post", on_click=on_delete,
    ) if is_own else ft.PopupMenuButton(
        icon=ft.Icons.MORE_VERT_ROUNDED, icon_color=theme.TEXT_MUTED, icon_size=18,
        items=[
            ft.PopupMenuItem(text="Report", icon=ft.Icons.FLAG_OUTLINED, on_click=open_report_dialog),
            ft.PopupMenuItem(text="Block user", icon=ft.Icons.BLOCK_ROUNDED, on_click=open_block_dialog),
        ],
    )

    header = ft.Container(
        content=ft.Row(
            [
                ft.CircleAvatar(
                    content=ft.Text((name[:1] or "B").upper(), size=13, weight="bold", color=theme.ACCENT_ON),
                    radius=17, bgcolor=theme.ACCENT,
                ),
                ft.Column(
                    [
                        ft.Text(name, size=13, weight="w600", color=theme.TEXT_PRIMARY),
                        ft.Text(time_str, size=11, color=theme.TEXT_MUTED),
                    ],
                    spacing=0, expand=True,
                ),
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(tag_icon, size=12, color=theme.TEXT_MUTED),
                            ft.Text(tag_text, size=11, weight="w600", color=theme.TEXT_MUTED),
                        ],
                        spacing=4, tight=True,
                    ),
                    bgcolor=theme.BG_SURFACE_ALT, border_radius=100,
                    padding=ft.padding.symmetric(horizontal=10, vertical=5),
                ),
                theme.sponsored_badge() if post.get("is_sponsored") else ft.Container(width=0),
                trailing_action,
            ],
            spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.padding.only(left=14, right=4, top=12, bottom=10),
    )

    photo = ft.Image(
        src=photo_url, fit=ft.ImageFit.COVER, height=280,
    ) if photo_url else ft.Container()

    like_row = ft.Row(
        [
            ft.IconButton(
                icon=ft.Icons.FAVORITE_ROUNDED if liked else ft.Icons.FAVORITE_BORDER_ROUNDED,
                icon_color=theme.PROTEIN if liked else theme.TEXT_MUTED,
                icon_size=20, tooltip="Unlike" if liked else "Like",
                on_click=on_toggle_like,
            ),
            ft.Text(
                f"{like_count:,} like{'s' if like_count != 1 else ''}" if like_count else "Be the first to like this",
                size=12, color=theme.TEXT_MUTED,
            ),
        ],
        spacing=2, vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    meal_name = post.get("meal_name") or ""
    ingredients_text = post.get("ingredients") or ""
    ingredient_lines = [line.strip() for line in ingredients_text.splitlines() if line.strip()]

    footer_items = []
    if meal_name:
        footer_items.append(ft.Text(meal_name, size=15, weight="bold", color=theme.TEXT_PRIMARY))

    # Calorie/macro numbers only ever render on the author's own card, never
    # on anyone else's -- see the module docstring. They're never a visible
    # or competitive metric between users in this feed.
    if is_own:
        macro_specs = [
            (post.get("calories"), "", "kcal", theme.ACCENT),
            (post.get("protein"), "g", "protein", theme.PROTEIN),
            (post.get("carbs"), "g", "carbs", theme.CARBS),
            (post.get("fat"), "g", "fat", theme.FAT),
        ]
        macro_tiles = [
            theme.macro_tile(f"{value:,}{unit}", label, color)
            for value, unit, label, color in macro_specs if value is not None
        ]
        if macro_tiles:
            footer_items.append(ft.Row(macro_tiles, spacing=8))

    if ingredient_lines:
        footer_items.append(
            ft.Column(
                [ft.Text(f"• {line}", size=12, color=theme.TEXT_MUTED) for line in ingredient_lines],
                spacing=2,
            )
        )

    if caption:
        footer_items.append(ft.Text(caption, size=13, color=theme.TEXT_PRIMARY))

    footer_items.append(like_row)

    footer = ft.Container(
        content=ft.Column(footer_items, spacing=6),
        padding=ft.padding.only(left=14, right=14, top=8, bottom=14),
    )

    return ft.Container(
        content=ft.Column(
            [header, photo, footer],
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
        border_radius=theme.RADIUS_LG, bgcolor=theme.BG_SURFACE,
        border=ft.border.all(1, theme.BORDER), shadow=theme.CARD_SHADOW,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
    )


def build_meal_feed_view(page: ft.Page, state) -> ft.View:
    if hasattr(state, "refresh_meal_feed"):
        state.refresh_meal_feed()
    if hasattr(state, "refresh_circles"):
        state.refresh_circles()

    posts = state.get_meal_feed() if hasattr(state, "get_meal_feed") else []
    circles = state.get_circles() if hasattr(state, "get_circles") else []
    circle_names = {c.id: c.name for c in circles}
    my_uid = state.db.get_current_user_id() if hasattr(state, "db") else None

    def rerender() -> None:
        page.views[-1] = build_meal_feed_view(page, state)
        page.update()

    feed_list = ft.Column(spacing=18, scroll=ft.ScrollMode.HIDDEN, expand=True)

    if not posts:
        feed_list.controls.append(
            ft.Container(
                content=ft.Column(
                    [
                        ft.Icon(ft.Icons.RESTAURANT_MENU_ROUNDED, color=theme.TEXT_FAINT, size=28),
                        ft.Text(
                            "No meals posted yet -- be the first to share one.",
                            color=theme.TEXT_FAINT, size=13, italic=True,
                        ),
                    ],
                    spacing=10, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=28, alignment=ft.alignment.center,
            )
        )
    else:
        for post in posts:
            feed_list.controls.append(_post_card(post, circle_names, my_uid, state, page, rerender))

    return ft.View(
        route="/meal_feed",
        bgcolor=theme.BG_CANVAS,
        controls=[
            theme.app_bar(
                "Meal Feed", on_back=lambda e: page.go("/"),
                actions=[
                    ft.IconButton(
                        icon=ft.Icons.ADD_A_PHOTO_OUTLINED, icon_color=theme.TEXT_MUTED,
                        tooltip="Post a Meal", on_click=lambda e: page.go("/post_meal"),
                    ),
                ],
            ),
            ft.Container(content=feed_list, padding=20, expand=True),
        ],
    )
