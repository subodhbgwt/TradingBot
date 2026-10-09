# TradingBot

Trend-following bot for SPY. It goes long when the 20-period SMA is above the 130-period SMA, only trades when ADX is above 25, and gets out early if price drops more than 2x ATR in one bar. Orders go through Alpaca's paper-trading API.

## Strategy

| Indicator | What it does |
|---|---|
| SMA 20 / 130 | Long when the fast average is above the slow one |
| ADX > 25 | Only trade when there's a clear trend |
| 2 x ATR | Exit on a large down move |

The live bot (`TradingTesting.py`) pulls the latest minute bars every 60 seconds and places a market order when the signal changes. It's long or flat, never short.

## Backtest

`backtest.py` runs the same signal logic on daily SPY bars from 2005. Positions are taken on the bar after the signal, so there's no look-ahead.

The committed `trades.csv` and `equity_curve.png` are from a run on data up to April 2026:

| | Strategy | Buy and hold |
|---|---|---|
| Annualised volatility | 9.5% | 19.2% |
| Max drawdown | -27% | -55% |
| Sharpe (rf 2%) | 0.43 | |
| Trades | 138 | |

It roughly halves volatility and drawdown compared with holding SPY, but the total return is lower. Re-running it gives slightly different numbers as new data comes in.

## Running it

```bash
pip install -r requirements.txt
cp .env.example .env       # add your Alpaca paper-trading keys
python backtest.py         # writes trades.csv and equity_curve.png
python TradingTesting.py   # live paper trading
```

Paper-trading keys are free: https://app.alpaca.markets/signup

While running, the bot prints a status line every minute:

```
[14:32:10] Price: $527.43 | ADX: 31.2
Daily PnL: +$12.50 | Market: OPEN
```

## Settings

At the top of `TradingTesting.py`:

| Variable | Default | Meaning |
|---|---|---|
| `TICKER` | `"SPY"` | Symbol to trade |
| `QTY` | `1` | Shares per trade |
| `LIVE_MODE` | `True` | Not used yet, the client is hardcoded to `paper=True` |

## Files

```
TradingTesting.py   live bot: signals and order execution
backtest.py         backtest with metrics and a trade log
trades.csv          trades from the last backtest run
equity_curve.png    strategy vs. buy and hold
.env.example        template for the API keys
```
