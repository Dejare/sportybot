"""
sportybet.py — SportyBet API wrapper (updated for 2026 API structure)
Uses the current liveOrPrematchEvents endpoint with sr:sport ID format.
API requires sportId in "sr:sport:N" format (plain integers return 422).
"""

import logging
import requests
from config import SPORTYBET_BASE, SPORTYBET_COUNTRY

log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.sportybet.com",
    "Referer": f"https://www.sportybet.com/{SPORTYBET_COUNTRY}/",
    "x-requested-with": "XMLHttpRequest",
}

# Booking code endpoints
BOOKING_ENDPOINTS = [
    f"https://www.sportybet.com/api/{SPORTYBET_COUNTRY}/orders/share/booking-code",
]

# Event endpoints (primary + fallback)
EVENT_ENDPOINTS = [
    f"https://www.sportybet.com/api/{SPORTYBET_COUNTRY}/factsCenter/liveOrPrematchEvents",
]


def _get(url: str, params: dict = None) -> dict:
    """Make a GET request and return parsed JSON."""
    r = requests.get(url, params=params, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()


def _flatten_tournament_events(data: dict) -> list:
    """
    New SportyBet API returns data as a list of tournaments,
    each containing an 'events' list. Flatten to a single events list.
    """
    result = data.get("data")
    if result is None:
        return []

    # If data is already a flat list of events (old format)
    if isinstance(result, list):
        all_events = []
        for item in result:
            # New format: item is a tournament with nested events
            if "events" in item:
                for ev in item["events"]:
                    # Attach tournament name to each event
                    if "sport" not in ev:
                        ev["_tournamentName"] = item.get("name", "")
                    all_events.append(ev)
            else:
                # Old format: item IS an event
                all_events.append(item)
        return all_events

    # If data is a dict, try known keys
    if isinstance(result, dict):
        for key in ("events", "sportEvents", "inplayEvents", "result", "list"):
            val = result.get(key)
            if val:
                return val

    return []


def _parse_game(ev: dict, live: bool = False) -> dict:
    """Parse a single event into our standard game dict."""
    home = ev.get("homeTeamName") or ev.get("homeName") or ev.get("home") or "?"
    away = ev.get("awayTeamName") or ev.get("awayName") or ev.get("away") or "?"

    # Tournament/league name: prefer the _tournamentName injected during flattening,
    # then try the nested sport > category > tournament hierarchy
    league = ev.get("_tournamentName") or ""
    if not league:
        sport_obj = ev.get("sport")
        if sport_obj and isinstance(sport_obj, dict):
            cat = sport_obj.get("category", {})
            tourn = cat.get("tournament", {})
            league = tourn.get("name", "") or cat.get("name", "")
    if not league:
        league = ev.get("tournamentName") or ev.get("leagueName") or ""

    event_id = str(ev.get("eventId") or ev.get("id") or "")

    # Odds — parse from markets array
    odds = {"home": 0, "draw": 0, "away": 0}
    markets = ev.get("markets") or ev.get("marketList") or []
    if markets:
        # Find the 1X2 market (id "1" or desc "1X2")
        main_market = None
        for m in markets:
            m_desc = (m.get("desc") or m.get("name") or "").lower()
            m_id = str(m.get("id", ""))
            if m_id == "1" or "1x2" in m_desc:
                # Skip 1UP/2UP variants
                if "1up" in m_desc or "2up" in m_desc:
                    continue
                main_market = m
                break

        if main_market:
            outcomes = main_market.get("outcomes") or main_market.get("outcomeList") or []
            for o in outcomes:
                desc = (o.get("desc") or o.get("name") or "").strip()
                val = float(o.get("odds") or o.get("odd") or 0)
                if desc in ("1", "Home", "W1"):
                    odds["home"] = val
                elif desc in ("X", "Draw"):
                    odds["draw"] = val
                elif desc in ("2", "Away", "W2"):
                    odds["away"] = val

    game = {
        "event_id": event_id,
        "home": home,
        "away": away,
        "league": league,
        "odds": odds,
        "raw": ev,
    }

    if live:
        game["score"] = ev.get("setScore") or ev.get("score") or ev.get("liveScore") or "0-0"
        # Parse minute from playedSeconds or matchTime
        played = ev.get("playedSeconds") or ""
        if played and ":" in str(played):
            try:
                game["minute"] = str(int(str(played).split(":")[0]))
            except (ValueError, IndexError):
                game["minute"] = played
        else:
            game["minute"] = ev.get("matchTime") or ev.get("minute") or ev.get("matchStatus") or "?"
    else:
        game["kick_off"] = ev.get("estimateStartTime") or ev.get("startTime") or ev.get("kickOff") or ""

    return game


# ─────────────────────────────────────────────────────────────────────────────
#  LIVE GAMES
# ─────────────────────────────────────────────────────────────────────────────

def get_live_games(sport_id: int = 1, limit: int = 50) -> list:
    """Fetch currently live games using group=LiveNow for reliable filtering."""
    # First try with group=LiveNow (confirmed working, returns only live events)
    param_sets = [
        {
            "sportId": f"sr:sport:{sport_id}",
            "pageSize": limit,
            "pageNum": 1,
            "group": "LiveNow",
        },
        # Fallback: fetch all and filter client-side
        {
            "sportId": f"sr:sport:{sport_id}",
            "pageSize": limit,
            "pageNum": 1,
        },
    ]
    last_error = None

    for url in EVENT_ENDPOINTS:
        for params in param_sets:
            try:
                data = _get(url, params)
                events = _flatten_tournament_events(data)
                if events:
                    # If we used group=LiveNow, all events are live
                    if params.get("group") == "LiveNow":
                        live_events = events
                    else:
                        # Filter to only live events (status=1 means live)
                        live_events = [
                            ev for ev in events
                            if ev.get("status") == 1
                            or ev.get("setScore")
                            or ev.get("playedSeconds")
                        ]
                        if not live_events:
                            live_events = events

                    log.info(f"Live games fetched from {url}: {len(live_events)} events")
                    return [_parse_game(ev, live=True) for ev in live_events[:limit]]
            except Exception as e:
                last_error = e
                log.warning(f"Live endpoint failed {url} (params={params.get('group','default')}): {e}")
                continue

    raise RuntimeError(
        f"All SportyBet live endpoints failed. Last error: {last_error}\n"
        "SportyBet may have changed their API. Check network requests at sportybet.com"
    )


# ─────────────────────────────────────────────────────────────────────────────
#  UPCOMING MATCHES
# ─────────────────────────────────────────────────────────────────────────────

def get_upcoming_matches(sport_id: int = 1, hours_ahead: int = 24, limit: int = 30) -> list:
    """Fetch upcoming (prematch) games."""
    params = {
        "sportId": f"sr:sport:{sport_id}",
        "pageSize": limit,
        "pageNum": 1,
    }
    last_error = None

    for url in EVENT_ENDPOINTS:
        try:
            data = _get(url, params)
            events = _flatten_tournament_events(data)
            if events:
                # Filter to prematch only (status=0 or no live indicators)
                prematch = [
                    ev for ev in events
                    if ev.get("status") == 0
                    or (not ev.get("setScore") and not ev.get("playedSeconds"))
                ]
                if not prematch:
                    prematch = events

                log.info(f"Upcoming matches fetched from {url}: {len(prematch)} events")
                return [_parse_game(ev, live=False) for ev in prematch[:limit]]
        except Exception as e:
            last_error = e
            log.warning(f"Upcoming endpoint failed {url}: {e}")
            continue

    raise RuntimeError(
        f"All SportyBet upcoming endpoints failed. Last error: {last_error}"
    )


# ─────────────────────────────────────────────────────────────────────────────
#  RESOLVE BOOKING CODE
# ─────────────────────────────────────────────────────────────────────────────

def resolve_booking_code(code: str) -> dict:
    """Decode a SportyBet booking code into a slip dict."""
    code = code.upper().strip()
    last_error = None

    for base_url in BOOKING_ENDPOINTS:
        try:
            data = _get(base_url, {"bookingCode": code})
            biz = data.get("bizCode")

            # bizCode 10000 = success, 19000 = invalid code
            if biz == 19000:
                raise ValueError(f"Invalid booking code: {data.get('message', 'Code not found')}")
            if biz not in (10000, 1, "1", 0, "0", None):
                raise ValueError(f"SportyBet error: {data.get('message', 'Unknown error')}")

            order = data.get("data") or {}
            events = (
                order.get("events") or order.get("orderEvents")
                or order.get("eventList") or order.get("outcomes") or []
            )

            games = []
            total_odds = 1.0
            for ev in events:
                home = ev.get("homeTeamName") or ev.get("home", "?")
                away = ev.get("awayTeamName") or ev.get("away", "?")
                odds_val = float(ev.get("odds") or ev.get("marketOdds") or 1.0)
                market = ev.get("marketName") or ev.get("market", "1X2")
                selection = ev.get("outcomeName") or ev.get("selection", "?")
                event_id = str(ev.get("eventId") or ev.get("id", ""))
                kick_off = ev.get("estimateStartTime") or ev.get("kickOff", "")
                league = ev.get("tournamentName") or ev.get("league", "")
                sport = ev.get("sportName") or ev.get("sport", "Football")
                total_odds *= odds_val
                games.append({
                    "event_id": event_id, "home": home, "away": away,
                    "sport": sport, "market": market, "selection": selection,
                    "odds": odds_val, "kick_off": kick_off, "league": league,
                })

            if games:
                return {"code": code, "games": games, "total_odds": round(total_odds, 2)}

            # No games parsed but request succeeded - might be empty
            if biz == 10000:
                raise ValueError(f"Booking code {code} returned no games")

        except ValueError:
            raise
        except Exception as e:
            last_error = e
            log.warning(f"Booking endpoint failed {base_url}: {e}")
            continue

    raise RuntimeError(f"Could not resolve booking code {code}. Last error: {last_error}")


# ─────────────────────────────────────────────────────────────────────────────
#  BUILD BETSLIP → BOOKING CODE
# ─────────────────────────────────────────────────────────────────────────────

def build_betslip(selections: list) -> dict:
    """POST selections to SportyBet to generate a new booking code."""
    payload = {
        "events": [
            {
                "eventId": str(s["event_id"]),
                "marketId": str(s["market_id"]),
                "outcomeId": str(s["outcome_id"]),
                "odds": str(s["odds"]),
            }
            for s in selections
        ]
    }
    headers = {**HEADERS, "Content-Type": "application/json"}
    last_error = None

    for url in BOOKING_ENDPOINTS:
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=15)
            r.raise_for_status()
            data = r.json()
            code = data.get("data", {}).get("bookingCode") or data.get("data", "")
            if code:
                return {"booking_code": str(code), "selections": selections}
        except Exception as e:
            last_error = e
            continue

    raise RuntimeError(f"Booking failed: {last_error}")


def extract_market_outcome_ids(raw_event: dict, desired_market: str = "1X2", desired_outcome: str = "1") -> dict:
    """Extract market_id and outcome_id from raw event data."""
    for market in raw_event.get("markets") or raw_event.get("marketList") or []:
        market_name = (market.get("desc") or market.get("name") or market.get("marketName") or "").lower()
        if desired_market.lower() in market_name:
            # Skip 1UP/2UP variants
            if "1up" in market_name or "2up" in market_name:
                continue
            for outcome in market.get("outcomes") or market.get("outcomeList") or []:
                desc = (outcome.get("desc") or outcome.get("name") or outcome.get("outcomeName") or "").strip()
                if desc == desired_outcome.strip():
                    return {
                        "market_id": str(market.get("id") or market.get("marketId", "")),
                        "outcome_id": str(outcome.get("id") or outcome.get("outcomeId", "")),
                        "odds": float(outcome.get("odds") or outcome.get("odd") or 0),
                    }
    return {}


def search_match(team_name: str) -> list:
    """
    Search events by team name keyword.
    Since the searchEvents endpoint was removed (returns 404),
    we fetch all events and filter locally by team name.
    """
    team_lower = team_name.strip().lower()
    if not team_lower:
        return []

    try:
        # Fetch a large batch of live + prematch events
        params = {
            "sportId": "sr:sport:1",
            "pageSize": 100,
            "pageNum": 1,
        }
        for url in EVENT_ENDPOINTS:
            try:
                data = _get(url, params)
                events = _flatten_tournament_events(data)
                if events:
                    # Filter by team name substring match
                    matched = [
                        ev for ev in events
                        if team_lower in (ev.get("homeTeamName") or "").lower()
                        or team_lower in (ev.get("awayTeamName") or "").lower()
                    ]
                    log.info(f"Search for '{team_name}': {len(matched)} matches found")
                    return matched
            except Exception as e:
                log.warning(f"Search endpoint failed {url}: {e}")
                continue
    except Exception as e:
        log.warning(f"Search failed: {e}")
    return []
