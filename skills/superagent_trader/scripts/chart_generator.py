#!/usr/bin/env python3.12
"""
Superagent Trader — Chart Generator
Generates visual forex chart with indicators overlaid.

Usage:
    python chart_generator.py EURUSD H4 /tmp/chart.png
    python chart_generator.py GBPJPY D /tmp/chart.png
"""
import sys, os
import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
from datetime import datetime


# Reuse pair/tf maps
PAIR_MAP = {
    "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X",
    "USDCHF": "USDCHF=X", "AUDUSD": "AUDUSD=X", "NZDUSD": "NZDUSD=X",
    "USDCAD": "USDCAD=X", "GBPJPY": "GBPJPY=X", "EURJPY": "EURJPY=X",
    "EURGBP": "EURGBP=X", "AUDJPY": "AUDJPY=X", "CHFJPY": "CHFJPY=X",
    "XAUUSD": "GC=F", "XAGUSD": "SI=F",
    "DXY": "DX-Y.NYB", "US30": "YM=F", "NAS100": "NQ=F", "SPX500": "ES=F",
}

TF_MAP = {
    "M15": ("15m", "5d"),  "M30": ("30m", "5d"),
    "H1":  ("1h", "30d"),  "H4":  ("1h", "60d"),
    "D":   ("1d", "365d"), "W":   ("1wk", "730d"),
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


def generate_chart(pair: str, timeframe: str, output_path: str, last_n: int = 100):
    symbol = PAIR_MAP.get(pair.upper(), f"{pair.upper()}=X")
    interval, period = TF_MAP.get(timeframe.upper(), ("1h", "60d"))
    
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval)
    
    if df.empty:
        print(f"ERROR: No data for {pair}")
        return None
    
    if timeframe.upper() == "H4":
        df = df.resample("4h").agg({
            "Open": "first", "High": "max", "Low": "min",
            "Close": "last", "Volume": "sum"
        }).dropna()
    
    df = df.tail(last_n)
    close = df["Close"]
    
    # Calculate indicators
    ema21 = calc_ema(close, 21)
    sma50 = calc_sma(close, 50)
    rsi = calc_rsi(close, 14)
    macd_line, signal_line, histogram = calc_macd(close)
    bb_upper, bb_mid, bb_lower = calc_bb(close)
    
    # ─── CHART STYLING ───
    fig = plt.figure(figsize=(16, 12), facecolor="#0a0a0a")
    
    # Grid: price (60%), RSI (20%), MACD (20%)
    gs = fig.add_gridspec(3, 1, height_ratios=[3, 1, 1], hspace=0.05)
    
    ax1 = fig.add_subplot(gs[0])  # Price
    ax2 = fig.add_subplot(gs[1], sharex=ax1)  # RSI
    ax3 = fig.add_subplot(gs[2], sharex=ax1)  # MACD
    
    for ax in [ax1, ax2, ax3]:
        ax.set_facecolor("#0a0a0a")
        ax.tick_params(colors="#666666", labelsize=8)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["bottom"].set_color("#333333")
        ax.spines["left"].set_color("#333333")
        ax.grid(True, alpha=0.15, color="#333333")
    
    x = range(len(df))
    
    # ─── CANDLESTICK ───
    for i in range(len(df)):
        o, h, l, c = df["Open"].iloc[i], df["High"].iloc[i], df["Low"].iloc[i], df["Close"].iloc[i]
        color = "#00c853" if c >= o else "#ff1744"
        ax1.plot([i, i], [l, h], color=color, linewidth=0.7)
        body_bottom = min(o, c)
        body_height = abs(c - o)
        rect = Rectangle((i - 0.35, body_bottom), 0.7, body_height if body_height > 0 else 0.00001,
                         facecolor=color, edgecolor=color, linewidth=0.5)
        ax1.add_patch(rect)
    
    # ─── INDICATORS ON PRICE ───
    ax1.plot(x, ema21.values, color="#FFD600", linewidth=1, alpha=0.8, label="EMA 21")
    ax1.plot(x, sma50.values, color="#2979FF", linewidth=1, alpha=0.8, label="SMA 50")
    ax1.plot(x, bb_upper.values, color="#B388FF", linewidth=0.6, alpha=0.5, linestyle="--")
    ax1.plot(x, bb_lower.values, color="#B388FF", linewidth=0.6, alpha=0.5, linestyle="--")
    ax1.fill_between(x, bb_upper.values, bb_lower.values, alpha=0.03, color="#B388FF")
    
    ax1.set_ylabel("Price", color="#999999", fontsize=9)
    ax1.legend(loc="upper left", fontsize=7, facecolor="#1a1a1a", edgecolor="#333333",
              labelcolor="#cccccc", framealpha=0.9)
    
    # Title
    ax1.set_title(f"  {pair.upper()} — {timeframe.upper()}  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                  color="#ffffff", fontsize=12, fontweight="bold", loc="left", pad=10,
                  fontfamily="monospace")
    
    # ─── RSI ───
    ax2.plot(x, rsi.values, color="#FFD600", linewidth=1)
    ax2.axhline(y=70, color="#ff1744", linewidth=0.5, linestyle="--", alpha=0.7)
    ax2.axhline(y=30, color="#00c853", linewidth=0.5, linestyle="--", alpha=0.7)
    ax2.axhline(y=50, color="#666666", linewidth=0.3, linestyle=":", alpha=0.5)
    ax2.fill_between(x, 70, rsi.values, where=rsi.values >= 70, alpha=0.15, color="#ff1744")
    ax2.fill_between(x, 30, rsi.values, where=rsi.values <= 30, alpha=0.15, color="#00c853")
    ax2.set_ylabel("RSI", color="#999999", fontsize=9)
    ax2.set_ylim(0, 100)
    
    # ─── MACD ───
    colors_hist = ["#00c853" if v >= 0 else "#ff1744" for v in histogram.values]
    ax3.bar(x, histogram.values, color=colors_hist, alpha=0.6, width=0.7)
    ax3.plot(x, macd_line.values, color="#2979FF", linewidth=1, label="MACD")
    ax3.plot(x, signal_line.values, color="#FF6D00", linewidth=1, label="Signal")
    ax3.axhline(y=0, color="#666666", linewidth=0.3)
    ax3.set_ylabel("MACD", color="#999999", fontsize=9)
    ax3.legend(loc="upper left", fontsize=6, facecolor="#1a1a1a", edgecolor="#333333",
              labelcolor="#cccccc", framealpha=0.9)
    
    # Hide x-axis labels for top panels
    plt.setp(ax1.get_xticklabels(), visible=False)
    plt.setp(ax2.get_xticklabels(), visible=False)
    
    # X-axis ticks
    tick_interval = max(len(df) // 10, 1)
    tick_positions = list(range(0, len(df), tick_interval))
    tick_labels = [df.index[i].strftime("%m/%d %H:%M") if hasattr(df.index[i], 'strftime') else str(i) 
                   for i in tick_positions]
    ax3.set_xticks(tick_positions)
    ax3.set_xticklabels(tick_labels, rotation=30, fontsize=7, color="#666666")
    
    # Watermark
    fig.text(0.99, 0.01, "SUPERAGENT TRADER · Viktor AI", fontsize=7,
            color="#333333", ha="right", va="bottom", fontfamily="monospace")
    
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="#0a0a0a",
               edgecolor="none", pad_inches=0.3)
    plt.close()
    
    print(f"Chart saved: {output_path}")
    return output_path


def main():
    pair = sys.argv[1] if len(sys.argv) > 1 else "EURUSD"
    tf = sys.argv[2] if len(sys.argv) > 2 else "H4"
    output = sys.argv[3] if len(sys.argv) > 3 else "/tmp/forex_chart.png"
    
    generate_chart(pair, tf, output)


if __name__ == "__main__":
    main()
