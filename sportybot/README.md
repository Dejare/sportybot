# ⚽ SportyBot AI — Full Telegram Betting Agent

A complete, AI-powered Telegram betting agent built with Python, Google Gemini AI, and SportyBet's API.

---

## 🚀 Features

| Feature | Command | Description |
|---|---|---|
| **Resolve Slip** | `/code ABC123` | Decode any SportyBet booking code and display all selections |
| **AI Slip Analysis** | (auto on `/code`) | Gemini AI rates every selection, flags weak picks, gives slip score |
| **Bookie Conversion** | `/convert ABC123 bet9ja` | Convert a SportyBet slip to Bet9ja, BetKing, Betway, etc. |
| **Live Scanner** | `/live` | Fetch all live games + AI picks the 5 safest bets with reasoning |
| **Upcoming Predictions** | `/predict` | AI predictions for upcoming matches with confidence ratings |
| **Auto-Book** | `/book` | AI decides which games to combine → generates SportyBet booking code |
| **Slip Improvement** | `/improve ABC123` | AI suggests better alternatives for weak selections in your slip |
| **Chat Agent** | Free text | Full conversational AI — ask anything about any match |

---

## 📦 Supported Bookmakers (Conversion)

| Bookie | Key |
|---|---|
| Bet9ja | `bet9ja` |
| BetKing | `betking` |
| Betway | `betway` |
| 1xBet | `1xbet` |
| MSport | `msport` |
| Parimatch | `parimatch` |

---

## 🛠️ Setup & Installation

### 1. Clone / Extract project
```bash
cd sportybot
```

### 2. Create virtual environment
```bash
python3 -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
playwright install chromium     # for Playwright (optional, future scraping)
```

### 4. Configure environment
```bash
cp .env.example .env
nano .env                       # Fill in your keys
```

**Required keys:**
- `TELEGRAM_TOKEN` — From [@BotFather](https://t.me/botfather)
- `GEMINI_API_KEY` — From [Google AI Studio](https://aistudio.google.com/)
- `SPORTYBET_COUNTRY` — Your SportyBet country code (ng, gh, ke, tz, za...)

**Optional (for conversion to work via API):**
- `BET9JA_EMAIL` / `BET9JA_PASSWORD`
- `BETKING_EMAIL` / `BETKING_PASSWORD`
- `BETWAY_EMAIL` / `BETWAY_PASSWORD`

### 5. Run the bot
```bash
python main.py
```

---

## 🗂️ Project Structure

```
sportybot/
│
├── main.py                  # Telegram bot — all handlers
├── config.py                # Environment config loader
├── requirements.txt
├── .env.example             # Copy to .env and fill in
│
├── agents/
│   └── gemini_agent.py      # All Gemini AI analysis functions
│
├── scrapers/
│   ├── sportybet.py         # SportyBet API: resolve, live, upcoming, book
│   └── converter.py         # Convert slips to other bookies
│
└── utils/
    └── formatters.py        # Telegram message formatters
```

---

## 💬 Usage Examples

### Resolve and analyse a slip
```
/code XYZA12
```

### Convert to Bet9ja
```
/convert XYZA12 bet9ja
```

### Scan live games
```
/live
```
Bot will show all live games then AI picks 5 safest with reasoning.

### Get predictions
```
/predict
/predict focus on Premier League games only
/predict who has the best value bet today?
```

### Auto-book predictions
Run `/predict` first, then:
```
/book
```
Or click the inline button after `/predict`.

### Improve a slip
```
/improve XYZA12
```

### Just chat
```
Who do you think wins Chelsea vs Arsenal tomorrow?
Is Man City over 2.5 goals a good bet?
What's the safest accumulator I can build today?
```

---

## ⚙️ Country Codes

| Country | Code |
|---|---|
| Nigeria | `ng` |
| Ghana | `gh` |
| Kenya | `ke` |
| Tanzania | `tz` |
| South Africa | `za` |
| Zambia | `zm` |
| Uganda | `ug` |
| Ethiopia | `et` |
| Cameroon | `cm` |
| Senegal | `sn` |

---

## 🚀 Deploy to Production (24/7)

### Option A: Railway (easiest)
1. Push code to GitHub
2. Create new Railway project → connect repo
3. Set environment variables in Railway dashboard
4. Deploy

### Option B: VPS with systemd
```bash
sudo nano /etc/systemd/system/sportybot.service
```
```ini
[Unit]
Description=SportyBot Telegram Agent
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/sportybot
Environment=PATH=/home/ubuntu/sportybot/venv/bin
ExecStart=/home/ubuntu/sportybot/venv/bin/python main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable sportybot
sudo systemctl start sportybot
```

### Option C: Docker
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "main.py"]
```

---

## ⚠️ Important Notes

1. **SportyBet API** — SportyBet doesn't have a documented public API. The endpoints used are reverse-engineered from their mobile app. These may change without notice. If something breaks, inspect SportyBet's network requests in DevTools and update the URLs in `scrapers/sportybet.py`.

2. **Gemini Model** — There is no "Gemini 3" as of early 2026. The bot uses `gemini-2.0-flash` by default (fast, free tier available). Change `GEMINI_MODEL` in `.env` to use other models.

3. **Auto-Booking** — The booking code generation requires correctly resolved `market_id` and `outcome_id` from SportyBet's API. This may not always work due to API changes. The bot falls back to showing manual entry instructions.

4. **Bookie Conversion** — Some bookies (1xBet, MSport, Parimatch) don't expose booking APIs publicly. For these, the bot returns the matched game list and instructs manual entry. Bet9ja, BetKing, and Betway have more accessible APIs.

---

## ⚠️ Disclaimer

> This software is for **educational and entertainment purposes only**.
> Sports betting involves significant financial risk.
> Never bet money you cannot afford to lose.
> The authors take no responsibility for financial losses.
> If you have a gambling problem, please seek professional help.
