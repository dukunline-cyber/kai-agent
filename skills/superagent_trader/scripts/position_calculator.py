#!/usr/bin/env python3.12
"""
Superagent Trader — Position Size Calculator
Menghitung lot size yang tepat berdasarkan equity, risk%, SL, dan pair.

Usage:
    python position_calculator.py --equity 10000 --risk 1 --sl-pips 50 --pair EURUSD
    python position_calculator.py --equity 5000 --risk 2 --sl-pips 30 --pair USDJPY
    python position_calculator.py --equity 10000 --risk 1 --entry 1.0850 --sl 1.0800 --pair EURUSD
"""
import argparse, json, sys


# Pip values per standard lot (100,000 units) in USD
# For XXX/USD pairs: pip = $10 per lot
# For USD/XXX pairs: pip = $10 / price per lot (approximate)
# For XXX/XXX pairs: depends on quote currency

PIP_VALUES = {
    # Major pairs (approximate pip value per standard lot in USD)
    "EURUSD": 10.0, "GBPUSD": 10.0, "AUDUSD": 10.0, "NZDUSD": 10.0,
    "USDJPY": 6.7, "USDCHF": 10.8, "USDCAD": 7.3,
    # Crosses
    "GBPJPY": 6.7, "EURJPY": 6.7, "AUDJPY": 6.7, "CHFJPY": 6.7,
    "EURGBP": 12.5, "EURAUD": 6.5, "EURCHF": 10.8, "GBPAUD": 6.5,
    "GBPCAD": 7.3, "AUDCAD": 7.3, "AUDNZD": 5.8, "NZDJPY": 6.7,
    # Metals / Indices
    "XAUUSD": 10.0,  # 1 pip = $0.10 per 1 oz, but std lot = 100 oz → $10
    "XAGUSD": 50.0,   # 1 pip = $0.01 per 1 oz, std lot = 5000 oz → $50
}

# Pip size (how many decimal places = 1 pip)
PIP_SIZES = {
    "EURUSD": 0.0001, "GBPUSD": 0.0001, "AUDUSD": 0.0001, "NZDUSD": 0.0001,
    "USDJPY": 0.01, "USDCHF": 0.0001, "USDCAD": 0.0001,
    "GBPJPY": 0.01, "EURJPY": 0.01, "AUDJPY": 0.01, "CHFJPY": 0.01,
    "EURGBP": 0.0001, "EURAUD": 0.0001, "EURCHF": 0.0001, "GBPAUD": 0.0001,
    "GBPCAD": 0.0001, "AUDCAD": 0.0001, "AUDNZD": 0.0001, "NZDJPY": 0.01,
    "XAUUSD": 0.1, "XAGUSD": 0.01,
}


def calculate_position(
    equity: float,
    risk_pct: float,
    sl_pips: float = None,
    entry: float = None,
    sl: float = None,
    pair: str = "EURUSD",
) -> dict:
    pair = pair.upper().replace("/", "")
    
    # Calculate SL in pips if entry/sl provided
    pip_size = PIP_SIZES.get(pair, 0.0001)
    if sl_pips is None and entry is not None and sl is not None:
        sl_pips = abs(entry - sl) / pip_size
    
    if sl_pips is None or sl_pips <= 0:
        return {"error": "SL pips must be > 0. Provide --sl-pips or --entry + --sl"}
    
    risk_amount = equity * (risk_pct / 100)
    pip_value = PIP_VALUES.get(pair, 10.0)
    
    # Position size in standard lots
    lot_size = risk_amount / (sl_pips * pip_value)
    
    # Different lot types
    mini_lots = lot_size * 10     # 10,000 units
    micro_lots = lot_size * 100   # 1,000 units
    units = lot_size * 100_000
    
    # Risk-Reward scenarios
    rr_scenarios = {}
    for rr in [1.0, 1.5, 2.0, 3.0, 5.0]:
        tp_pips = sl_pips * rr
        potential_profit = tp_pips * pip_value * lot_size
        rr_scenarios[f"1:{rr}"] = {
            "tp_pips": round(tp_pips, 1),
            "potential_profit": round(potential_profit, 2),
        }
    
    result = {
        "pair": pair,
        "equity": equity,
        "risk_pct": risk_pct,
        "risk_amount": round(risk_amount, 2),
        "sl_pips": round(sl_pips, 1),
        "pip_value_per_lot": pip_value,
        "position_size": {
            "standard_lots": round(lot_size, 2),
            "mini_lots": round(mini_lots, 2),
            "micro_lots": round(micro_lots, 2),
            "units": round(units, 0),
        },
        "rr_scenarios": rr_scenarios,
    }
    
    if entry is not None and sl is not None:
        direction = "BUY" if entry > sl else "SELL"
        result["entry"] = entry
        result["sl"] = sl
        result["direction"] = direction
        for rr_label, rr_data in rr_scenarios.items():
            rr_val = float(rr_label.split(":")[1])
            if direction == "BUY":
                tp = entry + (abs(entry - sl) * rr_val)
            else:
                tp = entry - (abs(entry - sl) * rr_val)
            rr_data["tp_price"] = round(tp, 5)
    
    return result


def format_report(r: dict) -> str:
    if "error" in r:
        return f"ERROR: {r['error']}"
    
    lines = [
        f"═══════════════════════════════════════════",
        f"  POSITION SIZE CALCULATOR",
        f"═══════════════════════════════════════════",
        f"  Pair           : {r['pair']}",
        f"  Equity         : ${r['equity']:,.2f}",
        f"  Risk           : {r['risk_pct']}% (${r['risk_amount']:,.2f})",
        f"  Stop Loss      : {r['sl_pips']} pips",
    ]
    if "entry" in r:
        lines += [
            f"  Entry          : {r['entry']}",
            f"  SL Price       : {r['sl']}",
            f"  Direction      : {r['direction']}",
        ]
    lines += [
        f"",
        f"── POSITION SIZE ──────────────────────────",
        f"  Standard Lots  : {r['position_size']['standard_lots']}",
        f"  Mini Lots      : {r['position_size']['mini_lots']}",
        f"  Micro Lots     : {r['position_size']['micro_lots']}",
        f"  Units          : {r['position_size']['units']:,.0f}",
        f"",
        f"── RISK-REWARD SCENARIOS ───────────────────",
    ]
    for label, data in r["rr_scenarios"].items():
        tp_info = f"  TP: {data.get('tp_price', 'N/A')}" if "tp_price" in data else ""
        lines.append(f"  {label}  →  TP: {data['tp_pips']} pips  |  Profit: ${data['potential_profit']:,.2f}{tp_info}")
    
    lines.append(f"═══════════════════════════════════════════")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Position Size Calculator")
    parser.add_argument("--equity", type=float, required=True, help="Account equity in USD")
    parser.add_argument("--risk", type=float, default=1.0, help="Risk percentage (default: 1)")
    parser.add_argument("--sl-pips", type=float, help="Stop loss in pips")
    parser.add_argument("--entry", type=float, help="Entry price")
    parser.add_argument("--sl", type=float, help="Stop loss price")
    parser.add_argument("--pair", type=str, default="EURUSD", help="Currency pair")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    result = calculate_position(args.equity, args.risk, args.sl_pips, args.entry, args.sl, args.pair)
    
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(format_report(result))


if __name__ == "__main__":
    main()
