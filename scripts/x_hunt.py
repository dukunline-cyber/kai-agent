#!/usr/bin/env python3
"""X bug bounty scanner via twscrape."""
import asyncio, sys, os, json, re
from twscrape import API, AccountsPool

AUTH_TOKEN = '3b54a9d0ca49ad313117585f790b4d18555665e4'
CT0 = '441677cc301d8e8221dd112d97c7b064afc260b292b783b7a0134dcaac7f78d0525100105babdf6923dd10e713e135877063aba192d7f8ad3a3bc21346a35b003b7b45c17c1f9bd26833bf6a4909ba64'
DB = os.path.expanduser('~/ai-agent/data/xhunt/accounts.db')

async def setup():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    api = API(DB)
    # Add account with cookies only (skip login)
    cookies = f'auth_token={AUTH_TOKEN}; ct0={CT0}'
    await api.pool.add_account(
        username='eskrimabc',
        password='dummy',
        email='dummy@dummy.com',
        email_password='dummy',
        cookies=cookies,
    )
    # Mark active
    accs = await api.pool.get_all()
    print(f'accounts: {len(accs)}', file=sys.stderr)
    for a in accs:
        print(f'  {a.username} active={a.active}', file=sys.stderr)
    return api

async def search(query, limit=40):
    api = await setup()
    out = []
    async for tw in api.search(query, limit=limit):
        out.append({
            'id': str(tw.id),
            'user': tw.user.username,
            'name': tw.user.displayname,
            'text': tw.rawContent,
            'date': tw.date.isoformat() if tw.date else '',
            'fav': tw.likeCount,
            'rt': tw.retweetCount,
            'reply': tw.replyCount,
            'views': tw.viewCount or 0,
            'url': tw.url,
        })
    return out

if __name__ == '__main__':
    q = sys.argv[1] if len(sys.argv) > 1 else 'bug bounty program'
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    print(f'# Q: {q} | limit: {limit}', file=sys.stderr)
    tweets = asyncio.run(search(q, limit=limit))
    print(f'# {len(tweets)} tweets', file=sys.stderr)
    for t in tweets:
        print(json.dumps(t, ensure_ascii=False))
