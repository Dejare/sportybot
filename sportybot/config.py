import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")

# Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL   = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# SportyBet
SPORTYBET_COUNTRY  = os.getenv("SPORTYBET_COUNTRY", "ng").lower()
SPORTYBET_EMAIL    = os.getenv("SPORTYBET_EMAIL", "")
SPORTYBET_PASSWORD = os.getenv("SPORTYBET_PASSWORD", "")

# Other bookies credentials
BOOKIE_CREDENTIALS = {
    "1xbet":    {"email": os.getenv("ONEXBET_API_KEY", "")},
    "bet9ja":   {"email": os.getenv("BET9JA_EMAIL", ""),    "password": os.getenv("BET9JA_PASSWORD", "")},
    "betway":   {"email": os.getenv("BETWAY_EMAIL", ""),    "password": os.getenv("BETWAY_PASSWORD", "")},
    "betking":  {"email": os.getenv("BETKING_EMAIL", ""),   "password": os.getenv("BETKING_PASSWORD", "")},
    "parimatch":{"email": os.getenv("PARIMATCH_EMAIL", ""), "password": os.getenv("PARIMATCH_PASSWORD", "")},
}

# Bot settings
MAX_LIVE_PICKS     = int(os.getenv("MAX_LIVE_PICKS", 5))
MAX_PREDICTION_GAMES = int(os.getenv("MAX_PREDICTION_GAMES", 10))
DEFAULT_BOOKIE     = os.getenv("DEFAULT_BOOKIE", "sportybet")
LOG_LEVEL          = os.getenv("LOG_LEVEL", "INFO")

# SportyBet base URLs per country
SPORTYBET_URLS = {
    "ng": "https://www.sportybet.com/api/ng",
    "gh": "https://www.sportybet.com/api/gh",
    "ke": "https://www.sportybet.com/api/ke",
    "tz": "https://www.sportybet.com/api/tz",
    "za": "https://www.sportybet.com/api/za",
    "zm": "https://www.sportybet.com/api/zm",
    "ug": "https://www.sportybet.com/api/ug",
    "et": "https://www.sportybet.com/api/et",
    "cm": "https://www.sportybet.com/api/cm",
    "sn": "https://www.sportybet.com/api/sn",
}

SPORTYBET_BASE = SPORTYBET_URLS.get(SPORTYBET_COUNTRY, SPORTYBET_URLS["ng"])
