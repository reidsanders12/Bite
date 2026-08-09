"""
Persists a Supabase session's tokens via Flet's page.client_storage so
"Remember me" at login can survive a full app restart.

By default the Supabase client's session lives in memory only (see
database.py's create_client() call -- no custom auth storage is passed),
so every cold start otherwise forces a fresh login no matter how recently
the user signed in. This intentionally doesn't touch that client
construction -- it's simpler to explicitly save/restore the two tokens
ourselves at the moments that matter (login, sign-out, app start) than to
swap in a custom GoTrue storage backend that persists unconditionally.
"""
import logging

logger = logging.getLogger(__name__)

_ACCESS_TOKEN_KEY = "bite_remember_access_token"
_REFRESH_TOKEN_KEY = "bite_remember_refresh_token"


async def save_remembered_session(page, access_token: str, refresh_token: str) -> None:
    """Called after a successful login/registration when "Remember me" is
    checked. Async (and awaited by every caller) -- ClientStorage.set() is
    a blocking call that waits on a round-trip via threading.Event.wait(),
    same shape as the flet_audio_recorder deadlock this project already
    hit once: called synchronously from inside an async handler on the
    event loop's own thread, it can never get the response it's blocking
    on. set_async() runs the same round-trip without blocking that thread."""
    await page.client_storage.set_async(_ACCESS_TOKEN_KEY, access_token)
    await page.client_storage.set_async(_REFRESH_TOKEN_KEY, refresh_token)


async def clear_remembered_session(page) -> None:
    """Called on sign-out, and after a login/registration where "Remember
    me" was left unchecked -- otherwise a previous session someone *did*
    choose to remember would silently keep restoring even after they
    unchecked the box on a later login. Async for the same reason as
    save_remembered_session above."""
    await page.client_storage.remove_async(_ACCESS_TOKEN_KEY)
    await page.client_storage.remove_async(_REFRESH_TOKEN_KEY)


def try_restore_session(page, db) -> bool:
    """Attempts to restore a previously-remembered session into `db`'s
    Supabase client at app start. Returns True if a live session is now
    active. set_session() itself refreshes an expired access token using
    the stored refresh token, and raises if the refresh token itself is no
    longer valid (revoked, or the user changed their password elsewhere) --
    either way, a failure here means the stored tokens are no longer any
    good, so they're cleared rather than left to fail the same way on
    every future launch."""
    access_token = page.client_storage.get(_ACCESS_TOKEN_KEY)
    refresh_token = page.client_storage.get(_REFRESH_TOKEN_KEY)
    if not access_token or not refresh_token:
        return False
    try:
        db.client.auth.set_session(access_token, refresh_token)
        return db.client.auth.get_session() is not None
    except Exception as err:
        logger.info("Remembered session couldn't be restored: %s", err)
        clear_remembered_session(page)
        return False
