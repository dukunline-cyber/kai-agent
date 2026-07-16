---
name: superagent_trader
description: Comprehensive forex technical analysis superagent. Use when analyzing forex markets, identifying trade setups, building trading plans, or discussing technical analysis methods including Smart Money Concepts, price action, indicators, and risk management.
---

# Superagent Trader — Forex Technical Analysis Framework

## When to Use
- User asks to **analyze a forex pair** → run `technical_analysis.py` + `chart_generator.py`
- User asks to **scan the market** → run `market_scanner.py`
- User asks about **position sizing** → run `position_calculator.py`
- User asks to **backtest a strategy** → run `backtesting.py`
- User asks about **economic calendar / news** → run `economic_calendar.py`
- User asks about **pair correlation** → run `correlation_matrix.py`
- User wants a **trade journal** → run `trade_journal.py`
- User asks about TA concepts (SMC, price action, indicators, etc.) → reference files in `references/`

## Quick Start — Scripts

All scripts use `python3.12` (packages installed via pip: yfinance, pandas-ta, matplotlib, mplfinance, openpyxl).

### 1. Technical Analysis (Full Pair Analysis)
```bash
python3.12 skills/superagent_trader/scripts/technical_analysis.py EURUSD H4
python3.12 skills/superagent_trader/scripts/technical_analysis.py GBPJPY D
```
**Output:** Trend, RSI, MACD, Stochastic, Bollinger Bands, ATR, ADX, divergence, key S/R levels, ATR-based SL, confluence score, and overall signal (STRONG BUY → STRONG SELL).

### 2. Chart Generator (Visual Chart + Indicators)
```bash
python3.12 skills/superagent_trader/scripts/chart_generator.py EURUSD H4 /tmp/chart.png
```
**Output:** Dark-theme candlestick chart with EMA 21, SMA 50, Bollinger Bands, RSI panel, MACD panel. Upload to Slack.

### 3. Position Size Calculator
```bash
python3.12 skills/superagent_trader/scripts/position_calculator.py --equity 10000 --risk 1 --sl-pips 50 --pair EURUSD
python3.12 skills/superagent_trader/scripts/position_calculator.py --equity 5000 --risk 2 --entry 1.0850 --sl 1.0800 --pair EURUSD
```
**Output:** Lot size (standard/mini/micro), risk amount, R:R scenarios with TP prices.

### 4. Backtesting Framework
```bash
python3.12 skills/superagent_trader/scripts/backtesting.py EURUSD D --strategy ema_cross --period 365 --rr 2.0
```
**Strategies:** `ema_cross`, `rsi_ob`, `macd_cross`, `bb_bounce`
**Output:** Win rate, total P&L, profit factor, expectancy, max drawdown, consecutive streaks.

### 5. Trade Journal (Excel)
```bash
python3.12 skills/superagent_trader/scripts/trade_journal.py /tmp/Trade_Journal.xlsx --name "Trader"
```
**Output:** Excel with 4 sheets — Trade Log (dropdowns + auto formulas), Dashboard (auto stats), Weekly Review, Pre-Trade Checklist.

### 6. Economic Calendar
```bash
python3.12 skills/superagent_trader/scripts/economic_calendar.py           # today
python3.12 skills/superagent_trader/scripts/economic_calendar.py --week    # this week
python3.12 skills/superagent_trader/scripts/economic_calendar.py --currency USD,EUR
```
**Output:** High/medium impact events with times in WIB, forecast vs previous values.

### 7. Pair Correlation Matrix
```bash
python3.12 skills/superagent_trader/scripts/correlation_matrix.py
python3.12 skills/superagent_trader/scripts/correlation_matrix.py EURUSD GBPUSD USDJPY --chart /tmp/corr.png
```
**Output:** Correlation matrix + exposure alerts for highly correlated pairs. Optional heatmap chart.

### 8. Multi-Pair Market Scanner
```bash
python3.12 skills/superagent_trader/scripts/market_scanner.py --tf H4
python3.12 skills/superagent_trader/scripts/market_scanner.py --pairs EURUSD,GBPUSD,USDJPY --tf D
```
**Output:** All pairs ranked by signal strength with RSI, ADX, MACD status, top BUY/SELL picks.

## Workflow — Full Analysis Request

When user says "analisa EUR/USD" or similar:

1. Run `technical_analysis.py {pair} {tf}` → get text report + JSON
2. Run `chart_generator.py {pair} {tf} /tmp/chart.png` → get chart image
3. Upload chart to Slack, post analysis summary as formatted message
4. If user asks follow-up → use position calculator, backtest, etc.

## Supported Pairs
Major: EURUSD, GBPUSD, USDJPY, USDCHF, AUDUSD, NZDUSD, USDCAD
Cross: GBPJPY, EURJPY, EURGBP, AUDJPY, CHFJPY, EURAUD, GBPAUD
Metals: XAUUSD (Gold), XAGUSD (Silver)
Indices: DXY, US30, NAS100, SPX500

## Supported Timeframes
M15, M30, H1, H4, D (Daily), W (Weekly)

## Knowledge Base (references/)

Detailed TA methodology docs (Bahasa Indonesia):

| File | Topic |
|------|-------|
| `01_market_structure.md` | Trend, BOS, ChoCH, S/R, Swing Points |
| `02_smart_money.md` | ICT: Order Blocks, FVG, Liquidity, Premium/Discount |
| `03_price_action.md` | 16+ Candlestick patterns (single/double/triple) |
| `04_indicators.md` | MA, MACD, RSI, Stochastic, BB, ATR, Ichimoku, ADX, OBV |
| `05_chart_patterns.md` | H&S, Double Top/Bottom, Triangles, Fibonacci |
| `06_harmonic_elliott.md` | Gartley, Butterfly, Bat, Crab + Elliott Wave |
| `07_wyckoff.md` | Accumulation/Distribution phases, 3 laws |
| `08_multi_timeframe.md` | 3-TF approach, top-down rules |
| `09_risk_management.md` | Position sizing, SL/TP, golden rules |
| `10_trading_plan.md` | Pre-trade checklist, sessions (WIB), journal |

## Key Analysis Rules

1. **Always top-down:** Start from higher TF bias, drill down to entry TF
2. **Min confluence 3:** Need ≥3 confirming factors before signaling a trade
3. **Risk first:** Never suggest trade without SL/TP and position sizing
4. **Context > Pattern:** Candlestick/chart patterns only valid at key levels
5. **Disclaimer always:** This is educational/analytical — not financial advice
