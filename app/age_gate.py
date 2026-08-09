"""
Age gate: COPPA-driven account-creation floor + Meal Feed minor restriction.

MIN_ACCOUNT_AGE blocks registration outright below the COPPA threshold --
simpler and lower-risk than building a verifiable-parental-consent flow for
under-13 accounts (COPPA's other compliant path), which is out of scope for
this project's size. MIN_FEED_AGE is stricter still: the Meal Feed carries
its own bullying/pro-ED risk (see app/moderation.py), so accounts between
MIN_ACCOUNT_AGE and MIN_FEED_AGE can use Bite!'s core tracking features but
never see or post to the social feed.

Age is self-attested at registration (a plain integer, same shape as the
existing onboarding "age" field in survey_view.py used for BMR calculation)
and stored in Supabase Auth user_metadata as `signup_age` -- it is not
re-derived from a birthdate, so it goes stale exactly the same way that
onboarding age field already does. That's an existing, accepted limitation
of this codebase, not a new one this file introduces.

Accounts with no `signup_age` in their metadata at all -- either created
before this field existed, or some future case where the profile fetch
fails -- are treated by can_access_meal_feed() as under-age, not as an
exception. "Make sure minors can't access it" only holds if unknown
defaults to blocked rather than allowed; the tradeoff is that a legitimate
adult account with no age on file needs to confirm their age once (see
profile_view.py's age-confirmation prompt, which writes signup_age via the
same update_profile_data() path as registration) before Meal Feed unlocks.
"""
from typing import Optional

MIN_ACCOUNT_AGE = 13
MIN_FEED_AGE = 18


def is_account_age_allowed(age: Optional[int]) -> bool:
    """True if `age` clears the account-creation floor. Called at
    registration, before any account is created."""
    if age is None:
        return False
    return age >= MIN_ACCOUNT_AGE


def can_access_meal_feed(signup_age: Optional[int]) -> bool:
    """True if the signed-in user's stored age clears the Meal Feed floor.
    A missing signup_age is treated as NOT allowed -- see the module
    docstring for why unknown defaults to blocked, not allowed."""
    if signup_age is None:
        return False
    return signup_age >= MIN_FEED_AGE
