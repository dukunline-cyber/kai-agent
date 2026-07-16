# Examples

## connect_uniswap.py — end-to-end

Install MetaMask from the Chrome Web Store → import a seed once (persistent
profile keeps it) → connect to Uniswap behind Cloudflare via the stealth core.
Stops at "connected"; no signing/tx (real tx must go through `governed_sign`).

```bash
export MM_SEED="word1 word2 ... word12"      # a wallet YOU control (use a burner)
export MM_PASSWORD="a-strong-password"
export AGENT_BROWSER_PROFILE=~/.agent/uniswap-profile
export MM_PROXY="http://user:pass@residential-host:port"   # recommended for Cloudflare
python examples/connect_uniswap.py
```

Secrets come from env only — never hardcoded. The profile dir stores the
unlocked wallet on disk; treat it as a secret. MetaMask's onboarding DOM drifts
between versions; selector lists live in `_MM` at the top of the script and are
tolerant (steps skip if a screen isn't shown).
