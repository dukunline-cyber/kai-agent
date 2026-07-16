#!/usr/bin/env python3
"""OWASP Top 10 2025 — auto study material generator.
Reads track_82_raw.json, generates cheat sheet + per-challenge study guides."""

import json, os, sys
from datetime import datetime

OUT = os.path.expanduser("~/ai-agent/data/htb-progress/owasp-2025")
os.makedirs(OUT, exist_ok=True)

# ── OWASP Top 10:2025 knowledge base ──
A01 = {
    "id": "A01:2025",
    "title": "Broken Access Control",
    "what": "Pengguna bisa mengakses resource atau fungsi yang seharusnya di luar izin mereka.",
    "patterns": ["IDOR", "Missing function-level checks", "Force browsing", "CORS misconfig", "JWT tampering"],
    "tests": [
        "Ganti user ID di URL/body request",
        "Akses endpoint admin tanpa login",
        "Ubah role/group di parameter",
        "Test CORS headers — origin sembarang",
        "Decode & ubah payload JWT tanpa signature"
    ],
    "tools": ["Burp Suite", "curl", "jwt_tool"]
}

A02 = {
    "id": "A02:2025",
    "title": "Cryptographic Failures",
    "what": "Data sensitif exposed atau crypto lemah — tidak pake TLS, hardcoded keys, weak hashing.",
    "patterns": ["Plaintext transmission", "Weak TLS version", "Hardcoded keys/secrets", "MD5/SHA1 for passwords", "Missing HSTS"],
    "tests": [
        "Cek apakah ada http:// (bukan https)",
        "SSLScan / testssl.sh — cek cipher suite",
        "Grep source code untuk base64/rot13 data sensitif",
        "Cek cookie — Secure/HttpOnly/HSTS header"
    ],
    "tools": ["testssl.sh", "SSLScan", "grep"]
}

A03 = {
    "id": "A03:2025",
    "title": "Injection",
    "what": "User input ditafsirkan sebagai kode — SQLi, NoSQLi, OS command, LDAP, XSS, SSTI.",
    "patterns": ["SQL injection", "NoSQL injection", "Command injection", "XSS", "SSTI", "LDAP injection"],
    "tests": [
        "' OR 1=1--",
        "' UNION SELECT 1,2,3--",
        "; id",
        "; ls -la",
        "$where: '1; return true'",
        "<script>alert(1)</script>",
        "{{7*7}}",
        "${7*7}"
    ],
    "tools": ["sqlmap", "Burp Suite", "ffuf"]
}

A04 = {
    "id": "A04:2025",
    "title": "Insecure Design",
    "what": "Desain aplikasi cacat — missing rate limiting, business logic flaws, workflow bypass.",
    "patterns": ["Race condition", "Missing rate limiting", "Logic bypass", "Workflow abuse", "Integer overflow"],
    "tests": [
        "Kirim request racing (concurrent) ke endpoint critical",
        "Cek apakah bisa abuse workflow (skip steps)",
        "Test negative quantities, huge numbers",
        "Cek reset password flow — bisa bypass?"
    ],
    "tools": ["Burp Suite", "Turbo Intruder", "custom script"]
}

A05 = {
    "id": "A05:2025",
    "title": "Security Misconfiguration",
    "what": "Konfigurasi nggak aman — default creds, open endpoints, verbose errors, unnecessary features.",
    "patterns": ["Default credentials", "Open admin panels", "Verbose error messages", "Sample apps enabled", "Directory listing"],
    "tests": [
        "Check /admin, /actuator, /console, /.env, /.git",
        "Try admin/admin, root/root, guest/guest",
        "Trigger error → lihat stack trace",
        "Dirbust untuk hidden endpoints"
    ],
    "tools": ["ffuf", "dirb", "gobuster"]
}

A06 = {
    "id": "A06:2025",
    "title": "Vulnerable and Outdated Components",
    "what": "Library/component usang dengan CVE known.",
    "patterns": ["Known CVE", "Unsupported version", "End-of-life software", "Unpatched dependency"],
    "tests": [
        "Fingerprint tech stack (Wappalyzer / manual)",
        "Cari versi di header, comment, error",
        "Lookup CVE di NVD / Exploit-DB",
        "Test PoC exploit"
    ],
    "tools": ["Wappalyzer", "nuclei", "searchsploit"]
}

A07 = {
    "id": "A07:2025",
    "title": "Identification and Authentication Failures",
    "what": "Auth lemah — brute-force possible, missing MFA, session fixation, credential stuffing.",
    "patterns": ["Weak password policy", "No rate limiting on login", "Session fixation", "Missing MFA", "Token leak"],
    "tests": [
        "Brute force login dengan wordlist pendek",
        "Cek session token before/after login",
        "Test credential stuffing dengan known leak",
        "Cek token di URL"
    ],
    "tools": ["hydra", "Burp Intruder", "custom script"]
}

A08 = {
    "id": "A08:2025",
    "title": "Software and Data Integrity Failures",
    "what": "Kode/data dari source untrusted — insecure deserialization, unsigned updates, CI/CD pipeline injection.",
    "patterns": ["Insecure deserialization", "Unsigned firmware/plugin updates", "CI/CD injection", "Missing signature verification"],
    "tests": [
        "Cek input deserialization (pickle, yaml, Java serialized)",
        "Coba inject payload serialized object",
        "Cek update mechanism — signed?",
        "Test dependency confusion / typosquatting"
    ],
    "tools": ["ysoserial", "python pickletools", "custom script"]
}

A09 = {
    "id": "A09:2025",
    "title": "Security Logging and Monitoring Failures",
    "what": "No logging, no alerts, deteksi breach impossible.",
    "patterns": ["No audit trail", "Logs tidak ke SIEM", "No rate-throttle alerts", "PII logged plaintext"],
    "tests": [
        "Trigger errors → cek apakah response ada log ID",
        "Cek header — X-Request-ID?",
        "Kirim payload malformed → cek response time (WAF?)",
        "Kirim banyak request → ada rate limit?"
    ],
    "tools": ["curl", "custom script"]
}

A10 = {
    "id": "A10:2025",
    "title": "Server-Side Request Forgery (SSRF)",
    "what": "Server fetch URL dari input pengguna — bisa internal recon, cloud metadata theft.",
    "patterns": ["Profile picture upload via URL", "Webhook callback", "PDF/image generator", "Import from URL", "Health check endpoint"],
    "tests": [
        "http://169.254.169.254/latest/meta-data/",
        "http://localhost:8080/admin",
        "file:///etc/passwd",
        "blind: callback ke webhook lo",
        "gopher:// untuk internal SMTP"
    ],
    "tools": ["Burp Collaborator", "requestbin", "custom listener"]
}

OWASP = [A01, A02, A03, A04, A05, A06, A07, A08, A09, A10]

# ── Challenge name → category mapping (best guess) ──
CHALLENGE_MAP = {
    "Criticalops": A01,          # critical operations → access control
    "NovaEnergy": A02,           # energy → crypto (smart grid? sensitive data)
    "Blackout Ops": A05,         # blackout → misconfiguration (operational shutdown)
    "Spellbound Servants": A08,  # spellbound → deserialization?? "spell" = magic bytes
    "CDNio": A10,                # CDN → SSRF (CDN internal endpoints)
    "PumpkinSpice": A03,         # spice → injection (SQLi/XSS themed)
    "Volnaya Forums": A03,       # forums → SQLi (classic forum injection)
    "POP Restaurant": A08,       # POP chain = deserialization
    "NexusSeven": A04,           # nexus → complex system → design flaw
    "Sattrack": A10              # satellite tracking → SSRF (data feeds from sat)
}

# ── Generate master cheat sheet ──
def gen_cheatsheet():
    print("[*] Generating master cheat sheet...")
    lines = []
    lines.append("# OWASP Top 10:2025 — Master Cheat Sheet")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("")
    for cat in OWASP:
        lines.append(f"## {cat['id']}: {cat['title']}")
        lines.append(f"**Apa:** {cat['what']}")
        lines.append("")
        lines.append("**Pola umum:**")
        for p in cat['patterns']:
            lines.append(f"- {p}")
        lines.append("")
        lines.append("**Cara test:**")
        for t in cat['tests']:
            lines.append(f"1. {t}")
        lines.append("")
        lines.append(f"**Tools:** {', '.join(cat['tools'])}")
        lines.append("")
        lines.append("---")
        lines.append("")
    
    path = os.path.join(OUT, "MASTER_CHEATSHEET.md")
    with open(path, 'w') as f:
        f.write('\n'.join(lines))
    print(f"  -> saved {path} ({len(lines)} lines)")

# ── Generate per-challenge study guides ──
def gen_challenge_study(challenge_name, item_id):
    cat = CHALLENGE_MAP.get(challenge_name)
    if not cat:
        print(f"[!] No mapping for {challenge_name} — skipping")
        return
    
    lines = []
    lines.append(f"# {challenge_name} (item #{item_id})")
    lines.append(f"**Mapped to:** {cat['id']}: {cat['title']}")
    lines.append("")
    lines.append("## Probable vulnerability")
    lines.append(f"Berdasarkan nama & OWASP mapping, kemungkinan challenge ini fokus ke **{cat['title'].lower()}**.")
    lines.append("")
    lines.append(f"**Context clue:** `{challenge_name}` — {_context_clue(challenge_name)}")
    lines.append("")
    lines.append("## Recon phase")
    lines.append("Before attacking:")
    lines.append(f"1. Identifikasi tech stack (Wappalyzer / HTTP headers)")
    lines.append(f"2. Crawl & map semua endpoint (gobuster/ffuf)")
    lines.append(f"3. Baca source code / comment / hidden fields")
    lines.append(f"4. Identifikasi input points (form, API, file upload)")
    lines.append("")
    lines.append("## Exploitation playbook")
    for i, t in enumerate(cat['tests'], 1):
        lines.append(f"{i}. {t}")
    lines.append("")
    lines.append("## Tools")
    lines.append(', '.join(cat['tools']))
    lines.append("")
    lines.append("## PoC template")
    lines.append("```bash")
    if cat['id'] == 'A10:2025':
        lines.append("# SSRF test — ganti TARGET dengan IP challenge lo")
        lines.append("curl -X POST https://TARGET/api/fetch \\")
        lines.append("  -d 'url=http://169.254.169.254/latest/meta-data/'")
    elif cat['id'] == 'A03:2025':
        lines.append("# Injection test")
        lines.append("curl 'https://TARGET/login' -d \"username=admin' OR '1'='1&password=x\"")
    elif cat['id'] == 'A01:2025':
        lines.append("# IDOR test")
        lines.append("curl 'https://TARGET/api/user/2' -H 'Cookie: session=YOURS'")
    else:
        lines.append(f"# {cat['title']} PoC")
        lines.append("# TODO: customize after recon")
    lines.append("```")
    lines.append("")
    lines.append("## Notes / Findings")
    lines.append("(isi setelah ngerjain challenge)")
    lines.append("")
    
    safe_name = challenge_name.lower().replace(' ', '_')
    path = os.path.join(OUT, f"{safe_name}.md")
    with open(path, 'w') as f:
        f.write('\n'.join(lines))
    print(f"  -> saved {path}")

def _context_clue(name):
    clues = {
        "Criticalops": "Mungkin ada endpoint admin yang bisa diakses lewat force browsing / IDOR.",
        "NovaEnergy": "Energy company dashboard — kemungkinan ada data sensor yang tidak dienkripsi.",
        "Blackout Ops": "Blackout operasi — mungkin ada admin panel dengan default creds.",
        "Spellbound Servants": "\"Spell\" = casting spell = Java deserialization gadget chain? Atau SSTI?",
        "CDNio": "CDN management — likely SSRF ke internal CDN nodes / origin IP.",
        "PumpkinSpice": "Fun name tapi kemungkinan SQLi di query pencarian produk musiman.",
        "Volnaya Forums": "Forum = user-generated content = XSS di post/comment, atau SQLi di search.",
        "POP Restaurant": "POP chain = gadget chain deserialization. Cari endpoint yang menerima serialized object.",
        "NexusSeven": "Complex system — business logic flaw: bisa bypass payment? atau race condition?",
        "Sattrack": "Satellite tracking data — SSRF untuk fetch internal sat data feed."
    }
    return clues.get(name, "Need recon dulu.")

# ── Main ──
def main():
    print("[*] Loading track 82 data...")
    track_path = os.path.join(OUT, "track_82_raw.json")
    with open(track_path) as f:
        track = json.load(f)
    
    items = track.get('items', [])
    print(f"[*] Found {len(items)} challenges in track: {track['name']}")
    
    gen_cheatsheet()
    print()
    print("[*] Generating per-challenge study guides...")
    for item in items:
        gen_challenge_study(item['name'], item['id'])
    
    # Summary index
    print()
    print("[*] Generating index...")
    idx_lines = [f"# Track: {track['name']}", f"**Total challenges:** {len(items)}", ""]
    for item in items:
        cat = CHALLENGE_MAP.get(item['name'], {})
        cat_id = cat.get('id', 'TBD')
        safe_name = item['name'].lower().replace(' ', '_')
        idx_lines.append(f"1. [{item['name']}]({safe_name}.md) → {cat_id} (item #{item['id']})")
    
    idx_path = os.path.join(OUT, "INDEX.md")
    with open(idx_path, 'w') as f:
        f.write('\n'.join(idx_lines))
    
    # Final summary
    files = sorted(os.listdir(OUT))
    print(f"\n{'='*50}")
    print(f"Done! Output: {OUT}/")
    for f_name in files:
        f_path = os.path.join(OUT, f_name)
        size = os.path.getsize(f_path)
        print(f"  {f_name:35} {size:>6} bytes")
    print(f"{'='*50}")
    print("Review: cat ~/ai-agent/data/htb-progress/owasp-2025/INDEX.md")

if __name__ == "__main__":
    main()
