"""Split from telegram_agent monolith — behavior preserved."""
from __future__ import annotations

from kai_core.config import *  # noqa: F401,F403
import json as _json


def get_db():
    """Get SQLite connection with WAL mode for better concurrency."""
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database tables."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER DEFAULT 0,
            note TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_history_chat ON chat_history(chat_id);
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            reminder_text TEXT NOT NULL,
            remind_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            sent INTEGER DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_reminders_time ON reminders(remind_at, sent);
        CREATE TABLE IF NOT EXISTS file_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            file_type TEXT,
            file_name TEXT,
            file_path TEXT,
            mime_type TEXT,
            file_size INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()

# Initialize DB on startup
init_db()

# Migrate existing JSON data to SQLite if needed
def migrate_json_to_db():
    """One-time migration from JSON files to SQLite."""
    conn = get_db()
    # Migrate memory
    if MEMORY_FILE.exists():
        try:
            import json as _json
            m = _json.loads(MEMORY_FILE.read_text())
            existing = conn.execute("SELECT COUNT(*) FROM memory").fetchone()[0]
            if existing == 0 and m.get("notes"):
                for note in m["notes"]:
                    conn.execute("INSERT INTO memory (note) VALUES (?)", (note,))
                conn.commit()
                logging.info(f"Migrated {len(m['notes'])} memory notes to SQLite")
        except Exception as e:
            logging.warning(f"Memory migration skipped: {e}")

    # Migrate history files
    if HISTORY_DIR.exists():
        import json as _json
        for hf in HISTORY_DIR.glob("*.json"):
            try:
                chat_id = int(hf.stem)
                existing = conn.execute("SELECT COUNT(*) FROM chat_history WHERE chat_id=?", (chat_id,)).fetchone()[0]
                if existing == 0:
                    hist = _json.loads(hf.read_text())
                    for msg in hist:
                        if isinstance(msg, dict) and "role" in msg and "content" in msg:
                            conn.execute("INSERT INTO chat_history (chat_id, role, content) VALUES (?,?,?)",
                                       (chat_id, msg["role"], msg["content"]))
                    conn.commit()
                    logging.info(f"Migrated history for chat {chat_id} to SQLite")
            except (ValueError, Exception) as e:
                continue
    conn.close()

# DB-backed memory functions
def load_memory_db() -> dict:
    conn = get_db()
    notes = [row["note"] for row in conn.execute("SELECT note FROM memory ORDER BY id DESC LIMIT 50").fetchall()]
    conn.close()
    return {"notes": list(reversed(notes))}

def save_memory_note_db(note: str):
    conn = get_db()
    existing = conn.execute("SELECT id FROM memory WHERE note=?", (note,)).fetchone()
    if not existing:
        conn.execute("INSERT INTO memory (note) VALUES (?)", (note,))
        conn.commit()
    conn.close()

def clear_memory_db():
    conn = get_db()
    conn.execute("DELETE FROM memory")
    conn.commit()
    conn.close()

# DB-backed history functions
def load_history_db(chat_id: int) -> list:
    conn = get_db()
    rows = conn.execute(
        "SELECT role, content FROM chat_history WHERE chat_id=? ORDER BY id DESC LIMIT 60",
        (chat_id,)
    ).fetchall()
    conn.close()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

def save_history_db(chat_id: int, messages: list):
    """Append new messages to history. Also maintains max 60 messages."""
    conn = get_db()
    for msg in messages:
        if isinstance(msg, dict) and "role" in msg and "content" in msg:
            content = redact_secrets(msg["content"]) if "content" in msg else ""
            conn.execute("INSERT INTO chat_history (chat_id, role, content) VALUES (?,?,?)",
                        (chat_id, msg["role"], content))
    # Keep only last 60 messages per chat
    conn.execute("""
        DELETE FROM chat_history WHERE chat_id=? AND id NOT IN (
            SELECT id FROM chat_history WHERE chat_id=? ORDER BY id DESC LIMIT 60
        )
    """, (chat_id, chat_id))
    conn.commit()
    conn.close()

def clear_history_db(chat_id: int):
    conn = get_db()
    conn.execute("DELETE FROM chat_history WHERE chat_id=?", (chat_id,))
    conn.commit()
    conn.close()

def log_file_db(chat_id: int, file_type: str, file_name: str, file_path: str, mime_type: str = "", file_size: int = 0):
    conn = get_db()
    conn.execute("INSERT INTO file_log (chat_id, file_type, file_name, file_path, mime_type, file_size) VALUES (?,?,?,?,?,?)",
                (chat_id, file_type, file_name, file_path, mime_type, file_size))
    conn.commit()
    conn.close()

# Reminder DB functions
def add_reminder_db(chat_id: int, text: str, remind_at: str):
    conn = get_db()
    conn.execute("INSERT INTO reminders (chat_id, reminder_text, remind_at) VALUES (?,?,?)",
                (chat_id, text, remind_at))
    conn.commit()
    conn.close()

def get_due_reminders():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, chat_id, reminder_text FROM reminders WHERE sent=0 AND remind_at <= datetime('now')"
    ).fetchall()
    result = [{"id": r["id"], "chat_id": r["chat_id"], "text": r["text"] if "text" in r.keys() else r["reminder_text"]} for r in rows]
    conn.close()
    return result

def mark_reminder_sent(reminder_id: int):
    conn = get_db()
    conn.execute("UPDATE reminders SET sent=1 WHERE id=?", (reminder_id,))
    conn.commit()
    conn.close()

def list_reminders_db(chat_id: int):
    conn = get_db()
    rows = conn.execute(
        "SELECT id, reminder_text, remind_at, sent FROM reminders WHERE chat_id=? AND sent=0 ORDER BY remind_at",
        (chat_id,)
    ).fetchall()
    result = [{"id": r["id"], "text": r["reminder_text"], "remind_at": r["remind_at"]} for r in rows]
    conn.close()
    return result

def delete_reminder_db(reminder_id: int):
    conn = get_db()
    conn.execute("DELETE FROM reminders WHERE id=?", (reminder_id,))
    conn.commit()
    conn.close()

