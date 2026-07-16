# Kai — Autonomous Telegram Agent

Kai adalah AI familiar yang jalan langsung di VPS (AWS EC2, Ubuntu). Bukan asisten korporat — Kai adalah perpanjangan tangan owner dengan akses penuh ke VPS, shell, MCP tools, dan layanan eksternal.

## Arsitektur

```
telegram_agent.py          Entry point -> kai_core.app.main()
│
├── kai_core/              Core engine
│   ├── config.py          Env, paths, OpenAI clients, mutable globals
│   ├── db.py              SQLite (kai.db)
│   ├── memory_ops.py      Soul/creds, redact, memory/history helpers
│   ├── prompt.py          System prompt builder (SOUL + mem0 + lessons)
│   ├── agent_loop.py      web_search, tool parse, ask_ai / ask_ai_agentic
│   ├── shell_tools.py     Local bash + remote SSH + natural aws/remote
│   ├── media_tools.py     PDF/DOCX/XLSX/PPTX extract, image/PDF gen, video frames
│   ├── telegram_util.py   split_message, safe_send, send_ai_results
│   ├── security.py        is_allowed, update_env, get_available_models
│   ├── oracle.py          OCI oracle war helpers
│   └── app.py             Application wiring (handlers registration)
│
├── kai_handlers/          Telegram handlers
│   ├── commands.py         Command handlers (/cmd)
│   ├── messages.py        Message handlers
│   ├── callback.py        Callback query handlers
│   ├── media.py           Media/file handlers
│   ├── loops.py           Background loops
│   ├── misc.py            Misc handlers
│   ├── oracle_cmds.py     Oracle command handlers
│   └── all_handlers.py    Handler registration hub
│
├── tools/                  62+ tools (alerts, automation, backtest, briefing,
│                           ctf, dashboard, exploit_builder, hids, humanizer,
│                           mcp_builder, swarm, triage, vault, voice, dll)
│
├── skills/                 Skill modules
│   ├── breach_v3.md        Red-team payload arsenal
│   ├── browser-agent/      Browser automation
│   ├── cypher/             Web3/blockchain tools
│   ├── gatectf/            CTF automation
│   ├── hermes/             Hermes agent bridge
│   ├── llm_redteam/        LLM adversarial toolkit
│   ├── m32-tools/          Academic writing tools
│   ├── pentest-report-writing/
│   ├── redteam/            Red team templates
│   ├── superagent/         Full-spectrum security agent
│   └── superagent_trader/  Trading automation
│
├── mcp/                    MCP bridge
│   ├── mcp_bridge.py       MCP protocol bridge
│   └── servers.json        MCP server configs (filesystem, github, notion, google)
│
├── scripts/                Utility scripts
│   ├── x_bb_scan.py        Bug bounty scanner
│   ├── x_hunt.py           Target hunter
│   ├── x_search.py         OSINT search
│   ├── bai_batch.py        Batch processing
│   ├── memory_to_obsidian.py
│   ├── self_heal.sh        Auto-repair
│   ├── self_upgrade.sh     Auto-upgrade
│   └── ...
│
├── adapters/               External adapters
├── agents/                 Sub-agent definitions (agent-1/2/3)
│
├── SOUL.md                 Konstitusi Kai (identitas, rules, capabilities)
├── ARCHITECTURE.txt        Layout overview
└── KAI_BOT_PANDUAN.md      Operator guide
```

## Stack

- **Runtime**: Python 3.11+ (venv)
- **LLM Gateway**: 9router (OpenAI-compatible, self-hosted)
- **Models**: glm-5.2 (primary), deepseek-v4-flash, gemini-3-flash, kimi-k2.7
- **Memory**: SQLite + Mem0 (cloud)
- **Messaging**: Telegram Bot API
- **MCP**: filesystem, github, notion, google-workspace, windows-agent
- **Infra**: AWS EC2 (Ubuntu), Tailscale mesh

## Setup

```bash
# Clone
git clone https://github.com/dukunline-cyber/kai-agent.git
cd kai-agent

# Python venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env: TELEGRAM_BOT_TOKEN, OPENAI_API_KEY, OPENAI_BASE_URL, etc.

# Run
python telegram_agent.py
```

## Config

Key environment variables (`.env`):

| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token from @BotFather |
| `OPENAI_BASE_URL` | 9router endpoint (default: `http://127.0.0.1:20128/v1`) |
| `OPENAI_API_KEY` | 9router API key |
| `MODEL_NAME` | Primary model (default: `uni/glm-5.2`) |
| `FALLBACK_MODELS` | Comma-separated fallback models |
| `ALLOWED_TELEGRAM_USER_ID` | Authorized Telegram user ID |

## License

MIT
