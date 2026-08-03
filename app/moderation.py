"""
Meal Feed content moderation: a lightweight, pre-post caption filter.

Apple App Store Review Guideline 1.2 and Google Play's User Generated
Content policy both require "a method for filtering objectionable material
from being posted" for any app with a UGC feed -- this is that method for
captions. It's a small, maintainable blocklist, not a comprehensive
moderation system; photos themselves aren't scanned (that would need an
image-moderation API/service, out of scope for this project's size). Report
+ block (see database.py's meal_post_reports/blocked_users) are the
backstop for anything this list misses.
"""
import re

# Deliberately short and conservative -- common slurs and explicit sexual
# terms, not ordinary profanity. Word-boundary matched, case-insensitive.
_BLOCKED_TERMS = [
    "nigger", "nigga", "faggot", "retard", "kike", "spic", "chink", "tranny",
    "cunt", "whore", "porn", "nude", "nudes",
]

_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(term) for term in _BLOCKED_TERMS) + r")\b",
    re.IGNORECASE,
)


def is_caption_allowed(caption: str) -> bool:
    """True if the caption doesn't match anything in the blocklist."""
    if not caption:
        return True
    return not _PATTERN.search(caption)
