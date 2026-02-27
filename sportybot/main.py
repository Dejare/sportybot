"""
main.py — SportyBot Telegram Agent
Uses pyTelegramBotAPI (telebot) instead of python-telegram-bot
Compatible with google-genai and httpx 0.28+
"""

import logging
import re
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

import config
from scrapers.sportybet import (
    resolve_booking_code, get_live_games, get_upcoming_matches,
    build_betslip, extract_market_outcome_ids,
)
from scrapers.converter import convert_slip, list_supported_bookies
from agents.gemini_agent import (
    analyse_slip, pick_live_safest, predict_upcoming,
    decide_booking, chat, clear_session, suggest_slip_improvements,
)
from utils.formatters import (
    format_slip, format_live_games, format_upcoming,
    format_conversion_result, format_booked_slip, format_disclaimer,
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=getattr(logging, config.LOG_LEVEL),
)
log = logging.getLogger(__name__)

bot = telebot.TeleBot(config.TELEGRAM_TOKEN, parse_mode="MARKDOWN")

# Store last predictions per user
_last_predictions: dict = {}


def send(chat_id, text, reply_markup=None):
    """Send markdown message, splitting if too long."""
    MAX = 4000
    chunks = [text[i:i+MAX] for i in range(0, len(text), MAX)]
    for i, chunk in enumerate(chunks):
        try:
            bot.send_message(
                chat_id,
                chunk,
                parse_mode="Markdown",
                reply_markup=reply_markup if i == len(chunks) - 1 else None,
                disable_web_page_preview=True,
            )
        except Exception as e:
            # fallback without markdown if it fails
            try:
                bot.send_message(chat_id, chunk, reply_markup=reply_markup if i == len(chunks) - 1 else None)
            except Exception as e2:
                log.error(f"Send failed: {e2}")


# ─────────────────────────────────────────────────────────────────────────────
#  /start
# ─────────────────────────────────────────────────────────────────────────────

@bot.message_handler(commands=["start", "help"])
def cmd_start(message):
    welcome = (
        "⚽ *Welcome to SportyBot AI* 🤖\n"
        "Your personal AI-powered betting analyst\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "*📋 Commands:*\n\n"
        "🎫 `/code ABC123` — Analyse a SportyBet booking code\n"
        "🔄 `/convert ABC123 bet9ja` — Convert slip to another bookie\n"
        "🔴 `/live` — Show live games + 5 safest AI picks\n"
        "📊 `/predict` — AI predictions for upcoming matches\n"
        "📦 `/book` — Auto-book AI predictions → get booking code\n"
        "🔧 `/improve ABC123` — Improve your existing slip with AI\n"
        "📚 `/bookies` — List supported bookmakers\n"
        "🔁 `/reset` — Clear AI memory and start fresh\n\n"
        "*💬 Or just chat with me!*\n"
        "_Ask anything: Who wins Man United vs Arsenal?_\n\n"
        "⚠️ _Always gamble responsibly._"
    )
    send(message.chat.id, welcome)


# ─────────────────────────────────────────────────────────────────────────────
#  /code
# ─────────────────────────────────────────────────────────────────────────────

@bot.message_handler(commands=["code"])
def cmd_code(message):
    parts = message.text.split()
    if len(parts) < 2:
        send(message.chat.id, "Usage: `/code YOUR_BOOKING_CODE`\nExample: `/code ABC123`")
        return

    code = parts[1].strip().upper()
    send(message.chat.id, f"🔍 Resolving booking code `{code}`...")

    try:
        slip = resolve_booking_code(code)
    except Exception as e:
        send(message.chat.id, f"❌ Could not resolve code `{code}`\nError: `{e}`\nCheck the code is valid and your country in `.env` is correct.")
        return

    send(message.chat.id, format_slip(slip))
    send(message.chat.id, "🤖 *AI is analysing your slip...*")

    try:
        analysis = analyse_slip(slip)
        send(message.chat.id, f"📊 *AI Analysis:*\n\n{analysis}{format_disclaimer()}")
    except Exception as e:
        send(message.chat.id, f"⚠️ AI analysis failed: `{e}`")

    # Inline buttons
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("🔄 → Bet9ja", callback_data=f"convert:{code}:bet9ja"),
        InlineKeyboardButton("🔄 → BetKing", callback_data=f"convert:{code}:betking"),
    )
    markup.row(
        InlineKeyboardButton("🔄 → Betway", callback_data=f"convert:{code}:betway"),
        InlineKeyboardButton("🔧 Improve Slip", callback_data=f"improve:{code}"),
    )
    send(message.chat.id, "What would you like to do with this slip?", reply_markup=markup)


# ─────────────────────────────────────────────────────────────────────────────
#  /convert
# ─────────────────────────────────────────────────────────────────────────────

@bot.message_handler(commands=["convert"])
def cmd_convert(message):
    parts = message.text.split()
    if len(parts) < 3:
        send(message.chat.id, "Usage: `/convert BOOKING_CODE BOOKIE`\nExample: `/convert ABC123 bet9ja`\n\nUse /bookies to see all supported bookmakers.")
        return

    code, target = parts[1].upper(), parts[2].lower()
    send(message.chat.id, f"🔍 Fetching slip `{code}` and converting to *{target}*...")

    try:
        slip = resolve_booking_code(code)
    except Exception as e:
        send(message.chat.id, f"❌ Could not resolve `{code}`: `{e}`")
        return

    result = convert_slip(slip["games"], target)
    send(message.chat.id, format_conversion_result(result))


# ─────────────────────────────────────────────────────────────────────────────
#  /live
# ─────────────────────────────────────────────────────────────────────────────

@bot.message_handler(commands=["live"])
def cmd_live(message):
    send(message.chat.id, "🔴 *Fetching all live games...*")

    try:
        games = get_live_games(sport_id=1, limit=50)
    except Exception as e:
        send(message.chat.id, f"❌ Failed to fetch live games: `{e}`")
        return

    if not games:
        send(message.chat.id, "😔 No live games found right now. Try again in a few minutes.")
        return

    send(message.chat.id, format_live_games(games))
    send(message.chat.id, f"🤖 *AI is scanning {len(games)} live games for the 5 safest bets...*")

    try:
        picks = pick_live_safest(games, n=config.MAX_LIVE_PICKS)
        send(message.chat.id, f"🎯 *AI Live Picks:*\n\n{picks}{format_disclaimer()}")
    except Exception as e:
        send(message.chat.id, f"⚠️ AI analysis failed: `{e}`")
        return

    user_id = message.from_user.id
    _last_predictions[user_id] = {"games": games, "type": "live"}

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📦 Auto-Book These Picks on SportyBet", callback_data="book_live"))
    send(message.chat.id, "Want me to book these picks and get a SportyBet code?", reply_markup=markup)


# ─────────────────────────────────────────────────────────────────────────────
#  /predict
# ─────────────────────────────────────────────────────────────────────────────

@bot.message_handler(commands=["predict"])
def cmd_predict(message):
    parts = message.text.split(maxsplit=1)
    user_request = parts[1] if len(parts) > 1 else ""

    send(message.chat.id, "📡 *Fetching upcoming matches...*")

    try:
        matches = get_upcoming_matches(sport_id=1, limit=30)
    except Exception as e:
        send(message.chat.id, f"❌ Could not fetch matches: `{e}`")
        return

    if not matches:
        send(message.chat.id, "No upcoming matches found right now.")
        return

    send(message.chat.id, f"🤖 *AI is predicting {len(matches)} upcoming matches...*")

    try:
        prediction = predict_upcoming(matches, user_request)
        send(message.chat.id, f"📊 *AI Predictions:*\n\n{prediction}{format_disclaimer()}")
    except Exception as e:
        send(message.chat.id, f"⚠️ AI prediction failed: `{e}`")
        return

    user_id = message.from_user.id
    _last_predictions[user_id] = {"matches": matches, "prediction": prediction, "type": "upcoming"}

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📦 Book Recommended Games → Get Code", callback_data="book_predictions"))
    send(message.chat.id, "Want me to auto-book the recommended games?", reply_markup=markup)


# ─────────────────────────────────────────────────────────────────────────────
#  /book
# ─────────────────────────────────────────────────────────────────────────────

@bot.message_handler(commands=["book"])
def cmd_book(message):
    user_id = message.from_user.id
    data = _last_predictions.get(user_id)
    if not data:
        send(message.chat.id, "⚠️ No recent predictions found. Run `/predict` or `/live` first.")
        return
    do_booking(message.chat.id, user_id, data)


def do_booking(chat_id, user_id, data):
    send(chat_id, "🤖 *AI is deciding which games to book...*")

    matches = data.get("matches") or data.get("games", [])
    prediction = data.get("prediction", "Pick the best available games.")

    try:
        selected = decide_booking(matches, prediction)
    except Exception as e:
        send(chat_id, f"⚠️ AI booking decision failed: `{e}`")
        return

    if not selected:
        send(chat_id, "⚠️ AI couldn't extract selections. Try `/predict` again.")
        return

    send(chat_id, f"✅ *AI selected {len(selected)} games:*\n\n" + "\n".join([
        f"• {s.get('home','?')} vs {s.get('away','?')} → *{s.get('selection','?')}* @ `{s.get('odds',0)}`"
        for s in selected
    ]))

    send(chat_id, "📦 *Generating SportyBet booking code...*")

    slip_selections = []
    for s in selected:
        match = next((m for m in matches if str(m.get("event_id")) == str(s.get("event_id"))), None)
        if match and match.get("raw"):
            ids = extract_market_outcome_ids(
                match["raw"],
                desired_market=s.get("market", "1X2"),
                desired_outcome=s.get("selection", "1"),
            )
            if ids:
                slip_selections.append({
                    "event_id": s["event_id"],
                    "market_id": ids["market_id"],
                    "outcome_id": ids["outcome_id"],
                    "odds": ids["odds"],
                })

    if not slip_selections:
        send(chat_id, format_booked_slip("MANUAL_ENTRY", selected))
        send(chat_id,
            "⚠️ *Auto-booking via API failed* — event IDs not resolved.\n"
            "Please add these selections manually on SportyBet."
        )
        return

    try:
        result = build_betslip(slip_selections)
        send(chat_id, format_booked_slip(result["booking_code"], selected))
    except Exception as e:
        send(chat_id,
            f"⚠️ Booking API error: `{e}`\n\nAdd these manually:\n\n" +
            "\n".join([f"• {s.get('home','?')} vs {s.get('away','?')} → *{s.get('selection')}*" for s in selected])
        )


# ─────────────────────────────────────────────────────────────────────────────
#  /improve
# ─────────────────────────────────────────────────────────────────────────────

@bot.message_handler(commands=["improve"])
def cmd_improve(message):
    parts = message.text.split()
    if len(parts) < 2:
        send(message.chat.id, "Usage: `/improve YOUR_BOOKING_CODE`")
        return

    code = parts[1].upper()
    send(message.chat.id, f"🔍 Loading slip `{code}`...")

    try:
        slip = resolve_booking_code(code)
        live = get_live_games(limit=20)
        upcoming = get_upcoming_matches(limit=20)
    except Exception as e:
        send(message.chat.id, f"❌ Error: `{e}`")
        return

    send(message.chat.id, "🤖 *AI is finding ways to improve your slip...*")
    try:
        suggestion = suggest_slip_improvements(slip, live, upcoming)
        send(message.chat.id, f"🔧 *Improvement Suggestions:*\n\n{suggestion}{format_disclaimer()}")
    except Exception as e:
        send(message.chat.id, f"⚠️ AI failed: `{e}`")


# ─────────────────────────────────────────────────────────────────────────────
#  /bookies  /reset
# ─────────────────────────────────────────────────────────────────────────────

@bot.message_handler(commands=["bookies"])
def cmd_bookies(message):
    send(message.chat.id, list_supported_bookies())


@bot.message_handler(commands=["reset"])
def cmd_reset(message):
    user_id = message.from_user.id
    clear_session(user_id)
    _last_predictions.pop(user_id, None)
    send(message.chat.id, "🔁 *Memory cleared!* Starting fresh. How can I help you?")


# ─────────────────────────────────────────────────────────────────────────────
#  INLINE BUTTON CALLBACKS
# ─────────────────────────────────────────────────────────────────────────────

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    bot.answer_callback_query(call.id)
    data = call.data
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if data.startswith("convert:"):
        _, code, target = data.split(":")
        try:
            slip = resolve_booking_code(code)
            result = convert_slip(slip["games"], target)
            send(chat_id, format_conversion_result(result))
        except Exception as e:
            send(chat_id, f"❌ Conversion failed: `{e}`")

    elif data.startswith("improve:"):
        code = data.split(":")[1]
        try:
            slip = resolve_booking_code(code)
            live = get_live_games(limit=20)
            upcoming = get_upcoming_matches(limit=20)
            suggestion = suggest_slip_improvements(slip, live, upcoming)
            send(chat_id, f"🔧 *Improvement Suggestions:*\n\n{suggestion}{format_disclaimer()}")
        except Exception as e:
            send(chat_id, f"❌ Error: `{e}`")

    elif data in ("book_predictions", "book_live"):
        pred_data = _last_predictions.get(user_id)
        if pred_data:
            do_booking(chat_id, user_id, pred_data)
        else:
            send(chat_id, "⚠️ Session expired. Please run `/predict` or `/live` again.")


# ─────────────────────────────────────────────────────────────────────────────
#  FREE TEXT HANDLER
# ─────────────────────────────────────────────────────────────────────────────

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    text = message.text.strip()
    user_id = message.from_user.id
    chat_id = message.chat.id

    # Auto-detect booking codes (must be 5-10 chars, alphanumeric, contain at least one digit)
    upper = text.upper()
    if (re.match(r"^[A-Z0-9]{5,10}$", upper)
            and text.isalnum()
            and any(c.isdigit() for c in text)):
        message.text = f"/code {text}"
        cmd_code(message)
        return

    lower = text.lower()
    if any(k in lower for k in ["live game", "live now", "playing now", "live match"]):
        cmd_live(message)
        return
    if any(k in lower for k in ["predict", "upcoming", "who will win", "best bet today"]):
        cmd_predict(message)
        return
    if any(k in lower for k in ["book my", "generate code", "booking code", "book these"]):
        cmd_book(message)
        return

    # General AI chat
    context_data = ""
    try:
        if any(k in lower for k in ["odds", "game", "match", "bet", "win"]):
            live = get_live_games(limit=10)
            if live:
                context_data = "Current live games:\n" + "\n".join([
                    f"{g['home']} {g['score']} {g['away']} ({g['minute']}')"
                    for g in live[:5]
                ])
    except Exception:
        pass

    try:
        response = chat(user_id, text, context=context_data)
        send(chat_id, response + format_disclaimer())
    except Exception as e:
        send(chat_id, f"⚠️ AI error: `{e}`")


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    if not config.TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN is not set in .env")
    if not config.OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY is not set in .env")

    log.info("🤖 SportyBot is running...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)


if __name__ == "__main__":
    main()
