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

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard button presses."""
    query = update.callback_query
    if not query: return
    await query.answer()
    data = query.data or ""
    chat_id = update.effective_chat.id
    thread_id = (update.message.message_thread_id if update.message else (update.callback_query.message.message_thread_id if update.callback_query and update.callback_query.message else None))

    if data.startswith("exec_yes_"):
        cmd = pending_aws_commands.pop(chat_id, None)
        if cmd:
            await query.edit_message_text(_html_format(f"\u2699\ufe0f Running:\n```\n{cmd}\n```"), parse_mode="HTML")
            result = await asyncio.to_thread(run_aws_command, cmd)
            for chunk in split_message(result):
                await safe_send(context.bot, chunk, chat_id=chat_id, message_thread_id=thread_id)
        else:
            await query.edit_message_text("Ga ada command yang pending.")

    elif data.startswith("exec_no_"):
        pending_aws_commands.pop(chat_id, None)
        await query.edit_message_text("\u274c Command dibatalkan.")

    elif data.startswith("delrem_"):
        try:
            rid = int(data.split("_")[1])
            await asyncio.to_thread(delete_reminder_db, rid)
            await query.edit_message_text(f"Reminder #{rid} dihapus.")
        except:
            await query.edit_message_text("Gagal hapus reminder.")

    elif data.startswith("smp_"):
        prov = data[4:]
        active = resolve_model(chat_id, thread_id)
        buttons, row = [], []
        for tok in model_groups.get(prov, []):
            m = model_button_map.get(tok, "?")
            label = ("✅ " if m == active else "") + m
            row.append(InlineKeyboardButton(label, callback_data=f"sm_{tok}"))
            if len(row) == 2:
                buttons.append(row); row = []
        if row: buttons.append(row)
        buttons.append([InlineKeyboardButton("⬅️ Provider", callback_data="smback")])
        await query.edit_message_text(f"Provider {prov} (aktif: {active}):", reply_markup=InlineKeyboardMarkup(buttons))

    elif data == "smback":
        active = resolve_model(chat_id, thread_id)
        buttons, row = [], []
        for prov in sorted(model_groups):
            row.append(InlineKeyboardButton(f"{prov} ({len(model_groups[prov])})", callback_data=f"smp_{prov}"))
            if len(row) == 2:
                buttons.append(row); row = []
        if row: buttons.append(row)
        await query.edit_message_text(f"Pilih provider (aktif: {active}):", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("sm_"):
        model = model_button_map.get(data[3:])
        if model:
            chat_models[model_key(chat_id, thread_id)] = model
            save_chat_models()
            await query.edit_message_text(f"Model diganti ke: {model} (tersimpan permanen)")
        else:
            await query.edit_message_text("Model ga ketemu, jalanin /models lagi.")


async def retry_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Retry last failed LLM call with a fallback model."""
    if not is_allowed(update): return
    chat_id = update.effective_chat.id
    thread_id = (update.message.message_thread_id if update.message else None)
    err_info = last_llm_error.pop(chat_id, None)
    if not err_info:
        await update.message.reply_text("Ga ada error terakhir buat di-retry.")
        return
    failed_model = err_info["model"]
    user_text = err_info["user_text"]
    extra_context = err_info["extra_context"]
    # Pick first fallback that is not the failed model
    fallback = None
    for m in FALLBACK_MODELS:
        if m != failed_model:
            fallback = m
            break
    if not fallback:
        await update.message.reply_text(
            f"Ga ada fallback model tersedia.\nModel {failed_model} gagal: {err_info['error'][:150]}"
        )
        return
    await update.message.reply_text(f"🔄 Retry dengan fallback: {fallback}")
    # Temporarily set fallback model for this chat
    old_model = chat_models.get(model_key(chat_id, thread_id)) or chat_models.get(str(chat_id))
    chat_models[model_key(chat_id, thread_id)] = fallback
    save_chat_models()
    try:
        async with TypingIndicator(context.bot, chat_id):
            result = await asyncio.to_thread(ask_ai_agentic, chat_id, user_text, extra_context, thread_id)
        if isinstance(result, dict):
            answer = result.get("answer", "")
        else:
            answer = str(result)
        chunks = split_message(answer)
        for chunk in chunks:
            await safe_send(update.message, chunk)
    except Exception as e:
        logging.error(f"[RETRY] fallback {fallback} also failed: {e}")
        await update.message.reply_text(f"⚠️ Fallback {fallback} juga gagal: {str(e)[:200]}")
    finally:
        # Restore original model
        if old_model:
            chat_models[model_key(chat_id, thread_id)] = old_model
        else:
            chat_models.pop(model_key(chat_id, thread_id), None)
        save_chat_models()


async def extract_and_store_memory(chat_id: int, user_text: str, ai_response: str, thread_id=None):
    """Extract important facts from conversation and store to Mem0.
    Called after each conversation to auto-learn user preferences, facts, etc."""
    if not mem0_integration.MEM0_AVAILABLE:
        return
    # Only extract from substantial conversations
    if len(user_text) < 10 or len(ai_response) < 10:
        return
    try:
        extract_prompt = f"""Analyze this conversation and extract ONLY important facts worth remembering long-term.
Rules:
- Extract: user preferences, personal info, important decisions, recurring tasks, technical setup details
- Skip: casual greetings, temporary questions, generic AI responses
- Output: one fact per line, starting with "FACT: "
- If nothing worth remembering, output exactly "NONE"

User said: {user_text[:500]}
AI responded: {ai_response[:500]}"""

        extract_response = client.chat.completions.create(
            model="ag/gemini-3-flash",
            messages=[{"role": "user", "content": extract_prompt}],
            stream=False, temperature=0.0, max_tokens=200
        )
        raw = extract_response.choices[0].message.content or ""
        facts = []
        for line in raw.strip().split("\n"):
            line = line.strip()
            if line.startswith("FACT:"):
                fact = line[5:].strip()
                if fact and len(fact) > 5:
                    facts.append(fact)
        if facts:
            for fact in facts[:3]:  # max 3 facts per conversation
                try:
                    mem0_integration.add_to_memory(fact, metadata={"chat_id": str(chat_id), "ts": str(int(time.time()))})
                    logging.info(f"[MEM0] Auto-stored: {fact[:80]}")
                except Exception as e:
                    logging.warning(f"[MEM0] Failed to store fact: {e}")
    except Exception as e:
        logging.warning(f"[MEM0] Auto-extraction failed: {e}")


async def error_handler(update, context):
    """Handle errors in the bot — also sends notification to owner."""
    import logging
    logger = logging.getLogger(__name__)
    if "Conflict" in str(context.error):
        logger.warning("Conflict error - another bot instance may be running. Ignoring.")
        return
    logger.error(f"Bot error: {context.error}")

    # Send error notification to owner
    if ALLOWED_TELEGRAM_USER_ID:
        try:
            error_msg = str(context.error)[:500]
            await safe_send(context.bot,
                chat_id=int(ALLOWED_TELEGRAM_USER_ID),
                text=f"\u26a0\ufe0f *Bot Error Alert*\n\n`{error_msg}`"
            )
        except Exception:
            pass  # Don't recurse on error

