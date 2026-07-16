"""Split from telegram_agent monolith — behavior preserved."""
from __future__ import annotations

from kai_core.config import *  # noqa: F401,F403
import html as _html_mod


def split_message(text: str, limit: int = 3900):
    chunks = []
    while len(text) > limit:
        split_at = text.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].strip()
    if text:
        chunks.append(text)
    return chunks




def _html_format(text):
    """Convert LLM-ish text -> Telegram HTML parse_mode.
    Rules:
      - Escape & < > di prose
      - ```lang\n...\n``` -> <pre><code class="language-lang">...</code></pre>
      - ``` ... ``` -> <pre>...</pre>
      - `inline` -> <code>inline</code>
      - **bold** -> <b>bold</b>
    Unclosed fenced di-pass-through (no HTML inserted, escape happens normally).
    """
    if not text:
        return text
    placeholders = []
    def stash(content):
        idx = len(placeholders)
        placeholders.append(content)
        return f"\x00PH{idx}\x00"
    def fenced_repl(m):
        lang = (m.group(1) or "").strip()
        body = m.group(2)
        escaped = _html_mod.escape(body)
        if lang:
            return stash(f'<pre><code class="language-{_html_mod.escape(lang)}">{escaped}</code></pre>')
        return stash(f"<pre>{escaped}</pre>")
    text = re.sub(r"```([a-zA-Z0-9_+\-]*)\n?([\s\S]*?)```", fenced_repl, text)
    def inline_repl(m):
        return stash(f"<code>{_html_mod.escape(m.group(1))}</code>")
    text = re.sub(r"`([^`\n]+)`", inline_repl, text)
    text = _html_mod.escape(text)
    text = re.sub(r"\*\*([^\*\n]+)\*\*", r"<b>\1</b>", text)
    # single-asterisk bold (Markdown legacy)
    text = re.sub(r"(?<![\*\w])\*(\S(?:[^\*\n]*\S)?)\*(?![\*\w])", r"<b>\1</b>", text)
    for i, content in enumerate(placeholders):
        text = text.replace(f"\x00PH{i}\x00", content)
    return text


async def safe_send(bot_or_msg, text, chat_id=None, message_thread_id=None, reply_markup=None, **kwargs):
    """Send message with HTML parse_mode (formatted), fallback to plain text on BadRequest."""
    from telegram.error import BadRequest
    send_kwargs = {}
    if reply_markup:
        send_kwargs["reply_markup"] = reply_markup
    is_message = hasattr(bot_or_msg, "reply_text")
    formatted = _html_format(text) if text else text
    try:
        if is_message:
            return await bot_or_msg.reply_text(formatted, parse_mode="HTML", **send_kwargs)
        else:
            return await bot_or_msg.send_message(
                chat_id=chat_id, text=formatted, message_thread_id=message_thread_id,
                parse_mode="HTML", **send_kwargs
            )
    except BadRequest:
        # HTML render failed (malformed tags?) — strip markdown-ish chars and send plain
        plain = re.sub(r"```[a-zA-Z0-9_+\-]*\n?", "", text or "")
        plain = plain.replace("```", "").replace("`", "").replace("**", "")
        try:
            if is_message:
                return await bot_or_msg.reply_text(plain[:4000], **send_kwargs)
            else:
                return await bot_or_msg.send_message(
                    chat_id=chat_id, text=plain[:4000], message_thread_id=message_thread_id, **send_kwargs
                )
        except Exception:
            if is_message:
                return await bot_or_msg.reply_text(plain[:4000])
            else:
                return await bot_or_msg.send_message(chat_id=chat_id, text=plain[:4000])
    except Exception:
        plain = (text or "").replace("```", "").replace("`", "")
        try:
            if is_message:
                return await bot_or_msg.reply_text(plain[:4000], **send_kwargs)
            else:
                return await bot_or_msg.send_message(chat_id=chat_id, text=plain[:4000], message_thread_id=message_thread_id, **send_kwargs)
        except Exception:
            if is_message:
                return await bot_or_msg.reply_text(plain[:4000])
            else:
                return await bot_or_msg.send_message(chat_id=chat_id, text=plain[:4000])


async def send_ai_results(update, context, result, thread_id=None):
    """Send generated files and images from AI agentic result."""
    chat_id = update.effective_chat.id
    if not isinstance(result, dict):
        return
    if result.get("generated_files"):
        for gf in result["generated_files"]:
            try:
                await context.bot.send_document(
                    chat_id=chat_id, message_thread_id=thread_id,
                    document=open(gf["path"], "rb"),
                    filename=os.path.basename(gf["path"]),
                    caption=gf.get("caption", "")[:200]
                )
            except Exception as e:
                logging.error(f"Error sending file: {e}")
    if result.get("generated_images"):
        for gi in result["generated_images"]:
            try:
                await context.bot.send_photo(
                    chat_id=chat_id, message_thread_id=thread_id,
                    photo=open(gi["path"], "rb"),
                    caption=gi.get("caption", "")[:200]
                )
            except Exception as e:
                logging.error(f"Error sending image: {e}")
