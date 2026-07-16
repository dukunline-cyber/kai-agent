#!/usr/bin/env python3
"""
Parse raw HTML dari ForexFactory jadi data terstruktur (events, date, impact)
"""

import re
import json
import sys
from datetime import datetime, timedelta

RAW_SAMPLE = """
Forums
Trades
News
Calendar
Market
Brokers
9:23pm
Search
Create Account
Login
Navigation
«
‹
Jul 2026
›
	S	M	T	W	T	F	S

	
28
	
29
	
30
	
1
	
2
	
3
	
4


	
5
	
6
	
7
	
8
	
9
	
10
	
11


	
12
	
13
	
14
	
15
	
16
	
17
	
18


	
19
	
20
	
21
	
22
	
23
	
24
	
25


	
26
	
27
	
28
	
29
	
30
	
31

"""

print('Raw sample length:', len(RAW_SAMPLE))
print()

# Parse calendar - cari baris yang ada angka + nama hari
lines = RAW_SAMPLE.split('\n')
print('Total lines:', len(lines))

# Cari pola tanggal (angka doang)
dates = []
for line in lines:
    line = line.strip()
    if line and line.isdigit():
        dates.append(line)

print('Dates found:', dates)
print('Count:', len(dates))

# Simpan ke JSON
output = {
    'source': 'ForexFactory',
    'scrape_time': datetime.now().isoformat(),
    'raw_length': len(RAW_SAMPLE),
    'dates_found': len(dates),
    'dates': dates[:10],
}

with open('/tmp/forexfactory_sample.json', 'w') as f:
    json.dump(output, f, indent=2)

print('\nSaved to /tmp/forexfactory_sample.json')
