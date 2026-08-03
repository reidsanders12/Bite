"""
Meal Feed view: browse meal posts visible to you (your own, everyone's
public posts, and circle-only posts from circles you belong to), like a
post anonymously (see database.py's meal_post_likes RLS -- nobody, not even
the app, can see who liked what, only the total), and jump to Post a Meal.
"""
from datetime import datetime, timezone

import flet as ft

from app import theme


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
    reason_field = ft.TextField(
        label="Why are you reporting this? (optional)", multiline=True, min_lines=2, max_lines=4,
        **theme.styled_field(),
    )

    def open_report_dialog(e):
        reason_field.value = ""

        def submit_report(e2):
            state.report_meal_post(post_id, reason_field.value or "")
            page.close(report_dialog)

        def cancel(e2):
            page.close(report_dialog)

        report_dialog.title = ft.Text("Report this post?")
        report_dialog.content = reason_field
        report_dialog.actions = [
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

    footer_items = [like_row]
    if caption:
        footer_items.append(ft.Text(caption, size=13, color=theme.TEXT_PRIMARY))

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
