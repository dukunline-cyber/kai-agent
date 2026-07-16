#!/usr/bin/env bash
# recon.sh — bug bounty recon pipeline (hardened)
# usage: recon.sh <domain> [--deep]
set -uo pipefail
TARGET="${1:-}"
DEEP="${2:-}"
[ -z "$TARGET" ] && { echo "usage: $0 <domain> [--deep]"; exit 1; }

TS=$(date +%Y%m%d-%H%M%S)
ROOT="$HOME/ai-agent/bughunt/targets/$TARGET"
RUN="$ROOT/recon-$TS"
mkdir -p "$RUN"; cd "$RUN"

log() { echo "[$(date +%H:%M:%S)] $*" | tee -a recon.log; }
log "target=$TARGET deep=$DEEP run=$RUN"

# 1. subdomain enum: subfinder + crt.sh fallback
log "step 1/6 subdomain enum (subfinder + crt.sh)"
subfinder -d "$TARGET" -silent -all > subs-subfinder.txt 2>>recon.log || true
curl -s --max-time 30 "https://crt.sh/?q=%25.${TARGET}&output=json" \
  | python3 -c "import sys,json;\nd=json.load(sys.stdin);\n[print(x.strip().lower()) for r in d for x in r.get('name_value','').split(chr(10)) if x and '*' not in x]" 2>/dev/null > subs-crtsh.txt || true
# also include hosts from gau/wayback historical (run early to harvest subs)
echo "$TARGET" | gau --threads 5 --subs 2>/dev/null | head -8000 > urls-gau.txt &
echo "$TARGET" | waybackurls 2>/dev/null | head -8000 > urls-wayback.txt &
wait
awk -F/ '{print $3}' urls-gau.txt urls-wayback.txt 2>/dev/null | sed 's/:[0-9]*$//' | grep -iE "\.${TARGET}$|^${TARGET}$" > subs-urls.txt || true
cat subs-subfinder.txt subs-crtsh.txt subs-urls.txt 2>/dev/null | sort -u > subs-passive.txt
log "  subs-passive.txt: $(wc -l <subs-passive.txt) lines (subfinder=$(wc -l <subs-subfinder.txt) crtsh=$(wc -l <subs-crtsh.txt) urls=$(wc -l <subs-urls.txt))"
[ ! -s subs-passive.txt ] && echo "$TARGET" > subs-passive.txt && log "  fallback: using root domain only"

# 2. dns resolve
log "step 2/6 dnsx resolve"
dnsx -l subs-passive.txt -silent -a -resp-only > dns-ips.txt 2>>recon.log || true
dnsx -l subs-passive.txt -silent > subs-live.txt 2>>recon.log || true
log "  subs-live.txt: $(wc -l <subs-live.txt) | unique IPs: $(sort -u dns-ips.txt | wc -l)"
touch subs-live.txt

# 3. http probe
log "step 3/6 httpx probe"
touch httpx-full.txt web-urls.txt
if [ -s subs-live.txt ]; then
  /usr/local/bin/httpx -l subs-live.txt -silent -title -sc -tech-detect -web-server -ip \
    -follow-redirects -timeout 10 -rl 100 -no-color -o httpx-full.txt 2>>recon.log || true
  awk '{print $1}' httpx-full.txt | sort -u > web-urls.txt
fi
log "  web-urls.txt: $(wc -l <web-urls.txt) live web endpoints"

# 4. historical urls already harvested in step 1
cat urls-gau.txt urls-wayback.txt 2>/dev/null | sort -u > urls-historical.txt
log "step 4/6 historical URLs: $(wc -l <urls-historical.txt)"

# 5. nuclei scan
log "step 5/6 nuclei (info,low,medium)"
touch nuclei-findings.txt
if [ -s web-urls.txt ]; then
  nuclei -l web-urls.txt -severity info,low,medium -silent -rl 50 -c 25 \
    -exclude-tags intrusive,dos,fuzz \
    -o nuclei-findings.txt 2>>recon.log || true
fi
log "  nuclei-findings.txt: $(wc -l <nuclei-findings.txt) findings"

# 6. summary
log "step 6/6 summary"
{
  echo "target: $TARGET"
  echo "timestamp: $TS"
  echo "subs-passive: $(wc -l <subs-passive.txt)"
  echo "subs-live: $(wc -l <subs-live.txt)"
  echo "web-urls: $(wc -l <web-urls.txt)"
  echo "historical-urls: $(wc -l <urls-historical.txt)"
  echo "nuclei-findings: $(wc -l <nuclei-findings.txt)"
  echo
  echo "### live web endpoints"
  cat httpx-full.txt 2>/dev/null | head -50
  echo
  echo "### top tech"
  grep -oP '\[[^\]]+\]' httpx-full.txt 2>/dev/null | sort | uniq -c | sort -rn | head -15
  echo
  echo "### interesting nuclei findings"
  grep -iE 'critical|high|medium|exposed|disclosure|takeover|default|admin|debug|trace|backup|\.git|\.env|swagger|graphql|api-docs|jwt|cors' nuclei-findings.txt 2>/dev/null | head -30
} > SUMMARY.md

log "DONE. Result: $RUN/SUMMARY.md"
