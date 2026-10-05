"""ESPN provider for the LiveScore tool.

Uses ESPN's public site API, which needs no API key and no signup, so LiveScore
works immediately. API-Football is preferred when a key is configured because
its data is a supported contract; see ``main.py`` for the selection logic.

Caveat: these endpoints are not publicly documented or covered by a support
contract. They are the ones espn.com itself uses and they could change or
disappear without notice. Everything here is defensive: if a field moves, the
page degrades rather than crashing.

Data notes:
* ``scoreboard`` gives the day's fixtures and scorelines, one request per
  competition. There is no combined endpoint, so the requests are issued
  concurrently.
* ``summary`` gives the full event timeline (commentary) and lineups (rosters)
  in a single request, which is all the match detail page needs.
* ESPN states the assister in prose ("Assisted by X with a through ball") rather
  than as a structured field, so the goal text is parsed for it.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import date as _date
from typing import Any, Awaitable, Callable, NamedTuple, Optional

import httpx

from . import DOMESTIC, INTERNATIONAL, NotFound, ProviderError, sort_matches

logger = logging.getLogger(__name__)

PREFIX = "espn"
BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer"

# The summary endpoint resolves an event by id and ignores the league in the
# path (any valid slug works; the response carries the real league), so a single
# placeholder league is reused for every detail lookup.
SUMMARY_LEAGUE = "eng.1"


class Competition(NamedTuple):
    name: str
    group: str  # DOMESTIC or INTERNATIONAL


# Competitions to fetch, by ESPN league slug. ESPN has no multi-league scoreboard
# endpoint, so each competition costs one request; they are fetched concurrently.
#
# Friendly names are set here because ESPN's own labels are inconsistent for the
# domestic leagues ("LALIGA" rather than "La Liga").
LEAGUES = {
    # Top five European domestic leagues.
    "eng.1": Competition("Premier League", DOMESTIC),
    "esp.1": Competition("La Liga", DOMESTIC),
    "ger.1": Competition("Bundesliga", DOMESTIC),
    "ita.1": Competition("Serie A", DOMESTIC),
    "fra.1": Competition("Ligue 1", DOMESTIC),
    # International: national-team competitions.
    "fifa.friendly": Competition("International Friendly", INTERNATIONAL),
    "fifa.world": Competition("FIFA World Cup", INTERNATIONAL),
    "fifa.worldq.uefa": Competition("World Cup Qualifying - UEFA", INTERNATIONAL),
    "fifa.worldq.conmebol": Competition("World Cup Qualifying - CONMEBOL", INTERNATIONAL),
    "fifa.worldq.concacaf": Competition("World Cup Qualifying - Concacaf", INTERNATIONAL),
    "fifa.worldq.afc": Competition("World Cup Qualifying - AFC", INTERNATIONAL),
    "fifa.worldq.caf": Competition("World Cup Qualifying - CAF", INTERNATIONAL),
    "fifa.worldq.ofc": Competition("World Cup Qualifying - OFC", INTERNATIONAL),
    "uefa.nations": Competition("UEFA Nations League", INTERNATIONAL),
    "uefa.euro": Competition("UEFA European Championship", INTERNATIONAL),
    "uefa.euroq": Competition("European Championship Qualifying", INTERNATIONAL),
    "caf.nations": Competition("Africa Cup of Nations", INTERNATIONAL),
    "afc.asian.cup": Competition("AFC Asian Cup", INTERNATIONAL),
    "concacaf.gold": Competition("Concacaf Gold Cup", INTERNATIONAL),
    "concacaf.nations.league": Competition("Concacaf Nations League", INTERNATIONAL),
}

# Copa America has no working slug on ESPN - conmebol.copa, copa.america and
# conmebol.copaamerica all return HTTP 400 - so that competition is unavailable
# here. Do not spend time re-testing those names.

TTL_FIXTURES = 30
TTL_SUMMARY = 30

_cache: dict[str, tuple[float, Any]] = {}


def leagues_for_scope(scope: Optional[str]) -> dict[str, Competition]:
    """The competitions to fetch for a scope filter (``all`` when unset).

    An unrecognised scope falls back to everything rather than to nothing, so a
    bad value degrades to the default instead of an empty page.
    """
    if not scope or scope == "all" or scope not in {meta.group for meta in LEAGUES.values()}:
        return LEAGUES
    return {slug: meta for slug, meta in LEAGUES.items() if meta.group == scope}


async def _cached(key: str, ttl: float, loader: Callable[[], Awaitable[Any]]) -> Any:
    now = time.monotonic()
    hit = _cache.get(key)
    if hit is not None and now - hit[0] < ttl:
        return hit[1]
    value = await loader()
    _cache[key] = (now, value)
    return value


def is_configured() -> bool:
    """ESPN needs no credentials, so it is always usable."""
    return True


def _strip_prefix(fixture_id: str) -> str:
    """Accept ``espn-401879272`` or a bare event id."""
    prefix = PREFIX + "-"
    return fixture_id[len(prefix):] if fixture_id.startswith(prefix) else fixture_id


async def _get_json(client: httpx.AsyncClient, path: str) -> dict:
    try:
        response = await client.get(BASE_URL + path)
    except httpx.HTTPError as exc:
        raise ProviderError(f"Could not reach ESPN: {exc}") from exc
    if response.status_code != 200:
        raise ProviderError(f"ESPN returned HTTP {response.status_code}.")
    try:
        payload = response.json()
    except ValueError as exc:
        raise ProviderError("ESPN returned a response that was not JSON.") from exc
    if not isinstance(payload, dict):
        raise ProviderError("ESPN returned an unexpected payload.")
    return payload


# --------------------------------------------------------------------------
# Normalisation helpers
# --------------------------------------------------------------------------


def _logo(team: Optional[dict]) -> Optional[str]:
    team = team or {}
    if team.get("logo"):
        return team["logo"]
    for entry in team.get("logos") or []:
        if entry.get("href"):
            return entry["href"]
    return None


def _side(node: Optional[dict]) -> dict:
    node = node or {}
    team = node.get("team") or {}
    score = node.get("score")
    return {
        "id": team.get("id"),
        "name": team.get("displayName") or team.get("shortDisplayName") or "Unknown",
        "logo": _logo(team),
        "score": int(score) if str(score).strip().isdigit() else None,
    }


def _blank_side() -> dict:
    return {"id": None, "name": "Unknown", "logo": None, "score": None}


def _status(status: Optional[dict]) -> tuple[str, Optional[int], str]:
    """Map an ESPN status onto the shared status codes.

    Returns ``(short, elapsed_minutes, long)``.
    """
    status = status or {}
    kind = status.get("type") or {}
    state = kind.get("state")

    if state == "pre":
        return "NS", None, kind.get("shortDetail") or kind.get("detail") or "Not Started"
    if state == "post":
        return "FT", None, kind.get("description") or "Full Time"
    if state == "in":
        # ESPN reports the elapsed minute as a plain integer. Guard the range so a
        # wall-clock style value cannot render as "minute 52345".
        clock = status.get("clock")
        elapsed = clock if isinstance(clock, int) and 0 < clock <= 130 else None
        return "LIVE", elapsed, kind.get("description") or "In Progress"

    # Postponed, cancelled and similar.
    name = (kind.get("name") or "").split("_")[-1]
    short = {"POSTPONED": "PST", "CANCELED": "CANC", "CANCELLED": "CANC"}.get(name, "PST")
    return short, None, kind.get("description") or kind.get("detail") or "Unknown"


def _minute(display: Optional[str]) -> str:
    """``"45'+6'"`` -> ``"45+6"``, ``"9'"`` -> ``"9"``."""
    if not display:
        return ""
    match = re.fullmatch(r"(\d+)(?:\+(\d+))?", display.strip().replace("'", ""))
    if not match:
        return ""
    return f"{match.group(1)}+{match.group(2)}" if match.group(2) else match.group(1)


def _sort_minute(minute: str) -> tuple:
    """Sort ``"45+6"`` after ``"45"`` but before ``"46"``."""
    parts = minute.split("+") if minute else [""]
    try:
        return (int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)
    except ValueError:
        return (999, 0)


def _side_for(team_name: Optional[str], home: str, away: str) -> str:
    """Map a team name taken from commentary text onto home/away."""
    if not team_name:
        return ""
    name = team_name.strip().casefold()
    if name == home.casefold():
        return "home"
    if name == away.casefold():
        return "away"
    # Commentary sometimes uses a short name, so fall back to containment.
    if name in home.casefold() or home.casefold() in name:
        return "home"
    if name in away.casefold() or away.casefold() in name:
        return "away"
    return ""


# Commentary text shapes, verified against real top-five fixtures.
_GOAL_RE = re.compile(r"^Goal!\s+.*?\.\s*(?P<player>[^()]+?)\s*\((?P<team>[^)]+)\)")
_ASSIST_RE = re.compile(r"Assisted by\s+(?P<assist>.+?)(?:\s+with\b|\s+following\b|[.!]|$)")
_OWN_GOAL_RE = re.compile(r"^Own Goal by\s+(?P<player>.+?),\s*(?P<team>[^.]+?)\s*\.")
_CARD_RE = re.compile(
    r"^(?P<player>.+?)\s*\((?P<team>[^)]+)\)\s+is shown the\s+(?P<card>[\w\s-]+?)\s*card"
)
_SUB_RE = re.compile(
    r"^Substitution,\s*(?P<team>[^.]+?)\.\s*(?P<player_in>.+?)\s+replaces\s+(?P<player_out>.+?)\s*\.?\s*$"
)

# "goal", "goal---free-kick", "goal---header", "goal---volley", "goal---penalty"
_GOAL_TYPE_RE = re.compile(r"^goal(?:---(?P<kind>.+))?$")
_GOAL_NOTES = {
    "free-kick": "free kick",
    "header": "header",
    "volley": "volley",
    "penalty": "penalty",
}


def _normalise_events(commentary: list, home: str, away: str) -> list[dict]:
    """Turn ESPN commentary into the shared goal/card/substitution shape."""
    events: list[dict] = []

    for entry in commentary or []:
        play = entry.get("play") or {}
        play_type = ((play.get("type") or {}).get("type")) or ""
        text = (entry.get("text") or "").strip()
        minute = _minute((entry.get("time") or {}).get("displayValue"))

        if play_type == "own-goal":
            match = _OWN_GOAL_RE.match(text)
            if not match:
                continue
            # An own goal is credited to the opponent of the team named in the text.
            named = _side_for(match.group("team"), home, away)
            side = "away" if named == "home" else "home" if named == "away" else ""
            events.append(
                {
                    "minute": minute,
                    "kind": "goal",
                    "side": side,
                    "player": match.group("player").strip(),
                    "assist": None,
                    "note": "own goal",
                }
            )
            continue

        goal_type = _GOAL_TYPE_RE.match(play_type)
        if goal_type:
            match = _GOAL_RE.match(text)
            if not match:
                continue
            assist = _ASSIST_RE.search(text)
            events.append(
                {
                    "minute": minute,
                    "kind": "goal",
                    "side": _side_for(match.group("team"), home, away),
                    "player": match.group("player").strip(),
                    "assist": assist.group("assist").strip() if assist else None,
                    "note": _GOAL_NOTES.get(goal_type.group("kind") or ""),
                }
            )
            continue

        if "card" in play_type:
            match = _CARD_RE.match(text)
            if not match:
                continue
            # "yellow", "red", or "yellow red" for a dismissal.
            colour = match.group("card").strip().split()[-1]
            card = "yellowred" if "yellow" in colour and "red" in colour else colour
            events.append(
                {
                    "minute": minute,
                    "kind": "card",
                    "side": _side_for(match.group("team"), home, away),
                    "player": match.group("player").strip(),
                    "card": card,
                    "note": "second yellow" if card == "yellowred" else None,
                }
            )
            continue

        if play_type == "substitution":
            match = _SUB_RE.match(text)
            if not match:
                continue
            events.append(
                {
                    "minute": minute,
                    "kind": "sub",
                    "side": _side_for(match.group("team"), home, away),
                    "player_in": match.group("player_in").strip(),
                    "player_out": match.group("player_out").strip(),
                }
            )

    events.sort(key=lambda e: _sort_minute(e["minute"]))
    return events


def _events_from_details(details: list, home_id: Optional[str], away_id: Optional[str]) -> list[dict]:
    """Fallback when commentary is unavailable: scorers and cards, no assists.

    The summary header carries a structured ``details`` array, so the timeline
    still renders even if commentary is missing.
    """
    events: list[dict] = []
    for detail in details or []:
        if not isinstance(detail, dict):
            continue
        minute = _minute((detail.get("clock") or {}).get("displayValue"))
        athletes = detail.get("athletesInvolved") or []
        player = athletes[0].get("displayName") if athletes else None
        team_id = str((detail.get("team") or {}).get("id") or "")

        if team_id and team_id == str(home_id):
            side = "home"
        elif team_id and team_id == str(away_id):
            side = "away"
        else:
            side = ""

        if detail.get("scoringPlay"):
            events.append(
                {
                    "minute": minute,
                    "kind": "goal",
                    "side": side,
                    "player": player,
                    "assist": None,
                    "note": "own goal" if detail.get("ownGoal") else None,
                }
            )
        elif detail.get("redCard") or detail.get("yellowCard"):
            events.append(
                {
                    "minute": minute,
                    "kind": "card",
                    "side": side,
                    "player": player,
                    "card": "red" if detail.get("redCard") else "yellow",
                    "note": None,
                }
            )

    events.sort(key=lambda e: _sort_minute(e["minute"]))
    return events


def _normalise_lineups(rosters: list) -> list[dict]:
    out = []
    for entry in rosters or []:
        team = entry.get("team") or {}
        players = []
        for slot in entry.get("roster") or []:
            athlete = slot.get("athlete") or {}
            players.append(
                {
                    "number": slot.get("jersey") or athlete.get("jersey"),
                    "name": athlete.get("displayName") or athlete.get("fullName"),
                    "pos": (slot.get("position") or {}).get("abbreviation") or None,
                    "starter": bool(slot.get("starter")),
                }
            )
        side = entry.get("homeAway")
        out.append(
            {
                "side": side if side in ("home", "away") else None,
                "team": team.get("displayName") or "Unknown",
                "logo": _logo(team),
                "formation": entry.get("formation"),
                "starters": [p for p in players if p["starter"]],
                "bench": [p for p in players if not p["starter"]],
            }
        )
    return out


def _normalise_event(raw: dict, league_slug: str) -> dict:
    # The site API returns each event unwrapped, while ESPN's core API nests it
    # under an "event" key. Accept either shape.
    event = raw.get("event") or raw
    competition = (event.get("competitions") or [{}])[0]
    short, elapsed, long_text = _status(event.get("status") or competition.get("status"))
    sides = {c.get("homeAway"): _side(c) for c in competition.get("competitors") or []}
    known = LEAGUES.get(league_slug)

    return {
        "id": f"{PREFIX}-{event.get('id')}",
        "kickoff": event.get("date") or competition.get("date"),
        "kickoff_utc": event.get("date") or competition.get("date"),
        "round": None,
        "venue": (competition.get("venue") or {}).get("fullName"),
        "league_id": league_slug,
        "league": known.name if known else league_slug,
        "group": known.group if known else DOMESTIC,
        "country": None,
        "league_logo": None,
        "status_short": short,
        "status_long": long_text,
        "elapsed": elapsed,
        "home": sides.get("home") or _blank_side(),
        "away": sides.get("away") or _blank_side(),
    }


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


async def fixtures_for_day(
    client: httpx.AsyncClient, day: Optional[str] = None, scope: Optional[str] = None
) -> list[dict]:
    """Fixtures for a day (defaults to today, UTC), across the chosen scope.

    ESPN has no combined multi-league endpoint, so each competition is queried
    separately; they are fetched concurrently because there are more than twenty
    of them. Results are merged and sorted into the shared order.

    A competition that fails is logged and skipped rather than failing the page,
    since a transient error on one scoreboard should not blank the rest. If every
    request fails the error is raised, because an empty page would look identical
    to a genuine day without fixtures.
    """
    stamp = (day or _date.today().isoformat()).replace("-", "")
    competitions = leagues_for_scope(scope)

    async def scoreboard(slug: str) -> dict:
        return await _get_json(client, f"/{slug}/scoreboard?dates={stamp}")

    async def load() -> list[dict]:
        slugs = list(competitions)
        payloads = await asyncio.gather(
            *(scoreboard(slug) for slug in slugs), return_exceptions=True
        )

        matches: list[dict] = []
        failures: list[str] = []
        for slug, payload in zip(slugs, payloads):
            if isinstance(payload, BaseException):
                logger.warning("live-score: %s scoreboard failed: %s", slug, payload)
                failures.append(f"{slug}: {payload}")
                continue
            for raw in payload.get("events") or []:
                matches.append(_normalise_event(raw, slug))

        if not matches and failures:
            raise ProviderError(failures[0])
        return sort_matches(matches)

    # The cache key includes the scope: domestic and international results are
    # different subsets, so one must not be served in place of the other.
    return await _cached(f"fixtures:{stamp}:{scope or 'all'}", TTL_FIXTURES, load)


async def _summary(client: httpx.AsyncClient, event_id: str) -> dict:
    """Fetch (and cache) the summary payload, which carries events and lineups."""

    async def load() -> dict:
        # ESPN answers 404 for an id that matches no event, which the caller
        # should treat as "no such match" rather than an upstream failure.
        try:
            return await _get_json(client, f"/{SUMMARY_LEAGUE}/summary?event={event_id}")
        except ProviderError as exc:
            if "HTTP 404" in str(exc):
                raise NotFound("That match could not be found.") from exc
            raise

    return await _cached(f"summary:{event_id}", TTL_SUMMARY, load)


async def match_detail(client: httpx.AsyncClient, fixture_id: str) -> dict:
    """Fixture plus its event timeline and lineups, for the detail page."""
    event_id = _strip_prefix(fixture_id)
    if not event_id.isdigit():
        raise NotFound("That match could not be found.")

    async def load() -> dict:
        summary = await _summary(client, event_id)
        header = summary.get("header") or {}
        competition = (header.get("competitions") or [{}])[0]
        if not competition.get("competitors"):
            raise NotFound("That match could not be found.")

        competitors = competition.get("competitors") or []
        sides = {c.get("homeAway"): _side(c) for c in competitors}
        home = sides.get("home") or _blank_side()
        away = sides.get("away") or _blank_side()

        short, elapsed, long_text = _status(competition.get("status") or header.get("status"))
        league = header.get("league") or {}

        commentary = summary.get("commentary") or []
        events = _normalise_events(commentary, home["name"], away["name"])
        if not events:
            # Commentary can lag or be absent; fall back to the structured scoring
            # events, which carry scorers but no assists.
            events = _events_from_details(
                competition.get("details") or [], home.get("id"), away.get("id")
            )

        return {
            "id": f"{PREFIX}-{event_id}",
            "kickoff": competition.get("date"),
            "kickoff_utc": competition.get("date"),
            "round": None,
            "venue": ((summary.get("gameInfo") or {}).get("venue") or {}).get("fullName"),
            "league_id": league.get("slug"),
            "league": league.get("abbreviation") or league.get("name"),
            "group": (LEAGUES.get(league.get("slug")) or Competition("", DOMESTIC)).group,
            "country": None,
            "league_logo": None,
            "status_short": short,
            "status_long": long_text,
            "elapsed": elapsed,
            "home": home,
            "away": away,
            "events": events,
            "lineups": _normalise_lineups(summary.get("rosters") or []),
        }

    return await _cached(f"detail:{event_id}", TTL_SUMMARY, load)


async def fixture_events(client: httpx.AsyncClient, fixture_id: str) -> list[dict]:
    """Goals, cards and substitutions as one minute-ordered list."""
    return (await match_detail(client, fixture_id)).get("events") or []


async def fixture_lineups(client: httpx.AsyncClient, fixture_id: str) -> list[dict]:
    """Starting XI and bench for both teams."""
    return (await match_detail(client, fixture_id)).get("lineups") or []