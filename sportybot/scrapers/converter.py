"""
converter.py  — Convert a SportyBet slip to other bookmakers
Supported targets: bet9ja | betway | betking | 1xbet | parimatch | msport
"""

import logging
from typing import Optional
import requests
from fake_useragent import UserAgent
from tenacity import retry, stop_after_attempt, wait_exponential

log = logging.getLogger(__name__)
ua = UserAgent()

# ─────────────────────────────────────────────────────────────────────────────
# Each bookie has a unique search + booking flow.
# We match games by team name since event IDs differ across platforms.
# ─────────────────────────────────────────────────────────────────────────────

BOOKIE_CONFIGS = {
    "bet9ja": {
        "name": "Bet9ja",
        "search_url": "https://sport.bet9ja.com/bet9jaapi/api/GetEventsByKeyword",
        "booking_url": "https://sport.bet9ja.com/bet9jaapi/api/ShareBetCode",
        "flag": "🇳🇬",
        "country": "Nigeria",
    },
    "betway": {
        "name": "Betway",
        "search_url": "https://sports.betway.com.ng/api/event/getSearchResult",
        "booking_url": "https://sports.betway.com.ng/api/betslip/share",
        "flag": "🌍",
        "country": "Multi",
    },
    "betking": {
        "name": "BetKing",
        "search_url": "https://www.betking.com/api/v1/sports/search",
        "booking_url": "https://www.betking.com/api/v1/sports/booking-codes",
        "flag": "🇳🇬",
        "country": "Nigeria",
    },
    "1xbet": {
        "name": "1xBet",
        "search_url": "https://1xbet.com/LineFeed/GetGamesZip",
        "booking_url": "https://1xbet.com/en/allgameresults",
        "flag": "🌐",
        "country": "Multi",
    },
    "msport": {
        "name": "MSport",
        "search_url": "https://www.msport.com/api/v1/eventList",
        "booking_url": "https://www.msport.com/api/v1/share/betCode",
        "flag": "🇳🇬",
        "country": "Nigeria",
    },
    "parimatch": {
        "name": "Parimatch",
        "search_url": "https://www.parimatch.com/api/bet/search",
        "booking_url": "https://www.parimatch.com/api/bet/share",
        "flag": "🌍",
        "country": "Multi",
    },
}


def _headers(referer: str = "") -> dict:
    return {
        "User-Agent": ua.random,
        "Accept": "application/json, */*",
        "Referer": referer,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  BET9JA
# ─────────────────────────────────────────────────────────────────────────────

def _search_bet9ja(home: str, away: str) -> Optional[dict]:
    try:
        r = requests.get(
            BOOKIE_CONFIGS["bet9ja"]["search_url"],
            params={"keyword": home, "pagesize": 5},
            headers=_headers("https://sport.bet9ja.com/"),
            timeout=10,
        )
        events = r.json().get("data", {}).get("events", [])
        for ev in events:
            if away.lower() in (ev.get("AwayTeam") or "").lower():
                return ev
    except Exception as e:
        log.warning(f"Bet9ja search error: {e}")
    return None


def _book_bet9ja(selections: list) -> str:
    try:
        payload = {"events": selections}
        r = requests.post(
            BOOKIE_CONFIGS["bet9ja"]["booking_url"],
            json=payload,
            headers={**_headers("https://sport.bet9ja.com/"), "Content-Type": "application/json"},
            timeout=12,
        )
        return r.json().get("data", {}).get("code", "UNAVAILABLE")
    except Exception as e:
        log.warning(f"Bet9ja booking error: {e}")
        return "UNAVAILABLE"


# ─────────────────────────────────────────────────────────────────────────────
#  BETKING
# ─────────────────────────────────────────────────────────────────────────────

def _search_betking(home: str, away: str) -> Optional[dict]:
    try:
        r = requests.get(
            BOOKIE_CONFIGS["betking"]["search_url"],
            params={"query": home},
            headers=_headers("https://www.betking.com/"),
            timeout=10,
        )
        for ev in r.json().get("data", []):
            if away.lower() in (ev.get("away_team") or "").lower():
                return ev
    except Exception as e:
        log.warning(f"BetKing search error: {e}")
    return None


def _book_betking(selections: list) -> str:
    try:
        r = requests.post(
            BOOKIE_CONFIGS["betking"]["booking_url"],
            json={"selections": selections},
            headers={**_headers("https://www.betking.com/"), "Content-Type": "application/json"},
            timeout=12,
        )
        return r.json().get("data", {}).get("booking_code", "UNAVAILABLE")
    except Exception as e:
        log.warning(f"BetKing booking error: {e}")
        return "UNAVAILABLE"


# ─────────────────────────────────────────────────────────────────────────────
#  BETWAY
# ─────────────────────────────────────────────────────────────────────────────

def _search_betway(home: str, away: str) -> Optional[dict]:
    try:
        r = requests.get(
            BOOKIE_CONFIGS["betway"]["search_url"],
            params={"search": f"{home} {away}"},
            headers=_headers("https://sports.betway.com.ng/"),
            timeout=10,
        )
        events = r.json().get("events", [])
        for ev in events:
            if home.lower() in (ev.get("homeTeam") or "").lower():
                return ev
    except Exception as e:
        log.warning(f"Betway search error: {e}")
    return None


def _book_betway(selections: list) -> str:
    try:
        r = requests.post(
            BOOKIE_CONFIGS["betway"]["booking_url"],
            json={"selections": selections},
            headers={**_headers("https://sports.betway.com.ng/"), "Content-Type": "application/json"},
            timeout=12,
        )
        return r.json().get("shareCode", "UNAVAILABLE")
    except Exception as e:
        log.warning(f"Betway booking error: {e}")
        return "UNAVAILABLE"


# ─────────────────────────────────────────────────────────────────────────────
#  MASTER CONVERTER
# ─────────────────────────────────────────────────────────────────────────────

def convert_slip(games: list, target_bookie: str) -> dict:
    """
    Convert a list of SportyBet games to a target bookie booking code.

    games: list of game dicts from sportybet.resolve_booking_code()
    target_bookie: "bet9ja" | "betway" | "betking" | "1xbet" | "msport"

    Returns:
    {
      "bookie": str,
      "booking_code": str,
      "matched": int,   # games successfully found on target bookie
      "total": int,
      "failed": [list of games not found],
      "selections": [list],
    }
    """
    target = target_bookie.lower().replace(" ", "")
    config = BOOKIE_CONFIGS.get(target)

    if not config:
        return {
            "error": f"Bookie '{target_bookie}' is not supported yet.",
            "supported": list(BOOKIE_CONFIGS.keys()),
        }

    matched = []
    failed = []
    selections = []

    for game in games:
        home = game["home"]
        away = game["away"]
        selection = game["selection"]   # "1", "X", "2", "Over 2.5", etc.

        found = None
        if target == "bet9ja":
            found = _search_bet9ja(home, away)
        elif target == "betking":
            found = _search_betking(home, away)
        elif target == "betway":
            found = _search_betway(home, away)
        else:
            # For unsupported direct API bookies, we still return match info
            found = {"_manual": True}

        if found and not found.get("_manual"):
            matched.append(game)
            selections.append({
                "event_id": found.get("Id") or found.get("id") or found.get("event_id"),
                "market": game["market"],
                "selection": selection,
                "odds": game["odds"],
            })
        elif found and found.get("_manual"):
            # Manual conversion — user needs to add themselves
            matched.append(game)
            selections.append({
                "home": home,
                "away": away,
                "market": game["market"],
                "selection": selection,
                "odds": game["odds"],
                "note": "Manually add to betslip",
            })
        else:
            failed.append(game)

    # Book if we have a real booking API
    booking_code = "N/A"
    if target == "bet9ja" and selections:
        booking_code = _book_bet9ja(selections)
    elif target == "betking" and selections:
        booking_code = _book_betking(selections)
    elif target == "betway" and selections:
        booking_code = _book_betway(selections)
    else:
        booking_code = "MANUAL_ENTRY_REQUIRED"

    return {
        "bookie": config["name"],
        "flag": config["flag"],
        "booking_code": booking_code,
        "matched": len(matched),
        "total": len(games),
        "failed": failed,
        "selections": selections,
    }


def list_supported_bookies() -> str:
    lines = ["📚 *Supported Bookmakers:*\n"]
    for key, cfg in BOOKIE_CONFIGS.items():
        lines.append(f"{cfg['flag']} *{cfg['name']}* (`{key}`) — {cfg['country']}")
    return "\n".join(lines)
