#!/usr/bin/env python3
"""Bugcrowd scope extractor (reusable). proven 2026-06-26.
Usage:
  bc_recon.py list                 # daftar program yg accessible
  bc_recon.py scope <slug>         # extract scope 1 program
Env: source credentials/bugcrowd.env dulu (BUGCROWD_COOKIE wajib).
Cookie/CSRF ga pernah di-print.
"""
import os,sys,asyncio,json
from playwright.async_api import async_playwright

CK=os.environ.get('BUGCROWD_COOKIE','')
if not CK:
    print('ERR: BUGCROWD_COOKIE kosong. source credentials/bugcrowd.env dulu.'); sys.exit(1)
cookies=[]
for part in CK.split(';'):
    part=part.strip()
    if '=' in part:
        n,v=part.split('=',1)
        cookies.append({'name':n.strip(),'value':v.strip(),'domain':'.bugcrowd.com','path':'/'})

UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36'

async def newctx(pw):
    b=await pw.chromium.launch(headless=True,executable_path='/usr/bin/google-chrome',args=['--no-sandbox','--disable-dev-shm-usage'])
    ctx=await b.new_context(user_agent=UA)
    await ctx.add_cookies(cookies)
    return b,ctx

async def list_programs():
    found=[]
    async with async_playwright() as pw:
        b,ctx=await newctx(pw); pg=await ctx.new_page()
        async def on_resp(r):
            try:
                if 'json' in r.headers.get('content-type','') and 'engagement' in r.url:
                    d=await r.json()
                    items = d.get('engagements') or d.get('data') or (d if isinstance(d,list) else [])
                    for it in (items if isinstance(items,list) else []):
                        if isinstance(it,dict):
                            found.append({'name':it.get('name'),'slug':it.get('briefUrl') or it.get('slug') or it.get('code'),'rew':it.get('rewardRangeSummary') or it.get('maxReward')})
            except: pass
        pg.on('response',on_resp)
        for url in ['https://bugcrowd.com/engagements','https://bugcrowd.com/programs']:
            try:
                await pg.goto(url,wait_until='networkidle',timeout=45000); await pg.wait_for_timeout(3000)
            except Exception as e: print('[!]',url,str(e)[:60])
        await b.close()
    seen=set(); uniq=[]
    for f in found:
        k=f.get('slug') or f.get('name')
        if k and k not in seen: seen.add(k); uniq.append(f)
    print(json.dumps(uniq,indent=1)[:4000]); print(f'\n[*] total program: {len(uniq)}')

async def scope(slug):
    slug=slug.strip('/').split('/')[-1]
    api=[]; bodies=[]
    async with async_playwright() as pw:
        b,ctx=await newctx(pw); pg=await ctx.new_page()
        async def on_resp(r):
            try:
                if 'json' in r.headers.get('content-type','') and 'fresh' not in r.url:
                    api.append((r.status,r.url))
                    if any(k in r.url for k in ['target','scope','change']):
                        bodies.append((r.url,(await r.text())[:3500]))
            except: pass
        pg.on('response',on_resp)
        await pg.goto(f'https://bugcrowd.com/engagements/{slug}',wait_until='networkidle',timeout=45000)
        await pg.wait_for_timeout(4000)
        for sel in ['text=Scope','text=Targets','a:has-text("Scope")','[href*=scope]']:
            try:
                el=await pg.query_selector(sel)
                if el: await el.click(); await pg.wait_for_timeout(2500); break
            except: pass
        print('[*] final url:',pg.url)
        await b.close()
    print(f'[*] api calls: {len(api)}')
    for u,bd in bodies:
        print(f'\n=== {u}\n{bd[:2500]}')

if __name__=='__main__':
    if len(sys.argv)<2: print(__doc__); sys.exit(0)
    cmd=sys.argv[1]
    if cmd=='list': asyncio.run(list_programs())
    elif cmd=='scope' and len(sys.argv)>2: asyncio.run(scope(sys.argv[2]))
    else: print(__doc__)
