# FinanceBrah 📈

A live algorithmic trading bot for **SPY** that uses a trend-following strategy built on SMA crossovers, ADX filtering, and ATR-based volatility exits. Trades are executed through the [Alpaca](https://alpaca.markets/) paper-trading API.

## Strategy

| Indicator | Role |
|---|---|
| **SMA 20 / 130** | Trend direction (fast crosses above slow → long) |
| **ADX > 25** | Only trade when there's a real trend |
| **ATR × 2** | Emergency exit on large adverse moves |

The bot polls every 60 seconds, checks the latest minute bars, computes signals, and executes market orders when the conditions line up.

## Quick Start

### 1. Clone & install

```bash
git clone https://github.com/<your-username>/TradingBot.git
cd TradingBot
pip install -r requirements.txt
```

### 2. Add your Alpaca keys

Copy the example env file and fill in your credentials:

```bash
cp .env.example .env
```

Then edit `.env`:

```
ALPACA_KEY=your_alpaca_api_key_here
ALPACA_SECRET=your_alpaca_secret_key_here
```

> You can get free paper-trading keys at [https://app.alpaca.markets/signup](https://app.alpaca.markets/signup).

### 3. Run

```bash
python financebrah.py
```

The bot will start polling and print a diagnostic pulse every minute:

```
--- BOT ACTIVE: Monitoring SPY with Daily PnL ---
[14:32:10] Price: $527.43 | ADX: 31.2
Daily PnL: +$12.50 | Market: OPEN
```

## Configuration

Edit the constants at the top of `financebrah.py`:

| Variable | Default | Description |
|---|---|---|
| `TICKER` | `"SPY"` | Symbol to trade |
| `QTY` | `1` | Number of shares per trade |
| `LIVE_MODE` | `False` | Currently unused — Alpaca `paper=True` is hardcoded |

## Project Structure

```
financialllm/
├── financebrah.py      # Main bot: strategy + execution loop
├── requirements.txt    # Python dependencies
├── .env                # Your API keys (git-ignored)
├── .env.example        # Template for .env
└── .gitignore
```
