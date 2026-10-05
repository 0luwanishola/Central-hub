"""Third-party data providers for Central Hub.

Each provider returns the same normalised shape so the page templates never
depend on a specific upstream API.

Two providers are available for LiveScore:

* ``apifootball`` - API-Football (api-sports.io). Richer data, needs an API key.
* ``espn``        - ESPN's public site API. No key and no signup, but the data is
  unofficial and may change without notice.

``active_provider()`` picks API-Football when a key is configured and falls back
to ESPN otherwise, so the feature works out of the box.

Both modules raise the same exception types so routes can handle any provider's
failures with one ``except`` clause.
"""

from datetime import date, datetime, timezone
from typing import Optional


class ProviderError(RuntimeError):
    """Upstream API could not be used. Message is safe to show to the user."""


class NotFound(ProviderError):
    """The requested fixture does not exist."""


class NotConfigured(ProviderError):
    """The feature needs credentials that have not been supplied."""

# Status codes follow API-Football's vocabulary so templates can treat any
# provider's output identically.
LIVE_STATUSES = {"1H", "2H", "HT", "LIVE", "ET", "BT", "P", "VAR"}
FINISHED_STATUSES = {"FT", "AET", "PEN"}
POSTPONED_STATUSES = {"PST", "CANC", "ABD", "AWD", "NS"}

# Coverage groups for the LiveScore filter. ``all`` is not a real group; it means
# "no filter" and is handled separately.
DOMESTIC = "domestic"
INTERNATIONAL = "international"
GROUPS = (DOMESTIC, INTERNATIONAL)
SCOPES = ("all",) + GROUPS


def clean_scope(scope: Optional[str]) -> str:
    """Normalise a ``?scope=`` query parameter, falling back to ``all``.

    Anything unrecognised becomes ``all`` rather than an error, so a hand-typed
    URL still renders instead of 400-ing.
    """
    value = (scope or "").strip().lower()
    return value if value in SCOPES else "all"



def is_live(match: dict) -> bool:
    return match.get("status_short") in LIVE_STATUSES


def is_finished(match: dict) -> bool:
    return match.get("status_short") in FINISHED_STATUSES


def sort_matches(matches: list) -> list:
    """Order a day's matches for a scoreboard: live first, then upcoming, then played.

    Live matches lead because that is what the page is for; finished matches fall
    to the bottom but stay visible so a quiet day is not an empty page.
    """
    def key(match: dict) -> tuple:
        short = match.get("status_short")
        if is_live(match):
            bucket = 0
        elif short == "NS":
            bucket = 1
        elif short in POSTPONED_STATUSES:
            bucket = 2
        else:
            bucket = 3
        return (bucket, match.get("kickoff") or "")

    return sorted(matches, key=key)


def clock_label(match: dict) -> str:
    """Short status text for a match, preferring the live minute when present."""
    if match.get("elapsed"):
        return f"{match['elapsed']}'"
    if is_live(match):
        return "LIVE"
    return match.get("status_long") or match.get("status_short") or ""


def has_score(match: dict) -> bool:
    """Whether a scoreline means anything yet.

    A fixture that has not kicked off reports 0-0, so rendering the raw score
    would show a nil-nil result for a match that has never been played. Only live
    and finished matches have a real scoreline; everything else (not started,
    postponed, cancelled) has not been played.
    """
    return is_live(match) or is_finished(match)


def parse_kickoff(match: dict) -> Optional[datetime]:
    """The kickoff as an aware UTC datetime, or None if it is missing or unusable.

    Providers send different formats - ESPN uses ``2026-10-10T11:30Z`` and
    API-Football uses ``2026-10-10 11:30:00+00:00``. Normalising here keeps the
    templates from slicing a string they do not own, and keeps working on Python
    3.10, whose ``fromisoformat`` rejects a trailing ``Z``.
    """
    raw = (match.get("kickoff") or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00").replace(" ", "T", 1))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        # A naive timestamp is assumed to be UTC, which is what both providers mean.
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def kickoff_label(match: dict) -> str:
    """When a match is due to be played, relative to today where that is clearer.

    An empty string means there is no usable kickoff, so the template can fall back
    to the provider's own wording rather than printing a stray "UTC".
    """
    kickoff = parse_kickoff(match)
    if kickoff is None:
        return ""

    days = (kickoff.date() - datetime.now(timezone.utc).date()).days
    if days == 0:
        prefix = "Today"
    elif days == 1:
        prefix = "Tomorrow"
    elif days == -1:
        prefix = "Yesterday"
    else:
        # Built by hand rather than with strftime: "the portable %-d" is a glibc
        # extension and does not exist on Windows, where this app also runs.
        prefix = f"{kickoff.strftime('%a')} {kickoff.day} {kickoff.strftime('%b')}"
    return f"{prefix} {kickoff.strftime('%H:%M')}"


def active_provider():
    """The provider LiveScore should use right now.

    API-Football is preferred because it is a supported API, but it needs a key.
    ESPN needs none, so it takes over when no key is configured and the feature
    still works out of the box.
    """
    from . import apifootball, espn

    return apifootball if apifootball.is_configured() else espn


def provider_for(fixture_id: str):
    """Find the provider that owns a fixture id.

    Ids carry their provider as a prefix (``espn-401879272``) because both
    providers use plain numeric ids and would otherwise be ambiguous. The prefix
    is authoritative, so a link stays valid even if the active provider later
    changes - otherwise a bookmarked API-Football URL would break once the key
    is removed.
    """
    from . import apifootball, espn

    for module in (espn, apifootball):
        if fixture_id.startswith(module.PREFIX + "-"):
            return module
    return active_provider()