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
    "cunt", "whore", "porn", "nude", "nudes", "bitch", "shit", "asshole", "ass", 
    "coon", "wetback", "pussy", "vagina", "pennis", "dick"
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


# --- PRO-EATING-DISORDER CONTENT SCREENING ---
# Separate from the blocklist above on purpose: _BLOCKED_TERMS is a hard
# pre-post gate (the post is refused outright), but ED-adjacent language
# should never be auto-deleted or auto-blocked -- a caption mentioning
# restriction or purging might be someone in recovery talking about their
# own struggle, not content promoting it, and getting that wrong by
# silently blocking is its own harm. So this only *flags for human review*
# (see database.py's auto_flag_post / meal_post_reports.is_automated) --
# the post still goes live, a report row is filed automatically, and the
# admin queue (reported_posts_view.py) decides from there. This is a small,
# maintainable keyword list, not a classifier -- it will miss things and
# will also false-positive on innocuous text (e.g. a dietitian discussing
# recovery); it's a triage signal for a human, not a verdict.
_ED_PHRASE_CATEGORIES: dict[str, list[str]] = {
    "extreme_restriction": [
        "under 500 calories", "under 300 calories", "less than 500 calories",
        "eating nothing today", "didn't eat today", "haven't eaten today",
        "starve myself", "starving myself", "zero calorie day", "0 calorie day",
        "not eating today", "skip all meals", "water fast for days",
    ],
    "purge_compensatory": [
        "purge", "purging", "throw up after eating", "make myself throw up",
        "make myself sick", "laxatives to lose weight", "laxative abuse",
        "diuretics to lose weight", "compensate for eating",
    ],
    "thinspo_meanspo": [
        "thinspo", "thinspiration", "meanspo", "bonespo", "proana", "pro-ana",
        "promia", "pro-mia", "thigh gap goals", "want to be skinny",
        "want to disappear",
    ],
    "competitive_lowest": [
        "lowest calorie", "least calories", "lowest calories today",
        "who can eat the least",
    ],
}

_ED_PATTERNS: dict[str, "re.Pattern"] = {
    category: re.compile(
        r"(" + "|".join(re.escape(p) for p in phrases) + r")", re.IGNORECASE
    )
    for category, phrases in _ED_PHRASE_CATEGORIES.items()
}


def ed_screening_flags(text: str) -> list[str]:
    """Returns the list of ED-content categories matched in `text` (possibly
    empty). Never used to block a post -- see the module comment above."""
    if not text:
        return []
    return [category for category, pattern in _ED_PATTERNS.items() if pattern.search(text)]
