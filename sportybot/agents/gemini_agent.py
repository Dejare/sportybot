"""
gemini_agent.py  — All AI-powered analysis via Google Gemini
Uses the new google-genai package
"""

import json
import logging
from google import genai
from google.genai import types
from config import GEMINI_API_KEY, GEMINI_MODEL

log = logging.getLogger(__name__)
client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = """
You are SportyBot AI — an elite professional sports betting analyst.
You work exclusively for the user to maximize their chances.

ANALYSIS FRAMEWORK:
- Win probability = 1 / decimal_odds x 100
- SAFE BET: probability > 65%, odds < 1.60
- VALUE BET: probability > 55%, odds > 1.80
- AVOID: odds < 1.20 or odds > 4.0
- For live games: score momentum, cards, corners matter heavily

OUTPUT: Use emojis, rate confidence as HIGH/MEDIUM/LOW, always add risk disclaimer.
Never encourage reckless gambling.
"""

_histories: dict = {}


def _ask(prompt: str) -> str:
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=2048,
            temperature=0.7,
        ),
    )
    return response.text


def analyse_slip(slip: dict) -> str:
    games_text = "\n".join([
        f"{i+1}. {g['home']} vs {g['away']} | {g['league']}\n"
        f"   Market: {g['market']} | Pick: {g['selection']} | Odds: {g['odds']}\n"
        f"   Kick-off: {g['kick_off']}"
        for i, g in enumerate(slip["games"])
    ])
    return _ask(f"""
Booking code: {slip['code']} | Total odds: {slip['total_odds']}
Selections:
{games_text}

1. Review each game - is the pick logical? Win probability?
2. Flag risky selections
3. Highlight strong picks
4. Overall slip quality score (1-10)
5. Suggest improvements
6. Worth placing as-is?
""")


def pick_live_safest(live_games: list, n: int = 5) -> str:
    if not live_games:
        return "No live games found right now. Try again shortly."
    games_text = "\n".join([
        f"{i+1}. {g['home']} {g['score']} {g['away']} | {g['league']} | {g['minute']}' | Odds: 1:{g['odds']['home']} X:{g['odds']['draw']} 2:{g['odds']['away']}"
        for i, g in enumerate(live_games[:40])
    ])
    return _ask(f"""
LIVE games right now:
{games_text}

Pick EXACTLY {n} safest bets. For each: game, recommended bet, confidence, reasoning, odds & implied probability.
Sort safest first. Accumulator or singles?
""")


def predict_upcoming(matches: list, user_request: str = "") -> str:
    if not matches:
        return "No upcoming matches found."
    games_text = "\n".join([
        f"{i+1}. {m['home']} vs {m['away']} | {m['league']} | {m['kick_off']} | Odds: 1:{m['odds']['home']} X:{m['odds']['draw']} 2:{m['odds']['away']}"
        for i, m in enumerate(matches[:20])
    ])
    extra = f"\nUser request: {user_request}" if user_request else ""
    return _ask(f"""
Upcoming matches:
{games_text}
{extra}

For each: predicted outcome with confidence %, reasoning, best market, risk rating.
End with a section called RECOMMENDED BOOKING LIST with your top 5-8 picks.
""")


def decide_booking(matches: list, prediction_text: str) -> list:
    matches_json = json.dumps([{
        "event_id": m["event_id"], "home": m["home"],
        "away": m["away"], "odds": m["odds"],
    } for m in matches], indent=2)

    response = _ask(f"""
Prediction analysis:
{prediction_text}

Available matches:
{matches_json}

Return ONLY a raw JSON array, no markdown, no explanation:
[{{"event_id":"...","home":"...","away":"...","selection":"1","market":"1X2","odds":1.85,"confidence":"HIGH"}}]
""")
    text = response.strip()
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip().rstrip("`")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        log.warning(f"Could not parse booking JSON: {text[:200]}")
        return []


def chat(user_id: int, message: str, context: str = "") -> str:
    if user_id not in _histories:
        _histories[user_id] = []
    full_message = f"{context}\n\n{message}" if context else message
    _histories[user_id].append({"role": "user", "parts": [{"text": full_message}]})
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=_histories[user_id],
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=2048,
            temperature=0.7,
        ),
    )
    reply = response.text
    _histories[user_id].append({"role": "model", "parts": [{"text": reply}]})
    return reply


def clear_session(user_id: int):
    _histories.pop(user_id, None)


def suggest_slip_improvements(slip: dict, live_games: list, upcoming: list) -> str:
    slip_summary = "\n".join([f"- {g['home']} vs {g['away']}: {g['selection']} @ {g['odds']}" for g in slip["games"]])
    live_summary = "\n".join([f"- {g['home']} {g['score']} {g['away']} ({g['minute']}')" for g in live_games[:10]]) or "None"
    upcoming_summary = "\n".join([f"- {m['home']} vs {m['away']} @ {m['kick_off']}" for m in upcoming[:10]]) or "None"
    return _ask(f"""
Existing slip ({slip['code']}), total odds {slip['total_odds']}:
{slip_summary}

Live games: {live_summary}
Upcoming: {upcoming_summary}

Suggest: weak selections to replace, better alternatives, optimised slip, expected new odds.
""")
