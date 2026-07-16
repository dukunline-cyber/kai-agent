# Skills Index — Kai VPS

Auto-generated 2026-07-14. Structured skill dirs only. Legacy flat m*.md/x*.md archived to `.archive/skill_cleanup_20260714/legacy_flat/`.

## Security / Bug Bounty
- **superagent/** — Full-spectrum bug bounty & exploit agent (Web3, web/API, infra). 6-phase workflow: scope→recon→analyze→exploit→report→triage. References: recon, vuln-classes, web3, verification-and-poc, reporting, tooling + legacy merged (bugbounty playbook/tools, portswigger sqli/access-control). Trigger: bug bounty, hunt, exploit, audit contract, recon.
- **redteam/** — Offensive security ops: recon, exploitation, lateral movement, privesc, evasion, reporting. References: auth_bypass, ssrf_kit, graphql_pentest, takeover_playbook, xss_modern + 12 topic refs. Trigger: pentest, red team, attack.
- **llm_redteam/** — LLM/AI red team (Breach Mode). AI target only: CTF, AI bounty, prompt injection. Trigger: `breach:` / `🔓` prefix or AI target mentioned.
- **pentest-report-writing/** — Draft pentest/bug bounty vulnerability reports. web-app, mobile, network pentest templates.
- **gatectf/** — Gate CTF solver (Cupang Ventures). API pattern + EVM/crypto knowledge bank.

## Crypto / Trading
- **cypher/** — Multi-chain crypto + Web3 agent toolkit untuk Cypher. Swap, bridge, stake, mint, snipe, monitor.
- **superagent_trader/** — Forex technical analysis superagent. Market analysis, trade signals.

## Automation / Tooling
- **browser-agent/** — Stealth browser automation, extension control, dApp interaction. (no SKILL.md, entry via scripts).
- **m32-tools/** — Academic writing tools: abstract_writer, citation_generator, document_formatter, lit_review_matrix, paraphrase_checker, structure_checker. Used with m32 academic writing skill (archived).

## Archive
Legacy content moved to `~/ai-agent/.archive/skill_cleanup_20260714/`:
- `legacy_flat/` — m0-m32, x1-x6 flat .md files (38 files). Pre-refactor skill content.
- `bugbounty/` — Empty prompts dir (content merged to superagent).
- `portswigger/` — sqli.md (merged to superagent/references/legacy-portswigger-sqli.md).
- `knowledge/` — bugbounty_playbook, bugbounty_tools, portswigger_access_control (merged to superagent). finbot_ctf_threshold kept for CTF reference.

## Rule of thumb
- **superagent/** = primary bug bounty + exploit dev skill. Load first for any hunting task.
- **redteam/** = broader offensive sec (infra, AD, cloud, evasion). Load for pentest beyond web3.
- **llm_redteam/** = AI targets only, separate scope.
- Legacy flat files available in archive if needed — do NOT restore to skills/ root.
