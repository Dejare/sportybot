"""
sportybet.py  — SportyBet API wrapper
Covers:
  • Resolve a booking code → list of selections
  • Fetch live games
  • Fetch upcoming matches
  • Book a betslip → return new booking code
"""

import logging
import time
import re
import requests
from typing import Optional
from fake_useragent import UserAgent
from tenacity import retry, stop_after_attempt, wait_exponential

from config import SPORTYBET_BASE, SPORTYBET_COUNTRY

log = logging.getLogger(__name__)

ua = UserAgent()

def _headers() -> dict:
    return {
        "User-Agent": ua.random,
        "Referer": f"https://www.sportybet.com/{SPORTYBET_COUNTRY}/",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": f"https://www.sportybet.com",
    }


# ─────────────────────────────────────────────────────────────────────────────
#  BOOKING CODE  →  SELECTIONS
# ─────────────────────────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=5))
def resolve_booking_code(code: str) -> dict:
    """
    Given a SportyBet booking code (e.g. ABC123), return the full slip data.
    Returns:
        {
          "code": str,
          "games": [
            {
              "event_id": str,
              "home": str,
              "away": str,
              "sport": str,
              "market": str,
              "selection": str,
              "odds": float,
              "kick_off": str,
              "league": str,
            }, ...
          ],
          "total_odds": float,
        }
    """
    url = f"{SPORTYBET_BASE}/order/share/booking-code"
    params = {"bookingCode": code.upper().strip()}

    r = requests.get(url, params=params, headers=_headers(), timeout=15)
    r.raise_for_status()
    data = r.json()

    if data.get("bizCode") != 1:
        raise ValueError(f"SportyBet returned error for code {code}: {data.get('message', 'Unknown error')}")

    order = data.get("data", {})
    events = order.get("events", []) or order.get("orderEvents", [])

    games = []
    total_odds = 1.0
    for ev in events:
        # Normalise across different SportyBet API response schemas
        home = ev.get("homeTeamName") or ev.get("home", "?")
        away = ev.get("awayTeamName") or ev.get("away", "?")
        odds = float(ev.get("odds") or ev.get("marketOdds") or 1.0)
        market = ev.get("marketName") or ev.get("market", "1X2")
        selection = ev.get("outcomeName") or ev.get("selection", "?")
        event_id = str(ev.get("eventId") or ev.get("id", ""))
        kick_off = ev.get("estimateStartTime") or ev.get("kickOff", "")
        league = ev.get("tournamentName") or ev.get("league", "")
        sport = ev.get("sportName") or ev.get("sport", "Football")

        total_odds *= odds
        games.append({
            "event_id": event_id,
            "home": home,
            "away": away,
            "sport": sport,
            "market": market,
            "selection": selection,
            "odds": odds,
            "kick_off": kick_off,
            "league": league,
        })

    return {"code": code.upper(), "games": games, "total_odds": round(total_odds, 2)}


# ─────────────────────────────────────────────────────────────────────────────
#  LIVE GAMES
# ─────────────────────────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=5))
def get_live_games(sport_id: int = 1, limit: int = 50) -> list:
    """
    Fetch currently live games from SportyBet.
    sport_id: 1=Football, 2=Basketball, 5=Tennis, etc.
    Returns list of game dicts.
    """
    url = f"{SPORTYBET_BASE}/factsCenter/liveEvents"
    params = {
        "sportId": sport_id,
        "pageSize": limit,
        "pageNum": 1,
    }

    r = requests.get(url, params=params, headers=_headers(), timeout=15)
    r.raise_for_status()
    data = r.json()

    events = (
        data.get("data", {}).get("events")
        or data.get("data", {}).get("sportEvents")
        or data.get("events", [])
        or []
    )

    games = []
    for ev in events:
        home = ev.get("homeTeamName") or ev.get("home", "?")
        away = ev.get("awayTeamName") or ev.get("away", "?")
        score = ev.get("setScore") or ev.get("score") or "0-0"
        minute = ev.get("matchTime") or ev.get("minute") or "?"
        league = ev.get("tournamentName") or ev.get("tournament", "")
        event_id = str(ev.get("eventId") or ev.get("id", ""))

        # Extract 1X2 odds from market outcomes
        outcomes = ev.get("markets", [{}])[0].get("outcomes", []) if ev.get("markets") else []
        odds_map = {o.get("desc", ""): float(o.get("odds", 0)) for o in outcomes}

        games.append({
            "event_id": event_id,
            "home": home,
            "away": away,
            "score": score,
            "minute": minute,
            "league": league,
            "sport_id": sport_id,
            "odds": {
                "home": odds_map.get("1") or odds_map.get("Home") or 0,
                "draw": odds_map.get("X") or odds_map.get("Draw") or 0,
                "away": odds_map.get("2") or odds_map.get("Away") or 0,
            },
            "raw": ev,  # keep for booking
        })

    return games


# ─────────────────────────────────────────────────────────────────────────────
#  UPCOMING MATCHES
# ─────────────────────────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=5))
def get_upcoming_matches(sport_id: int = 1, hours_ahead: int = 24, limit: int = 30) -> list:
    """Fetch upcoming (pre-match) events."""
    url = f"{SPORTYBET_BASE}/factsCenter/popularSportEvents"
    params = {
        "sportId": sport_id,
        "pageSize": limit,
        "pageNum": 1,
    }

    r = requests.get(url, params=params, headers=_headers(), timeout=15)
    r.raise_for_status()
    data = r.json()

    events = (
        data.get("data", {}).get("events")
        or data.get("events", [])
        or []
    )

    games = []
    for ev in events:
        home = ev.get("homeTeamName") or ev.get("home", "?")
        away = ev.get("awayTeamName") or ev.get("away", "?")
        kick_off = ev.get("estimateStartTime") or ev.get("kickOff", "")
        league = ev.get("tournamentName") or ev.get("tournament", "")
        event_id = str(ev.get("eventId") or ev.get("id", ""))

        outcomes = ev.get("markets", [{}])[0].get("outcomes", []) if ev.get("markets") else []
        odds_map = {o.get("desc", ""): float(o.get("odds", 0)) for o in outcomes}

        games.append({
            "event_id": event_id,
            "home": home,
            "away": away,
            "kick_off": kick_off,
            "league": league,
            "sport_id": sport_id,
            "odds": {
                "home": odds_map.get("1") or odds_map.get("Home") or 0,
                "draw": odds_map.get("X") or odds_map.get("Draw") or 0,
                "away": odds_map.get("2") or odds_map.get("Away") or 0,
            },
            "raw": ev,
        })

    return games


# ─────────────────────────────────────────────────────────────────────────────
#  BOOK A BETSLIP  →  RETURN BOOKING CODE
# ─────────────────────────────────────────────────────────────────────────────

def build_betslip(selections: list) -> dict:
    """
    selections: list of dicts with keys:
      event_id, market_id, outcome_id, odds
    Returns the SportyBet booking code string.
    """
    url = f"{SPORTYBET_BASE}/order/share/booking-code"
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

    headers = _headers()
    headers["Content-Type"] = "application/json"

    r = requests.post(url, json=payload, headers=headers, timeout=15)
    r.raise_for_status()
    data = r.json()

    if data.get("bizCode") != 1:
        raise ValueError(f"Booking failed: {data.get('message', 'Unknown error')}")

    code = data.get("data", {}).get("bookingCode") or data.get("data", "")
    return {"booking_code": str(code), "selections": selections}


def extract_market_outcome_ids(raw_event: dict, desired_market: str = "1X2", desired_outcome: str = "1") -> dict:
    """
    Given a raw event dict from SportyBet API, extract market_id and outcome_id
    for the specified market and outcome.
    """
    for market in raw_event.get("markets", []):
        if desired_market.lower() in (market.get("desc") or market.get("marketName", "")).lower():
            for outcome in market.get("outcomes", []):
                desc = outcome.get("desc") or outcome.get("outcomeName", "")
                if desc.strip() == desired_outcome.strip():
                    return {
                        "market_id": str(market.get("id") or market.get("marketId", "")),
                        "outcome_id": str(outcome.get("id") or outcome.get("outcomeId", "")),
                        "odds": float(outcome.get("odds", 0)),
                    }
    return {}


# ─────────────────────────────────────────────────────────────────────────────
#  SEARCH A MATCH BY TEAM NAME
# ─────────────────────────────────────────────────────────────────────────────

def search_match(team_name: str) -> list:
    """Search SportyBet for a match containing the given team name."""
    url = f"{SPORTYBET_BASE}/factsCenter/searchEvents"
    params = {"keyword": team_name, "pageSize": 10, "pageNum": 1}
    r = requests.get(url, params=params, headers=_headers(), timeout=15)
    r.raise_for_status()
    data = r.json()
    return data.get("data", {}).get("events", []) or []
