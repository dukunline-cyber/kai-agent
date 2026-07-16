#!/usr/bin/env python3.12
"""
Superagent Trader — Multi-Pair Market Scanner
Scans multiple forex pairs and ranks them by signal strength.

Usage:
    python market_scanner.py                    # Scan all major pairs
    python market_scanner.py --tf H4            # Custom timeframe
    python market_scanner.py --pairs EURUSD,GBPUSD,USDJPY
"""
import argparse, json, sys
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime


PAIR_MAP = {
    "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X",
    "USDCHF": "USDCHF=X", "AUDUSD": "AUDUSD=X", "NZDUSD": "NZDUSD=X",
    "USDCAD": "USDCAD=X", "GBPJPY": "GBPJPY=X", "EURJPY": "EURJPY=X",
    "EURGBP": "EURGBP=X", "AUDJPY": "AUDJPY=X", "EURAUD": "EURAUD=X",
    "GBPAUD": "GBPAUD=X", "XAUUSD": "GC=F",
}

TF_MAP = {
    "H1": ("1h", "30d"), "H4": ("1h", "60d"),
    "D": ("1d", "365d"), "W": ("1wk", "730d"),
}

ALL_PAIRS = list(PAIR_MAP.keys())


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
def calc_atr(df, p=14):
    hl = df["High"]-df["Low"]
    hc = (df["High"]-df["Close"].shift()).abs()
    lc = (df["Low"]-df["Close"].shift()).abs()
    tr = pd.concat([hl,hc,lc],axis=1).max(axis=1)
    return tr.rolling(p).mean()
def calc_adx(df, p=14):
    plus_dm = df["High"].diff()
    minus_dm = -df["Low"].diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)
    atr = calc_atr(df, p)
    plus_di = 100 * calc_ema(plus_dm, p) / atr
    minus_di = 100 * calc_ema(minus_dm, p) / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = calc_ema(dx, p)
    return adx, plus_di, minus_di


def scan_pair(pair: str, timeframe: str = "H4") -> dict:
    """Quick scan of a single pair."""
    symbol = PAIR_MAP.get(pair.upper(), f"{pair.upper()}=X")
    interval, period = TF_MAP.get(timeframe.upper(), ("1h", "60d"))
    
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        
        if df.empty:
            return {"pair": pair, "error": "No data"}
        
        if timeframe.upper() == "H4":
            df = df.resample("4h").agg({
                "Open": "first", "High": "max", "Low": "min",
                "Close": "last", "Volume": "sum"
            }).dropna()
        
        close = df["Close"]
        last = close.iloc[-1]
        
        # Indicators
        ema21 = calc_ema(close, 21)
        sma50 = calc_sma(close, 50)
        rsi = calc_rsi(close, 14)
        _, _, histogram = calc_macd(close)
        atr = calc_atr(df)
        adx, plus_di, minus_di = calc_adx(df)
        
        # Score
        score = 0
        signals = []
        
        # Trend (EMA/SMA position)
        if last > ema21.iloc[-1] and last > sma50.iloc[-1]:
            score += 2; signals.append("↑ Above MA")
        elif last < ema21.iloc[-1] and last < sma50.iloc[-1]:
            score -= 2; signals.append("↓ Below MA")
        
        # RSI
        rsi_val = rsi.iloc[-1]
        if rsi_val > 70: score -= 1; signals.append("RSI OB")
        elif rsi_val < 30: score += 1; signals.append("RSI OS")
        elif rsi_val > 55: score += 1; signals.append("RSI Bull")
        elif rsi_val < 45: score -= 1; signals.append("RSI Bear")
        
        # MACD
        if histogram.iloc[-1] > 0: score += 1; signals.append("MACD+")
        else: score -= 1; signals.append("MACD-")
        
        # MACD cross
        if len(histogram) >= 2:
            if histogram.iloc[-2] < 0 and histogram.iloc[-1] > 0:
                score += 2; signals.append("⚡MACD Cross↑")
            elif histogram.iloc[-2] > 0 and histogram.iloc[-1] < 0:
                score -= 2; signals.append("⚡MACD Cross↓")
        
        # ADX trend strength
        adx_val = adx.iloc[-1] if not np.isnan(adx.iloc[-1]) else 0
        trending = adx_val > 25
        
        # Daily change
        change_pct = ((last - close.iloc[-2]) / close.iloc[-2] * 100) if len(close) > 1 else 0
        
        if score >= 4: signal = "STRONG BUY"
        elif score >= 2: signal = "BUY"
        elif score <= -4: signal = "STRONG SELL"
        elif score <= -2: signal = "SELL"
        else: signal = "NEUTRAL"
        
        return {
            "pair": pair.upper(),
            "price": round(float(last), 5),
            "change_pct": round(float(change_pct), 2),
            "score": score,
            "signal": signal,
            "rsi": round(float(rsi_val), 1),
            "adx": round(float(adx_val), 1),
            "trending": trending,
            "atr": round(float(atr.iloc[-1]), 5) if not np.isnan(atr.iloc[-1]) else 0,
            "signals": signals,
        }
    except Exception as e:
        return {"pair": pair.upper(), "error": str(e)}


def format_scanner(results: list, tf: str) -> str:
    lines = [
        f"═══════════════════════════════════════════════════════════════",
        f"  MARKET SCANNER — {tf.upper()} — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"═══════════════════════════════════════════════════════════════",
        f"",
    ]
    
    # Sort by absolute score
    valid = [r for r in results if "error" not in r]
    valid.sort(key=lambda x: abs(x["score"]), reverse=True)
    
    # Header
    lines.append(f"  {'PAIR':<10} {'PRICE':>10} {'CHG%':>7} {'RSI':>6} {'ADX':>6} {'SCORE':>6}  {'SIGNAL':<12} NOTES")
    lines.append(f"  {'─'*10} {'─'*10} {'─'*7} {'─'*6} {'─'*6} {'─'*6}  {'─'*12} {'─'*20}")
    
    for r in valid:
        emoji = "🟢" if "BUY" in r["signal"] else ("🔴" if "SELL" in r["signal"] else "⚪")
        trend_mark = "📈" if r.get("trending") else "  "
        notes = ", ".join(r.get("signals", [])[:3])
        lines.append(
            f"  {r['pair']:<10} {r['price']:>10.5f} {r['change_pct']:>+6.2f}% {r['rsi']:>5.1f} {r['adx']:>5.1f} {r['score']:>+5d}  {emoji} {r['signal']:<10} {trend_mark} {notes}"
        )
    
    errors = [r for r in results if "error" in r]
    if errors:
        lines.append(f"\n  ⚠ Errors: {', '.join(r['pair'] for r in errors)}")
    
    # Top picks
    buys = [r for r in valid if r["score"] >= 3]
    sells = [r for r in valid if r["score"] <= -3]
    
    if buys or sells:
        lines.append(f"\n── TOP PICKS ──────────────────────────────")
        if buys:
            lines.append(f"  🟢 BUY:  {', '.join(r['pair'] for r in buys)}")
        if sells:
            lines.append(f"  🔴 SELL: {', '.join(r['pair'] for r in sells)}")
    
    lines.append(f"═══════════════════════════════════════════════════════════════")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Multi-Pair Market Scanner")
    parser.add_argument("--tf", type=str, default="H4", help="Timeframe (H1, H4, D, W)")
    parser.add_argument("--pairs", type=str, help="Custom pairs (comma-separated)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    pairs = args.pairs.upper().split(",") if args.pairs else ALL_PAIRS
    
    print(f"Scanning {len(pairs)} pairs on {args.tf}...\n")
    
    results = []
    for pair in pairs:
        result = scan_pair(pair, args.tf)
        results.append(result)
    
    if args.json:
        print(json.dumps(results, indent=2, default=str))
    else:
        print(format_scanner(results, args.tf))


if __name__ == "__main__":
    main()
