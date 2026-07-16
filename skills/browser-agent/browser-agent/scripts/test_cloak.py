#!/usr/bin/env python3
import asyncio
from browser_engine import BrowserAgent, BrowserConfig, StealthConfig

async def main():
    cfg = BrowserConfig(
        headless=True,
        stealth=StealthConfig(humanize=False),
    )
    async with BrowserAgent(cfg) as b:
        print('Browser started', flush=True)
        await b.goto('https://example.com')
        title = await b.title()
        print(f'Page title: {title}', flush=True)

asyncio.run(main())
