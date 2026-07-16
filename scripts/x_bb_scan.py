#!/usr/bin/env python3
import asyncio, json, os, sys, re
from datetime import datetime, timezone
from twscrape import API

DB = os.path.expanduser('~/ai-agent/data/xhunt/accounts.db')
OUT_DIR = os.path.expanduser('~/ai-agent/data/xhunt')

QUERIES = [
    'bug bounty program launched',
    '"launched a bug bounty" -filter:retweets',
    '"new bug bounty program" -filter:retweets',
    'bug bounty live -filter:retweets',
    '"we are launching" bug bounty',
    'bounty program open scope',
    'hackerone new program',
    'bugcrowd new program',
    'immunefi bounty launched',
    'responsible disclosure program launched',
]

POSITIVE = re.compile(r'\b(launch(ed|ing)?|announc(e|ed|ing)|introduc(e|ing|ed)|live now|open to|invite|onboard|scope|reward|bounty|hackerone|bugcrowd|immunefi|intigriti|yeswehack|synack|hackenproof)\b', re.I)
NEGATIVE = re.compile(r'\b(jailbreak|memecoin|airdrop.*guide|shitcoin|referral|use my code|join my team|hiring|paying \$\d+ for a follow)\b', re.I)
PROGRAM_HINT = re.compile(r'\b(hackerone|bugcrowd|immunefi|intigriti|yeswehack|synack|hackenproof|@Hacker0x01|@Bugcrowd|@immunefi|VDP|vulnerability disclosure|responsible disclosure|bug bounty program|BBP)\b', re.I)

def score(t):
    s = 0
    txt = t['text']
    if POSITIVE.search(txt): s += 2
    if NEGATIVE.search(txt): s -= 3
    if PROGRAM_HINT.search(txt): s += 3
    if 'http' in txt: s += 1
    if t['fav'] > 10: s += 1
    if t['views'] > 500: s += 1
    if t['rt'] > 3: s += 1
    try:
        d = datetime.fromisoformat(t['date'])
        age_d = (datetime.now(timezone.utc) - d).days
        if age_d <= 7: s += 2
        elif age_d <= 30: s += 1
    except Exception:
        pass
    return s

async def main():
    api = API(DB)
    all_tweets = {}
    for q in QUERIES:
        try:
            n = 0
            async for tw in api.search(q, limit=30):
                tid = str(tw.id)
                if tid in all_tweets: continue
                all_tweets[tid] = {'id': tid,'user': tw.user.username,'name': tw.user.displayname,'text': tw.rawContent,'date': tw.date.isoformat() if tw.date else '','fav': tw.likeCount,'rt': tw.retweetCount,'reply': tw.replyCount,'views': tw.viewCount or 0,'url': tw.url,'query': q}
                n += 1
            print(f'  Q="{q}" -> {n} new', file=sys.stderr)
        except Exception as e:
            print(f'  ERR q="{q}": {e}', file=sys.stderr)
    print(f'total unique: {len(all_tweets)}', file=sys.stderr)
    scored = [(score(t), t) for t in all_tweets.values()]
    scored.sort(key=lambda x: -x[0])
    ts = datetime.now().strftime('%Y%m%d_%H%M')
    raw_path = os.path.join(OUT_DIR, f'raw_{ts}.jsonl')
    with open(raw_path, 'w') as f:
        for s, t in scored:
            t['_score'] = s
            f.write(json.dumps(t, ensure_ascii=False) + '\n')
    print(f'saved: {raw_path}', file=sys.stderr)
    print(f'=== TOP 20 ===', file=sys.stderr)
    for s, t in scored[:20]:
        head = t['text'][:180].replace('\n', ' ')
        print(f'[{s}] @{t["user"]} ({t["fav"]}L {t["views"]}V) {t["date"][:10]}', file=sys.stderr)
        print(f'    {head}', file=sys.stderr)
        print(f'    {t["url"]}', file=sys.stderr)

asyncio.run(main())
