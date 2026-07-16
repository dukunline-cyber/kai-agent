#!/usr/bin/env python3.12
"""
Superagent Trader — Pair Correlation Matrix
Analyze correlation between forex pairs to avoid double exposure.

Usage:
    python correlation_matrix.py                           # Major pairs
    python correlation_matrix.py EURUSD GBPUSD USDJPY     # Custom pairs
    python correlation_matrix.py --chart /tmp/corr.png     # With chart
"""
import sys, argparse, json
import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


PAIR_MAP = {
    "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X",
    "USDCHF": "USDCHF=X", "AUDUSD": "AUDUSD=X", "NZDUSD": "NZDUSD=X",
    "USDCAD": "USDCAD=X", "GBPJPY": "GBPJPY=X", "EURJPY": "EURJPY=X",
    "EURGBP": "EURGBP=X", "AUDJPY": "AUDJPY=X", "CHFJPY": "CHFJPY=X",
    "XAUUSD": "GC=F",
}

DEFAULT_PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "GBPJPY", "EURJPY"]


def get_correlation_matrix(pairs: list, period: str = "90d") -> tuple:
    """Download daily close data and compute correlation matrix."""
    data = {}
    for pair in pairs:
        symbol = PAIR_MAP.get(pair.upper(), f"{pair.upper()}=X")
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period, interval="1d")
            if not hist.empty:
                data[pair.upper()] = hist["Close"].pct_change().dropna()
        except Exception as e:
            print(f"Warning: Could not fetch {pair}: {e}")
    
    if len(data) < 2:
        return None, None
    
    df = pd.DataFrame(data)
    corr = df.corr()
    return corr, df


def interpret_correlation(val: float) -> str:
    """Interpret correlation strength."""
    abs_val = abs(val)
    if abs_val >= 0.8: strength = "SANGAT KUAT"
    elif abs_val >= 0.6: strength = "KUAT"
    elif abs_val >= 0.4: strength = "SEDANG"
    elif abs_val >= 0.2: strength = "LEMAH"
    else: strength = "TIDAK ADA"
    
    direction = "POSITIF" if val >= 0 else "NEGATIF"
    return f"{strength} {direction}"


def find_alerts(corr: pd.DataFrame, threshold: float = 0.7) -> list:
    """Find highly correlated pairs that pose exposure risk."""
    alerts = []
    seen = set()
    
    for i in range(len(corr)):
        for j in range(i+1, len(corr)):
            pair_a = corr.index[i]
            pair_b = corr.columns[j]
            val = corr.iloc[i, j]
            key = f"{pair_a}-{pair_b}"
            
            if abs(val) >= threshold and key not in seen:
                seen.add(key)
                if val > 0:
                    alert = f"⚠ {pair_a} & {pair_b}: korelasi +{val:.2f} → HINDARI trade searah di kedua pair (double exposure)"
                else:
                    alert = f"⚠ {pair_a} & {pair_b}: korelasi {val:.2f} → HINDARI trade berlawanan di kedua pair (double exposure)"
                alerts.append(alert)
    
    return alerts


def generate_heatmap(corr: pd.DataFrame, output_path: str):
    """Generate correlation heatmap chart."""
    fig, ax = plt.subplots(figsize=(10, 8), facecolor="#0a0a0a")
    ax.set_facecolor("#0a0a0a")
    
    n = len(corr)
    
    # Custom colormap: red (negative) → black (zero) → green (positive)
    from matplotlib.colors import LinearSegmentedColormap
    colors = ["#ff1744", "#1a1a1a", "#00c853"]
    cmap = LinearSegmentedColormap.from_list("custom", colors, N=256)
    
    im = ax.imshow(corr.values, cmap=cmap, vmin=-1, vmax=1, aspect="equal")
    
    # Labels
    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(corr.columns, fontsize=9, color="#cccccc", rotation=45, ha="right")
    ax.set_yticklabels(corr.index, fontsize=9, color="#cccccc")
    
    # Annotate cells
    for i in range(n):
        for j in range(n):
            val = corr.iloc[i, j]
            color = "#ffffff" if abs(val) > 0.5 else "#999999"
            ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                   fontsize=8, color=color, fontweight="bold" if abs(val) > 0.7 else "normal")
    
    ax.set_title("PAIR CORRELATION MATRIX (90D)", color="#ffffff", fontsize=14,
                fontweight="bold", pad=15, fontfamily="monospace")
    
    # Colorbar
    cbar = plt.colorbar(im, ax=ax, shrink=0.8)
    cbar.ax.tick_params(colors="#666666", labelsize=8)
    cbar.set_label("Correlation", color="#999999", fontsize=9)
    
    fig.text(0.99, 0.01, "SUPERAGENT TRADER · Viktor AI", fontsize=7,
            color="#333333", ha="right", va="bottom", fontfamily="monospace")
    
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="#0a0a0a",
               edgecolor="none", pad_inches=0.3)
    plt.close()
    print(f"Heatmap saved: {output_path}")


def format_report(corr: pd.DataFrame, alerts: list) -> str:
    lines = [
        f"═══════════════════════════════════════════",
        f"  PAIR CORRELATION MATRIX (90 Days)",
        f"═══════════════════════════════════════════",
        f"",
    ]
    
    # Matrix display
    header = "          " + "  ".join(f"{p:>8}" for p in corr.columns)
    lines.append(header)
    lines.append("  " + "─" * (len(header) - 2))
    
    for pair in corr.index:
        row_vals = []
        for col in corr.columns:
            val = corr.loc[pair, col]
            if pair == col:
                row_vals.append("    ─   ")
            else:
                row_vals.append(f"  {val:>6.2f}")
        lines.append(f"  {pair:<8}" + "".join(row_vals))
    
    lines.append("")
    lines.append("── INTERPRETASI ───────────────────────────")
    lines.append("  +0.8 ~ +1.0  = Sangat Kuat Positif")
    lines.append("  +0.6 ~ +0.8  = Kuat Positif")
    lines.append("  -0.6 ~ -0.8  = Kuat Negatif (mirror)")
    lines.append("  -0.8 ~ -1.0  = Sangat Kuat Negatif")
    
    if alerts:
        lines.append("")
        lines.append("── ⚠ EXPOSURE ALERTS ──────────────────────")
        for alert in alerts:
            lines.append(f"  {alert}")
    else:
        lines.append("")
        lines.append("  ✅ Tidak ada pair dengan korelasi tinggi yang berbahaya.")
    
    lines.append(f"═══════════════════════════════════════════")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Pair Correlation Matrix")
    parser.add_argument("pairs", nargs="*", default=DEFAULT_PAIRS, help="Currency pairs to analyze")
    parser.add_argument("--chart", type=str, help="Output heatmap chart path")
    parser.add_argument("--period", type=str, default="90d", help="Historical period (default: 90d)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    corr, df = get_correlation_matrix(args.pairs, args.period)
    
    if corr is None:
        print("ERROR: Could not fetch enough data. Check pair names.")
        return
    
    alerts = find_alerts(corr)
    
    if args.json:
        print(json.dumps({
            "correlation": corr.to_dict(),
            "alerts": alerts,
        }, indent=2, default=str))
    else:
        print(format_report(corr, alerts))
    
    if args.chart:
        generate_heatmap(corr, args.chart)


if __name__ == "__main__":
    main()
