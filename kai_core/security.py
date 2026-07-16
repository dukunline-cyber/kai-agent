"""Split from telegram_agent monolith — behavior preserved."""
from __future__ import annotations

from kai_core.config import *  # noqa: F401,F403


def is_allowed(update: Update) -> bool:
    if not ALLOWED_TELEGRAM_USER_ID:
        return True
    user = update.effective_user
    if not user:
        return False
    return str(user.id) == ALLOWED_TELEGRAM_USER_ID

def update_env_value(key: str, value: str):
    env_path = Path.home() / "ai-agent" / ".env"
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    new_lines = []
    found = False
    for line in lines:
        if line.startswith(f"{key}="):
            new_lines.append(f"{key}={value}")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"{key}={value}")
    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    env_path.chmod(0o600)

def get_available_models():
    url = OPENAI_BASE_URL.rstrip("/") + "/models"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        return sorted([i.get("id") for i in data.get("data", []) if i.get("id")])
    except:
        return []

# ========================
# AWS LOCAL SKILL
# ========================

def looks_like_aws_request(text: str) -> bool:
    t = text.lower().strip()

    # Explicit command-like patterns — harus spesifik
    explicit = [
        "cek docker", "cek container", "cek disk", "cek storage",
        "cek ram", "cek memory", "cek memori", "cek cpu", "cek port",
        "cek service", "cek 9router", "cek bot", "cek tmux", "cek vps",
        "cek server", "cek proses", "cek log",
        "restart bot", "restart 9router", "restart agent", "restart server",
        "tmux ls", "tmux new", "tmux kill", "docker ps", "docker run",
        "jalanin command", "jalanin bash", "run di vps", "run di server",
        "execute di vps", "eksekusi di vps",
        "apt install", "apt update", "apt upgrade", "apt remove",
        "pip install", "npm install",
        "ps aux", "df -h", "free -h", "uptime", "netstat", "ss -",
        "/aws ", "lihat log", "log bot", "log 9router",
        "git push", "git pull", "git commit", "git add", "git clone",
        "git checkout", "git merge", "git stash", "git status", "git log",
        "push github", "push ke github", "push repo", "commit dan push",
        "commit push", "deploy github", "upload github", "update repo",
    ]
    if any(k in t for k in explicit):
        return True

    # Hanya trigger kalau ada konteks VPS yang jelas
    vps_context = any(k in t for k in ["vps", "server", "aws", "9router", "tmux", "docker", "git", "github", "repo"])
    action_words = any(k in t for k in ["cek ", "restart", "install", "jalanin", "jalankan", "stop", "start", "kill"])

    return vps_context and action_words

