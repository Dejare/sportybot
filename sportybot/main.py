"""
main.py  — SportyBot Telegram Agent
Full-featured betting agent with:
  /start         — Welcome & help
  /code <CODE>   — Resolve + analyse a SportyBet booking code
  /convert <CODE> <BOOKIE> — Convert slip to another bookmaker
  /live          — Show live games + AI picks 5 safest bets
  /predict       — AI predictions for upcoming matches
  /book          — Auto-book AI predictions → generate SportyBet code
  /improve <CODE>— Improve an existing slip with AI suggestions
  /bookies       — List supported bookmakers
  /reset         — Clear AI conversation memory
  Free text      — Full conversational AI agent
"""

import asyncio
import logging
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters,
)
from telegram.constants import ParseMode, ChatAction

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

# Store last predictions per user for /book command
_last_predictions: dict[int, dict] = {}


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

async def typing(update: Update):
    await update.effective_chat.send_action(ChatAction.TYPING)

async def send(update: Update, text: str, reply_markup=None):
    """Send markdown message, splitting if too long."""
    MAX = 4000
    chunks = [text[i:i+MAX] for i in range(0, len(text), MAX)]
    for i, chunk in enumerate(chunks):
        await update.effective_message.reply_text(
            chunk,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup if i == len(chunks)-1 else None,
            disable_web_page_preview=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
#  /start
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        "🔁 `/reset` — Clear AI memory & start fresh\n\n"
        "*💬 Or just chat with me!*\n"
        "Ask anything: _\"Who's likely to win Man United vs Arsenal?\"_\n\n"
        "⚠️ _Always gamble responsibly._"
    )
    await send(update, welcome)


# ─────────────────────────────────────────────────────────────────────────────
#  /code <BOOKING_CODE>  — Resolve + AI analyse slip
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await send(update, "Usage: `/code YOUR_BOOKING_CODE`\nExample: `/code ABC123`")
        return

    code = args[0].strip().upper()
    await typing(update)
    await send(update, f"🔍 Resolving booking code `{code}`...")

    try:
        slip = resolve_booking_code(code)
    except Exception as e:
        await send(update, f"❌ Could not resolve code `{code}`\n\nError: `{e}`\n\nMake sure the code is valid and your country is set correctly in `.env`")
        return

    # Show slip
    await send(update, format_slip(slip))

    # AI analysis
    await typing(update)
    await send(update, "🤖 *AI is analysing your slip...*")
    analysis = analyse_slip(slip)
    await send(update, f"📊 *AI Analysis:*\n\n{analysis}{format_disclaimer()}")

    # Offer to convert
    keyboard = [
        [
            InlineKeyboardButton("🔄 Convert to Bet9ja", callback_data=f"convert:{code}:bet9ja"),
            InlineKeyboardButton("🔄 Convert to BetKing", callback_data=f"convert:{code}:betking"),
        ],
        [
            InlineKeyboardButton("🔄 Convert to Betway", callback_data=f"convert:{code}:betway"),
            InlineKeyboardButton("🔧 Improve This Slip", callback_data=f"improve:{code}"),
        ],
    ]
    await send(update, "What would you like to do with this slip?", reply_markup=InlineKeyboardMarkup(keyboard))


# ─────────────────────────────────────────────────────────────────────────────
#  /convert <CODE> <BOOKIE>
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_convert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await send(update, "Usage: `/convert BOOKING_CODE BOOKIE`\nExample: `/convert ABC123 bet9ja`\n\nUse /bookies to see all supported bookmakers.")
        return

    code, target = args[0].upper(), args[1].lower()
    await typing(update)
    await send(update, f"🔍 Fetching slip `{code}` and converting to *{target}*...")

    try:
        slip = resolve_booking_code(code)
    except Exception as e:
        await send(update, f"❌ Could not resolve `{code}`: `{e}`")
        return

    result = convert_slip(slip["games"], target)
    await send(update, format_conversion_result(result))


# ─────────────────────────────────────────────────────────────────────────────
#  /live  — Fetch live games + AI picks 5 safest
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await typing(update)
    await send(update, "🔴 *Fetching all live games...*")

    try:
        games = get_live_games(sport_id=1, limit=50)  # Football
    except Exception as e:
        await send(update, f"❌ Failed to fetch live games: `{e}`")
        return

    if not games:
        await send(update, "😔 No live games found right now. Try again in a few minutes.")
        return

    # Show live game summary
    await send(update, format_live_games(games))

    # AI picks 5 safest
    await typing(update)
    await send(update, f"🤖 *AI is scanning {len(games)} live games for the 5 safest bets...*")
    picks = pick_live_safest(games, n=config.MAX_LIVE_PICKS)
    await send(update, f"🎯 *AI Live Picks:*\n\n{picks}{format_disclaimer()}")

    # Store for booking
    user_id = update.effective_user.id
    _last_predictions[user_id] = {"games": games, "type": "live"}

    keyboard = [[InlineKeyboardButton("📦 Auto-Book These Picks on SportyBet", callback_data="book_live")]]
    await send(update, "Want me to book these picks and get a SportyBet code?", reply_markup=InlineKeyboardMarkup(keyboard))


# ─────────────────────────────────────────────────────────────────────────────
#  /predict  — AI predictions for upcoming
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_predict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_request = " ".join(context.args) if context.args else ""
    await typing(update)
    await send(update, "📡 *Fetching upcoming matches...*")

    try:
        matches = get_upcoming_matches(sport_id=1, limit=30)
    except Exception as e:
        await send(update, f"❌ Could not fetch matches: `{e}`")
        return

    if not matches:
        await send(update, "No upcoming matches found right now.")
        return

    await typing(update)
    await send(update, f"🤖 *AI is predicting {len(matches)} upcoming matches...*")
    prediction = predict_upcoming(matches, user_request)
    await send(update, f"📊 *AI Predictions:*\n\n{prediction}{format_disclaimer()}")

    # Store for /book
    user_id = update.effective_user.id
    _last_predictions[user_id] = {"matches": matches, "prediction": prediction, "type": "upcoming"}

    keyboard = [[InlineKeyboardButton("📦 Book Recommended Games → Get Code", callback_data="book_predictions")]]
    await send(update, "Want me to auto-book the recommended games and generate a SportyBet booking code?", reply_markup=InlineKeyboardMarkup(keyboard))


# ─────────────────────────────────────────────────────────────────────────────
#  /book  — Book AI predictions
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_book(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = _last_predictions.get(user_id)

    if not data:
        await send(update, "⚠️ No recent predictions found. Run `/predict` or `/live` first, then use `/book`.")
        return

    await _do_booking(update, data)


async def _do_booking(update: Update, data: dict):
    """Internal: book selected games and return SportyBet code."""
    await typing(update)
    await send(update, "🤖 *AI is deciding which games to book...*")

    matches = data.get("matches") or data.get("games", [])
    prediction = data.get("prediction", "Pick the best available games.")

    selected = decide_booking(matches, prediction)

    if not selected:
        await send(update, "⚠️ AI couldn't extract specific selections for booking. Try `/predict` again and I'll pick cleaner games.")
        return

    await send(update, f"✅ *AI selected {len(selected)} games to book:*\n\n" + "\n".join([
        f"• {s.get('home','?')} vs {s.get('away','?')} → *{s.get('selection','?')}* @ `{s.get('odds',0)}`"
        for s in selected
    ]))

    await typing(update)
    await send(update, "📦 *Generating SportyBet booking code...*")

    # Build betslip selections with market/outcome IDs
    slip_selections = []
    for s in selected:
        # Find matching raw event
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
        # Fallback: show manual entry if API IDs not found
        await send(update, format_booked_slip("MANUAL_ENTRY", selected))
        await send(update,
            "⚠️ *Auto-booking via API failed* (event IDs not resolved).\n"
            "Please add these selections manually on SportyBet.\n\n"
            "_Tip: Make sure your .env SPORTYBET\\_COUNTRY is set correctly._"
        )
        return

    try:
        result = build_betslip(slip_selections)
        await send(update, format_booked_slip(result["booking_code"], selected))
    except Exception as e:
        await send(update,
            f"⚠️ Booking API returned an error: `{e}`\n\n"
            "Here are your selections to add manually:\n\n" +
            "\n".join([
                f"• {s.get('home','?')} vs {s.get('away','?')} → *{s.get('selection')}* on {s.get('market')}"
                for s in selected
            ])
        )


# ─────────────────────────────────────────────────────────────────────────────
#  /improve <CODE>
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_improve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await send(update, "Usage: `/improve YOUR_BOOKING_CODE`")
        return

    code = args[0].upper()
    await typing(update)
    await send(update, f"🔍 Loading slip `{code}`...")

    try:
        slip = resolve_booking_code(code)
        live = get_live_games(limit=20)
        upcoming = get_upcoming_matches(limit=20)
    except Exception as e:
        await send(update, f"❌ Error: `{e}`")
        return

    await typing(update)
    await send(update, "🤖 *AI is finding ways to improve your slip...*")
    suggestion = suggest_slip_improvements(slip, live, upcoming)
    await send(update, f"🔧 *Improvement Suggestions:*\n\n{suggestion}{format_disclaimer()}")


# ─────────────────────────────────────────────────────────────────────────────
#  /bookies
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_bookies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send(update, list_supported_bookies())


# ─────────────────────────────────────────────────────────────────────────────
#  /reset
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    clear_session(user_id)
    _last_predictions.pop(user_id, None)
    await send(update, "🔁 *Memory cleared!* Starting fresh. How can I help you?")


# ─────────────────────────────────────────────────────────────────────────────
#  INLINE BUTTON CALLBACKS
# ─────────────────────────────────────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    if data.startswith("convert:"):
        _, code, target = data.split(":")
        await typing(update)
        try:
            slip = resolve_booking_code(code)
            result = convert_slip(slip["games"], target)
            await send(update, format_conversion_result(result))
        except Exception as e:
            await send(update, f"❌ Conversion failed: `{e}`")

    elif data.startswith("improve:"):
        code = data.split(":")[1]
        context.args = [code]
        await cmd_improve(update, context)

    elif data in ("book_predictions", "book_live"):
        pred_data = _last_predictions.get(user_id)
        if pred_data:
            await _do_booking(update, pred_data)
        else:
            await send(update, "⚠️ Session expired. Please run `/predict` or `/live` again.")


# ─────────────────────────────────────────────────────────────────────────────
#  FREE-TEXT CONVERSATIONAL HANDLER
# ─────────────────────────────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.effective_user.id

    # Auto-detect booking codes (all-caps alphanumeric, 4-8 chars)
    code_match = re.match(r"^([A-Z0-9]{4,10})$", text.upper())
    if code_match:
        context.args = [code_match.group(1)]
        await cmd_code(update, context)
        return

    # Detect intent keywords
    lower = text.lower()
    if any(k in lower for k in ["live game", "live now", "playing now", "live match"]):
        await cmd_live(update, context)
        return
    if any(k in lower for k in ["predict", "upcoming", "who will win", "best bet today"]):
        context.args = text.split()
        await cmd_predict(update, context)
        return
    if any(k in lower for k in ["book my", "generate code", "booking code", "book these"]):
        await cmd_book(update, context)
        return

    # General conversational AI
    await typing(update)
    # Inject live context if relevant
    context_data = ""
    if any(k in lower for k in ["odds", "game", "match", "bet", "win"]):
        try:
            live = get_live_games(limit=10)
            if live:
                context_data = "Current live games for context:\n" + "\n".join([
                    f"{g['home']} {g['score']} {g['away']} ({g['minute']}')"
                    for g in live[:5]
                ])
        except Exception:
            pass

    response = chat(user_id, text, context=context_data)
    await send(update, response + format_disclaimer())


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    if not config.TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN is not set in .env")
    if not config.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set in .env")

    app = ApplicationBuilder().token(config.TELEGRAM_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("help",    cmd_start))
    app.add_handler(CommandHandler("code",    cmd_code))
    app.add_handler(CommandHandler("convert", cmd_convert))
    app.add_handler(CommandHandler("live",    cmd_live))
    app.add_handler(CommandHandler("predict", cmd_predict))
    app.add_handler(CommandHandler("book",    cmd_book))
    app.add_handler(CommandHandler("improve", cmd_improve))
    app.add_handler(CommandHandler("bookies", cmd_bookies))
    app.add_handler(CommandHandler("reset",   cmd_reset))

    # Inline buttons
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Free text
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    log.info("🤖 SportyBot is running...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
