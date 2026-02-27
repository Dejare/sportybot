"""
utils/formatters.py  — Telegram message formatters
"""

from datetime import datetime


def format_slip(slip: dict) -> str:
    """Format a resolved slip for Telegram display."""
    lines = [
        f"🎫 *Booking Code:* `{slip['code']}`",
        f"🎯 *Total Odds:* `{slip['total_odds']}`",
        f"📋 *Selections ({len(slip['games'])} games):*\n",
    ]
    for i, g in enumerate(slip["games"], 1):
        lines.append(
            f"*{i}.* {g['home']} vs {g['away']}\n"
            f"   🏆 {g['league']}\n"
            f"   📊 {g['market']} → *{g['selection']}* @ `{g['odds']}`\n"
            f"   🕐 {g['kick_off']}\n"
        )
    return "\n".join(lines)


def format_live_games(games: list) -> str:
    """Format live games list for Telegram."""
    if not games:
        return "⚽ No live games found right now."
    lines = [f"🔴 *{len(games)} Live Games Right Now:*\n"]
    for i, g in enumerate(games[:20], 1):
        home_odds = g['odds'].get('home', 0)
        draw_odds = g['odds'].get('draw', 0)
        away_odds = g['odds'].get('away', 0)
        lines.append(
            f"*{i}.* {g['home']} `{g.get('score', '0-0')}` {g['away']}\n"
            f"   ⏱ `{g.get('minute', '?')}'` | {g.get('league', '')}\n"
            f"   💰 1:`{home_odds}` X:`{draw_odds}` 2:`{away_odds}`\n"
        )
    return "\n".join(lines)


def format_upcoming(matches: list) -> str:
    """Format upcoming matches for Telegram."""
    if not matches:
        return "📅 No upcoming matches found."
    lines = [f"📅 *Upcoming Matches ({len(matches)} games):*\n"]
    for i, m in enumerate(matches[:15], 1):
        lines.append(
            f"*{i}.* {m['home']} vs {m['away']}\n"
            f"   🏆 {m['league']} | 🕐 {m['kick_off']}\n"
            f"   💰 1:`{m['odds']['home']}` X:`{m['odds']['draw']}` 2:`{m['odds']['away']}`\n"
        )
    return "\n".join(lines)


def format_conversion_result(result: dict) -> str:
    """Format a bookie conversion result."""
    if "error" in result:
        return (
            f"❌ *Conversion Error*\n{result['error']}\n\n"
            f"Supported bookies: {', '.join(result.get('supported', []))}"
        )

    lines = [
        f"{result['flag']} *{result['bookie']} Booking Code*\n",
        f"🎫 Code: `{result['booking_code']}`",
        f"✅ Matched: {result['matched']}/{result['total']} games\n",
    ]

    if result["failed"]:
        lines.append("⚠️ *Games not found on this bookie:*")
        for g in result["failed"]:
            lines.append(f"  • {g['home']} vs {g['away']}")
        lines.append("\n_Add these manually to your betslip._")

    if result["booking_code"] == "MANUAL_ENTRY_REQUIRED":
        lines.append(
            "\n📝 *Manual Entry Required*\n"
            "This bookie doesn't support auto-booking via API.\n"
            "Copy the selections below and add them manually:\n"
        )
        for i, s in enumerate(result["selections"], 1):
            lines.append(
                f"*{i}.* {s.get('home','?')} vs {s.get('away','?')}\n"
                f"   Pick: *{s['selection']}* on {s['market']}"
            )

    return "\n".join(lines)


def format_booked_slip(booking_code: str, selections: list) -> str:
    """Format a newly booked SportyBet slip."""
    lines = [
        "🎉 *SportyBet Booking Code Generated!*\n",
        f"🎫 *Code:* `{booking_code}`\n",
        f"📋 *Games in slip ({len(selections)}):*\n",
    ]
    total_odds = 1.0
    for i, s in enumerate(selections, 1):
        odds = s.get("odds", 0)
        total_odds *= odds
        lines.append(
            f"*{i}.* {s.get('home','?')} vs {s.get('away','?')}\n"
            f"   📊 {s.get('market','?')} → *{s.get('selection','?')}* @ `{odds}`\n"
            f"   🎯 Confidence: {s.get('confidence','?')}\n"
        )
    lines.append(f"\n💰 *Total Combined Odds:* `{round(total_odds, 2)}`")
    lines.append("\n⚠️ _Always bet responsibly. Never stake more than you can afford to lose._")
    return "\n".join(lines)


def format_disclaimer() -> str:
    return (
        "\n\n━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ *Disclaimer:* SportyBot AI provides analysis and predictions for entertainment purposes. "
        "Sports betting involves significant financial risk. Never bet money you cannot afford to lose. "
        "If you feel you may have a gambling problem, please seek help."
    )
