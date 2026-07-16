"""Split from telegram_agent monolith — behavior preserved."""
from __future__ import annotations

from kai_core.config import *  # noqa: F401,F403

from kai_core.db import *
from kai_core.memory_ops import *
from kai_core.security import *
from kai_core.agent_loop import *
from kai_core.shell_tools import *
from kai_core.media_tools import *
from kai_core.telegram_util import *
from kai_core.oracle import *
from kai_core.prompt import build_system_prompt
import mem0_integration
import self_learning as sl

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    user = update.effective_user
    name = user.first_name if user else "bos"
    m = load_memory()
    if user and user.first_name:
        m["user_name"] = user.first_name
        save_memory(m)
    await update.message.reply_text(
        f"Halo {name}! Gue {AGENT_NAME} — AI asisten pribadi lo yang jalan di VPS ini.\n\n"
        f"Gue bisa:\n• Ngobrol dan bantu apapun\n• Jalanin command di VPS ini\n"
        f"• Akses remote VPS\n• Cari info dari internet\n• Ingat hal-hal penting\n\nLangsung aja."
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    await safe_send(update.message,
        f"*{AGENT_NAME} — Commands*\n\n"
        "*Chat & AI:*\n"
        "/start — Mulai\n/reset — Reset history\n"
        "/memory — Lihat memory\n/remember [hal] — Simpan\n/forget — Hapus memory\n"
        "/model — Model aktif\n/models — Daftar model\n/setmodel [nama] — Ganti\n"
        "/cancel — Batalkan task\n/retry — Retry dengan fallback model\n\n"
        "*VPS & Server:*\n"
        "/aws [cmd] — Command VPS\n/search [query] — Cari internet\n"
        "/remote [cmd] — Remote VPS\n/setremote — Set remote\n\n"
        "*Voice:*\n"
        "/tts [teks] — Text-to-Speech\n"
        "Kirim voice note — otomatis di-transcribe\n\n"
        "*Reminder:*\n"
        "/reminders — Lihat reminder\n/delreminder [id] — Hapus\n"
        '\"ingetin 5 menit lagi ...\" — Set reminder\n\n'
        "*Media:*\n"
        "\u2022 Foto/gambar — analisis AI\n"
        "\u2022 Video — extract frame + analisis\n"
        "\u2022 Sticker — analisis visual\n"
        "\u2022 PDF/DOCX/XLSX/PPTX — baca isi\n"
        "\u2022 Voice note — transcribe + jawab\n"
        '\u2022 \"buatin gambar ...\" — generate gambar\n'
        '\u2022 \"buatin PDF ...\" — generate dokumen\n\n'
        "*Database:*\n"
        "/dbstats — Statistik database\n\n"
        "*Oracle:*\n"
        "/oracle\\_setup — Setup Oracle War\n\n"
        "/soul — Lihat personality\n/creds — Lihat credentials"
    )

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    cid = update.effective_chat.id
    hist_file = HISTORY_DIR / f"{cid}.json"
    if hist_file.exists() and hist_file.stat().st_size > 4:
        archive_dir = HISTORY_DIR / "archive"
        archive_dir.mkdir(exist_ok=True)
        from datetime import datetime as _dt
        ts = _dt.utcnow().strftime("%Y%m%d-%H%M%S")
        archive_dir_file = archive_dir / f"{cid}-{ts}.json"
        import shutil
        shutil.copy2(str(hist_file), str(archive_dir_file))
    save_history(cid, [])
    await update.message.reply_text("✔️ Chat history di-reset. Mulai dari nol.")

async def memory_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    m = load_memory()
    notes = m.get("notes", [])
    if not notes:
        await update.message.reply_text("Memory kosong.")
        return
    text = "📝 *Yang gue inget:*\n\n" + "\n".join(f"{i+1}. {n}" for i, n in enumerate(notes))
    await safe_send(update.message, text)

async def remember_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    if not context.args:
        await update.message.reply_text("Format: /remember hal yang mau diingat")
        return
    note = " ".join(context.args)
    add_memory_note(note)
    await update.message.reply_text(f"✅ Oke, gue inget: {note}")

async def forget_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    m = load_memory()
    m["notes"] = []
    save_memory(m)
    await update.message.reply_text("Memory dihapus.")

async def model_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    active = resolve_model(update.effective_chat.id, update.message.message_thread_id if update.message else None)
    await safe_send(update.message, f"Model aktif: `{active}`")

async def models_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    model_list = await asyncio.to_thread(get_available_models)
    all_models = list(model_list or [])
    if FREEMODEL_API_KEY and FREEMODEL_MODELS:
        all_models += list(FREEMODEL_MODELS)
    if not all_models:
        await update.message.reply_text("Gagal ambil daftar model.")
        return
    active = resolve_model(update.effective_chat.id, update.message.message_thread_id if update.message else None)
    model_button_map.clear()
    model_groups.clear()
    for i, m in enumerate(all_models):
        tok = str(i)
        model_button_map[tok] = m
        prov = m.split("/")[0] if "/" in m else "lain"
        model_groups.setdefault(prov, []).append(tok)
    buttons, row = [], []
    for prov in sorted(model_groups):
        row.append(InlineKeyboardButton(f"{prov} ({len(model_groups[prov])})", callback_data=f"smp_{prov}"))
        if len(row) == 2:
            buttons.append(row); row = []
    if row: buttons.append(row)
    kb = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(f"Pilih provider (model aktif: {active}):", reply_markup=kb)

async def setmodel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    if not context.args:
        await update.message.reply_text("Format: /setmodel nama-model")
        return
    chat_models[model_key(update.effective_chat.id, update.message.message_thread_id if update.message else None)] = context.args[0]
    save_chat_models()
    await safe_send(update.message, f"Model diganti ke: `{context.args[0]}` (tersimpan permanen)")

async def aws_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    if not context.args:
        await update.message.reply_text("Format: /aws command\n\nContoh: /aws df -h")
        return
    command = " ".join(context.args)
    await safe_send(update.message, f"⚙️ Running:\n`{command}`")
    result = await asyncio.to_thread(run_aws_command, command)
    for chunk in split_message(result):
        await safe_send(update.message, chunk)

async def search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    if not context.args:
        await update.message.reply_text("Format: /search query")
        return
    query = " ".join(context.args)
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    result = await asyncio.to_thread(web_search, query)
    for chunk in split_message(result):
        await safe_send(update.message, chunk)

async def setremote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    if not context.args:
        await update.message.reply_text("Format: /setremote host [port] [user]")
        return
    global REMOTE_SSH_HOST, REMOTE_SSH_PORT, REMOTE_SSH_USER
    host = context.args[0]
    port = context.args[1] if len(context.args) > 1 else "22"
    user = context.args[2] if len(context.args) > 2 else "root"
    if not port.isdigit():
        await update.message.reply_text("Port harus angka.")
        return
    update_env_value("REMOTE_SSH_HOST", host)
    update_env_value("REMOTE_SSH_PORT", port)
    update_env_value("REMOTE_SSH_USER", user)
    REMOTE_SSH_HOST = host
    REMOTE_SSH_PORT = port
    REMOTE_SSH_USER = user
    await update.message.reply_text(
        f"Remote VPS tersimpan: {user}@{host}:{port}\n\n"
        "Kirim private key:\n/setremote_key\n-----BEGIN...-----"
    )

async def setremote_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    raw_text = update.message.text or ""
    key_text = raw_text.replace("/setremote_key", "", 1).strip()
    if not key_text:
        await update.message.reply_text("Format:\n/setremote_key\n-----BEGIN...-----")
        return
    valid = ["-----BEGIN OPENSSH PRIVATE KEY-----", "-----BEGIN RSA PRIVATE KEY-----", "-----BEGIN EC PRIVATE KEY-----"]
    if not any(h in key_text for h in valid):
        await update.message.reply_text("Format key tidak valid.")
        return
    ssh_dir = Path.home() / ".ssh"
    ssh_dir.mkdir(mode=0o700, exist_ok=True)
    key_path = ssh_dir / "remote_vps_key"
    key_path.write_text(key_text.strip() + "\n")
    key_path.chmod(0o600)
    update_env_value("REMOTE_SSH_KEY", str(key_path))
    global REMOTE_SSH_KEY
    REMOTE_SSH_KEY = str(key_path)
    try:
        await update.message.delete()
    except:
        pass
    await context.bot.send_message(chat_id=update.effective_chat.id, text="✅ Key tersimpan. Test: /remote hostname")

async def remote_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    if not context.args:
        await update.message.reply_text("Format: /remote command")
        return
    command = " ".join(context.args)
    await safe_send(update.message, f"⚙️ Remote:\n`{command}`")
    result = await asyncio.to_thread(run_remote_command, command)
    for chunk in split_message(result):
        await safe_send(update.message, chunk)

async def remote_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    key_exists = Path(REMOTE_SSH_KEY).exists() if REMOTE_SSH_KEY else False
    await update.message.reply_text(
        f"Remote VPS:\nHost: {REMOTE_SSH_HOST or '-'}\nPort: {REMOTE_SSH_PORT}\n"
        f"User: {REMOTE_SSH_USER}\nKey exists: {key_exists}"
    )


# ========================
# FILE CONTENT EXTRACTION
# ========================

async def reminder_check_loop(app):
    """Background loop to check and send due reminders."""
    bot = app.bot
    while True:
        try:
            reminders = await asyncio.to_thread(get_due_reminders)
            for r in reminders:
                try:
                    await safe_send(bot,
                        chat_id=r["chat_id"],
                        text=f"\u23f0 *REMINDER!*\n\n{r['text']}"
                    )
                    await asyncio.to_thread(mark_reminder_sent, r["id"])
                except Exception as e:
                    logging.error(f"Failed to send reminder {r['id']}: {e}")
        except Exception as e:
            logging.error(f"Reminder check error: {e}")
        await asyncio.sleep(30)  # Check every 30 seconds


async def reflect_loop():
    """Periodik: refleksi pengalaman jadi learned_patterns (self-learning layer 2)."""
    await asyncio.sleep(300)
    while True:
        try:
            res = await asyncio.to_thread(sl.reflect, 5)
            logging.info(f"[self_learning] reflect: {res}")
        except Exception as _e:
            logging.warning(f"[self_learning] reflect error: {_e}")
        await asyncio.sleep(3600 * 6)


