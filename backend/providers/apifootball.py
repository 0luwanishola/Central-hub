"""API-Football (api-sports.io) v3 client for the LiveScore tool.

Requires a free API key in the environment:

    API_FOOTBALL_KEY=your-key-here

The key is read from the environment on every request and is never sent to the
browser. Responses are normalised into plain dictionaries so the templates do
not depend on the upstream schema.

Free-tier quota is 100 requests/day, so every call is cached in memory for a
short TTL. Raise the TTLs below if you have a paid plan.

Caveat: this provider has not been exercised against the live API, because no key
was available while it was written. The request shapes and field names follow
API-Football's published v3 documentation, but the international-league
classification below in particular is inferred from how the docs describe the
``league.country`` field rather than observed. ESPN is the default provider and
is verified end to end; treat this path as needing a test run once a key exists.
"""

from __future__ import annotations

import os
import time
from datetime import date
from typing import Any, Awaitable, Callable, Optional

import httpx

from . import (
    DOMESTIC,
    INTERNATIONAL,
    NotConfigured,
    NotFound,
    ProviderError,
    sort_matches,
)

PREFIX = "apifootball"
BASE_URL = "https://v3.football.api-sports.io/"

# The five European leagues the LiveScore tool covers, by API-Football league id.
# Names are taken from the API response rather than hardcoded, so only the ids
# live here.
TOP_LEAGUES = {39, 140, 135, 78, 61}

# National-team competitions are identified by the league's `country` field rather
# than by a hardcoded id list. API-Football sets `country` to a confederation (or
# "World") for national-team competitions and to the actual country for club
# competitions, so this needs no list of ids to keep in step with their catalogue.
INTERNATIONAL_COUNTRIES = {
    "World",
    "Europe",
    "Asia",
    "Africa",
    "South America",
    "North America",
}

# Cache lifetimes in seconds. The free tier allows only 100 requests/day, so the
# live list is polled sparingly.
TTL_FIXTURES = 30
TTL_DETAIL = 30
TTL_LINEUPS = 300

_cache: dict[str, tuple[float, Any]] = {}


async def _cached(key: str, ttl: float, loader: Callable[[], Awaitable[Any]]) -> Any:
    now = time.monotonic()
    hit = _cache.get(key)
    if hit is not None and now - hit[0] < ttl:
        return hit[1]
    value = await loader()
    _cache[key] = (now, value)
    return value


def is_configured() -> bool:
    return bool(os.environ.get("API_FOOTBALL_KEY", "").strip())


def _api_key() -> str:
    key = os.environ.get("API_FOOTBALL_KEY", "").strip()
    if not key:
        raise NotConfigured(
            "API_FOOTBALL_KEY is not set. Add it to backend/.env to enable LiveScore."
        )
    return key


async def _get(client: httpx.AsyncClient, path: str, params: Optional[dict] = None) -> list:
    """Call the API and return the `response` list, raising ProviderError on failure."""
    # Resolve the key before touching the client so a missing key always reports
    # NotConfigured rather than an error from the HTTP layer.
    headers = {"x-apisports-key": _api_key()}

    try:
        response = await client.get(BASE_URL + path, params=params or {}, headers=headers)
    except httpx.HTTPError as exc:
        raise ProviderError(f"Could not reach API-Football: {exc}") from exc

    if response.status_code == 429:
        raise ProviderError(
            "API-Football rate limit reached. The free plan allows 100 requests per day."
        )
    if response.status_code != 200:
        raise ProviderError(f"API-Football returned HTTP {response.status_code}.")

    try:
        payload = response.json()
    except ValueError as exc:
        raise ProviderError("API-Football returned a response that was not JSON.") from exc

    # API-Football reports failures in an `errors` object, sometimes alongside a
    # 200 status and an HTTP 429, so check it before trusting the payload.
    errors = payload.get("errors") or {}
    messages = [str(v) for v in errors.values() if v] if isinstance(errors, dict) else []
    if messages:
        raise ProviderError("API-Football error: " + "; ".join(messages))

    data = payload.get("response")
    return data if isinstance(data, list) else []


# --------------------------------------------------------------------------
# Normalisation
# --------------------------------------------------------------------------


def _side(node: Optional[dict]) -> dict:
    node = node or {}
    team = node.get("team") or {}
    return {
        "id": team.get("id"),
        "name": team.get("name") or "Unknown",
        "logo": team.get("logo"),
        "score": node.get("goals"),
    }


def group_of(league: Optional[dict]) -> str:
    """Which coverage group a fixture's league belongs to.

    Returns an empty string for competitions the tool does not cover (club
    competitions, domestic leagues outside the top five), which the caller treats
    as "drop this fixture".
    """
    league = league or {}
    if league.get("id") in TOP_LEAGUES:
        return DOMESTIC
    if (league.get("country") or "").strip() in INTERNATIONAL_COUNTRIES:
        return INTERNATIONAL
    return ""


def normalise_fixture(raw: dict) -> dict:
    """Flatten one API-Football fixture object."""
    fixture = raw.get("fixture") or {}
    league = raw.get("league") or {}
    teams = raw.get("teams") or {}
    venue = fixture.get("venue") or {}
    status = fixture.get("status") or {}

    return {
        # Ids carry the provider prefix so /match/<id> can be routed back here.
        "id": f"{PREFIX}-{fixture.get('id')}",
        "kickoff": fixture.get("date"),
        "kickoff_utc": fixture.get("date"),
        "round": fixture.get("round"),
        "venue": venue.get("name"),
        "league_id": league.get("id"),
        "league": league.get("name"),
        "group": group_of(league),
        "country": league.get("country"),
        "league_logo": league.get("logo"),
        "status_short": status.get("short"),
        "status_long": status.get("long"),
        "elapsed": status.get("elapsed"),
        "home": _side(teams.get("home")),
        "away": _side(teams.get("away")),
    }


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


def _strip_prefix(fixture_id: str) -> str:
    """Accept ``apifootball-123`` or a bare fixture id."""
    prefix = PREFIX + "-"
    return fixture_id[len(prefix):] if fixture_id.startswith(prefix) else fixture_id


async def fixtures_for_day(
    client: httpx.AsyncClient, day: Optional[str] = None, scope: Optional[str] = None
) -> list[dict]:
    """Fixtures for a day (defaults to today, UTC), across the chosen scope.

    Covers scheduled, in-progress and completed matches, which is what a live
    scoreboard needs: on a quiet day the page still shows the day's fixtures
    rather than going blank.

    One request covers the whole day because ``/fixtures?date=`` spans every
    competition; the response is filtered down locally, which matters on a free
    plan where each call costs quota.
    """
    day = day or date.today().isoformat()
    wanted = scope if scope and scope != "all" else None

    async def load() -> list[dict]:
        raw = await _get(client, "fixtures", {"date": day})
        matches = []
        for fixture in raw:
            match = normalise_fixture(fixture)
            # An empty group means a competition this tool does not cover.
            if not match["group"]:
                continue
            if wanted and match["group"] != wanted:
                continue
            matches.append(match)
        return sort_matches(matches)

    return await _cached(f"fixtures:{day}:{scope or 'all'}", TTL_FIXTURES, load)


async def fixture_events(client: httpx.AsyncClient, fixture_id: str) -> list[dict]:
    """Goals, cards and substitutions for a fixture, as one minute-ordered list.

    API-Football splits these across three differently shaped fields, so this
    flattens them into a common `kind`/`side` shape for the template.
    """
    fixture_id = _strip_prefix(fixture_id)

    async def load() -> list[dict]:
        raw = (await _get(client, "fixtures", {"id": fixture_id})) or [{}]
        fixture = (raw[0].get("fixture") or {}) if raw else {}
        teams = raw[0].get("teams") or {} if raw else {}
        home_id = ((teams.get("home") or {}).get("team") or {}).get("id")
        away_id = ((teams.get("away") or {}).get("team") or {}).get("id")

        events: list[dict] = []

        def side_of(team_id) -> str:
            if team_id is None:
                return ""
            if team_id == home_id:
                return "home"
            if team_id == away_id:
                return "away"
            return ""

        for goal in raw[0].get("goals") or []:
            goal_type = goal.get("type")
            note = "penalty" if goal_type == "penalty" else None
            # An own goal is credited to the scoring team's opponent in the
            # timeline, so record who scored it rather than the team id.
            if goal_type == "owngoal":
                note = "own goal"
            events.append(
                {
                    "minute": goal.get("minute"),
                    "kind": "goal",
                    "side": side_of((goal.get("team") or {}).get("id")),
                    "player": (goal.get("player") or {}).get("name"),
                    "assist": goal.get("assist"),
                    "note": note,
                }
            )

        # Some responses carry `cards` as a dict keyed by side, others as a flat
        # list carrying a team id. Accept both.
        raw_cards = raw[0].get("cards") or []
        if isinstance(raw_cards, dict):
            cards = [
                {**card, "__side": side_key}
                for side_key in ("home", "away")
                for card in (raw_cards.get(side_key) or [])
            ]
        else:
            cards = list(raw_cards)

        for card in cards:
            events.append(
                {
                    "minute": card.get("minute"),
                    "kind": "card",
                    # Prefer the explicit side, else derive it from the team id.
                    "side": card.get("__side") or side_of((card.get("team") or {}).get("id")),
                    "player": (card.get("player") or {}).get("name"),
                    "card": card.get("card"),
                    "note": "second yellow" if card.get("card") == "yellowred" else None,
                }
            )

        # `in` is a Python keyword, so it is spelled "player_in" downstream.
        for sub in raw[0].get("substitutions") or []:
            events.append(
                {
                    "minute": sub.get("minute"),
                    "kind": "sub",
                    "side": side_of((sub.get("team") or {}).get("id")),
                    "player_in": (sub.get("in") or {}).get("name"),
                    "player_out": (sub.get("out") or {}).get("name"),
                }
            )

        events.sort(key=lambda e: (e["minute"] is None, e["minute"] or 0))
        return [
            {
                "id": str(fixture.get("id") or fixture_id),
                "events": events,
            }
        ]

    data = await _cached(f"events:{fixture_id}", TTL_DETAIL, load)
    return data[0]["events"] if data else []


async def fixture_lineups(client: httpx.AsyncClient, fixture_id: str) -> list[dict]:
    """Starting XI and bench for both teams.

    Lineups are only published shortly before kickoff, so an empty list is a
    normal result rather than an error.
    """
    fixture_id = _strip_prefix(fixture_id)

    async def load() -> list[dict]:
        # startXI / substitutes carry no team id, so the home side is resolved
        # from the fixture itself.
        fixture_raw = (await _get(client, "fixtures", {"id": fixture_id})) or [{}]
        teams = (fixture_raw[0].get("teams") or {}) if fixture_raw else {}
        home_id = ((teams.get("home") or {}).get("team") or {}).get("id")
        away_id = ((teams.get("away") or {}).get("team") or {}).get("id")

        raw = await _get(client, "fixtures/lineups", {"fixture": fixture_id})
        out = []
        for entry in raw:
            team = entry.get("team") or {}
            starters = [
                {
                    "number": (p.get("player") or {}).get("number"),
                    "name": (p.get("player") or {}).get("name"),
                    "pos": (p.get("player") or {}).get("pos"),
                }
                for p in entry.get("startXI") or []
            ]
            bench = [
                {
                    "number": (p.get("player") or {}).get("number"),
                    "name": (p.get("player") or {}).get("name"),
                    "pos": (p.get("player") or {}).get("pos"),
                }
                for p in entry.get("substitutes") or []
            ]
            if team.get("id") == home_id:
                side = "home"
            elif team.get("id") == away_id:
                side = "away"
            else:
                # Unrecognised team id: keep the API order, which is home first.
                side = "home" if not out else "away"

            out.append(
                {
                    "side": side,
                    "team": team.get("name"),
                    "logo": team.get("logo"),
                    "formation": entry.get("formation"),
                    "starters": starters,
                    "bench": bench,
                }
            )
        return out

    return await _cached(f"lineups:{fixture_id}", TTL_LINEUPS, load)


async def match_detail(client: httpx.AsyncClient, fixture_id: str) -> dict:
    """Fixture plus its event timeline and lineups, for the detail page."""
    fixture_id = _strip_prefix(fixture_id)
    raw = await _get(client, "fixtures", {"id": fixture_id})
    if not raw:
        raise NotFound("That match could not be found.")
    match = normalise_fixture(raw[0])
    match["events"] = await fixture_events(client, fixture_id)
    try:
        match["lineups"] = await fixture_lineups(client, fixture_id)
    except ProviderError:
        # A missing lineup call should not blank out the whole page.
        match["lineups"] = []
    return match
