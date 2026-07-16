#!/usr/bin/env python3
"""
Scraper fundamental gold - full pipeline
1. Scrape dari ForexFactory
2. Parse events
3. Simpan ke JSON
"""

import asyncio
import sys
import os
from datetime import datetime
import json
import re

sys.path.insert(0, os.path.expanduser('~/ai-agent/skills/browser-agent'))
sys.path.insert(0, os.path.expanduser('~/ai-agent/skills/browser-agent/browser-agent/scripts'))

from browser_engine import BrowserAgent, BrowserConfig, StealthConfig

async def scrape_forexfactory():
    """Ambil data economic calendar dari ForexFactory"""
    cfg = BrowserConfig(
        headless=True,
        cloaking=True,
        stealth=StealthConfig(humanize=True, fingerprint_seed=42069),
        viewport=(1280, 800),
        locale='en-US',
    )
    
    async with BrowserAgent(cfg) as b:
        await b.goto('https://www.forexfactory.com/calendar')
        await asyncio.sleep(3)
        text = await b.read_text()
        return text

async def scrape_investing_gold():
    """Ambil data gold dari Investing.com"""
    cfg = BrowserConfig(
        headless=True,
        cloaking=True,
        stealth=StealthConfig(humanize=True, fingerprint_seed=42069),
        viewport=(1280, 800),
        locale='en-US',
    )
    
    async with BrowserAgent(cfg) as b:
        await b.goto('https://www.investing.com/commodities/gold')
        await asyncio.sleep(3)
        text = await b.read_text()
        return text

def parse_forexfactory(raw):
    """Parse raw HTML jadi list of events"""
    lines = raw.split('\n')
    
    # Cari baris yang ada info event
    events = []
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        
        # Skip navigasi
        if any(x in line for x in ['Forums', 'Trades', 'News', 'Calendar', 'Market', 'Brokers', 'Search', 'Login', 'Navigation']):
            continue
        
        # Simpan
        events.append({
            'line': i,
            'text': line[:200],
        })
    
    return events

def parse_investing_gold(raw):
    """Parse raw HTML jadi data harga"""
    lines = raw.split('\n')
    
    # Cari angka harga
    prices = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Cek kalo angka desimal
        if re.match(r'^[\d,.]+$', line):
            prices.append(line)
    
    return prices

async def main():
    print('=== GOLD FUNDAMENTAL SCRAPER ===')
    
    # 1. ForexFactory
    print('[1] Scraping ForexFactory...')
    try:
        raw = await scrape_forexfactory()
        events = parse_forexfactory(raw)
        
        output = {
            'source': 'ForexFactory',
            'timestamp': datetime.now().isoformat(),
            'raw_length': len(raw),
            'events_count': len(events),
            'events': events[:50],
        }
        
        with open('/tmp/forexfactory_events.json', 'w') as f:
            json.dump(output, f, indent=2)
        print(f'   Saved {len(events)} events to /tmp/forexfactory_events.json')
    except Exception as e:
        print(f'   Error: {e}')
    
    # 2. Investing.com
    print('[2] Scraping Investing.com Gold...')
    try:
        raw = await scrape_investing_gold()
        prices = parse_investing_gold(raw)
        
        output = {
            'source': 'Investing.com',
            'timestamp': datetime.now().isoformat(),
            'raw_length': len(raw),
            'prices_count': len(prices),
            'prices': prices[:20],
        }
        
        with open('/tmp/investing_gold.json', 'w') as f:
            json.dump(output, f, indent=2)
        print(f'   Saved {len(prices)} prices to /tmp/investing_gold.json')
    except Exception as e:
        print(f'   Error: {e}')
    
    print('\n=== DONE ===')

if __name__ == '__main__':
    asyncio.run(main())
