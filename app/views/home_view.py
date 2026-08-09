"""
Main Home Dashboard View - Modern Minimalist Edition.
"""
import flet as ft
from app import promotions
from app import qr_engine
from app import theme
from app.config import SUPABASE_URL
from app.health_engine import get_health_control, get_today_summary, get_today_workouts
from app.state import AppState

METERS_PER_MILE = 1609.344

# Sort weight for the sponsor grid -- higher tiers sort first (top-left,
# most visible position) since Gold/Category Exclusive sponsors are paying
# for prominence, not just an equal spot in the grid. Category Exclusive
# sits above Gold since it's the only voice in its whole category.
_SPONSOR_LEVEL_WEIGHTS = {"bronze": 1, "silver": 2, "gold": 4, "category_exclusive": 5}

def build_home_view(page: ft.Page, state: AppState) -> ft.View:
    if hasattr(state, "refresh_logs"):
        state.refresh_logs()
    if hasattr(state, "refresh_log_streak"):
        state.refresh_log_streak()
    if hasattr(state, "refresh_circles"):
        state.refresh_circles()
    if hasattr(state, "refresh_workouts"):
        state.refresh_workouts()
    if hasattr(state, "refresh_sponsors"):
        state.refresh_sponsors()

    def rerender() -> None:
        # See the matching comment in circles_view.py -- rebuilds this view
        # fresh and swaps it into the stack, rather than relying on
        # page.go("/") to redraw a route we're already on.
        page.views[-1] = build_home_view(page, state)
        page.update()

    # Populated (if Health access was already granted on a previous visit)
    # by _sync_health_data below, once its background fetch resolves --
    # empty/invisible until then, never a static section like the ones
    # built synchronously further down, since Health data is only
    # available via an async call.
    health_section = ft.Column(
        [
            ft.Text("TODAY'S ACTIVITY", size=11, color=theme.TEXT_FAINT, weight="w700"),
            ft.Row(spacing=8),
        ],
        spacing=10, visible=False,
    )

    async def _sync_health_data() -> None:
        # Silent, best-effort: pulls today's Apple Health / Health Connect
        # summary (steps/distance/etc, for health_section above) and any
        # workouts (e.g. an Apple Watch workout) into the same table a
        # manually-logged workout lands in -- both without the user needing
        # to visit Connect Health App at all. Never prompts for permission
        # (that only happens from the Connect Health App screen) and never
        # surfaces an error -- if the user hasn't connected yet, or the
        # read fails, this is a no-op, not a broken home screen.
        if page.platform not in (ft.PagePlatform.IOS, ft.PagePlatform.ANDROID):
            return
        try:
            health = get_health_control(page, state)
            is_ios = page.platform == ft.PagePlatform.IOS

            summary = await get_today_summary(health, is_ios)
            tiles = []
            if summary["steps"] is not None:
                tiles.append(theme.macro_tile(f"{summary['steps']:,}", "steps", theme.ACCENT))
            if summary["distance_m"] is not None:
                dist = (
                    f"{summary['distance_m'] / METERS_PER_MILE:,.1f}mi" if is_ios
                    else f"{summary['distance_m'] / 1000:,.1f}km"
                )
                tiles.append(theme.macro_tile(dist, "distance", theme.SUCCESS))
            if summary["flights_climbed"] is not None:
                tiles.append(theme.macro_tile(f"{summary['flights_climbed']:,.0f}", "floors", theme.FAT))
            if summary["active_calories"] is not None:
                tiles.append(theme.macro_tile(f"{summary['active_calories']:,.0f}", "active kcal", theme.PROTEIN))
            if tiles:
                # Direct mutation + page.update() rather than rerender() --
                # this section doesn't feed into any of the calorie/macro
                # math computed below, so a full rebuild isn't needed just
                # to reveal it.
                health_section.controls[1] = ft.Row(tiles, spacing=8)
                health_section.visible = True
                page.update()

            # rerender() re-runs this same sync on its way back in, but
            # only calls it again when new rows were actually added, so it
            # settles after at most one extra pass.
            workouts = await get_today_workouts(health, is_ios)
            added = state.sync_health_workouts(workouts)
            if added:
                rerender()
        except Exception:
            pass

    page.run_task(_sync_health_data)

    daily_logs = state.get_daily_logs() if hasattr(state, "get_daily_logs") else getattr(state, "logs", [])
    log_streak = state.get_log_streak() if hasattr(state, "get_log_streak") else None
    streak_days = getattr(log_streak, "current_streak", 0)
    streak_logged_today = getattr(log_streak, "logged_today", False)
    goals = state.get_goals() if hasattr(state, "get_goals") else getattr(state, "goals", None)
    circles = state.get_circles() if hasattr(state, "get_circles") else []
    daily_workouts = state.get_daily_workouts() if hasattr(state, "get_daily_workouts") else []
    my_uid = state.db.get_current_user_id() if hasattr(state, "db") else None

    # Defensively compute macros
    consumed_cal, consumed_pro, consumed_carb, consumed_fat = 0, 0, 0, 0
    for log in (daily_logs or []):
        try:
            consumed_cal += int(log.get("calories", 0) if isinstance(log, dict) else getattr(log, "calories", 0))
            consumed_pro += int(log.get("protein", 0) if isinstance(log, dict) else getattr(log, "protein", 0))
            consumed_carb += int(log.get("carbs", 0) if isinstance(log, dict) else getattr(log, "carbs", 0))
            consumed_fat += int(log.get("fat", 0) if isinstance(log, dict) else getattr(log, "fat", 0))
        except (TypeError, ValueError):
            pass

    target_cal = int(getattr(goals, "daily_calories", 2000) if not isinstance(goals, dict) else goals.get("daily_calories", 2000))
    target_pro = int(getattr(goals, "daily_protein", 150) if not isinstance(goals, dict) else goals.get("daily_protein", 150))
    target_carb = int(getattr(goals, "daily_carbs", 200) if not isinstance(goals, dict) else goals.get("daily_carbs", 200))
    target_fat = int(getattr(goals, "daily_fat", 65) if not isinstance(goals, dict) else goals.get("daily_fat", 65))

    # Logged exercise adds back to today's calorie budget (Goal + Exercise -
    # Food = Remaining), same convention as MyFitnessPal/most calorie trackers.
    burned_today = 0
    for w in (daily_workouts or []):
        try:
            burned_today += int(w.get("calories_burned", 0) if isinstance(w, dict) else getattr(w, "calories_burned", 0))
        except (TypeError, ValueError):
            pass

    adjusted_target_cal = target_cal + burned_today
    cal_progress = min(1.0, consumed_cal / max(1, adjusted_target_cal))

    # --- NEW MODERN UI ELEMENTS ---
    
    # Sleek Pill-Shaped Action Controls -- top row is the three core food-log
    # actions, second row is the lower-frequency workout/weight logging.
    logging_shortcuts = ft.Column([
        ft.Row([
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.SUBTITLES_OUTLINED, size=15, color=theme.TEXT_PRIMARY),
                    ft.Text("Text Log", size=12, weight="w600")
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=6),
                bgcolor=theme.BG_SURFACE_ALT,
                border=ft.border.all(1, theme.BORDER),
                border_radius=theme.RADIUS_LG,
                padding=ft.padding.symmetric(12, 10),
                on_click=lambda _: page.go("/text_log"),
                expand=True
            ),
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.SEARCH_ROUNDED, size=15, color=theme.TEXT_PRIMARY),
                    ft.Text("Lookup", size=12, weight="w600")
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=6),
                bgcolor=theme.BG_SURFACE_ALT,
                border=ft.border.all(1, theme.BORDER),
                border_radius=theme.RADIUS_LG,
                padding=ft.padding.symmetric(12, 10),
                on_click=lambda _: page.go("/lookup"),
                expand=True
            ),
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.CAMERA_ALT_OUTLINED, size=15, color=theme.ACCENT_ON),
                    ft.Text("Snap", size=12, weight="bold", color=theme.ACCENT_ON)
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=6),
                bgcolor=theme.ACCENT,
                border_radius=theme.RADIUS_LG,
                padding=ft.padding.symmetric(12, 10),
                on_click=lambda _: page.go("/snap"),
                expand=True
            ),
        ], spacing=10),
        ft.Row([
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.FITNESS_CENTER_ROUNDED, size=15, color=theme.TEXT_PRIMARY),
                    ft.Text("Workout", size=12, weight="w600")
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=6),
                bgcolor=theme.BG_SURFACE_ALT,
                border=ft.border.all(1, theme.BORDER),
                border_radius=theme.RADIUS_LG,
                padding=ft.padding.symmetric(12, 10),
                on_click=lambda _: page.go("/log_workout"),
                expand=True
            ),
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.MONITOR_WEIGHT_OUTLINED, size=15, color=theme.TEXT_PRIMARY),
                    ft.Text("Weight", size=12, weight="w600")
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=6),
                bgcolor=theme.BG_SURFACE_ALT,
                border=ft.border.all(1, theme.BORDER),
                border_radius=theme.RADIUS_LG,
                padding=ft.padding.symmetric(12, 10),
                on_click=lambda _: page.go("/weight"),
                expand=True
            ),
        ], spacing=10),
    ], spacing=10)

    # Progress Overview Box: calorie ring gauge + macro meters
    remaining_cal = max(0, adjusted_target_cal - consumed_cal)
    calorie_ring = ft.Stack(
        [
            ft.ProgressRing(
                value=cal_progress, width=132, height=132, stroke_width=12,
                color=theme.ACCENT, bgcolor=theme.BG_SURFACE_ALT, stroke_cap=ft.StrokeCap.ROUND,
            ),
            ft.Container(
                content=ft.Column(
                    [
                        ft.Text(f"{remaining_cal:,}", size=26, weight="bold", color=theme.TEXT_PRIMARY),
                        ft.Text("Remaining", size=11, color=theme.TEXT_MUTED),
                    ],
                    spacing=0,
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    tight=True,
                ),
                width=132, height=132, alignment=ft.alignment.center,
            ),
        ],
        width=132, height=132,
    )

    calorie_breakdown = ft.Column(
        [
            ft.Row(
                [ft.Icon(ft.Icons.FLAG_OUTLINED, size=16, color=theme.TEXT_MUTED),
                 ft.Text("Goal", size=13, color=theme.TEXT_MUTED, expand=True),
                 ft.Text(f"{target_cal:,}", size=13, weight="w600", color=theme.TEXT_PRIMARY)],
                spacing=8,
            ),
            ft.Row(
                [ft.Icon(ft.Icons.FITNESS_CENTER_ROUNDED, size=16, color=theme.TEXT_MUTED),
                 ft.Text("Exercise", size=13, color=theme.TEXT_MUTED, expand=True),
                 ft.Text(f"+{burned_today:,}", size=13, weight="w600", color=theme.TEXT_PRIMARY)],
                spacing=8,
            ) if burned_today else ft.Container(),
            ft.Row(
                [ft.Icon(ft.Icons.RESTAURANT_OUTLINED, size=16, color=theme.TEXT_MUTED),
                 ft.Text("Food", size=13, color=theme.TEXT_MUTED, expand=True),
                 ft.Text(f"{consumed_cal:,}", size=13, weight="w600", color=theme.TEXT_PRIMARY)],
                spacing=8,
            ),
        ],
        spacing=12,
        expand=True,
    )

    progress_card = ft.Container(
        content=ft.Column([
            ft.Text("Calories", size=17, weight="bold", color=theme.TEXT_PRIMARY, font_family=theme.DISPLAY_FONT),
            ft.Text(
                "Remaining = Goal + Exercise − Food" if burned_today else "Remaining = Goal − Food",
                size=12, color=theme.TEXT_FAINT,
            ),
            ft.Row(
                [calorie_ring, calorie_breakdown],
                alignment=ft.MainAxisAlignment.SPACE_AROUND,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Divider(color=theme.BORDER, height=1),
            ft.Row([
                _modern_macro("PROTEIN", consumed_pro, target_pro, theme.PROTEIN),
                _modern_macro("CARBS", consumed_carb, target_carb, theme.CARBS),
                _modern_macro("FAT", consumed_fat, target_fat, theme.FAT),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        ], spacing=18),
        padding=26, border_radius=theme.RADIUS_LG, bgcolor=theme.BG_SURFACE,
        border=ft.border.all(1, theme.BORDER), shadow=theme.CARD_SHADOW,
    )

    # Streak Badge -- consecutive days with at least one food log. Counts
    # through yesterday (not reset to zero) until today actually ends, so
    # the "keep it alive" nudge only shows once there's something to lose.
    if streak_days > 0:
        streak_text = f"{streak_days} day{'s' if streak_days != 1 else ''} streak"
        streak_hint = "" if streak_logged_today else " · log today to keep it"
    else:
        streak_text = "Log today to start a streak"
        streak_hint = ""

    streak_badge = ft.Container(
        content=ft.Row(
            [
                ft.Icon(
                    ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED,
                    size=16,
                    color=theme.ACCENT if streak_days > 0 else theme.TEXT_FAINT,
                ),
                ft.Text(streak_text, size=12, weight="w600", color=theme.TEXT_PRIMARY),
                ft.Text(streak_hint, size=12, color=theme.TEXT_FAINT),
            ],
            spacing=6, tight=True,
        ),
        padding=ft.padding.symmetric(6, 12),
        bgcolor=theme.BG_SURFACE_ALT,
        border_radius=theme.RADIUS_LG,
    )

    # TODAY'S LINEUP fold/unfold -- purely a display toggle (no data changes,
    # no rerender()), so it stays snappy and doesn't refetch anything.
    meals_expanded = [True]
    fold_icon_btn = ft.IconButton(
        icon=ft.Icons.KEYBOARD_ARROW_UP_ROUNDED,
        icon_color=theme.TEXT_FAINT,
        icon_size=20,
        tooltip="Collapse",
    )

    def toggle_meals_section(e):
        meals_expanded[0] = not meals_expanded[0]
        timeline_items.visible = meals_expanded[0]
        fold_icon_btn.icon = ft.Icons.KEYBOARD_ARROW_UP_ROUNDED if meals_expanded[0] else ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED
        fold_icon_btn.tooltip = "Collapse" if meals_expanded[0] else "Expand"
        page.update()
    fold_icon_btn.on_click = toggle_meals_section

    # Timeline Build List
    timeline_items = ft.Column(spacing=12)
    if not daily_logs:
        timeline_items.controls.append(
            ft.Container(
                content=ft.Column(
                    [
                        ft.Icon(ft.Icons.RESTAURANT_ROUNDED, color=theme.TEXT_FAINT, size=28),
                        ft.Text("No entries recorded for today.", color=theme.TEXT_FAINT, size=13, italic=True),
                    ],
                    spacing=10,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=28,
                alignment=ft.alignment.center,
            )
        )
    else:
        for log in daily_logs:
            name = log.get("meal_name", "Logged Food") if isinstance(log, dict) else getattr(log, "meal_name", "Logged Food")
            c = log.get("calories", 0) if isinstance(log, dict) else getattr(log, "calories", 0)
            p = log.get("protein", 0) if isinstance(log, dict) else getattr(log, "protein", 0)
            ch = log.get("carbs", 0) if isinstance(log, dict) else getattr(log, "carbs", 0)
            f = log.get("fat", 0) if isinstance(log, dict) else getattr(log, "fat", 0)

            timeline_items.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Column([
                            ft.Text(name, size=15, weight="w600"),
                            ft.Row(
                                [
                                    _macro_chip("P", p, theme.PROTEIN),
                                    _macro_chip("C", ch, theme.CARBS),
                                    _macro_chip("F", f, theme.FAT),
                                ],
                                spacing=10,
                            ),
                        ], expand=True, spacing=6),
                        ft.Text(f"+{c:,}", size=16, weight="bold", color=theme.ACCENT)
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=18, border_radius=theme.RADIUS_MD, bgcolor=theme.BG_SURFACE,
                    border=ft.border.all(1, theme.BORDER), shadow=theme.CARD_SHADOW,
                )
            )

    # Circle Goal Cards -- only shown once the user has joined/created one
    circle_cards = ft.Column(spacing=10)
    for circle in circles:
        members = state.get_circle_status(circle.id) if hasattr(state, "get_circle_status") else []
        my_status = next((m for m in members if m.user_id == my_uid), None)
        checked_in_today = bool(my_status and my_status.checked_in_today)
        streak_days = my_status.streak_days if my_status else 0

        is_auto = circle.goal_type != "custom"

        def make_checkin_handler(circle_id, was_checked_in):
            # Toggles rather than only ever checking in -- an accidental
            # tap used to be permanent (disabled=checked_in_today, no way
            # back) until undo_checkin_circle existed.
            def handler(e):
                if was_checked_in:
                    success, err = state.undo_checkin_circle(circle_id)
                    failure_msg = "Couldn't undo check-in."
                else:
                    success, err = state.check_in_circle(circle_id)
                    failure_msg = "Couldn't check in."
                if success:
                    rerender()
                else:
                    page.open(ft.SnackBar(ft.Text(err or failure_msg), bgcolor=theme.ERROR))
            return handler

        status_icon = ft.Icon(
            ft.Icons.CHECK_CIRCLE if checked_in_today else ft.Icons.RADIO_BUTTON_UNCHECKED,
            color=theme.SUCCESS if checked_in_today else theme.TEXT_FAINT,
            size=22,
        ) if is_auto else ft.IconButton(
            icon=ft.Icons.CHECK_CIRCLE if checked_in_today else ft.Icons.RADIO_BUTTON_UNCHECKED,
            icon_color=theme.SUCCESS if checked_in_today else theme.TEXT_FAINT,
            tooltip="Tap to undo" if checked_in_today else "Mark today's goal done",
            on_click=make_checkin_handler(circle.id, checked_in_today),
        )

        circle_cards.controls.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Text(circle.name, size=14, weight="w600", color=theme.TEXT_PRIMARY),
                                ft.Text(circle.goal_description, size=12, color=theme.TEXT_MUTED),
                                ft.Text(f"{streak_days}d streak", size=11, color=theme.TEXT_FAINT),
                            ],
                            expand=True,
                            spacing=2,
                        ),
                        status_icon,
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=14, border_radius=theme.RADIUS_MD, bgcolor=theme.BG_SURFACE,
                border=ft.border.all(1, theme.BORDER), shadow=theme.CARD_SHADOW,
            )
        )

    # Today's Workouts -- only shown once at least one is logged today
    workout_items = ft.Column(spacing=10)
    for w in daily_workouts:
        w_name = w.get("workout_name", "Workout") if isinstance(w, dict) else getattr(w, "workout_name", "Workout")
        w_dur = w.get("duration_minutes", 0) if isinstance(w, dict) else getattr(w, "duration_minutes", 0)
        w_cal = w.get("calories_burned", 0) if isinstance(w, dict) else getattr(w, "calories_burned", 0)
        workout_items.controls.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.FITNESS_CENTER_ROUNDED, size=18, color=theme.ACCENT),
                        ft.Text(w_name, size=14, weight="w600", color=theme.TEXT_PRIMARY, expand=True),
                        ft.Text(
                            f"{w_dur or 0} min" + (f" • {w_cal} kcal" if w_cal else ""),
                            size=12, color=theme.TEXT_MUTED,
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=14, border_radius=theme.RADIUS_MD, bgcolor=theme.BG_SURFACE,
                border=ft.border.all(1, theme.BORDER), shadow=theme.CARD_SHADOW,
            )
        )

    # Promotions -- active sponsor rows come from Supabase's `sponsors`
    # table (submitted via sponsor_signup.html, reviewed from Profile ->
    # Sponsor Requests). Every active sponsor gets a tile in a grid (not
    # just one random pick per home load) so the section reads the same
    # regardless of how many sponsors sign up -- see the detail dialog
    # below for the Learn More / Redeem actions each tile used to show
    # inline, which don't fit a square tile.
    sponsors = state.get_sponsors() if hasattr(state, "get_sponsors") else []
    sponsors = sorted(sponsors, key=lambda s: -_SPONSOR_LEVEL_WEIGHTS.get(s.get("level"), 1))
    sponsor_dialog = ft.AlertDialog(modal=True)

    def open_sponsor_dialog(e, sponsor: dict) -> None:
        raw_url = (sponsor.get("website_url") or "").strip()
        # Only ever open http(s) links -- defense-in-depth against a
        # malicious/mistaken javascript:, file:, or other unexpected scheme
        # ending up in an approved sponsor row.
        website_url = raw_url if raw_url.lower().startswith(("http://", "https://")) else None

        def do_redeem(e2):
            redemption, err = state.get_or_create_sponsor_redemption(sponsor.get("id"))
            if not redemption:
                page.close(sponsor_dialog)
                page.open(ft.SnackBar(ft.Text(err or "Couldn't generate a redeem code -- try again.")))
                return
            redeem_url = f"{SUPABASE_URL}/functions/v1/redeem-sponsor?code={redemption['code']}"
            qr_b64 = qr_engine.qr_base64(redeem_url)
            # redemption_count only ever moves when staff actually scan the
            # QR (redeem_sponsor_code() in supabase_circles_schema.sql) --
            # opening this dialog never bumps it, so this reflects real
            # usage, not just how many times the user has looked at it.
            used = redemption.get("redemption_count") or 0
            max_uses = sponsor.get("max_redemptions_per_user")
            if used == 0:
                status_line = "Show this to staff to redeem:"
            elif max_uses is not None:
                status_line = f"Used {used} of {max_uses} -- show staff the code below."
            else:
                status_line = f"Used {used} time{'s' if used != 1 else ''} -- show staff the code below."
            sponsor_dialog.content = ft.Column(
                [
                    ft.Text(status_line, size=12, color=theme.TEXT_MUTED, text_align=ft.TextAlign.CENTER),
                    ft.Container(
                        content=ft.Image(src_base64=qr_b64, width=200, height=200),
                        alignment=ft.alignment.center,
                        padding=12, bgcolor="#FFFFFF", border_radius=theme.RADIUS_MD,
                    ),
                    ft.Text(redemption["code"], size=18, weight="bold", color=theme.TEXT_PRIMARY, text_align=ft.TextAlign.CENTER),
                ],
                tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12,
            )
            sponsor_dialog.actions = [ft.TextButton("Close", on_click=lambda e3: page.close(sponsor_dialog))]
            page.update()

        sponsor_dialog.title = ft.Row(
            [
                ft.Text(sponsor.get("title", ""), size=16, weight="bold", color=theme.TEXT_PRIMARY, expand=True),
                theme.sponsor_level_badge(sponsor.get("level")),
            ],
        )
        sponsor_dialog.content = ft.Text(sponsor.get("subtitle", ""), size=13, color=theme.TEXT_MUTED)
        sponsor_dialog.actions = [
            ft.TextButton(
                content=ft.Row(
                    [ft.Icon(ft.Icons.QR_CODE_ROUNDED, size=14, color=theme.TEXT_MUTED),
                     ft.Text("Redeem", size=12, weight="bold", color=theme.TEXT_MUTED)],
                    spacing=4, tight=True,
                ),
                on_click=do_redeem,
            ),
            ft.TextButton(
                content=ft.Text(sponsor.get("cta_text", "Learn More"), size=12, weight="bold", color=theme.ACCENT),
                on_click=(lambda e2, url=website_url: page.launch_url(url)) if website_url else None,
                disabled=website_url is None,
            ),
            ft.TextButton("Close", style=ft.ButtonStyle(color=theme.TEXT_MUTED), on_click=lambda e2: page.close(sponsor_dialog)),
        ]
        page.open(sponsor_dialog)

    def sponsor_tile(sponsor: dict) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                [
                    ft.Icon(promotions.icon_for(sponsor.get("icon_name")), size=22, color=theme.ACCENT),
                    ft.Text(
                        sponsor.get("title", ""), size=12, weight="w600", color=theme.TEXT_PRIMARY,
                        text_align=ft.TextAlign.CENTER, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    theme.sponsor_level_badge(sponsor.get("level")),
                ],
                spacing=6, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            bgcolor=theme.BG_SURFACE_ALT, border_radius=theme.RADIUS_MD,
            border=ft.border.all(1, theme.BORDER),
            padding=10, height=110, expand=True, alignment=ft.alignment.center,
            on_click=lambda e, s=sponsor: open_sponsor_dialog(e, s),
        )

    # Chunked into rows of 3 rather than ft.Row(wrap=True) -- each tile
    # uses expand=True to split the row evenly, and Expanded (what
    # expand=True compiles to) is only legal as a direct child of a Flex
    # (Row/Column), not a Wrap (what wrap=True compiles to). See the
    # matching fix in health_view.py for what that mismatch actually does
    # (renders as a blank error box) when it goes wrong.
    _SPONSOR_COLS = 3
    sponsor_rows = [
        ft.Row(
            [sponsor_tile(s) for s in sponsors[i:i + _SPONSOR_COLS]],
            spacing=10,
        )
        for i in range(0, len(sponsors), _SPONSOR_COLS)
    ]
    promo_card = ft.Column(
        [
            ft.Text("OUR SPONSORS", size=11, color=theme.TEXT_FAINT, weight="w700"),
            ft.Column(sponsor_rows, spacing=10),
        ],
        spacing=10,
    ) if sponsors else ft.Container()

    return ft.View(
        route="/",
        bgcolor=theme.BG_CANVAS,
        controls=[
            ft.AppBar(
                title=ft.Text("Bite! Profile", size=18, weight="bold", font_family=theme.DISPLAY_FONT),
                leading=ft.IconButton(icon=ft.Icons.ACCOUNT_CIRCLE_OUTLINED, icon_color=theme.TEXT_MUTED, on_click=lambda _: page.go("/profile")),
                actions=[
                    ft.IconButton(icon=ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED, icon_color=theme.TEXT_MUTED, tooltip="AI Coach", on_click=lambda _: page.go("/coach")),
                    # Hidden (not just gated at the route) for known-minor
                    # accounts -- see app/age_gate.py.
                    ft.IconButton(icon=ft.Icons.RESTAURANT_MENU_ROUNDED, icon_color=theme.TEXT_MUTED, tooltip="Meal Feed", on_click=lambda _: page.go("/meal_feed"))
                    if (not hasattr(state, "can_access_meal_feed") or state.can_access_meal_feed())
                    else ft.Container(width=0),
                    ft.IconButton(icon=ft.Icons.GROUPS_OUTLINED, icon_color=theme.TEXT_MUTED, tooltip="Friend Circles", on_click=lambda _: page.go("/circles")),
                    ft.IconButton(icon=ft.Icons.TUNE_ROUNDED, icon_color=theme.TEXT_MUTED, tooltip="History", on_click=lambda _: page.go("/history")),
                ],
                bgcolor=theme.BG_CANVAS, elevation=0
            ),
            ft.Container(
                content=ft.Column([
                    ft.Row([streak_badge], alignment=ft.MainAxisAlignment.START),
                    progress_card,
                    ft.Divider(color="transparent", height=4),
                    logging_shortcuts,
                    ft.Divider(color="transparent", height=4),
                    # Circles, today's activity (steps/etc), and today's
                    # workouts are all the same kind of glance-able "how am
                    # I doing" info -- grouped into one tighter-spaced
                    # cluster (spacing=20 vs the outer Column's 18, but
                    # between *these* sections specifically, so they read as
                    # one block) instead of being spread out at the outer
                    # Column's full spacing like unrelated sections.
                    ft.Column(
                        [
                            ft.Column(
                                [
                                    ft.Text("YOUR CIRCLES", size=11, color=theme.TEXT_FAINT, weight="w700"),
                                    circle_cards,
                                ],
                                spacing=10,
                            ) if circles else ft.Container(),
                            health_section,
                            ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Text("TODAY'S WORKOUTS", size=11, color=theme.TEXT_FAINT, weight="w700", expand=True),
                                            ft.TextButton(
                                                "View All",
                                                style=ft.ButtonStyle(color=theme.TEXT_MUTED),
                                                on_click=lambda e: page.go("/workout_history"),
                                            ),
                                        ],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    ),
                                    workout_items,
                                ],
                                spacing=0,
                            ) if daily_workouts else ft.Container(),
                        ],
                        spacing=20,
                    ) if (circles or daily_workouts) else health_section,
                    # Sponsor promo moved up here (was after the food log
                    # timeline below) -- that list has no length cap and
                    # keeps growing across the day, so a sponsor slot placed
                    # after it was getting pushed further down with every
                    # meal logged instead of sitting somewhere reliably seen.
                    promo_card,
                    ft.Row(
                        [
                            ft.Text("TODAY'S LINEUP", size=11, color=theme.TEXT_FAINT, weight="w700", expand=True),
                            fold_icon_btn,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    timeline_items,
                ], spacing=18, scroll=ft.ScrollMode.HIDDEN),
                padding=ft.padding.symmetric(20, 24), expand=True
            )
        ]
    )

def _modern_macro(label: str, cur: int, tgt: int, accent_color: str) -> ft.Control:
    return ft.Column([
        ft.Text(label, size=10, color=theme.TEXT_FAINT, weight="bold"),
        ft.Text(f"{cur}g", size=15, weight="bold"),
        ft.Text(f"of {tgt}g", size=10, color=theme.TEXT_MUTED),
        ft.ProgressBar(
            value=min(1.0, cur / max(1, tgt)), width=76, height=6,
            color=accent_color, bgcolor=ft.Colors.with_opacity(0.15, accent_color),
            border_radius=3,
        ),
    ], spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER)


def _macro_chip(letter: str, grams: int, color: str) -> ft.Control:
    return ft.Row(
        [
            ft.Container(width=8, height=8, border_radius=4, bgcolor=color),
            ft.Text(f"{letter} {grams}g", size=11, color=theme.TEXT_MUTED),
        ],
        spacing=5,
    )