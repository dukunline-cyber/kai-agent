"""Split from telegram_agent monolith — behavior preserved."""
from __future__ import annotations

from kai_core.config import *  # noqa: F401,F403
from kai_handlers.callback import extract_and_store_memory

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

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    if not update.message or not update.message.text: return
    chat_id = update.effective_chat.id
    thread_id = (update.message.message_thread_id if update.message else (update.callback_query.message.message_thread_id if update.callback_query and update.callback_query.message else None))
    user_text = update.message.text.strip()

    # Status query saat task lagi jalan → jawab cepat tanpa antri
    if chat_id in chat_busy and is_status_query(user_text):
        info = chat_busy[chat_id]
        elapsed = int(time.time() - info.get("start", time.time()))
        desc = info.get("description", "task")
        await update.message.reply_text(
            f"⏳ Lagi proses: {desc} (udah {elapsed}s). Tunggu beres, atau /cancel buat batalin."
        )
        return

    lock = get_chat_lock(chat_id)
    async with lock:
        chat_busy[chat_id] = {"description": user_text[:80], "start": time.time()}
        try:
            if await handle_remote_natural(update, context, user_text): return
            if await handle_aws_natural(update, context, user_text): return

            async with TypingIndicator(context.bot, chat_id):
                extra_context = ""

                # Check for TTS request — "bacain", "suarakan", "/tts"
                tts_request = False
                tts_text_override = ""
                if user_text.lower().startswith("/tts ") or user_text.lower().startswith("bacain ") or user_text.lower().startswith("suarakan "):
                    tts_request = True
                    tts_text_override = user_text.split(" ", 1)[1] if " " in user_text else ""

                # Check for reminder request
                reminder_parsed = parse_reminder(user_text)
                if reminder_parsed:
                    remind_text, remind_at = reminder_parsed
                    add_reminder_db(chat_id, remind_text, remind_at)
                    await update.message.reply_text(
                        f"\u23f0 Reminder di-set!\n\n"
                        f"Pesan: {remind_text}\n"
                        f"Waktu: {remind_at}\n\n"
                        f"Gua bakal ingetin lo nanti. Ketik /reminders buat lihat semua reminder."
                    )
                    history = load_history(chat_id, thread_id)
                    history.append({"role": "user", "content": user_text})
                    history.append({"role": "assistant", "content": f"[Reminder set: {remind_text} at {remind_at}]"})
                    save_history(chat_id, history[-40:], thread_id)
                    return

                if should_search_web(user_text):
                    search_result = await asyncio.to_thread(web_search, user_text)
                    extra_context = f"Hasil web search:\n{search_result}"

                # Check for image generation request
                if should_generate_image(user_text):
                    # Let AI generate a good prompt, then generate image
                    prompt_response = client.chat.completions.create(
                        model=resolve_model(chat_id, thread_id),
                        messages=[
                            {"role": "system", "content": "You are an image prompt expert. Convert the user's request into a detailed English prompt for an AI image generator. Output ONLY the prompt, nothing else."},
                            {"role": "user", "content": user_text}
                        ],
                        stream=False, temperature=0.7
                    )
                    img_prompt = prompt_response.choices[0].message.content or user_text
                    img_path = await asyncio.to_thread(generate_image_pollinations, img_prompt.strip())
                    if img_path and os.path.exists(img_path):
                        await context.bot.send_photo(
                            chat_id=chat_id, message_thread_id=thread_id,
                            photo=open(img_path, "rb"),
                            caption=f"Generated: {user_text[:200]}"
                        )
                        history = load_history(chat_id, thread_id)
                        history.append({"role": "user", "content": user_text})
                        history.append({"role": "assistant", "content": f"[Generated image: {img_prompt[:200]}]"})
                        save_history(chat_id, history[-40:], thread_id)
                        return
                    # If generation failed, fall through to normal AI response

                result = await asyncio.to_thread(ask_ai_agentic, chat_id, user_text, extra_context, thread_id)
                # Backward compat: dict vs string
                if isinstance(result, dict):
                    answer = result.get("answer", "")
                    if result.get("pending_command"):
                        pending_aws_commands[chat_id] = result["pending_command"]
                        # Send with inline keyboard buttons
                        keyboard = InlineKeyboardMarkup([
                            [
                                InlineKeyboardButton("\u2705 Ya, jalankan", callback_data=f"exec_yes_{chat_id}"),
                                InlineKeyboardButton("\u274c Batal", callback_data=f"exec_no_{chat_id}")
                            ]
                        ])
                        # We'll add keyboard to the last message
                        pending_keyboards[chat_id] = keyboard
                    # Check for generated files
                    if result.get("generated_files"):
                        for gf in result["generated_files"]:
                            try:
                                await context.bot.send_document(
                                    chat_id=chat_id, message_thread_id=thread_id,
                                    document=open(gf["path"], "rb"),
                                    filename=os.path.basename(gf["path"]),
                                    caption=gf.get("caption", "")
                                )
                            except Exception as e:
                                logging.error(f"Error sending generated file: {e}")
                    if result.get("generated_images"):
                        for gi in result["generated_images"]:
                            try:
                                await context.bot.send_photo(
                                    chat_id=chat_id, message_thread_id=thread_id,
                                    photo=open(gi["path"], "rb"),
                                    caption=gi.get("caption", "")[:200]
                                )
                            except Exception as e:
                                logging.error(f"Error sending generated image: {e}")
                else:
                    answer = str(result)
                keyboard = pending_keyboards.pop(chat_id, None)
                chunks = split_message(answer)
                for i, chunk in enumerate(chunks):
                    if i == len(chunks) - 1 and keyboard:
                        await safe_send(update.message, chunk, reply_markup=keyboard)
                    else:
                        await safe_send(update.message, chunk)

                # Auto-extract and store memory from this conversation
                asyncio.create_task(extract_and_store_memory(chat_id, user_text, answer, thread_id))

                # Send TTS if requested
                if tts_request and EDGE_TTS_AVAILABLE:
                    tts_content = tts_text_override if tts_text_override else answer
                    if tts_content and len(tts_content.strip()) > 0:
                        save_dir = Path.home() / "ai-agent" / "downloads"
                        save_dir.mkdir(parents=True, exist_ok=True)
                        tts_path = str(save_dir / f"tts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3")
                        if await text_to_speech(tts_content[:2000], tts_path):
                            try:
                                await context.bot.send_voice(chat_id=chat_id, message_thread_id=thread_id, voice=open(tts_path, "rb"))
                            except Exception as e:
                                logging.warning(f"Failed to send TTS: {e}")
                            finally:
                                try: os.remove(tts_path)
                                except: pass
        except Exception as e:
            logging.exception("Error handle_message")
            await update.message.reply_text(f"Error: {e}")
        finally:
            chat_busy.pop(chat_id, None)
            chat_cancel.pop(chat_id, None)


def parse_reminder(text: str):
    """Parse reminder request from user text. Returns (reminder_text, remind_at_iso) or None."""
    t = text.lower().strip()
    # Patterns: "ingetin gua jam 3 sore buat meeting", "remind me in 30 minutes to ...",
    # "ingetin 5 menit lagi ...", "reminder jam 14:00 ..."
    import re as _re
    from datetime import datetime as _dt, timedelta as _td

    now = _dt.utcnow() + _td(hours=7)  # WIB (UTC+7)

    # Pattern: "X menit/jam/detik lagi ..."
    m = _re.search(r'(\d+)\s*(menit|jam|detik|min|hour|sec|minute|second|hours|minutes|seconds)\s*(lagi\s*)?(.*)', t)
    if m:
        amount = int(m.group(1))
        unit = m.group(2).lower()
        rest = m.group(4).strip()
        if not rest:
            rest = text  # use full text as reminder
        if unit in ("menit", "min", "minute", "minutes"):
            remind_at = now + _td(minutes=amount)
        elif unit in ("jam", "hour", "hours"):
            remind_at = now + _td(hours=amount)
        elif unit in ("detik", "sec", "second", "seconds"):
            remind_at = now + _td(seconds=amount)
        else:
            return None
        return (rest or text, (remind_at - _td(hours=7)).strftime("%Y-%m-%d %H:%M:%S"))

    # Pattern: "jam HH:MM ..." or "jam H sore/pagi ..."
    m = _re.search(r'jam\s*(\d{1,2})[:.]?(\d{2})?\s*(pagi|siang|sore|malam)?\s*(.*)', t)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2)) if m.group(2) else 0
        period = m.group(3)
        rest = m.group(4).strip()
        if period in ("sore", "malam") and hour < 12:
            hour += 12
        elif period == "pagi" and hour == 12:
            hour = 0
        remind_at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if remind_at <= now:
            remind_at += _td(days=1)  # next day
        return (rest or text, (remind_at - _td(hours=7)).strftime("%Y-%m-%d %H:%M:%S"))

    # Check for keywords
    keywords = ["ingetin", "ingatkan", "remind", "reminder", "alarm"]
    if any(kw in t for kw in keywords):
        # Couldn't parse time — let AI handle it
        return None

    return None


