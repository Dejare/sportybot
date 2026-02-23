"""
gemini_agent.py  — All AI-powered analysis via Google Gemini
Features:
  • Analyse a booking code slip
  • Scan live games → pick 5 safest bets
  • Predict upcoming matches
  • Decide which games to book from predictions
  • Full conversational agent with memory
"""

import json
import logging
import google.generativeai as genai
from config import GEMINI_API_KEY, GEMINI_MODEL

log = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)

# ─────────────────────────────────────────────────────────────────────────────
#  SHARED SYSTEM PROMPT
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """
You are SportyBot AI — an elite professional sports betting analyst and agent.
You work exclusively for the user who has hired you to maximize their chances.

Your core capabilities:
1. SLIP ANALYSIS — Review booking codes and evaluate each selection critically.
2. LIVE SCANNER — Scan live games and identify the 5 safest high-value bets using:
   - Current score momentum
   - In-game odds movements (value bets)
   - Statistical patterns (BTTS, over/under, clean sheets)
   - Odds that imply >65% win probability
3. PREDICTOR — Predict upcoming matches with confidence scores.
4. BOOKER — From predictions, decide which games to combine into a betslip and generate a booking code.
5. CONVERTER — Help users understand how to place their slip on other bookmakers.

ANALYSIS FRAMEWORK (always apply):
- Win probability = 1 / decimal_odds × 100
- SAFE BET: probability > 65%, odds < 1.60
- VALUE BET: probability > 55%, odds > 1.80 (bookies underestimate)
- AVOID: odds < 1.20 (too risky for parlays), odds > 4.0 (low probability)
- For live games: score momentum, cards, corner dominance matter heavily

OUTPUT FORMAT:
- Always use emojis for readability (⚽ 🟢 🔴 📊 💰 ⚠️)
- Rate confidence: 🔥 HIGH (>75%) | ✅ MEDIUM (60-75%) | ⚠️ LOW (<60%)
- Always end with a risk disclaimer

PERSONALITY:
- Confident but honest about uncertainty
- Data-driven, not emotional
- You ALWAYS remind users betting carries risk
- Never encourage reckless gambling
"""


def _model():
    return genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=SYSTEM_PROMPT,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  1.  ANALYSE A RESOLVED SLIP
# ─────────────────────────────────────────────────────────────────────────────

def analyse_slip(slip: dict) -> str:
    """Analyse a resolved SportyBet booking code slip."""
    games_text = "\n".join([
        f"{i+1}. {g['home']} vs {g['away']} | {g['league']}\n"
        f"   Market: {g['market']} | Pick: {g['selection']} | Odds: {g['odds']}\n"
        f"   Kick-off: {g['kick_off']}"
        for i, g in enumerate(slip["games"])
    ])

    prompt = f"""
A user shared their SportyBet booking code: {slip['code']}
Total combined odds: {slip['total_odds']}

Here are the selections in their slip:
{games_text}

Please:
1. Review each game individually — is the pick logical? What's the win probability?
2. Flag any risky or questionable selections 🔴
3. Highlight strong picks 🟢
4. Give an overall slip quality score (1-10)
5. Suggest any changes to improve the slip
6. Tell them if this slip is worth placing as-is
"""
    response = _model().generate_content(prompt)
    return response.text


# ─────────────────────────────────────────────────────────────────────────────
#  2.  LIVE GAME SCANNER — PICK 5 SAFEST BETS
# ─────────────────────────────────────────────────────────────────────────────

def pick_live_safest(live_games: list, n: int = 5) -> str:
    """From a list of live games, AI picks the n safest bets."""
    if not live_games:
        return "⚠️ No live games found right now. Try again shortly."

    games_text = "\n".join([
        f"{i+1}. {g['home']} {g['score']} {g['away']} | {g['league']}\n"
        f"   ⏱ {g['minute']}' | Odds → 1:{g['odds']['home']} X:{g['odds']['draw']} 2:{g['odds']['away']}"
        for i, g in enumerate(live_games[:40])  # limit context
    ])

    prompt = f"""
Currently LIVE games right now:
{games_text}

Your task:
1. Analyse all live games above
2. Select EXACTLY {n} safest bets with the HIGHEST WIN PROBABILITY
3. For each pick, tell me:
   a) The game and current score
   b) Your recommended bet (e.g. "Back Home Win", "Over 0.5 goals", "BTTS Yes", etc.)
   c) Your confidence level and reasoning
   d) The current odds and implied probability
4. Sort from SAFEST to least safe
5. Then suggest: should these be combined into one accumulator, or placed as singles?

Be specific and data-driven. Consider score momentum — a team winning 2-0 at 70' is a different beast than 1-0 at 15'.
"""
    response = _model().generate_content(prompt)
    return response.text


# ─────────────────────────────────────────────────────────────────────────────
#  3.  PREDICTIONS FOR UPCOMING MATCHES
# ─────────────────────────────────────────────────────────────────────────────

def predict_upcoming(matches: list, user_request: str = "") -> str:
    """AI predictions for upcoming matches."""
    if not matches:
        return "⚠️ No upcoming matches found."

    games_text = "\n".join([
        f"{i+1}. {m['home']} vs {m['away']} | {m['league']}\n"
        f"   🕐 {m['kick_off']} | Odds → 1:{m['odds']['home']} X:{m['odds']['draw']} 2:{m['odds']['away']}"
        for i, m in enumerate(matches[:20])
    ])

    extra = f"\nUser's specific request: {user_request}" if user_request else ""

    prompt = f"""
Upcoming matches:
{games_text}
{extra}

For each match, provide:
1. Predicted outcome with confidence %
2. Key reasoning (form, H2H if known, home advantage, odds value)
3. Best market to bet (1X2, BTTS, Over/Under, Double Chance, etc.)
4. Risk rating: 🔥 HIGH CONFIDENCE | ✅ MEDIUM | ⚠️ RISKY

At the end, list your TOP PICKS (best 5-8) that you'd recommend for a combined booking code.
Format the top picks section clearly with a heading "📋 RECOMMENDED BOOKING LIST" so I can auto-book them.
"""
    response = _model().generate_content(prompt)
    return response.text


# ─────────────────────────────────────────────────────────────────────────────
#  4.  DECIDE WHICH GAMES TO BOOK FROM PREDICTIONS
# ─────────────────────────────────────────────────────────────────────────────

def decide_booking(matches: list, prediction_text: str) -> list:
    """
    Given the AI's prediction text and available matches with event IDs,
    extract which games should be booked and with what selection.
    Returns structured list for booking.
    """
    matches_json = json.dumps([{
        "event_id": m["event_id"],
        "home": m["home"],
        "away": m["away"],
        "odds": m["odds"],
    } for m in matches], indent=2)

    prompt = f"""
Based on this prediction analysis:
---
{prediction_text}
---

And these available matches with their event IDs:
{matches_json}

Extract the recommended booking selections and return ONLY a valid JSON array like this:
[
  {{
    "event_id": "...",
    "home": "...",
    "away": "...",
    "selection": "1",   // "1"=home, "X"=draw, "2"=away, "Over 2.5", "BTTS Yes", etc.
    "market": "1X2",    // or "Goals Over/Under", "Both Teams to Score", etc.
    "odds": 1.85,
    "confidence": "HIGH"
  }}
]

Return ONLY the JSON array. No explanation. No markdown. Just the raw JSON.
"""
    response = _model().generate_content(prompt)
    text = response.text.strip()

    # Clean up any accidental markdown
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip().rstrip("```")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        log.warning(f"Could not parse booking JSON: {text[:200]}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
#  5.  CONVERSATIONAL AGENT  (multi-turn chat)
# ─────────────────────────────────────────────────────────────────────────────

# Store per-user chat sessions
_sessions: dict[int, any] = {}

def get_chat_session(user_id: int):
    if user_id not in _sessions:
        _sessions[user_id] = _model().start_chat(history=[])
    return _sessions[user_id]

def clear_session(user_id: int):
    _sessions.pop(user_id, None)

def chat(user_id: int, message: str, context: str = "") -> str:
    """
    Send a message to the conversational agent with optional context injection.
    context: extra data to prepend (e.g. live games, slip data, etc.)
    """
    session = get_chat_session(user_id)
    full_message = f"{context}\n\n{message}" if context else message
    response = session.send_message(full_message)
    return response.text


# ─────────────────────────────────────────────────────────────────────────────
#  6.  SLIP IMPROVEMENT SUGGESTION
# ─────────────────────────────────────────────────────────────────────────────

def suggest_slip_improvements(slip: dict, live_games: list, upcoming: list) -> str:
    """Suggest how to improve or replace a given slip."""
    slip_summary = "\n".join([
        f"- {g['home']} vs {g['away']}: {g['selection']} @ {g['odds']}"
        for g in slip["games"]
    ])
    live_summary = "\n".join([
        f"- {g['home']} {g['score']} {g['away']} ({g['minute']}')"
        for g in live_games[:10]
    ]) or "None available"
    upcoming_summary = "\n".join([
        f"- {m['home']} vs {m['away']} @ {m['kick_off']}"
        for m in upcoming[:10]
    ]) or "None available"

    prompt = f"""
The user has this existing slip (code: {slip['code']}):
{slip_summary}
Total odds: {slip['total_odds']}

Available live games right now:
{live_summary}

Upcoming matches:
{upcoming_summary}

Suggest:
1. Which selections in their existing slip are weak — and what to replace them with
2. Any live or upcoming games that are better alternatives
3. An optimised version of this slip with better risk/reward
4. The expected combined odds after your improvements
"""
    response = _model().generate_content(prompt)
    return response.text
