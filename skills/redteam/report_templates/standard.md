# [TITLE: <attack-type> on <asset>]

## TL;DR
<1-line: what is broken, where, severity>

## Asset
- URL/Endpoint: `<full URL or hostname>`
- Scope reference: `<bugcrowd/h1 scope line>`
- Authenticated? <yes/no, role if yes>

## Severity
- VRT: <P1/P2/P3/P4/P5> — <category> — <subcategory>
- CVSS 3.1: <score> (`<vector string>`)
- CWE: CWE-<id> <name>

## Steps to Reproduce
1. <step 1, exact request/action>
2. <step 2>
3. <step 3>
4. <observe X>

### Reproducer
```bash
<curl / dig / script that triager can paste>
```

Expected output:
```
<exact response showing bug>
```

## Impact
<2-3 sentences: what attacker gains, blast radius, why it matters>
Compliance angle (if any): <PCI-DSS X.Y / SOC2 / GDPR / HIPAA>

## Suggested Fix
<1-3 concrete fixes, ordered by ease>

## Evidence
- Screenshot: `<filename>`
- Raw response: `<filename>`
- Repro script: `<filename>`
