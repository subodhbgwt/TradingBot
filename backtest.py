"""
Backtest for the SPY trend-following strategy from TradingTesting.py.

Reuses the exact signal logic (SMA 20/130 + ADX > 25 filter + 2*ATR volatility exit),
simulates a long/flat strategy on daily SPY bars since 2005, and reports the
performance metrics you'd want on a CV: Sharpe, max drawdown, CAGR, trade count,
win rate, and total return vs. buy-and-hold.

Run:
    pip install yfinance pandas numpy matplotlib
    python backtest.py

Output:
    - Prints summary metrics to stdout
    - Saves equity_curve.png (strategy vs. buy-and-hold)
    - Saves trades.csv (every round-trip trade with P&L)
"""

import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt

# --------------------------------------------------------------------------
# CONFIG
# --------------------------------------------------------------------------
TICKER = "SPY"
START = "2005-01-01"
END = None                  # None = today
FAST = 20
SLOW = 130
ADX_THRESHOLD = 25
ATR_MULT = 2.0
RISK_FREE_ANNUAL = 0.02     # 2% annual risk-free rate for Sharpe
TRADING_DAYS = 252

# --------------------------------------------------------------------------
# 1. LOAD DATA
# --------------------------------------------------------------------------
print(f"Downloading {TICKER} daily bars from {START}...")
df = yf.download(TICKER, start=START, end=END, auto_adjust=True, progress=False)
if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)
df = df[["Open", "High", "Low", "Close"]].dropna()
print(f"Loaded {len(df)} bars ({df.index.min().date()} → {df.index.max().date()})")


# --------------------------------------------------------------------------
# 2. SIGNAL LOGIC (identical to TradingTesting.py)
# --------------------------------------------------------------------------
def calculate_strategy(df, fast=FAST, slow=SLOW):
    df = df.copy()
    df["SMA_F"] = df["Close"].rolling(fast).mean()
    df["SMA_S"] = df["Close"].rolling(slow).mean()

    tr = pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - df["Close"].shift(1)).abs(),
            (df["Low"] - df["Close"].shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)
    df["ATR"] = tr.rolling(14).mean()

    plus_dm = df["High"].diff().clip(lower=0)
    minus_dm = (-df["Low"].diff()).clip(lower=0)
    tr_sum = tr.rolling(14).sum()
    di_plus = 100 * (plus_dm.rolling(14).sum() / tr_sum)
    di_minus = 100 * (minus_dm.rolling(14).sum() / tr_sum)
    df["ADX"] = (
        100 * ((di_plus - di_minus).abs() / (di_plus + di_minus)).rolling(14).mean()
    )

    df["Base_Pos"] = np.where(df["SMA_F"] > df["SMA_S"], 1, -1)
    df["Vol_Exit"] = np.where(
        (df["Close"] - df["Close"].shift(1)) < -(df["ATR"] * ATR_MULT), 1, 0
    )
    df["Trend_OK"] = np.where(df["ADX"] > ADX_THRESHOLD, 1, 0)
    df["Final_Pos"] = np.where(
        (df["Vol_Exit"] == 1) | (df["Trend_OK"] == 0), 0, df["Base_Pos"]
    )
    # Only take long positions (matches live bot's buy/flat behaviour)
    df["Final_Pos"] = df["Final_Pos"].clip(lower=0)
    return df


df = calculate_strategy(df).dropna().copy()

# --------------------------------------------------------------------------
# 3. BACKTEST (long/flat, next-bar execution)
# --------------------------------------------------------------------------
df["Ret"] = df["Close"].pct_change()
# shift position by 1 so we trade on the NEXT bar after a signal (no look-ahead)
df["Pos"] = df["Final_Pos"].shift(1).fillna(0)
df["StratRet"] = df["Pos"] * df["Ret"]
df["Equity"] = (1 + df["StratRet"]).cumprod()
df["BuyHold"] = (1 + df["Ret"]).cumprod()

# --------------------------------------------------------------------------
# 4. METRICS
# --------------------------------------------------------------------------
def metrics(equity, returns, label):
    total_return = equity.iloc[-1] - 1
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    cagr = equity.iloc[-1] ** (1 / years) - 1

    excess = returns - RISK_FREE_ANNUAL / TRADING_DAYS
    sharpe = (
        np.sqrt(TRADING_DAYS) * excess.mean() / returns.std()
        if returns.std() > 0
        else np.nan
    )

    running_max = equity.cummax()
    drawdown = equity / running_max - 1
    max_dd = drawdown.min()

    downside = returns[returns < 0].std()
    sortino = (
        np.sqrt(TRADING_DAYS) * excess.mean() / downside if downside > 0 else np.nan
    )

    return {
        "label": label,
        "Total Return": f"{total_return * 100:.1f}%",
        "CAGR": f"{cagr * 100:.2f}%",
        "Sharpe (rf=2%)": f"{sharpe:.2f}",
        "Sortino": f"{sortino:.2f}",
        "Max Drawdown": f"{max_dd * 100:.1f}%",
        "Annualised Vol": f"{returns.std() * np.sqrt(TRADING_DAYS) * 100:.1f}%",
    }


strat = metrics(df["Equity"], df["StratRet"].fillna(0), "Strategy")
bh = metrics(df["BuyHold"], df["Ret"].fillna(0), "Buy & Hold SPY")

# --------------------------------------------------------------------------
# 5. TRADE-LEVEL STATS
# --------------------------------------------------------------------------
pos_change = df["Pos"].diff().fillna(0)
entries = df.index[pos_change > 0]
exits = df.index[pos_change < 0]
# Align: each entry pairs with the next exit
trade_pairs = []
for entry in entries:
    future_exits = exits[exits > entry]
    if len(future_exits) == 0:
        exit_dt = df.index[-1]
    else:
        exit_dt = future_exits[0]
    entry_px = df.loc[entry, "Close"]
    exit_px = df.loc[exit_dt, "Close"]
    pnl_pct = (exit_px / entry_px) - 1
    trade_pairs.append(
        {
            "entry": entry.date(),
            "exit": exit_dt.date(),
            "bars": (exit_dt - entry).days,
            "entry_px": round(float(entry_px), 2),
            "exit_px": round(float(exit_px), 2),
            "pnl_pct": round(float(pnl_pct * 100), 2),
        }
    )

trades_df = pd.DataFrame(trade_pairs)
n_trades = len(trades_df)
win_rate = (trades_df["pnl_pct"] > 0).mean() * 100 if n_trades else 0
avg_win = trades_df.loc[trades_df["pnl_pct"] > 0, "pnl_pct"].mean() if n_trades else 0
avg_loss = trades_df.loc[trades_df["pnl_pct"] <= 0, "pnl_pct"].mean() if n_trades else 0
avg_hold = trades_df["bars"].mean() if n_trades else 0

# --------------------------------------------------------------------------
# 6. REPORT
# --------------------------------------------------------------------------
print("\n" + "=" * 70)
print(f"SPY TREND-FOLLOWING BACKTEST   |   {df.index[0].date()} → {df.index[-1].date()}")
print("=" * 70)


def print_block(m):
    print(f"\n{m['label']}")
    print("-" * len(m["label"]))
    for k, v in m.items():
        if k == "label":
            continue
        print(f"  {k:<18} {v:>10}")


print_block(strat)
print_block(bh)

print("\nTrade statistics")
print("-" * 16)
print(f"  Number of trades   {n_trades:>10}")
print(f"  Win rate           {win_rate:>9.1f}%")
print(f"  Average win        {avg_win:>9.2f}%")
print(f"  Average loss       {avg_loss:>9.2f}%")
print(f"  Avg holding (days) {avg_hold:>10.1f}")

# --------------------------------------------------------------------------
# 7. SAVE OUTPUTS
# --------------------------------------------------------------------------
trades_df.to_csv("trades.csv", index=False)
print("\nSaved trades.csv")

fig, ax = plt.subplots(figsize=(10, 5))
ax.plot(df.index, df["Equity"], label="Strategy", linewidth=1.5)
ax.plot(df.index, df["BuyHold"], label="Buy & Hold SPY", linewidth=1.0, alpha=0.7)
ax.set_yscale("log")
ax.set_title(f"{TICKER} Trend-Following vs. Buy & Hold (log scale)")
ax.set_ylabel("Growth of $1")
ax.legend()
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig("equity_curve.png", dpi=130)
print("Saved equity_curve.png")