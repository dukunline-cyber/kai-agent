#!/usr/bin/env python3.12
"""
Superagent Trader — Script Analisa Teknikal Otomatis
Ambil data forex real-time via yfinance, hitung semua indikator utama.

Usage:
    python technical_analysis.py EURUSD      # default H4
    python technical_analysis.py GBPJPY D    # Daily
    python technical_analysis.py XAUUSD H1   # Hourly
"""
import sys, json
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta


# ─── Pair Mapping ───
PAIR_MAP = {
    "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X",
    "USDCHF": "USDCHF=X", "AUDUSD": "AUDUSD=X", "NZDUSD": "NZDUSD=X",
    "USDCAD": "USDCAD=X", "GBPJPY": "GBPJPY=X", "EURJPY": "EURJPY=X",
    "EURGBP": "EURGBP=X", "AUDJPY": "AUDJPY=X", "CHFJPY": "CHFJPY=X",
    "EURAUD": "EURAUD=X", "EURCHF": "EURCHF=X", "GBPAUD": "GBPAUD=X",
    "XAUUSD": "GC=F", "XAGUSD": "SI=F",
    "DXY": "DX-Y.NYB", "US30": "YM=F", "NAS100": "NQ=F", "SPX500": "ES=F",
}

TF_MAP = {
    "M15": ("15m", "5d"),  "M30": ("30m", "5d"),
    "H1":  ("1h", "30d"),  "H4":  ("1h", "60d"),   # yf max for 1h is 730d
    "D":   ("1d", "365d"), "W":   ("1wk", "730d"),
}


# ─── Manual Indicator Calculations ───
def calc_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()

def calc_sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()

def calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calc_macd(series: pd.Series, fast=12, slow=26, signal=9):
    ema_fast = calc_ema(series, fast)
    ema_slow = calc_ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = calc_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calc_stochastic(df: pd.DataFrame, k_period=14, d_period=3):
    low_min = df["Low"].rolling(window=k_period).min()
    high_max = df["High"].rolling(window=k_period).max()
    k = 100 * (df["Close"] - low_min) / (high_max - low_min)
    d = k.rolling(window=d_period).mean()
    return k, d

def calc_bollinger(series: pd.Series, period=20, std_dev=2):
    sma = calc_sma(series, period)
    std = series.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return upper, sma, lower

def calc_atr(df: pd.DataFrame, period=14) -> pd.Series:
    high_low = df["High"] - df["Low"]
    high_close = (df["High"] - df["Close"].shift()).abs()
    low_close = (df["Low"] - df["Close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()

def calc_adx(df: pd.DataFrame, period=14):
    plus_dm = df["High"].diff()
    minus_dm = -df["Low"].diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)
    atr = calc_atr(df, period)
    plus_di = 100 * calc_ema(plus_dm, period) / atr
    minus_di = 100 * calc_ema(minus_dm, period) / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = calc_ema(dx, period)
    return adx, plus_di, minus_di

def calc_obv(df: pd.DataFrame) -> pd.Series:
    obv = (np.sign(df["Close"].diff()) * df["Volume"]).fillna(0).cumsum()
    return obv


# ─── Trend Detection ───
def detect_trend(df: pd.DataFrame) -> str:
    close = df["Close"]
    ema21 = calc_ema(close, 21)
    sma50 = calc_sma(close, 50)
    sma200 = calc_sma(close, 200)
    last = close.iloc[-1]
    
    signals = []
    if last > ema21.iloc[-1]: signals.append("BULL")
    else: signals.append("BEAR")
    if last > sma50.iloc[-1]: signals.append("BULL")
    else: signals.append("BEAR")
    if not np.isnan(sma200.iloc[-1]):
        if last > sma200.iloc[-1]: signals.append("BULL")
        else: signals.append("BEAR")
    
    bull = signals.count("BULL")
    if bull >= 2: return "BULLISH"
    elif bull == 0: return "BEARISH"
    return "NEUTRAL"


# ─── Divergence Detection ───
def detect_rsi_divergence(df: pd.DataFrame, lookback=20) -> str:
    close = df["Close"].iloc[-lookback:]
    rsi = calc_rsi(df["Close"], 14).iloc[-lookback:]
    
    mid = lookback // 2
    price_first = close.iloc[:mid].min()
    price_second = close.iloc[mid:].min()
    rsi_first = rsi.iloc[:mid].min()
    rsi_second = rsi.iloc[mid:].min()
    
    if price_second < price_first and rsi_second > rsi_first:
        return "BULLISH DIVERGENCE"
    
    price_first_h = close.iloc[:mid].max()
    price_second_h = close.iloc[mid:].max()
    rsi_first_h = rsi.iloc[:mid].max()
    rsi_second_h = rsi.iloc[mid:].max()
    
    if price_second_h > price_first_h and rsi_second_h < rsi_first_h:
        return "BEARISH DIVERGENCE"
    
    return "NO DIVERGENCE"


# ─── Key Levels ───
def find_key_levels(df: pd.DataFrame, n=5) -> dict:
    """Find support and resistance using local swing highs/lows."""
    highs, lows = [], []
    for i in range(2, len(df)-2):
        if df["High"].iloc[i] > df["High"].iloc[i-1] and df["High"].iloc[i] > df["High"].iloc[i+1]:
            if df["High"].iloc[i] > df["High"].iloc[i-2] and df["High"].iloc[i] > df["High"].iloc[i+2]:
                highs.append(df["High"].iloc[i])
        if df["Low"].iloc[i] < df["Low"].iloc[i-1] and df["Low"].iloc[i] < df["Low"].iloc[i+1]:
            if df["Low"].iloc[i] < df["Low"].iloc[i-2] and df["Low"].iloc[i] < df["Low"].iloc[i+2]:
                lows.append(df["Low"].iloc[i])
    
    last = df["Close"].iloc[-1]
    resistance = sorted([h for h in highs if h > last])[:n]
    support = sorted([l for l in lows if l < last], reverse=True)[:n]
    return {"resistance": resistance, "support": support}


# ─── Main Analysis ───
def analyze(pair: str, timeframe: str = "H4") -> dict:
    symbol = PAIR_MAP.get(pair.upper(), f"{pair.upper()}=X")
    interval, period = TF_MAP.get(timeframe.upper(), ("1h", "60d"))
    
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval)
    
    if df.empty:
        return {"error": f"No data for {pair} ({symbol})"}
    
    # For H4: resample from 1h data
    if timeframe.upper() == "H4":
        df = df.resample("4h").agg({
            "Open": "first", "High": "max", "Low": "min",
            "Close": "last", "Volume": "sum"
        }).dropna()
    
    close = df["Close"]
    last_price = close.iloc[-1]
    
    # Moving Averages
    ema21 = calc_ema(close, 21)
    sma50 = calc_sma(close, 50)
    sma200 = calc_sma(close, 200)
    
    # RSI
    rsi = calc_rsi(close, 14)
    
    # MACD
    macd_line, signal_line, histogram = calc_macd(close)
    
    # Stochastic
    stoch_k, stoch_d = calc_stochastic(df)
    
    # Bollinger Bands
    bb_upper, bb_mid, bb_lower = calc_bollinger(close)
    
    # ATR
    atr = calc_atr(df)
    
    # ADX
    adx, plus_di, minus_di = calc_adx(df)
    
    # Trend
    trend = detect_trend(df)
    
    # Divergence
    divergence = detect_rsi_divergence(df)
    
    # Key Levels
    levels = find_key_levels(df)
    
    # RSI Zone
    rsi_val = rsi.iloc[-1]
    if rsi_val > 70: rsi_zone = "OVERBOUGHT"
    elif rsi_val < 30: rsi_zone = "OVERSOLD"
    elif rsi_val > 50: rsi_zone = "BULLISH"
    else: rsi_zone = "BEARISH"
    
    # MACD Signal
    macd_signal = "BULLISH" if histogram.iloc[-1] > 0 else "BEARISH"
    macd_cross = ""
    if len(histogram) >= 2:
        if histogram.iloc[-2] < 0 and histogram.iloc[-1] > 0:
            macd_cross = "BULLISH CROSS"
        elif histogram.iloc[-2] > 0 and histogram.iloc[-1] < 0:
            macd_cross = "BEARISH CROSS"
    
    # Stochastic Zone
    stoch_val = stoch_k.iloc[-1]
    stoch_zone = "OVERBOUGHT" if stoch_val > 80 else ("OVERSOLD" if stoch_val < 20 else "NEUTRAL")
    
    # Bollinger position
    bb_pos = "UPPER" if last_price > bb_upper.iloc[-1] else (
        "LOWER" if last_price < bb_lower.iloc[-1] else "MIDDLE")
    
    # ADX interpretation
    adx_val = adx.iloc[-1]
    trend_strength = "STRONG" if adx_val > 25 else "WEAK/NO TREND"
    
    # Confluence score
    score = 0
    bias_signals = []
    if trend == "BULLISH": score += 1; bias_signals.append("Trend ↑")
    elif trend == "BEARISH": score -= 1; bias_signals.append("Trend ↓")
    if rsi_zone in ["BULLISH", "OVERSOLD"]: score += 1; bias_signals.append(f"RSI {rsi_zone}")
    elif rsi_zone in ["BEARISH", "OVERBOUGHT"]: score -= 1; bias_signals.append(f"RSI {rsi_zone}")
    if macd_signal == "BULLISH": score += 1; bias_signals.append("MACD ↑")
    else: score -= 1; bias_signals.append("MACD ↓")
    if stoch_zone == "OVERSOLD": score += 1; bias_signals.append("Stoch Oversold")
    elif stoch_zone == "OVERBOUGHT": score -= 1; bias_signals.append("Stoch OB")
    if "BULLISH" in divergence: score += 2; bias_signals.append("RSI Bullish Div")
    elif "BEARISH" in divergence: score -= 2; bias_signals.append("RSI Bearish Div")
    
    if score >= 3: overall = "STRONG BUY"
    elif score >= 1: overall = "BUY BIAS"
    elif score <= -3: overall = "STRONG SELL"
    elif score <= -1: overall = "SELL BIAS"
    else: overall = "NEUTRAL"
    
    decimals = 5 if "JPY" not in pair.upper() and "XAU" not in pair.upper() else (3 if "XAU" in pair.upper() else 3)
    
    def fmt(v):
        if pd.isna(v): return "N/A"
        return round(float(v), decimals)
    
    result = {
        "pair": pair.upper(),
        "timeframe": timeframe.upper(),
        "last_price": fmt(last_price),
        "data_points": len(df),
        "timestamp": str(df.index[-1]),
        "trend": trend,
        "trend_strength": trend_strength,
        "overall_signal": overall,
        "confluence_score": score,
        "bias_signals": bias_signals,
        "indicators": {
            "ema_21": fmt(ema21.iloc[-1]),
            "sma_50": fmt(sma50.iloc[-1]),
            "sma_200": fmt(sma200.iloc[-1]),
            "rsi_14": round(float(rsi.iloc[-1]), 1),
            "rsi_zone": rsi_zone,
            "macd_line": fmt(macd_line.iloc[-1]),
            "macd_signal": fmt(signal_line.iloc[-1]),
            "macd_histogram": fmt(histogram.iloc[-1]),
            "macd_bias": macd_signal,
            "macd_cross": macd_cross or "NONE",
            "stochastic_k": round(float(stoch_k.iloc[-1]), 1),
            "stochastic_d": round(float(stoch_d.iloc[-1]), 1),
            "stochastic_zone": stoch_zone,
            "bb_upper": fmt(bb_upper.iloc[-1]),
            "bb_middle": fmt(bb_mid.iloc[-1]),
            "bb_lower": fmt(bb_lower.iloc[-1]),
            "bb_position": bb_pos,
            "atr_14": fmt(atr.iloc[-1]),
            "adx_14": round(float(adx_val), 1),
            "plus_di": round(float(plus_di.iloc[-1]), 1),
            "minus_di": round(float(minus_di.iloc[-1]), 1),
        },
        "divergence": divergence,
        "key_levels": {
            "resistance": [fmt(r) for r in levels["resistance"][:3]],
            "support": [fmt(s) for s in levels["support"][:3]],
        },
        "suggested_sl_atr": {
            "buy_sl": fmt(last_price - 1.5 * atr.iloc[-1]),
            "sell_sl": fmt(last_price + 1.5 * atr.iloc[-1]),
        }
    }
    return result


def format_report(result: dict) -> str:
    """Format analysis result as readable text."""
    if "error" in result:
        return f"ERROR: {result['error']}"
    
    r = result
    ind = r["indicators"]
    lines = [
        f"═══════════════════════════════════════════",
        f"  ANALISA TEKNIKAL — {r['pair']} ({r['timeframe']})",
        f"═══════════════════════════════════════════",
        f"  Harga Terakhir : {r['last_price']}",
        f"  Waktu Data     : {r['timestamp']}",
        f"  Data Points    : {r['data_points']}",
        f"",
        f"── TREND & SIGNAL ──────────────────────────",
        f"  Trend          : {r['trend']}",
        f"  Kekuatan       : {r['trend_strength']} (ADX: {ind['adx_14']})",
        f"  Overall Signal : ★ {r['overall_signal']} ★ (score: {r['confluence_score']})",
        f"  Confluence     : {', '.join(r['bias_signals'])}",
        f"  Divergence     : {r['divergence']}",
        f"",
        f"── MOVING AVERAGES ─────────────────────────",
        f"  EMA 21  : {ind['ema_21']}",
        f"  SMA 50  : {ind['sma_50']}",
        f"  SMA 200 : {ind['sma_200']}",
        f"",
        f"── OSCILLATORS ─────────────────────────────",
        f"  RSI (14)       : {ind['rsi_14']} [{ind['rsi_zone']}]",
        f"  Stochastic K/D : {ind['stochastic_k']}/{ind['stochastic_d']} [{ind['stochastic_zone']}]",
        f"  MACD           : {ind['macd_line']} (Signal: {ind['macd_signal']})",
        f"  MACD Histogram : {ind['macd_histogram']} [{ind['macd_bias']}]",
        f"  MACD Cross     : {ind['macd_cross']}",
        f"",
        f"── VOLATILITY ──────────────────────────────",
        f"  BB Upper/Mid/Lower : {ind['bb_upper']} / {ind['bb_middle']} / {ind['bb_lower']}",
        f"  BB Position        : {ind['bb_position']}",
        f"  ATR (14)           : {ind['atr_14']}",
        f"",
        f"── KEY LEVELS ──────────────────────────────",
        f"  Resistance : {', '.join(str(r) for r in r['key_levels']['resistance'])}",
        f"  Support    : {', '.join(str(s) for s in r['key_levels']['support'])}",
        f"",
        f"── SUGGESTED SL (ATR-based) ────────────────",
        f"  Buy SL  : {r['suggested_sl_atr']['buy_sl']}",
        f"  Sell SL : {r['suggested_sl_atr']['sell_sl']}",
        f"═══════════════════════════════════════════",
    ]
    return "\n".join(lines)


def main():
    pair = sys.argv[1] if len(sys.argv) > 1 else "EURUSD"
    tf = sys.argv[2] if len(sys.argv) > 2 else "H4"
    
    result = analyze(pair, tf)
    print(format_report(result))
    
    # Also save JSON for other scripts
    with open("/tmp/last_analysis.json", "w") as f:
        json.dump(result, f, indent=2, default=str)


if __name__ == "__main__":
    main()
