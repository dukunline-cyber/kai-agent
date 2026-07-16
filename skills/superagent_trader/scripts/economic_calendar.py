#!/usr/bin/env python3.12
"""
Superagent Trader — Economic Calendar Alert
Check high-impact economic events for today/this week.

Usage:
    python economic_calendar.py           # today's events
    python economic_calendar.py --week    # this week
    python economic_calendar.py --currency USD,EUR
"""
import argparse, json
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup


def fetch_calendar_events(days_ahead: int = 0, currencies: list = None) -> list:
    """Fetch economic calendar from multiple free sources."""
    events = []
    
    # Method 1: Use nager.at for public holidays + manual high-impact events
    # Method 2: Scrape from ForexFactory (backup)
    try:
        events = _fetch_from_investing(days_ahead, currencies)
    except Exception as e:
        print(f"Primary source failed: {e}")
        events = _get_known_recurring_events(days_ahead, currencies)
    
    return events


def _fetch_from_investing(days_ahead: int, currencies: list) -> list:
    """Scrape economic calendar from investing.com API."""
    today = datetime.now()
    target = today + timedelta(days=days_ahead)
    
    url = "https://economic-calendar.tradingview.com/events"
    params = {
        "from": today.strftime("%Y-%m-%dT00:00:00.000Z"),
        "to": (today + timedelta(days=max(days_ahead, 1))).strftime("%Y-%m-%dT23:59:59.999Z"),
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Origin": "https://www.tradingview.com",
    }
    
    resp = requests.get(url, params=params, headers=headers, timeout=10)
    data = resp.json() if resp.status_code == 200 else []
    
    events = []
    for item in data:
        if not isinstance(item, dict):
            continue
        importance = item.get("importance", 0)
        if importance < 1:  # Skip low impact
            continue
        
        currency = item.get("currency", "")
        if currencies and currency not in currencies:
            continue
        
        impact = "🔴 HIGH" if importance >= 2 else "🟡 MEDIUM" if importance >= 1 else "🟢 LOW"
        
        event_time = item.get("date", "")
        if event_time:
            try:
                dt = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
                # Convert to WIB (UTC+7)
                dt_wib = dt + timedelta(hours=7)
                time_str = dt_wib.strftime("%H:%M WIB")
                date_str = dt_wib.strftime("%Y-%m-%d")
            except:
                time_str = event_time
                date_str = today.strftime("%Y-%m-%d")
        else:
            time_str = "TBD"
            date_str = today.strftime("%Y-%m-%d")
        
        events.append({
            "date": date_str,
            "time": time_str,
            "currency": currency,
            "event": item.get("title", "Unknown"),
            "impact": impact,
            "importance": importance,
            "actual": item.get("actual", ""),
            "forecast": item.get("forecast", ""),
            "previous": item.get("previous", ""),
        })
    
    events.sort(key=lambda e: (e["date"], e.get("importance", 0)), reverse=False)
    return events


def _get_known_recurring_events(days_ahead: int, currencies: list) -> list:
    """Fallback: Return known high-impact recurring events."""
    today = datetime.now()
    target = today + timedelta(days=days_ahead)
    day_name = target.strftime("%A")
    day_of_month = target.day
    
    events = []
    
    # NFP - First Friday of month
    if day_name == "Friday" and day_of_month <= 7:
        events.append({
            "date": target.strftime("%Y-%m-%d"),
            "time": "19:30 WIB",
            "currency": "USD",
            "event": "Non-Farm Payrolls (NFP)",
            "impact": "🔴 HIGH",
            "importance": 3,
            "note": "⚠ HINDARI TRADING ±30 MENIT"
        })
        events.append({
            "date": target.strftime("%Y-%m-%d"),
            "time": "19:30 WIB",
            "currency": "USD",
            "event": "Unemployment Rate",
            "impact": "🔴 HIGH",
            "importance": 3,
        })
    
    # Common weekly events
    known_weekly = {
        "Monday": [
            {"time": "Varies", "currency": "Various", "event": "Manufacturing PMI", "impact": "🟡 MEDIUM"},
        ],
        "Tuesday": [
            {"time": "Varies", "currency": "AUD", "event": "RBA Rate Decision (if scheduled)", "impact": "🔴 HIGH"},
        ],
        "Wednesday": [
            {"time": "Varies", "currency": "USD", "event": "ADP Employment / FOMC (if scheduled)", "impact": "🔴 HIGH"},
        ],
        "Thursday": [
            {"time": "19:30 WIB", "currency": "USD", "event": "Initial Jobless Claims", "impact": "🟡 MEDIUM"},
        ],
        "Friday": [
            {"time": "Varies", "currency": "Various", "event": "Services PMI / Retail Sales", "impact": "🟡 MEDIUM"},
        ],
    }
    
    for event in known_weekly.get(day_name, []):
        if currencies and event["currency"] not in currencies and event["currency"] != "Various":
            continue
        events.append({
            "date": target.strftime("%Y-%m-%d"),
            **event,
            "note": "Recurring weekly event (check forexfactory.com for exact schedule)"
        })
    
    return events


def format_report(events: list, period: str = "today") -> str:
    if not events:
        return f"✅ Tidak ada event high-impact {period}. Aman untuk trading!"
    
    lines = [
        f"═══════════════════════════════════════════",
        f"  ECONOMIC CALENDAR — {period.upper()}",
        f"═══════════════════════════════════════════",
    ]
    
    current_date = ""
    for e in events:
        if e["date"] != current_date:
            current_date = e["date"]
            lines.append(f"\n── {current_date} ──────────────────────────")
        
        lines.append(f"  {e['impact']}  {e.get('time', 'TBD')}  [{e['currency']}]  {e['event']}")
        
        if e.get("forecast") or e.get("previous"):
            extra = []
            if e.get("forecast"): extra.append(f"Forecast: {e['forecast']}")
            if e.get("previous"): extra.append(f"Previous: {e['previous']}")
            if e.get("actual"): extra.append(f"Actual: {e['actual']}")
            lines.append(f"           {' | '.join(extra)}")
        
        if e.get("note"):
            lines.append(f"           ⚠ {e['note']}")
    
    lines.append(f"\n═══════════════════════════════════════════")
    lines.append(f"  💡 TIPS: Hindari trading ±30 menit sebelum/sesudah event 🔴 HIGH")
    lines.append(f"  📌 Cek detail: forexfactory.com atau investing.com/economic-calendar")
    lines.append(f"═══════════════════════════════════════════")
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Economic Calendar Alert")
    parser.add_argument("--week", action="store_true", help="Show this week's events")
    parser.add_argument("--days", type=int, default=0, help="Days ahead to check")
    parser.add_argument("--currency", type=str, help="Filter currencies (comma-separated, e.g., USD,EUR)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    currencies = args.currency.upper().split(",") if args.currency else None
    
    if args.week:
        all_events = []
        for d in range(7):
            events = fetch_calendar_events(d, currencies)
            all_events.extend(events)
        period = "this week"
        events = all_events
    else:
        days = args.days
        events = fetch_calendar_events(days, currencies)
        period = "today" if days == 0 else f"in {days} days"
    
    if args.json:
        print(json.dumps(events, indent=2, default=str))
    else:
        print(format_report(events, period))


if __name__ == "__main__":
    main()
