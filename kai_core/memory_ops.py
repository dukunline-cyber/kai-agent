"""Split from telegram_agent monolith — behavior preserved."""
from __future__ import annotations

from kai_core.config import *  # noqa: F401,F403

import mem0_integration
from kai_core.db import *
def load_soul() -> str:
    """Baca SOUL.md tiap kali system prompt dibangun. Fallback ke default kalo file ga ada."""
    if SOUL_FILE.exists():
        try:
            return SOUL_FILE.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return ""

def list_credentials() -> list:
    """List file credentials yang available (cuma nama file, BUKAN isinya)."""
    if not CREDENTIALS_DIR.exists():
        return []
    return sorted([f.name for f in CREDENTIALS_DIR.iterdir() if f.is_file() and f.name.endswith(".env")])




def redact_secrets(text: str) -> str:
    if not isinstance(text, str):
        return text
    for pat, repl in SECRET_PATTERNS:
        text = pat.sub(repl, text)
    return text

# ========================
# MEMORY
# ========================

def load_memory() -> dict:
    if MEMORY_FILE.exists():
        try:
            return json.loads(MEMORY_FILE.read_text())
        except:
            pass
    return {"notes": [], "user_name": ""}

def save_memory(data: dict):
    MEMORY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

def add_memory_note(note: str):
    m = load_memory()
    if note not in m.get("notes", []):
        m.setdefault("notes", []).append(note)
        m["notes"] = m["notes"][-50:]
        save_memory(m)

# ========================
# HISTORY (persisten)
# ========================

def load_history(chat_id: int, thread_id: int = None) -> list:
    name = f"{chat_id}_{thread_id}" if thread_id else str(chat_id); f = HISTORY_DIR / f"{name}.json"
    if f.exists():
        try:
            return json.loads(f.read_text())
        except:
            pass
    return []

def save_history(chat_id: int, history: list, thread_id: int = None):
    sanitized = []
    for msg in history:
        if isinstance(msg, dict) and "content" in msg:
            sanitized.append({**msg, "content": redact_secrets(msg["content"])})
        else:
            sanitized.append(msg)
    name = f"{chat_id}_{thread_id}" if thread_id else str(chat_id); (HISTORY_DIR / f"{name}.json").write_text(json.dumps(sanitized, ensure_ascii=False, indent=2))

# ========================
# SYSTEM PROMPT
# ========================

