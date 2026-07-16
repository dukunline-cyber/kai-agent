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

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo messages — 2-stage: vision model reads image, then main model processes."""
    if not is_allowed(update): return
    if not update.message or not update.message.photo: return
    chat_id = update.effective_chat.id
    thread_id = (update.message.message_thread_id if update.message else (update.callback_query.message.message_thread_id if update.callback_query and update.callback_query.message else None))
    caption = (update.message.caption or "").strip()

    # Status query saat task lagi jalan
    if chat_id in chat_busy:
        info = chat_busy[chat_id]
        elapsed = int(time.time() - info.get("start", time.time()))
        desc = info.get("description", "task")
        await update.message.reply_text(
            f"\u23f3 Lagi proses: {desc} (udah {elapsed}s). Tunggu beres, atau /cancel buat batalin."
        )
        return

    lock = get_chat_lock(chat_id)
    async with lock:
        chat_busy[chat_id] = {"description": caption[:80] if caption else "photo analysis", "start": time.time()}
        try:
            async with TypingIndicator(context.bot, chat_id):
                # Download photo (ambil resolusi tertinggi)
                photo = update.message.photo[-1]
                file_obj = await context.bot.get_file(photo.file_id)
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                    tmp_path = tmp.name
                await file_obj.download_to_drive(tmp_path)

                # Encode to base64
                with open(tmp_path, "rb") as img_f:
                    img_b64 = base64.b64encode(img_f.read()).decode("utf-8")
                os.unlink(tmp_path)

                # === STAGE 1: Vision model baca gambar ===
                VISION_MODEL = "ag/gemini-3-flash"
                vision_prompt = caption if caption else "Describe this image in detail. Extract ALL text visible in the image. If it's a screenshot of a website/app, describe the layout, buttons, forms, and all visible text content."
                vision_content = [
                    {"type": "text", "text": vision_prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                ]
                vision_messages = [
                    {"role": "system", "content": "You are a vision assistant. Describe images accurately and extract all visible text. Respond in the same language as the user's prompt."},
                    {"role": "user", "content": vision_content}
                ]

                vision_response = client.chat.completions.create(
                    model=VISION_MODEL, messages=vision_messages, stream=False, temperature=0.7
                )
                image_description = vision_response.choices[0].message.content or "[Could not read image]"

                # === STAGE 2: Main model processes the description ===
                history = load_history(chat_id, thread_id)
                actual_model = resolve_model(chat_id, thread_id)
                active_client = client

                if caption:
                    combined_text = f"[User sent a photo. Vision analysis result:]\n{image_description}\n\n[User's message:]\n{caption}"
                else:
                    combined_text = f"[User sent a photo. Vision analysis result:]\n{image_description}\n\nAnalisa dan respond berdasarkan isi gambar di atas."

                system = build_system_prompt()
                messages = [{"role": "system", "content": system}]
                messages.extend(history[-40:])
                messages.append({"role": "user", "content": combined_text})

                response = active_client.chat.completions.create(
                    model=actual_model, messages=messages, stream=False, temperature=0.7
                )
                answer = response.choices[0].message.content or ""

                # Save history
                history_text = caption if caption else "[sent a photo]"
                history.append({"role": "user", "content": f"{history_text} [Image description: {image_description[:500]}]"})
                history.append({"role": "assistant", "content": answer})
                save_history(chat_id, history[-40:], thread_id)

                for chunk in split_message(answer):
                    await safe_send(update.message, chunk)
                await send_ai_results(update, context, result, thread_id)
        except Exception as e:
            logging.exception("Error handle_photo")
            await update.message.reply_text(f"Error processing photo: {e}")
        finally:
            chat_busy.pop(chat_id, None)
            chat_cancel.pop(chat_id, None)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle document/file messages — download, read content (PDF/DOCX/XLSX/PPTX/text/images), pass to main model."""
    if not is_allowed(update): return
    if not update.message or not update.message.document: return
    chat_id = update.effective_chat.id
    thread_id = (update.message.message_thread_id if update.message else (update.callback_query.message.message_thread_id if update.callback_query and update.callback_query.message else None))
    caption = (update.message.caption or "").strip()
    doc = update.message.document
    file_name = doc.file_name or "unknown_file"
    file_size = doc.file_size or 0
    mime_type = doc.mime_type or "application/octet-stream"

    # Limit: 20MB max
    if file_size > 20 * 1024 * 1024:
        await update.message.reply_text("File terlalu gede (max 20MB). Compress dulu atau simpen manual di VPS.")
        return

    lock = get_chat_lock(chat_id)
    async with lock:
        chat_busy[chat_id] = {"description": f"processing file: {file_name[:60]}", "start": time.time()}
        try:
            async with TypingIndicator(context.bot, chat_id):
                # Download file
                file_obj = await context.bot.get_file(doc.file_id)
                save_dir = Path.home() / "ai-agent" / "downloads"
                save_dir.mkdir(parents=True, exist_ok=True)
                save_path = save_dir / file_name
                if save_path.exists():
                    stem = save_path.stem
                    suffix = save_path.suffix
                    counter = 1
                    while save_path.exists():
                        save_path = save_dir / f"{stem}_{counter}{suffix}"
                        counter += 1
                await file_obj.download_to_drive(str(save_path))

                # Extract content using unified extractor
                file_content = await asyncio.to_thread(extract_file_content, str(save_path), mime_type)

                # Handle image files sent as documents
                if file_content == "__IMAGE__":
                    try:
                        with open(str(save_path), "rb") as img_f:
                            img_b64 = base64.b64encode(img_f.read()).decode("utf-8")
                        # Determine MIME type for base64
                        img_mime = mime_type if mime_type.startswith("image/") else "image/jpeg"
                        VISION_MODEL = "ag/gemini-3-flash"
                        vision_prompt = caption if caption else "Describe this image in detail. Extract ALL text visible."
                        vision_content = [
                            {"type": "text", "text": vision_prompt},
                            {"type": "image_url", "image_url": {"url": f"data:{img_mime};base64,{img_b64}"}}
                        ]
                        vision_messages = [
                            {"role": "system", "content": "You are a vision assistant. Describe images accurately. Respond in the same language as the user's prompt."},
                            {"role": "user", "content": vision_content}
                        ]
                        vision_response = client.chat.completions.create(
                            model=VISION_MODEL, messages=vision_messages, stream=False, temperature=0.7
                        )
                        file_content = f"[Image analysis:]\n{vision_response.choices[0].message.content}"
                    except Exception as e:
                        file_content = f"[Image file saved at {save_path}, could not analyze: {e}]"

                elif file_content == "__BINARY__":
                    file_content = f"[Binary file saved at {save_path}. Size: {file_size} bytes, MIME: {mime_type}]"

                # Build message for LLM
                if file_content.startswith("["):
                    combined_text = f"[User sent a file: {file_name} ({mime_type}, {file_size} bytes)]\n{file_content}"
                else:
                    combined_text = f"[User sent a file: {file_name} ({mime_type}, {file_size} bytes). Content:]\n{file_content}"
                if caption:
                    combined_text += f"\n\n[User's message:]\n{caption}"
                else:
                    combined_text += f"\n\nProses file ini sesuai konteks. Kalo ini skill file, install ke lokasi yang tepat."

                history = load_history(chat_id, thread_id)
                actual_model = resolve_model(chat_id, thread_id)
                system = build_system_prompt()
                messages = [{"role": "system", "content": system}]
                messages.extend(history[-40:])
                messages.append({"role": "user", "content": combined_text})

                # Use agentic loop for file processing
                result = await asyncio.to_thread(ask_ai_agentic, chat_id, combined_text, "", thread_id)
                if isinstance(result, dict):
                    answer = result.get("answer", "")
                else:
                    answer = result

                # Save history
                history_text = caption if caption else f"[sent file: {file_name}]"
                history.append({"role": "user", "content": f"{history_text} [File: {file_name}, saved at {save_path}]"})
                history.append({"role": "assistant", "content": answer})
                save_history(chat_id, history[-40:], thread_id)

                for chunk in split_message(answer):
                    await safe_send(update.message, chunk)
                await send_ai_results(update, context, result, thread_id)
        except Exception as e:
            logging.exception("Error handle_document")
            await update.message.reply_text(f"Error processing file: {e}")
        finally:
            chat_busy.pop(chat_id, None)
            chat_cancel.pop(chat_id, None)

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle video messages — extract frames, analyze with vision model."""
    if not is_allowed(update): return
    if not update.message: return
    video = update.message.video or update.message.video_note
    if not video: return
    chat_id = update.effective_chat.id
    thread_id = (update.message.message_thread_id if update.message else (update.callback_query.message.message_thread_id if update.callback_query and update.callback_query.message else None))
    caption = (update.message.caption or "").strip()

    if chat_id in chat_busy:
        info = chat_busy[chat_id]
        elapsed = int(time.time() - info.get("start", time.time()))
        await update.message.reply_text(
            f"\u23f3 Lagi proses: {info.get('description', 'task')} (udah {elapsed}s). Tunggu beres, atau /cancel."
        )
        return

    lock = get_chat_lock(chat_id)
    async with lock:
        chat_busy[chat_id] = {"description": caption[:80] if caption else "video analysis", "start": time.time()}
        try:
            async with TypingIndicator(context.bot, chat_id):
                # Download video
                file_obj = await context.bot.get_file(video.file_id)
                save_dir = Path.home() / "ai-agent" / "downloads"
                save_dir.mkdir(parents=True, exist_ok=True)
                video_ext = ".mp4"
                if hasattr(video, 'file_name') and video.file_name:
                    video_ext = Path(video.file_name).suffix or ".mp4"
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_path = save_dir / f"video_{timestamp}{video_ext}"
                await file_obj.download_to_drive(str(save_path))

                # Extract frames
                frames = await asyncio.to_thread(extract_video_frames, str(save_path), 4)

                if not frames:
                    await update.message.reply_text("Gagal extract frame dari video. Format mungkin ga didukung.")
                    return

                # Analyze each frame with vision model
                VISION_MODEL = "ag/gemini-3-flash"
                frame_descriptions = []

                for i, frame_path in enumerate(frames):
                    with open(frame_path, "rb") as img_f:
                        img_b64 = base64.b64encode(img_f.read()).decode("utf-8")

                    vision_content = [
                        {"type": "text", "text": f"Frame {i+1}/{len(frames)} of a video. Describe what you see in detail."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                    ]
                    vision_messages = [
                        {"role": "system", "content": "You are a vision assistant analyzing video frames. Be concise but detailed."},
                        {"role": "user", "content": vision_content}
                    ]
                    try:
                        vision_response = client.chat.completions.create(
                            model=VISION_MODEL, messages=vision_messages, stream=False, temperature=0.7
                        )
                        desc = vision_response.choices[0].message.content or "[no description]"
                        frame_descriptions.append(f"Frame {i+1}: {desc}")
                    except Exception as e:
                        frame_descriptions.append(f"Frame {i+1}: [error: {e}]")

                # Cleanup frames
                cleanup_frames(frames)

                # Build combined analysis
                video_analysis = "\n\n".join(frame_descriptions)
                duration = getattr(video, 'duration', 0) or 0

                if caption:
                    combined_text = f"[User sent a video ({duration}s). Frame analysis:]\n{video_analysis}\n\n[User's message:]\n{caption}"
                else:
                    combined_text = f"[User sent a video ({duration}s). Frame analysis:]\n{video_analysis}\n\nAnalisa video ini berdasarkan frame-frame di atas dan deskripsikan apa yang terjadi."

                # Main model response
                history = load_history(chat_id, thread_id)
                actual_model = resolve_model(chat_id, thread_id)
                system = build_system_prompt()
                messages = [{"role": "system", "content": system}]
                messages.extend(history[-40:])
                messages.append({"role": "user", "content": combined_text})

                response = client.chat.completions.create(
                    model=actual_model, messages=messages, stream=False, temperature=0.7
                )
                answer = response.choices[0].message.content or ""

                # Save history
                history_text = caption if caption else "[sent a video]"
                history.append({"role": "user", "content": f"{history_text} [Video analysis: {video_analysis[:500]}]"})
                history.append({"role": "assistant", "content": answer})
                save_history(chat_id, history[-40:], thread_id)

                for chunk in split_message(answer):
                    await safe_send(update.message, chunk)
                await send_ai_results(update, context, result, thread_id)
        except Exception as e:
            logging.exception("Error handle_video")
            await update.message.reply_text(f"Error processing video: {e}")
        finally:
            chat_busy.pop(chat_id, None)
            chat_cancel.pop(chat_id, None)


def transcribe_voice(file_path: str) -> str:
    """Transcribe voice/audio file to text using SpeechRecognition + Google free API."""
    if not SR_AVAILABLE:
        return ""
    try:
        # Convert ogg/mp3/etc to wav using ffmpeg
        wav_path = file_path.rsplit(".", 1)[0] + ".wav"
        result = subprocess.run(
            ["ffmpeg", "-i", file_path, "-ar", "16000", "-ac", "1", "-y", wav_path],
            capture_output=True, timeout=30
        )
        if result.returncode != 0:
            logging.warning(f"ffmpeg convert failed: {result.stderr.decode()[:200]}")
            return ""

        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio = recognizer.record(source, duration=120)  # max 2 min

        # Try Google free API first
        try:
            text = recognizer.recognize_google(audio, language="id-ID")
            return text
        except sr.UnknownValueError:
            # Try English
            try:
                text = recognizer.recognize_google(audio, language="en-US")
                return text
            except:
                return ""
        except sr.RequestError as e:
            logging.warning(f"Google STT error: {e}")
            return ""
    except Exception as e:
        logging.warning(f"Transcribe error: {e}")
        return ""
    finally:
        # Cleanup wav
        try:
            if os.path.exists(wav_path):
                os.remove(wav_path)
        except:
            pass


async def text_to_speech(text: str, output_path: str, voice: str = "id-ID-ArdiNeural") -> bool:
    """Convert text to speech using edge-tts. Returns True if successful."""
    if not EDGE_TTS_AVAILABLE:
        return False
    try:
        # Limit text length for TTS
        if len(text) > 2000:
            text = text[:2000] + "..."
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception as e:
        logging.warning(f"TTS error: {e}")
        return False


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice/audio messages — transcribe and process with AI."""
    if not is_allowed(update): return
    if not update.message: return
    voice = update.message.voice or update.message.audio
    if not voice: return
    chat_id = update.effective_chat.id
    thread_id = (update.message.message_thread_id if update.message else (update.callback_query.message.message_thread_id if update.callback_query and update.callback_query.message else None))

    if chat_id in chat_busy:
        info = chat_busy[chat_id]
        elapsed = int(time.time() - info.get("start", time.time()))
        await update.message.reply_text(
            f"\u23f3 Lagi proses: {info.get('description', 'task')} (udah {elapsed}s). Tunggu beres, atau /cancel."
        )
        return

    lock = get_chat_lock(chat_id)
    async with lock:
        chat_busy[chat_id] = {"description": "processing voice message", "start": time.time()}
        try:
            async with TypingIndicator(context.bot, chat_id):
                file_obj = await context.bot.get_file(voice.file_id)
                save_dir = Path.home() / "ai-agent" / "downloads"
                save_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_path = save_dir / f"voice_{timestamp}.ogg"
                await file_obj.download_to_drive(str(save_path))

                duration = getattr(voice, 'duration', 0) or 0

                # Transcribe voice to text
                transcription = await asyncio.to_thread(transcribe_voice, str(save_path))

                if transcription:
                    combined_text = (
                        f"[User sent a voice message ({duration}s). Transcription: {transcription}]\n\n"
                        f"{transcription}"
                    )
                else:
                    combined_text = (
                        f"[User sent a voice message ({duration}s). File saved at {save_path}. "
                        f"Ga bisa di-transcribe otomatis. Kasih tau user voice udah diterima tapi "
                        f"ga bisa di-convert ke teks — minta ketik ulang atau kirim teks.]"
                    )

                # Log file to DB
                log_file_db(chat_id, "voice", f"voice_{timestamp}.ogg", str(save_path), "audio/ogg", getattr(voice, 'file_size', 0) or 0)

                # Use agentic loop
                result = await asyncio.to_thread(ask_ai_agentic, chat_id, combined_text, "", thread_id)
                if isinstance(result, dict):
                    answer = result.get("answer", "")
                else:
                    answer = str(result)

                for chunk in split_message(answer):
                    await safe_send(update.message, chunk)
                await send_ai_results(update, context, result, thread_id)

                # If user asked for voice reply or answer is short, also send as voice
                if transcription and ("balas suara" in transcription.lower() or "voice" in transcription.lower()):
                    tts_path = str(save_dir / f"tts_{timestamp}.mp3")
                    if await text_to_speech(answer[:1000], tts_path):
                        try:
                            await context.bot.send_voice(chat_id=chat_id, message_thread_id=thread_id, voice=open(tts_path, "rb"))
                        except Exception as e:
                            logging.warning(f"Failed to send TTS: {e}")
                        finally:
                            try: os.remove(tts_path)
                            except: pass
        except Exception as e:
            logging.exception("Error handle_voice")
            await update.message.reply_text(f"Error processing voice: {e}")
        finally:
            chat_busy.pop(chat_id, None)
            chat_cancel.pop(chat_id, None)

async def handle_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle sticker messages — analyze sticker with vision if possible."""
    if not is_allowed(update): return
    if not update.message or not update.message.sticker: return
    chat_id = update.effective_chat.id
    thread_id = (update.message.message_thread_id if update.message else (update.callback_query.message.message_thread_id if update.callback_query and update.callback_query.message else None))
    sticker = update.message.sticker

    if chat_id in chat_busy:
        info = chat_busy[chat_id]
        elapsed = int(time.time() - info.get("start", time.time()))
        await update.message.reply_text(
            f"\u23f3 Lagi proses: {info.get('description', 'task')} (udah {elapsed}s). Tunggu beres, atau /cancel."
        )
        return

    lock = get_chat_lock(chat_id)
    async with lock:
        chat_busy[chat_id] = {"description": "processing sticker", "start": time.time()}
        try:
            async with TypingIndicator(context.bot, chat_id):
                emoji = sticker.emoji or ""
                set_name = sticker.set_name or "unknown"
                is_animated = sticker.is_animated
                is_video = sticker.is_video

                # Try to get sticker image for vision analysis
                sticker_desc = ""
                if not is_animated and not is_video and sticker.file_id:
                    try:
                        file_obj = await context.bot.get_file(sticker.file_id)
                        save_dir = Path.home() / "ai-agent" / "downloads"
                        save_dir.mkdir(parents=True, exist_ok=True)
                        save_path = save_dir / f"sticker_{datetime.now().strftime('%Y%m%d_%H%M%S')}.webp"
                        await file_obj.download_to_drive(str(save_path))

                        # Convert webp to png for vision
                        if PIL_AVAILABLE:
                            png_path = str(save_path).replace(".webp", ".png")
                            img = Image.open(str(save_path))
                            img.save(png_path, "PNG")
                            with open(png_path, "rb") as f:
                                img_data = base64.b64encode(f.read()).decode()

                            vision_model = "ag/gemini-3-flash"
                            vision_response = client.chat.completions.create(
                                model=vision_model,
                                messages=[{
                                    "role": "user",
                                    "content": [
                                        {"type": "text", "text": "Describe this sticker image briefly in 1-2 sentences. What does it show?"},
                                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_data}"}}
                                    ]
                                }],
                                stream=False, temperature=0.7
                            )
                            sticker_desc = vision_response.choices[0].message.content or ""
                            try: os.remove(png_path)
                            except: pass
                    except Exception as e:
                        logging.warning(f"Sticker vision failed: {e}")

                combined_text = f"[User sent a sticker. Emoji: {emoji}, Sticker set: {set_name}"
                if sticker_desc:
                    combined_text += f", Visual description: {sticker_desc}"
                combined_text += "]. Respond naturally to the sticker — bisa pake emoji atau sticker-like response."

                result = await asyncio.to_thread(ask_ai_agentic, chat_id, combined_text, "", thread_id)
                if isinstance(result, dict):
                    answer = result.get("answer", "")
                else:
                    answer = str(result)

                for chunk in split_message(answer):
                    await safe_send(update.message, chunk)
                await send_ai_results(update, context, result, thread_id)
        except Exception as e:
            logging.exception("Error handle_sticker")
            await update.message.reply_text(f"Error: {e}")
        finally:
            chat_busy.pop(chat_id, None)
            chat_cancel.pop(chat_id, None)


