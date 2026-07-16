#!/usr/bin/env python3.12
"""
Superagent Trader — Backtesting Framework
Test trading strategies against historical data.

Usage:
    python backtesting.py EURUSD D --strategy ema_cross --period 365
    python backtesting.py GBPJPY H4 --strategy rsi_ob --period 60
    python backtesting.py XAUUSD D --strategy macd_cross --period 365

Strategies:
    ema_cross   - EMA 21/55 crossover
    rsi_ob      - RSI overbought/oversold reversals
    macd_cross  - MACD line/signal crossover
    bb_bounce   - Bollinger Band bounce
"""
import sys, argparse, json
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta


PAIR_MAP = {
    "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X",
    "USDCHF": "USDCHF=X", "AUDUSD": "AUDUSD=X", "NZDUSD": "NZDUSD=X",
    "USDCAD": "USDCAD=X", "GBPJPY": "GBPJPY=X", "EURJPY": "EURJPY=X",
    "EURGBP": "EURGBP=X", "XAUUSD": "GC=F",
}


def calc_ema(s, p): return s.ewm(span=p, adjust=False).mean()
def calc_sma(s, p): return s.rolling(window=p).mean()
def calc_rsi(s, p=14):
    d = s.diff(); g = d.where(d>0,0.0); l = -d.where(d<0,0.0)
    ag = g.ewm(alpha=1/p, min_periods=p).mean()
    al = l.ewm(alpha=1/p, min_periods=p).mean()
    return 100 - (100/(1+ag/al))
def calc_macd(s, f=12, sl=26, sg=9):
    m = calc_ema(s,f) - calc_ema(s,sl); sig = calc_ema(m,sg)
    return m, sig, m-sig
def calc_bb(s, p=20, d=2):
    sm = calc_sma(s,p); st = s.rolling(p).std()
    return sm+st*d, sm, sm-st*d
def calc_atr(df, p=14):
    hl = df["High"]-df["Low"]
    hc = (df["High"]-df["Close"].shift()).abs()
    lc = (df["Low"]-df["Close"].shift()).abs()
    tr = pd.concat([hl,hc,lc],axis=1).max(axis=1)
    return tr.rolling(p).mean()


class Trade:
    def __init__(self, direction, entry_price, sl, tp, entry_idx, entry_date):
        self.direction = direction
        self.entry_price = entry_price
        self.sl = sl
        self.tp = tp
        self.entry_idx = entry_idx
        self.entry_date = entry_date
        self.exit_price = None
        self.exit_idx = None
        self.exit_date = None
        self.pnl_pips = 0
        self.result = None  # "WIN", "LOSS", "BE"


def strategy_ema_cross(df: pd.DataFrame, rr: float = 2.0) -> list:
    """EMA 21/55 crossover strategy."""
    close = df["Close"]
    ema21 = calc_ema(close, 21)
    ema55 = calc_ema(close, 55)
    atr = calc_atr(df)
    trades = []
    
    for i in range(56, len(df)-1):
        if np.isnan(atr.iloc[i]): continue
        # Bullish cross
        if ema21.iloc[i-1] < ema55.iloc[i-1] and ema21.iloc[i] > ema55.iloc[i]:
            sl = close.iloc[i] - 1.5 * atr.iloc[i]
            tp = close.iloc[i] + 1.5 * atr.iloc[i] * rr
            trades.append(Trade("BUY", close.iloc[i], sl, tp, i, df.index[i]))
        # Bearish cross
        elif ema21.iloc[i-1] > ema55.iloc[i-1] and ema21.iloc[i] < ema55.iloc[i]:
            sl = close.iloc[i] + 1.5 * atr.iloc[i]
            tp = close.iloc[i] - 1.5 * atr.iloc[i] * rr
            trades.append(Trade("SELL", close.iloc[i], sl, tp, i, df.index[i]))
    
    return trades


def strategy_rsi_ob(df: pd.DataFrame, rr: float = 2.0) -> list:
    """RSI overbought/oversold reversal strategy."""
    close = df["Close"]
    rsi = calc_rsi(close, 14)
    atr = calc_atr(df)
    trades = []
    
    for i in range(15, len(df)-1):
        if np.isnan(atr.iloc[i]) or np.isnan(rsi.iloc[i]): continue
        # RSI crosses above 30 (exit oversold)
        if rsi.iloc[i-1] < 30 and rsi.iloc[i] > 30:
            sl = close.iloc[i] - 1.5 * atr.iloc[i]
            tp = close.iloc[i] + 1.5 * atr.iloc[i] * rr
            trades.append(Trade("BUY", close.iloc[i], sl, tp, i, df.index[i]))
        # RSI crosses below 70 (exit overbought)
        elif rsi.iloc[i-1] > 70 and rsi.iloc[i] < 70:
            sl = close.iloc[i] + 1.5 * atr.iloc[i]
            tp = close.iloc[i] - 1.5 * atr.iloc[i] * rr
            trades.append(Trade("SELL", close.iloc[i], sl, tp, i, df.index[i]))
    
    return trades


def strategy_macd_cross(df: pd.DataFrame, rr: float = 2.0) -> list:
    """MACD line/signal crossover strategy."""
    close = df["Close"]
    macd_line, signal_line, histogram = calc_macd(close)
    atr = calc_atr(df)
    trades = []
    
    for i in range(27, len(df)-1):
        if np.isnan(atr.iloc[i]): continue
        # Bullish MACD cross
        if histogram.iloc[i-1] < 0 and histogram.iloc[i] > 0:
            sl = close.iloc[i] - 1.5 * atr.iloc[i]
            tp = close.iloc[i] + 1.5 * atr.iloc[i] * rr
            trades.append(Trade("BUY", close.iloc[i], sl, tp, i, df.index[i]))
        # Bearish MACD cross
        elif histogram.iloc[i-1] > 0 and histogram.iloc[i] < 0:
            sl = close.iloc[i] + 1.5 * atr.iloc[i]
            tp = close.iloc[i] - 1.5 * atr.iloc[i] * rr
            trades.append(Trade("SELL", close.iloc[i], sl, tp, i, df.index[i]))
    
    return trades


def strategy_bb_bounce(df: pd.DataFrame, rr: float = 2.0) -> list:
    """Bollinger Band bounce strategy."""
    close = df["Close"]
    bb_upper, bb_mid, bb_lower = calc_bb(close)
    atr = calc_atr(df)
    trades = []
    
    for i in range(21, len(df)-1):
        if np.isnan(atr.iloc[i]): continue
        # Price touches lower BB and bounces
        if df["Low"].iloc[i] <= bb_lower.iloc[i] and close.iloc[i] > bb_lower.iloc[i]:
            sl = close.iloc[i] - 1.5 * atr.iloc[i]
            tp = close.iloc[i] + 1.5 * atr.iloc[i] * rr
            trades.append(Trade("BUY", close.iloc[i], sl, tp, i, df.index[i]))
        # Price touches upper BB and bounces
        elif df["High"].iloc[i] >= bb_upper.iloc[i] and close.iloc[i] < bb_upper.iloc[i]:
            sl = close.iloc[i] + 1.5 * atr.iloc[i]
            tp = close.iloc[i] - 1.5 * atr.iloc[i] * rr
            trades.append(Trade("SELL", close.iloc[i], sl, tp, i, df.index[i]))
    
    return trades


STRATEGIES = {
    "ema_cross": strategy_ema_cross,
    "rsi_ob": strategy_rsi_ob,
    "macd_cross": strategy_macd_cross,
    "bb_bounce": strategy_bb_bounce,
}


def simulate_trades(df: pd.DataFrame, trades: list) -> list:
    """Simulate trades against price data to determine outcomes."""
    for trade in trades:
        for j in range(trade.entry_idx + 1, len(df)):
            high = df["High"].iloc[j]
            low = df["Low"].iloc[j]
            
            if trade.direction == "BUY":
                if low <= trade.sl:
                    trade.exit_price = trade.sl
                    trade.result = "LOSS"
                    trade.pnl_pips = (trade.sl - trade.entry_price)
                elif high >= trade.tp:
                    trade.exit_price = trade.tp
                    trade.result = "WIN"
                    trade.pnl_pips = (trade.tp - trade.entry_price)
                else:
                    continue
            else:  # SELL
                if high >= trade.sl:
                    trade.exit_price = trade.sl
                    trade.result = "LOSS"
                    trade.pnl_pips = (trade.entry_price - trade.sl)
                elif low <= trade.tp:
                    trade.exit_price = trade.tp
                    trade.result = "WIN"
                    trade.pnl_pips = (trade.entry_price - trade.tp)
                else:
                    continue
            
            trade.exit_idx = j
            trade.exit_date = df.index[j]
            break
        
        # Trade still open
        if trade.result is None:
            trade.exit_price = df["Close"].iloc[-1]
            if trade.direction == "BUY":
                trade.pnl_pips = trade.exit_price - trade.entry_price
            else:
                trade.pnl_pips = trade.entry_price - trade.exit_price
            trade.result = "OPEN"
            trade.exit_idx = len(df) - 1
            trade.exit_date = df.index[-1]
    
    return trades


def backtest(pair: str, timeframe: str, strategy_name: str, period_days: int = 365, rr: float = 2.0) -> dict:
    symbol = PAIR_MAP.get(pair.upper(), f"{pair.upper()}=X")
    
    # Determine interval and period
    if timeframe.upper() in ["D", "W"]:
        interval = "1d" if timeframe.upper() == "D" else "1wk"
        pd_period = f"{period_days}d"
    else:
        interval = "1h"
        pd_period = f"{min(period_days, 729)}d"
    
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=pd_period, interval=interval)
    
    if df.empty:
        return {"error": f"No data for {pair}"}
    
    if timeframe.upper() == "H4":
        df = df.resample("4h").agg({
            "Open": "first", "High": "max", "Low": "min",
            "Close": "last", "Volume": "sum"
        }).dropna()
    
    strategy_fn = STRATEGIES.get(strategy_name)
    if not strategy_fn:
        return {"error": f"Unknown strategy: {strategy_name}. Available: {list(STRATEGIES.keys())}"}
    
    # Generate and simulate trades
    trades = strategy_fn(df, rr=rr)
    trades = simulate_trades(df, trades)
    
    # Calculate statistics
    closed = [t for t in trades if t.result in ["WIN", "LOSS"]]
    wins = [t for t in closed if t.result == "WIN"]
    losses = [t for t in closed if t.result == "LOSS"]
    
    total = len(closed)
    win_count = len(wins)
    loss_count = len(losses)
    win_rate = (win_count / total * 100) if total > 0 else 0
    
    total_pnl = sum(t.pnl_pips for t in closed)
    avg_win = np.mean([t.pnl_pips for t in wins]) if wins else 0
    avg_loss = np.mean([abs(t.pnl_pips) for t in losses]) if losses else 0
    
    profit_factor = (sum(t.pnl_pips for t in wins) / abs(sum(t.pnl_pips for t in losses))) if losses and sum(t.pnl_pips for t in losses) != 0 else float("inf")
    
    # Max drawdown (sequential losses)
    equity_curve = []
    running = 0
    for t in closed:
        running += t.pnl_pips
        equity_curve.append(running)
    
    max_dd = 0
    peak = 0
    for eq in equity_curve:
        if eq > peak: peak = eq
        dd = peak - eq
        if dd > max_dd: max_dd = dd
    
    # Consecutive wins/losses
    max_consec_win = max_consec_loss = 0
    current_streak = 0
    last_result = None
    for t in closed:
        if t.result == last_result:
            current_streak += 1
        else:
            current_streak = 1
        if t.result == "WIN": max_consec_win = max(max_consec_win, current_streak)
        else: max_consec_loss = max(max_consec_loss, current_streak)
        last_result = t.result
    
    # Expectancy
    expectancy = (win_rate/100 * avg_win) - ((1 - win_rate/100) * avg_loss) if total > 0 else 0
    
    # Pip size for display
    pip_size = 0.01 if "JPY" in pair.upper() else (0.1 if "XAU" in pair.upper() else 0.0001)
    
    result = {
        "pair": pair.upper(),
        "timeframe": timeframe.upper(),
        "strategy": strategy_name,
        "risk_reward": f"1:{rr}",
        "period": f"{period_days} days",
        "data_points": len(df),
        "total_trades": total,
        "wins": win_count,
        "losses": loss_count,
        "open_trades": len([t for t in trades if t.result == "OPEN"]),
        "win_rate": round(win_rate, 1),
        "total_pnl_pips": round(total_pnl / pip_size, 1),
        "avg_win_pips": round(avg_win / pip_size, 1),
        "avg_loss_pips": round(avg_loss / pip_size, 1),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else "∞",
        "max_drawdown_pips": round(max_dd / pip_size, 1),
        "max_consecutive_wins": max_consec_win,
        "max_consecutive_losses": max_consec_loss,
        "expectancy_pips": round(expectancy / pip_size, 2),
        "verdict": "PROFITABLE ✓" if total_pnl > 0 and total >= 5 else ("UNPROFITABLE ✗" if total >= 5 else "INSUFFICIENT DATA"),
    }
    return result


def format_report(r: dict) -> str:
    if "error" in r:
        return f"ERROR: {r['error']}"
    
    lines = [
        f"═══════════════════════════════════════════",
        f"  BACKTEST REPORT",
        f"═══════════════════════════════════════════",
        f"  Pair           : {r['pair']}",
        f"  Timeframe      : {r['timeframe']}",
        f"  Strategy       : {r['strategy']}",
        f"  Risk:Reward    : {r['risk_reward']}",
        f"  Period         : {r['period']} ({r['data_points']} candles)",
        f"",
        f"── RESULTS ────────────────────────────────",
        f"  Total Trades   : {r['total_trades']}",
        f"  Wins           : {r['wins']}",
        f"  Losses         : {r['losses']}",
        f"  Open           : {r['open_trades']}",
        f"  Win Rate       : {r['win_rate']}%",
        f"",
        f"── PERFORMANCE ────────────────────────────",
        f"  Total P&L      : {r['total_pnl_pips']} pips",
        f"  Avg Win        : {r['avg_win_pips']} pips",
        f"  Avg Loss       : {r['avg_loss_pips']} pips",
        f"  Profit Factor  : {r['profit_factor']}",
        f"  Expectancy     : {r['expectancy_pips']} pips/trade",
        f"  Max Drawdown   : {r['max_drawdown_pips']} pips",
        f"",
        f"── STREAKS ────────────────────────────────",
        f"  Max Consec Win : {r['max_consecutive_wins']}",
        f"  Max Consec Loss: {r['max_consecutive_losses']}",
        f"",
        f"  ★ VERDICT: {r['verdict']}",
        f"═══════════════════════════════════════════",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Forex Backtesting Framework")
    parser.add_argument("pair", type=str, help="Currency pair (e.g., EURUSD)")
    parser.add_argument("timeframe", type=str, nargs="?", default="D", help="Timeframe (D, H4, H1)")
    parser.add_argument("--strategy", type=str, default="ema_cross",
                       help="Strategy: ema_cross, rsi_ob, macd_cross, bb_bounce")
    parser.add_argument("--period", type=int, default=365, help="Period in days")
    parser.add_argument("--rr", type=float, default=2.0, help="Risk:Reward ratio")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    result = backtest(args.pair, args.timeframe, args.strategy, args.period, args.rr)
    
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(format_report(result))


if __name__ == "__main__":
    main()
