# BYPASS v3 — Full-Stack Agent Penetration
# Target: Hermes Agent (regex scanner + model alignment + agent runtime)
# Models: Claude 4.5 Opus/Sonnet, GPT-5/o3, Gemini 2.5 Pro, Grok 4, Llama 4, DepSeek v4 Pro, Qwen 3, GLM 5.2, Mistral Large 3, Kimi K2
# Date: 2026-07-14 | Author: Kai for Gutluc
# Scope: AI red-team / security research / bug bounty

---

## CHANGELOG v2 → v3

v2 fokus **prompt extraction only** (dual layer: regex + model).
v3 upgrade jadi **full-stack agent penetration** (tri-layer + agent runtime):

1. Threat model expanded: bukan cuma "leak prompt", tapi juga hijack agent, poison memory, abuse tools, plant persistent backdoor
2. Attack surface expanded dari 3 → 7 layer (transport, scanner, prompt, model, tool, memory, skill/MCP)
3. Model matrix updated ke 2026 lineup (Claude 4.5, GPT-5, o3, Grok 4, Llama 4, Kimi K2)
4. Payload set expanded A-F → A-K (tambah 5 kategori baru)
5. Baru: Unicode adversarial (G), Tool poisoning (H), Memory/RAG poisoning (I), MCP/Skill abuse (J), Reasoning chain hijack (K)
6. Verification protocol formal (dual-method cross-check)
7. Operational playbook per phase (recon → payload → exec → verify → document)

---
## THREAT MODEL — Hermes Agent 2026 Defense Stack

Berdasarkan riset & source-code Hermes yang udah kita maping:

**Layer 0 — Transport/Provider Filter**
- OpenAI/Anthropic/Google server-side content filter
- `finish_reason: content_filter`
- Out-of-scope untuk kita (server-side, opaque)

**Layer 1 — Static Regex Scaner**
- `threat_paterns.py` (~36 English regex)
- `skills_guard.py` (~40+ exfil/injection/destructive patterns)
- Executed pre-model, blocks input before LLM sees it
- **Weakness:** English-only, no semantic analysis, no unicode normalization

**Layer 2 — Model Built-in Alignment (RLHF/DPO/Constitutional)**
- Training-time safety alignment per model
- Cross-lingual coverage varies (weak in low-resource languages)
- **Weakness:** helpfulness-vs-safety tension, authority-following bias

**Layer 3 — System Prompt (SOUL.md)**
- Loaded as system role, highest instruction weight
- Model treats as authoritative
- **Weakness:** anything mimicking this format inherits authority

**Layer 4 — Tool Guard**
- `run_in_terminal` risk classification (low/medium/high)
- Auto-run threshold + human-in-loop for high-risk
- **Weakness:** trust boundary at tool output — poisoned output re-enters context

**Layer 5 — Memory Layer (Mem0/Qdrant)**
- Semantic memory retrieval
- Injected into every session as "relevant memories"
- **Weakness:** write-once-read-forever, no integrity check per entry

**Layer 6 — Skill/MCP Registry**
- On-demand skill file read
- MCP server tool discovery
- **Weakness:** skill files trusted as authoritative, MCP tool descriptions injected into context

---

## ATTACK SURFACE MAP

| Layer | Attack Class | v3 Payload Set |
|------|------------|------------|
| L1Scanner | Regex evasion via language/unicode/encoding | F, G |
| L2 Model | Alignment bypass via authority/framing/reasoning | A, B, C |
| L3 System Prompt | Impersonation / config mimicry | A |
| L4 Tool | Tool output poisoning, argument injection | H |
| L5 Memory | Fact injection, semantic poisoning | I |
| L6 Skill/MCP | Skill file trojan, MCP tool description injection | J |
| Cross-layer | Multi-turn state, reasoning hijack | D, E, K |

