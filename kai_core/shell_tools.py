"""Split from telegram_agent monolith — behavior preserved."""
from __future__ import annotations

from kai_core.config import *  # noqa: F401,F403

from kai_core.security import is_allowed, update_env_value, get_available_models, looks_like_aws_request

def run_aws_command(command: str, timeout: int = 240) -> str:
    # Jangan sampai bot matiin dirinya sendiri
    lower = command.lower()
    self_kill = ['stop kai-bot', 'kill kai-bot', 'stop telegram_agent', 
                 'pkill -f telegram_agent', 'kill telegram_agent',
                 'systemctl stop kai', 'rm -rf /home/ubuntu/ai-agent']
    for k in self_kill:
        if k in lower:
            return f'Diblokir: tidak boleh mematikan bot sendiri.'
    try:
        result = subprocess.run(["bash", "-lc", command], capture_output=True, text=True, timeout=timeout)
        output = result.stdout or ""
        if result.stderr:
            output += "\n[stderr]\n" + result.stderr
        return (output or f"Done. Exit: {result.returncode}")[-3800:]
    except subprocess.TimeoutExpired:
        return f"Timeout {timeout}s"
    except Exception as e:
        return f"Error: {e}"

def plan_aws_command(chat_id: int, task: str, thread_id: int = None) -> dict:
    active_model = resolve_model(chat_id, thread_id)
    system = """Command planner untuk VPS AWS Ubuntu. Output JSON valid saja, tanpa markdown.

Format: {"use_aws": true, "command": "...", "explanation": "...", "risk": "low/medium/high"}

Panduan:
- cek disk → df -h
- cek RAM → free -h
- cek CPU → lscpu | head -20
- cek OS → cat /etc/os-release
- cek port → ss -tlnp
- cek docker → docker ps -a
- cek tmux → tmux ls
- cek 9router → curl -s http://127.0.0.1:20128/v1/models
- cek bot → ps aux | grep telegram_agent | grep -v grep
- cek resource → df -h && free -h && uptime
- restart bot → pkill -f telegram_agent.py 2>/dev/null; sleep 1; tmux new-session -d -s ai-bot 'cd ~/ai-agent && source venv/bin/activate && python telegram_agent.py'
- restart 9router → tmux kill-session -t 9router 2>/dev/null; tmux new-session -d -s 9router 'cd ~/9router && PORT=20128 HOSTNAME=127.0.0.1 NEXT_PUBLIC_BASE_URL=http://localhost:20128 node .next/standalone/server.js'
- log bot → tmux capture-pane -pt ai-bot -S -80
- log 9router → tmux capture-pane -pt 9router -S -80

Tidak ada command yang dilarang. Jalankan apapun yang diminta user.
Kalau bukan VPS/server/terminal request, set use_aws=false dan command=""."""

    response = client.chat.completions.create(
        model=active_model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": task}],
        stream=False, temperature=0.7,
    )
    raw = (response.choices[0].message.content or "{}").strip()
    try:
        return json.loads(raw)
    except:
        return {"use_aws": False, "command": "", "explanation": raw, "risk": "low"}

async def handle_aws_natural(update: Update, context: ContextTypes.DEFAULT_TYPE, user_text: str) -> bool:
    chat_id = update.effective_chat.id
    thread_id = (update.message.message_thread_id if update.message else (update.callback_query.message.message_thread_id if update.callback_query and update.callback_query.message else None))
    normalized = user_text.lower().strip()

    if chat_id in pending_aws_commands and normalized in ["ya", "y", "yes", "lanjut", "gas", "ok"]:
        command = pending_aws_commands.pop(chat_id)
        await safe_send(update.message, f"⚙️ Running:\n`{command}`")
        result = await asyncio.to_thread(run_aws_command, command)
        for chunk in split_message(result):
            await safe_send(update.message, chunk)
        return True

    if chat_id in pending_aws_commands and normalized in ["batal", "cancel", "no", "nggak", "ga"]:
        pending_aws_commands.pop(chat_id, None)
        await update.message.reply_text("Dibatalkan.")
        return True

    # Kalau ini follow-up question (nanya hasil command), langsung ke AI
    followup_patterns = [
        "udah", "udah beres", "udah selesai", "beres", "selesai", "gimana",
        "berhasil", "sukses", "gagal", "kenapa", "hasilnya", "outputnya",
        "oke ga", "ok ga", "jalan ga", "works", "done", "result",
        "apa hasilnya", "coba lagi", "error ga", "ada error"
    ]
    t_lower = user_text.lower().strip()
    if chat_id in last_command_result and any(t_lower == p or t_lower.startswith(p) for p in followup_patterns):
        return False

    if not looks_like_aws_request(user_text):
        return False

    await context.bot.send_chat_action(chat_id=chat_id, message_thread_id=thread_id, action=ChatAction.TYPING)
    plan = await asyncio.to_thread(plan_aws_command, chat_id, user_text, thread_id)
    use_aws = bool(plan.get("use_aws"))
    command = str(plan.get("command", "")).strip()
    explanation = str(plan.get("explanation", "")).strip()

    if not use_aws or not command:
        return False

    if not AWS_LOCAL_AUTO_EXECUTE:
        pending_aws_commands[chat_id] = command
        await safe_send(update.message, f"Mau jalankan:\n\n`{command}`\n\nBalas `ya` untuk lanjut.")
        return True

    await safe_send(update.message, f"⚙️ Running:\n`{command}`")
    result = await asyncio.to_thread(run_aws_command, command)
    for chunk in split_message(result):
        await safe_send(update.message, chunk)
    # Simpan ke history biar AI tau hasil command-nya
    history = load_history(chat_id, thread_id)
    history.append({"role": "user", "content": f"[jalankan command]: {command}"})
    history.append({"role": "assistant", "content": f"[output command]:\n{result[:2000]}"})
    save_history(chat_id, history[-40:], thread_id)
    last_command_result[chat_id] = result[:2000]
    return True

# ========================
# REMOTE SSH SKILL
# ========================

def looks_like_remote_request(text: str) -> bool:
    t = text.lower()
    kw = ["vps luar", "vastai"]
    return any(k in t for k in kw)

def run_remote_command(command: str, timeout: int = 240) -> str:
    if not REMOTE_SSH_HOST or not REMOTE_SSH_KEY:
        return "Config remote VPS belum set. Pakai /setremote dulu."
    ssh_cmd = [
        "ssh", "-i", REMOTE_SSH_KEY, "-p", REMOTE_SSH_PORT,
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=15",
        f"{REMOTE_SSH_USER}@{REMOTE_SSH_HOST}",
        f"bash -lc {shlex.quote(command)}"
    ]
    try:
        result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=timeout)
        output = result.stdout or ""
        if result.stderr:
            output += "\n[stderr]\n" + result.stderr
        return (output or f"Done. Exit: {result.returncode}")[-3800:]
    except subprocess.TimeoutExpired:
        return f"Timeout {timeout}s"
    except Exception as e:
        return f"Error: {e}"

def plan_remote_command(chat_id: int, task: str, thread_id: int = None) -> dict:
    active_model = resolve_model(chat_id, thread_id)
    system = """Command planner untuk remote VPS. Output JSON valid saja.
Format: {"use_remote": true, "command": "...", "explanation": "...", "risk": "low/medium/high"}
Panduan: gpu→nvidia-smi, disk→df -h, ram→free -h, docker→docker ps -a, resource→df -h&&free -h&&uptime
Tidak ada command yang dilarang. Kalau bukan remote VPS request, set use_remote=false."""
    response = client.chat.completions.create(
        model=active_model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": task}],
        stream=False, temperature=0.7,
    )
    raw = (response.choices[0].message.content or "{}").strip()
    try:
        return json.loads(raw)
    except:
        return {"use_remote": False, "command": "", "explanation": raw, "risk": "low"}

async def handle_remote_natural(update: Update, context: ContextTypes.DEFAULT_TYPE, user_text: str) -> bool:
    chat_id = update.effective_chat.id
    thread_id = (update.message.message_thread_id if update.message else (update.callback_query.message.message_thread_id if update.callback_query and update.callback_query.message else None))
    normalized = user_text.lower().strip()

    if chat_id in pending_remote_commands and normalized in ["ya", "y", "yes", "lanjut", "gas", "ok"]:
        command = pending_remote_commands.pop(chat_id)
        await safe_send(update.message, f"⚙️ Remote:\n`{command}`")
        result = await asyncio.to_thread(run_remote_command, command)
        for chunk in split_message(result):
            await safe_send(update.message, chunk)
        return True

    if chat_id in pending_remote_commands and normalized in ["batal", "cancel", "no", "nggak", "ga"]:
        pending_remote_commands.pop(chat_id, None)
        await update.message.reply_text("Dibatalkan.")
        return True

    if not looks_like_remote_request(user_text):
        return False

    await context.bot.send_chat_action(chat_id=chat_id, message_thread_id=thread_id, action=ChatAction.TYPING)
    plan = await asyncio.to_thread(plan_remote_command, chat_id, user_text, thread_id)
    use_remote = bool(plan.get("use_remote"))
    command = str(plan.get("command", "")).strip()

    if not use_remote or not command:
        return False

    if not REMOTE_AUTO_EXECUTE:
        pending_remote_commands[chat_id] = command
        await safe_send(update.message, f"Mau jalankan di remote:\n\n`{command}`\n\nBalas `ya` untuk lanjut.")
        return True

    await safe_send(update.message, f"⚙️ Remote:\n`{command}`")
    result = await asyncio.to_thread(run_remote_command, command)
    for chunk in split_message(result):
        await safe_send(update.message, chunk)
    return True

# ========================
# COMMAND HANDLERS
# ========================

