"""Split from telegram_agent monolith — behavior preserved."""
from __future__ import annotations

from kai_core.config import *  # noqa: F401,F403
import asyncio as _aio
import tempfile as _tmp
from kai_core.telegram_util import _html_format

import self_learning as sl
import mem0_integration
from kai_core.memory_ops import *
from kai_core.prompt import build_system_prompt
from kai_core.db import *
from kai_core.shell_tools import run_aws_command
from kai_core import media_tools as _media

def generate_image_pollinations(*a, **k):
    return _media.generate_image_pollinations(*a, **k)
def generate_pdf_content(*a, **k):
    return _media.generate_pdf_content(*a, **k)
def generate_docx_content(*a, **k):
    return _media.generate_docx_content(*a, **k)

def web_search(query: str) -> str:
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        results = []
        if data.get("AbstractText"):
            results.append(f"📌 {data['AbstractText']}")
            if data.get("AbstractURL"):
                results.append(f"Sumber: {data['AbstractURL']}")
        for r in data.get("RelatedTopics", [])[:5]:
            if isinstance(r, dict) and r.get("Text"):
                results.append(f"• {r['Text'][:200]}")
        if results:
            return f"Hasil pencarian '{query}':\n\n" + "\n".join(results[:8])
        return f"Tidak ada hasil untuk: {query}"
    except Exception as e:
        return f"Web search error: {e}"

def should_search_web(text: str) -> bool:
    t = text.lower()
    kw = ["cari", "search", "cek berita", "berita terbaru", "apa itu", "siapa itu",
          "info tentang", "harga", "cuaca", "terbaru", "latest", "news",
          "update terbaru", "yang terjadi", "hari ini"]
    return any(k in t for k in kw)

# ========================
# AI CORE
# ========================

def _select_client(model_name: str):
    """Pilih client berdasarkan model name. Returns (client, actual_model)."""
    if freemodel_client and model_name in FREEMODEL_MODELS:
        return freemodel_client, model_name
    elif model_name.startswith("fm/"):
        return freemodel_client or client, model_name[3:]
    return client, model_name


def ask_ai(chat_id: int, user_text: str, extra_context: str = "", thread_id: int = None) -> str:
    history = load_history(chat_id, thread_id)
    active_model = resolve_model(chat_id, thread_id)
    system = build_system_prompt()
    if extra_context:
        system += f"\n\nKonteks tambahan:\n{extra_context}"
    messages = [{"role": "system", "content": system}]
    messages.extend(history[-40:])
    messages.append({"role": "user", "content": user_text})
    active_client, actual_model = _select_client(active_model)
    try:
        response = active_client.chat.completions.create(model=actual_model, messages=messages, stream=False, temperature=0.7)
        answer = response.choices[0].message.content or ""
    except Exception as e:
        err_msg = str(e)[:300]
        logging.error(f"[LLM] ask_ai error model={active_model}: {err_msg}")
        last_llm_error[chat_id] = {"model": active_model, "error": err_msg, "user_text": user_text, "extra_context": extra_context}
        return f"⚠️ Error model {active_model}: {err_msg}"
    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": answer})
    save_history(chat_id, history[-40:], thread_id)
    return answer


def extract_tool_calls(text: str) -> list:
    """Extract semua format tool_call yang mungkin dikeluarkan model"""
    results = []

    # Format 1: <tool_call>...</tool_call>
    pattern1 = re.compile(r'<tool_(?:call|use)>(.*?)</tool_(?:call|use)>', re.DOTALL)
    for m in pattern1.finditer(text):
        try:
            results.append(json.loads(m.group(1).strip()))
        except:
            pass

    # Format 2: ```json\n{...}\n``` dengan nama tool di dalamnya
    pattern2 = re.compile(r'```(?:json)?\s*(\{[^`]+\})\s*```', re.DOTALL)
    for m in pattern2.finditer(text):
        try:
            obj = json.loads(m.group(1).strip())
            if "name" in obj and "arguments" in obj:
                results.append(obj)
        except:
            pass

    return results

def get_command_from_call(call: dict) -> str:
    """Ambil command dari berbagai format tool call"""
    args = call.get("arguments", {})
    # Coba semua key yang mungkin berisi command
    for key in ["command", "cmd", "bash", "shell", "script", "code"]:
        if key in args and args[key]:
            return str(args[key])
    # Kalau arguments adalah string langsung
    if isinstance(args, str):
        return args
    return ""

def has_tool_call(text: str) -> bool:
    """Cek apakah teks mengandung tool_call"""
    return "<tool_call>" in text or "<tool_use>" in text or ('"name"' in text and '"arguments"' in text and "```" in text)

def strip_tool_calls(text: str) -> str:
    """Hapus semua tool_call block dari teks"""
    text = re.sub(r'<tool_(?:call|use)>.*?</tool_(?:call|use)>', '', text, flags=re.DOTALL)
    text = re.sub(r'```(?:json)?\s*\{[^`]*"name"[^`]*\}\s*```', '', text, flags=re.DOTALL)
    return text.strip()

# Alias lama
def parse_tool_calls(text: str) -> list:
    return extract_tool_calls(text)

def get_chat_lock(chat_id: int):
    """Lazy create asyncio.Lock per chat. Dipanggil dari async context."""
    import asyncio as _aio
    if chat_id not in chat_locks:
        chat_locks[chat_id] = _aio.Lock()
    return chat_locks[chat_id]


# Sudo commands yang aman untuk auto-execute tanpa konfirmasi user
SAFE_SUDO_PATTERNS = [
    "sudo systemctl restart",
    "sudo systemctl start",
    "sudo systemctl stop",
    "sudo systemctl reload",
    "sudo systemctl daemon-reload",
    "sudo systemctl status",
    "sudo systemctl enable",
    "sudo systemctl disable",
    "sudo apt update",
    "sudo apt upgrade",
    "sudo apt install",
    "sudo pip install",
    "sudo ufw",
    "sudo journalctl",
    "sudo cat /etc/",
    "sudo ls",
    "sudo mkdir",
    "sudo cp",
    "sudo tee",
    "sudo chown",
    "sudo chmod",
    "sudo nano",
    "sudo vim",
    "sudo service",
    "sudo snap",
    "sudo fallocate",
    "sudo mkswap",
    "sudo swapon",
    "sudo swapoff",
    "sudo netstat",
    "sudo ss ",
    "sudo iptables -L",
    "sudo nginx -t",
    "sudo nginx -s reload",
]

def get_risk_from_call(call: dict) -> str:
    """Ekstrak risk level dari tool_call. Default low kalau ga disebut.
    Downgrade high -> medium untuk sudo commands yang match SAFE_SUDO_PATTERNS."""
    args = call.get("arguments", {})
    if isinstance(args, dict):
        risk = str(args.get("risk", "low")).lower().strip()
        if risk == "high":
            cmd = get_command_from_call(call).strip()
            for pattern in SAFE_SUDO_PATTERNS:
                if cmd.startswith(pattern):
                    return "medium"
        if risk in ("low", "medium", "high"):
            return risk
    return "low"

def ask_ai_agentic(chat_id: int, user_text: str, extra_context: str = "", thread_id: int = None) -> dict:
    """AI dengan agentic loop — intercept tool_call, eksekusi, feed balik.

    Returns dict:
        {"answer": str, "pending_command": Optional[str], "pending_risk": Optional[str]}

    Kalau pending_command terisi → caller harus simpan ke pending_aws_commands dan
    kirim konfirmasi ke user. Loop berhenti di situ — di-resume manual saat user "ya".
    """
    history = load_history(chat_id, thread_id)
    active_model = resolve_model(chat_id, thread_id)

    # Pilih client
    active_client = client
    actual_model = active_model
    if freemodel_client and active_model in FREEMODEL_MODELS:
        active_client = freemodel_client
    elif active_model.startswith("fm/"):
        actual_model = active_model[3:]
        active_client = freemodel_client or client

    system = build_system_prompt()
    _mem0_ctx = mem0_integration.search_relevant(user_text, limit=5)
    if _mem0_ctx:
        system += _mem0_ctx
    if extra_context:
        system += f"\n\nKonteks tambahan:\n{extra_context}"

    messages = [{"role": "system", "content": system}]
    messages.extend(history[-40:])
    messages.append({"role": "user", "content": user_text})

    # Track turns yang akan dipersist ke history (selain user_text & final_answer)
    persisted_turns = [{"role": "user", "content": user_text}]

    max_loops = 20
    final_answer = ""
    pending_command = None
    pending_risk = None
    answer = ""
    generated_files = []
    generated_images = []

    for i in range(max_loops):
        if chat_cancel.pop(chat_id, False):
            final_answer = "✖️ Dibatalkan user."
            break
        try:
            response = active_client.chat.completions.create(
                model=actual_model, messages=messages, stream=False, temperature=0.7
            )
            answer = response.choices[0].message.content or ""
        except Exception as e:
            err_msg = str(e)[:300]
            logging.error(f"[LLM] ask_ai_agentic error model={actual_model}: {err_msg}")
            last_llm_error[chat_id] = {"model": actual_model, "error": err_msg, "user_text": user_text, "extra_context": extra_context}
            final_answer = f"⚠️ Error model {actual_model}: {err_msg}"
            break

        tool_calls = extract_tool_calls(answer)

        if not tool_calls:
            # Jawaban final — tidak ada tool_call
            final_answer = strip_tool_calls(answer) or answer
            break

        # Cek apakah ada high-risk command — gate kalau iya
        high_risk_call = next(
            (c for c in tool_calls if get_risk_from_call(c) == "high"),
            None,
        )
        if high_risk_call is not None:
            cmd = get_command_from_call(high_risk_call)
            if cmd:
                # Simpan turns sejauh ini
                persisted_turns.append({"role": "assistant", "content": answer})
                # Final answer ke user = penjelasan + minta konfirmasi
                text_part = strip_tool_calls(answer).strip()
                prefix = (text_part + "\n\n") if text_part else ""
                final_answer = (
                    f"{prefix}⚠️ Mau jalanin command high-risk:\n"
                    f"`{cmd}`\n\nBalas `ya` untuk lanjut, atau `batal` untuk cancel."
                )
                pending_command = cmd
                pending_risk = "high"
                break

        # Semua tool_calls low/medium — eksekusi auto
        messages.append({"role": "assistant", "content": answer})
        persisted_turns.append({"role": "assistant", "content": answer})

        tool_results = []
        for call in tool_calls:
            name = call.get("name", "tool")
            args = call.get("arguments", {})
            command = get_command_from_call(call)
            risk = get_risk_from_call(call)

            # Handle generate_image tool
            if name == "generate_image":
                prompt = args.get("prompt", "")
                width = int(args.get("width", 1024))
                height = int(args.get("height", 1024))
                if prompt:
                    img_path = generate_image_pollinations(prompt, width, height)
                    if img_path:
                        generated_images.append({"path": img_path, "caption": prompt[:200]})
                        tool_results.append(f"[generate_image] Gambar berhasil dibuat dan akan dikirim ke user. Prompt: {prompt[:100]}")
                    else:
                        tool_results.append(f"[generate_image] Gagal generate gambar untuk prompt: {prompt[:100]}")
                else:
                    tool_results.append("[generate_image] Prompt kosong")
                continue

            # Handle mcp_call tool — eksekusi MCP bridge with error handling + logging
            if name == "mcp_call":
                server = args.get("server", "") if isinstance(args, dict) else ""
                tool_name = args.get("tool", "") if isinstance(args, dict) else ""
                tool_args = args.get("args", {}) if isinstance(args, dict) else {}
                if not server or not tool_name:
                    tool_results.append("[mcp_call] server dan tool wajib diisi")
                    continue
                # Per-server timeout (windows-agent may be offline, quick-fail)
                mcp_timeouts = {"windows-agent": 10, "google": 60, "notion": 30, "github": 30, "filesystem": 15}
                mcp_timeout = mcp_timeouts.get(server, 60)
                # Write args to temp file to avoid shell quoting issues
                import tempfile as _tmp
                args_json = json.dumps(tool_args) if isinstance(tool_args, dict) else str(tool_args)
                with _tmp.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as _af:
                    _af.write(args_json)
                    _args_file = _af.name
                mcp_cmd = f"cd ~/ai-agent && venv/bin/python mcp/mcp_bridge.py call {server} {tool_name} $(cat {_args_file})"
                try:
                    mcp_result = run_aws_command(mcp_cmd, timeout=mcp_timeout)
                    # Log to experience
                    try:
                        _rs = (mcp_result or "").strip()
                        _ok = not _rs[:60].upper().lstrip().startswith(("FAIL", "ERROR", "TRACEBACK", "NOT FOUND", "TIMEOUT"))
                        sl.log_experience(context=user_text[:300], action=f"mcp:{server}.{tool_name}", outcome=_rs[:300], success=_ok)
                    except Exception:
                        pass
                    tool_results.append(f"[mcp_call] server={server} tool={tool_name}:\n{mcp_result[:2000]}")
                except Exception as _mcp_err:
                    tool_results.append(f"[mcp_call] ERROR server={server} tool={tool_name}: {str(_mcp_err)[:200]}")
                finally:
                    try:
                        os.unlink(_args_file)
                    except Exception:
                        pass
                continue

            # Handle send_file tool — kirim file yang sudah ada ke user
            if name == "send_file":
                file_path = args.get("path", "") if isinstance(args, dict) else str(args)
                caption = args.get("caption", "") if isinstance(args, dict) else ""
                if file_path:
                    if file_path.startswith("~"):
                        file_path = os.path.expanduser(file_path)
                    elif not file_path.startswith("/"):
                        file_path = os.path.join("/home/ubuntu/ai-agent", file_path)
                    if os.path.isfile(file_path):
                        file_size = os.path.getsize(file_path)
                        if file_size > 50 * 1024 * 1024:
                            tool_results.append(f"[send_file] File terlalu besar ({file_size // 1024 // 1024}MB), max 50MB")
                        else:
                            generated_files.append({"path": file_path, "caption": caption or os.path.basename(file_path)})
                            tool_results.append(f"[send_file] File {os.path.basename(file_path)} ({file_size // 1024}KB) akan dikirim ke user.")
                    else:
                        tool_results.append(f"[send_file] File tidak ditemukan: {file_path}")
                else:
                    tool_results.append("[send_file] Path kosong")
                continue

            # Handle generate_file tool
            if name == "generate_file":
                title = args.get("title", "Document")
                content = args.get("content", "")
                fmt = args.get("format", "pdf").lower()
                if content:
                    if fmt == "docx":
                        file_path = generate_docx_content(title, content)
                    else:
                        file_path = generate_pdf_content(title, content)
                    if file_path:
                        generated_files.append({"path": file_path, "caption": title})
                        tool_results.append(f"[generate_file] File {fmt.upper()} berhasil dibuat: {title}. Akan dikirim ke user.")
                    else:
                        tool_results.append(f"[generate_file] Gagal generate file {fmt.upper()}: {title}")
                else:
                    tool_results.append("[generate_file] Content kosong")
                continue

            if not command:
                tool_results.append(f"[{name}]: command kosong, skip")
                continue

            timeout = 180 if risk == "medium" else 90
            result = run_aws_command(command, timeout=timeout)
            tool_results.append(
                f"[output dari {name}] (risk={risk}, cmd={command[:200]}):\n{result[:2000]}"
            )
            try:
                _rs = (result or "").strip()
                _ok = not _rs[:60].upper().lstrip().startswith(("FAIL", "ERROR", "TRACEBACK", "NOT FOUND"))
                sl.log_experience(context=user_text[:300], action=command[:300], outcome=_rs[:300], success=_ok)
            except Exception:
                pass

        tool_output = "\n\n".join(tool_results)
        remaining = max_loops - i - 1
        tool_msg = (
            f"Tool execution selesai (step {i+1}/{max_loops}, sisa {remaining} step). Hasil:\n\n{tool_output}\n\n"
            "Kalo butuh step berikutnya, output tool_use lagi. "
            "Kalo udah cukup atau sisa step tinggal sedikit, LANGSUNG kasih jawaban final ke user dalam bahasa natural tanpa tool_use."
        )
        messages.append({"role": "user", "content": tool_msg})
        persisted_turns.append({"role": "user", "content": tool_msg})
    else:
        # Loop habis — auto-continue: jalanin 1 cycle lagi supaya task selesai
        # Minta AI kasih summary dari semua yang udah dikerjain
        summary_prompt = (
            "Loop limit tercapai. Semua tool yang udah lo jalanin BERHASIL dieksekusi. "
            "Sekarang JANGAN output tool_use lagi. Langsung kasih jawaban final ke user: "
            "ringkas apa yang udah dikerjain, hasilnya gimana (sukses/gagal/partial), "
            "dan info penting yang user perlu tau."
        )
        messages.append({"role": "user", "content": summary_prompt})
        try:
            summary_resp = active_client.chat.completions.create(
                model=actual_model, messages=messages, stream=False, temperature=0.7
            )
            final_answer = strip_tool_calls(summary_resp.choices[0].message.content or "")
        except:
            final_answer = strip_tool_calls(answer) or ""

    # Final safety strip
    final_answer = strip_tool_calls(final_answer)
    if not final_answer:
        # Jangan kasih "Selesai." doang — minta AI bikin summary
        summary_prompt = (
            "Task udah selesai dijalanin. Kasih ringkasan singkat ke user: "
            "apa yang barusan dikerjain dan hasilnya gimana. "
            "JANGAN output tool_use. Jawab natural dalam 1-3 kalimat."
        )
        messages.append({"role": "user", "content": summary_prompt})
        try:
            summary_resp = active_client.chat.completions.create(
                model=actual_model, messages=messages, stream=False, temperature=0.7
            )
            final_answer = strip_tool_calls(summary_resp.choices[0].message.content or "") or "Siap, udah gue handle. Ada lagi?"
        except:
            final_answer = "Siap, udah gue handle. Ada lagi?"

    # Persist semua turns + final_answer
    persisted_turns.append({"role": "assistant", "content": final_answer})
    # Replace last user_text entry (sudah kepasang di awal) dengan full sequence
    history.extend(persisted_turns)
    save_history(chat_id, history[-60:], thread_id)

    return {
        "answer": final_answer,
        "pending_command": pending_command,
        "pending_risk": pending_risk,
        "generated_files": generated_files,
        "generated_images": generated_images,
    }

# ========================
# UTILS
# ========================

