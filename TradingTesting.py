import os
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

load_dotenv()

# --- settings ---
TICKER = "SPY"
QTY = 1
LIVE_MODE = True  # not wired up yet, client below is always paper
ALPACA_KEY = os.environ["ALPACA_KEY"]
ALPACA_SECRET = os.environ["ALPACA_SECRET"]
LOG_FILE = "trading_log.txt"

# --- signals ---
def calculate_strategy(df, fast=20, slow=130):
    if len(df) < slow: return df
    df['SMA_F'] = df['Close'].rolling(fast).mean()
    df['SMA_S'] = df['Close'].rolling(slow).mean()
    
    tr = pd.concat([df['High']-df['Low'], 
                    abs(df['High']-df['Close'].shift(1)), 
                    abs(df['Low']-df['Close'].shift(1))], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(14).mean()
    
    plus_dm = df['High'].diff().clip(lower=0)
    minus_dm = (-df['Low'].diff()).clip(lower=0)
    tr_sum = tr.rolling(14).sum()
    di_plus = 100 * (plus_dm.rolling(14).sum() / tr_sum)
    di_minus = 100 * (minus_dm.rolling(14).sum() / tr_sum)
    df['ADX'] = 100 * (abs(di_plus - di_minus) / (di_plus + di_minus)).rolling(14).mean()
    
    df['Base_Pos'] = np.where(df['SMA_F'] > df['SMA_S'], 1, -1)
    df['Vol_Exit'] = np.where((df['Close'] - df['Close'].shift(1)) < -(df['ATR'] * 2.0), 1, 0)
    df['Trend_OK'] = np.where(df['ADX'] > 25, 1, 0)
    df['Final_Pos'] = np.where((df['Vol_Exit'] == 1) | (df['Trend_OK'] == 0), 0, df['Base_Pos'])
    return df

# --- orders and logging ---
def get_daily_pnl(trading_client):
    """Dollar change in account equity since yesterday's close."""
    account = trading_client.get_account()
    # last_equity = equity at the previous close
    daily_pnl = float(account.equity) - float(account.last_equity)
    return daily_pnl

def log_trade(action, price, adx, sma_f, sma_s):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {action} | Price: ${price:.2f} | ADX: {adx:.1f} | SMA_F: {sma_f:.2f} | SMA_S: {sma_s:.2f}\n"
    with open(LOG_FILE, "a") as f:
        f.write(log_entry)

def execute_trade(trading_client, signal, last_row):
    try:
        try:
            position = trading_client.get_open_position(TICKER)
            current_qty = float(position.qty)
        except Exception:  # no open position
            current_qty = 0

        if signal == 1 and current_qty == 0:
            order_data = MarketOrderRequest(symbol=TICKER, qty=QTY, side=OrderSide.BUY, time_in_force=TimeInForce.GTC)
            trading_client.submit_order(order_data)
            log_trade("BUY", last_row['Close'], last_row['ADX'], last_row['SMA_F'], last_row['SMA_S'])
            print(f">>> EXECUTED: BUY {QTY} {TICKER}")

        elif signal <= 0 and current_qty > 0:
            trading_client.close_position(TICKER)
            log_trade("SELL", last_row['Close'], last_row['ADX'], last_row['SMA_F'], last_row['SMA_S'])
            print(f">>> EXECUTED: SELL {TICKER}")

    except Exception as e:
        print(f"Trade Execution Error: {e}")

def run_live():
    trading_client = TradingClient(ALPACA_KEY, ALPACA_SECRET, paper=True)
    data_client = StockHistoricalDataClient(ALPACA_KEY, ALPACA_SECRET)
    print(f"--- BOT ACTIVE: Monitoring {TICKER} with Daily PnL ---")
    
    while True:
        try:
            start_dt = datetime.now() - timedelta(days=5)
            request_params = StockBarsRequest(symbol_or_symbols=TICKER, timeframe=TimeFrame.Minute, start=start_dt, limit=300)
            bars_response = data_client.get_stock_bars(request_params)
            df_raw = bars_response.df
            
            df_flat = df_raw.reset_index()
            df_flat.columns = [str(c).lower() for c in df_flat.columns]
            clean_df = pd.DataFrame()
            clean_df['Open'] = df_flat['open']; clean_df['High'] = df_flat['high']
            clean_df['Low'] = df_flat['low']; clean_df['Close'] = df_flat['close']
            
            final_df = calculate_strategy(clean_df)
            last_row = final_df.iloc[-1]
            signal = int(last_row['Final_Pos'])
            
            clock = trading_client.get_clock()
            if clock.is_open:
                execute_trade(trading_client, signal, last_row)
            
            # status line
            pnl = get_daily_pnl(trading_client)
            now_str = datetime.now().strftime('%H:%M:%S')
            pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
            
            print(f"\n[{now_str}] Price: ${last_row['Close']:.2f} | ADX: {last_row['ADX']:.1f}")
            print(f"Daily PnL: {pnl_str} | Market: {'OPEN' if clock.is_open else 'CLOSED'}")
            
            time.sleep(60) 

        except Exception as e:
            print(f"Loop Error: {e}"); time.sleep(10)

if __name__ == "__main__":
    run_live()