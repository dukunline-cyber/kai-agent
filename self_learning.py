"""
self_learning.py — experience-based learning layer untuk Kai.
Standalone module. Di-hook ke agentic loop telegram_agent.py.

3 layer:
  1. log_experience()   -> append task outcome ke experience.jsonl
  2. reflect()          -> ekstrak pattern dari log, simpan ke memory.json[learned_patterns]
  3. recall_patterns()  -> ambil lesson relevan buat di-inject ke konteks sebelum eksekusi
"""
import json
import time
from pathlib import Path
from datetime import datetime, timezone
from difflib import SequenceMatcher

MAX_EXPERIENCE_LINES = 5000  # log rotation limit
DEDUP_THRESHOLD = 0.6  # similarity ratio for pattern dedup (0-1)

DATA_DIR = Path(__file__).parent / "data"
EXPERIENCE_FILE = DATA_DIR / "experience.jsonl"
MEMORY_FILE = DATA_DIR / "memory.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_experience(context: str, action: str, outcome: str,
                   success: bool, duration_s: float = 0.0,
                   error: str = "") -> None:
    """Append satu record pengalaman. Append-only, ga pernah overwrite."""
    DATA_DIR.mkdir(exist_ok=True)
    record = {
        "ts": _now_iso(),
        "context": context[:500],
        "action": action[:500],
        "outcome": outcome[:500],
        "success": bool(success),
        "duration_s": round(float(duration_s), 2),
        "error": error[:300],
    }
    with EXPERIENCE_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    # Log rotation: keep only last MAX_EXPERIENCE_LINES
    try:
        lines = EXPERIENCE_FILE.read_text(encoding="utf-8").strip().split("\n")
        if len(lines) > MAX_EXPERIENCE_LINES:
            EXPERIENCE_FILE.write_text("\n".join(lines[-MAX_EXPERIENCE_LINES:]) + "\n", encoding="utf-8")
    except Exception:
        pass


def _load_memory() -> dict:
    if MEMORY_FILE.exists():
        try:
            return json.loads(MEMORY_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_memory(data: dict) -> None:
    MEMORY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def _read_experiences(limit: int = 500) -> list:
    if not EXPERIENCE_FILE.exists():
        return []
    lines = EXPERIENCE_FILE.read_text(encoding="utf-8").strip().split("\n")
    out = []
    for ln in lines[-limit:]:
        try:
            out.append(json.loads(ln))
        except Exception:
            continue
    return out


def _similar(a: str, b: str, threshold: float = DEDUP_THRESHOLD) -> bool:
    """Check if two patterns are too similar (>= threshold ratio)."""
    if a == b:
        return True
    ratio = SequenceMatcher(None, a.lower(), b.lower()).ratio()
    return ratio >= threshold


def add_learned_pattern(pattern: str) -> bool:
    """Tambah satu lesson ke memory[learned_patterns]. Dedup exact + similarity, cap 100."""
    pattern = pattern.strip()
    if not pattern:
        return False
    m = _load_memory()
    lp = m.setdefault("learned_patterns", [])
    # Exact dedup
    if pattern in lp:
        return False
    # Similarity dedup — reject if too similar to any existing pattern
    for existing in lp:
        if _similar(pattern, existing):
            return False
    lp.append(pattern)
    m["learned_patterns"] = lp[-100:]
    _save_memory(m)
    return True


def cleanup_patterns() -> dict:
    """Remove duplicate/similar patterns from existing learned_patterns. Returns stats."""
    m = _load_memory()
    lp = m.get("learned_patterns", [])
    if not lp:
        return {"removed": 0, "remaining": 0}
    kept = []
    removed = 0
    for pattern in lp:
        is_dup = False
        for existing in kept:
            if _similar(pattern, existing):
                is_dup = True
                break
        if is_dup:
            removed += 1
        else:
            kept.append(pattern)
    m["learned_patterns"] = kept
    _save_memory(m)
    return {"removed": removed, "remaining": len(kept)}


def recall_patterns(max_items: int = 20, keywords: str = "") -> list:
    """Ambil learned_patterns buat di-inject ke system prompt.
    If keywords provided, filter by relevance (keyword match in pattern text).
    """
    m = _load_memory()
    all_patterns = m.get("learned_patterns", [])
    if not all_patterns:
        return []
    if not keywords:
        return all_patterns[-max_items:]
    # Filter by keyword relevance
    kw_lower = keywords.lower()
    kw_words = [w for w in kw_lower.split() if len(w) > 2]
    if not kw_words:
        return all_patterns[-max_items:]
    scored = []
    for p in all_patterns:
        p_lower = p.lower()
        score = sum(1 for kw in kw_words if kw in p_lower)
        if score > 0:
            scored.append((score, p))
    scored.sort(key=lambda x: -x[0])  # highest score first
    return [p for _, p in scored[:max_items]]


def stats() -> dict:
    exps = _read_experiences(limit=10000)
    total = len(exps)
    ok = sum(1 for e in exps if e.get("success"))
    return {
        "total": total,
        "success": ok,
        "fail": total - ok,
        "success_rate": round(ok / total, 3) if total else 0.0,
        "learned_patterns": len(recall_patterns(max_items=999)),
    }


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"
    if cmd == "stats":
        print(json.dumps(stats(), indent=2))
    elif cmd == "patterns":
        for p in recall_patterns(max_items=999):
            print("-", p)
    elif cmd == "cleanup":
        result = cleanup_patterns()
        print(json.dumps(result, indent=2))
    elif cmd == "test":
        log_experience("kirim file ke telegram", "coba 0x0.st", "uploads disabled", False, 1.2, "503")
        log_experience("kirim file ke telegram", "pakai sendDocument bot API", "OK terkirim", True, 0.8)
        add_learned_pattern("Kirim file ke Telegram: langsung pakai bot sendDocument (chat_id=5698128340), JANGAN upload ke 0x0.st/anonfiles/file.io/transfer.sh (mati/diblok).")
        print(json.dumps(stats(), indent=2))


# ========================
# LAYER 2: REFLECTION (LLM-driven)
# ========================
import os
import urllib.request

REFLECT_MARKER = DATA_DIR / ".reflect_offset"


def _llm_call(prompt: str, system: str = "") -> str:
    """Panggil LLM proxy (9router) buat ekstrak pattern. Pakai env bot."""
    base = os.environ.get("OPENAI_BASE_URL", "http://127.0.0.1:20128/v1").rstrip("/")
    key = os.environ.get("OPENAI_API_KEY", "sk-noauth")
    model = "ag/gemini-3-flash"  # use working model (kr/auto kiro provider dead)
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    body = json.dumps({"model": model, "messages": msgs, "temperature": 0.2, "stream": False}).encode()
    req = urllib.request.Request(
        f"{base}/chat/completions", data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"].strip()


def _get_offset() -> int:
    if REFLECT_MARKER.exists():
        try:
            return int(REFLECT_MARKER.read_text().strip())
        except Exception:
            return 0
    return 0


def _set_offset(n: int) -> None:
    REFLECT_MARKER.write_text(str(n))


def reflect(min_new: int = 5) -> dict:
    """Baca experience baru sejak reflect terakhir, ekstrak lesson via LLM,
    simpan ke learned_patterns. Idempotent via offset marker."""
    if not EXPERIENCE_FILE.exists():
        return {"status": "no_data", "new": 0}
    all_lines = EXPERIENCE_FILE.read_text(encoding="utf-8").strip().split("\n")
    total = len(all_lines)
    offset = _get_offset()
    new_lines = all_lines[offset:]
    if len(new_lines) < min_new:
        return {"status": "not_enough", "new": len(new_lines), "need": min_new}

    exps = []
    for ln in new_lines:
        try:
            exps.append(json.loads(ln))
        except Exception:
            continue
    fails = [e for e in exps if not e.get("success")]
    succs = [e for e in exps if e.get("success")]

    summary = "PENGALAMAN GAGAL:\n"
    for e in fails:
        summary += f"- konteks: {e['context']} | aksi: {e['action']} | hasil: {e['outcome']} | error: {e.get('error','')}\n"
    summary += "\nPENGALAMAN SUKSES:\n"
    for e in succs:
        summary += f"- konteks: {e['context']} | aksi: {e['action']} | hasil: {e['outcome']}\n"

    system = (
        "Lo modul refleksi buat agent bernama Kai. Dari log pengalaman, ekstrak "
        "lesson ACTIONABLE yang bikin Kai ga ngulang kesalahan. Format tiap lesson: "
        "1 kalimat, spesifik, kasih solusi konkret (tool/cara yang works). "
        "Output cuma JSON array of string, ga ada teks lain. Maksimal 5 lesson. "
        "Skip yang ga ada pelajarannya. Kalo ga ada lesson berarti, output []"
    )
    try:
        raw = _llm_call(summary, system)
    except Exception as ex:
        return {"status": "llm_error", "error": str(ex)[:200]}

    # parse JSON array dari output (toleran terhadap fence)
    raw_clean = raw.strip()
    if raw_clean.startswith("```"):
        raw_clean = raw_clean.split("```")[1] if "```" in raw_clean else raw_clean
        raw_clean = raw_clean.replace("json", "", 1).strip()
    try:
        lessons = json.loads(raw_clean)
        if not isinstance(lessons, list):
            lessons = []
    except Exception:
        return {"status": "parse_error", "raw": raw[:300]}

    added = 0
    for lesson in lessons:
        if isinstance(lesson, str) and lesson.strip():
            if add_learned_pattern(lesson.strip()):
                added += 1
    _set_offset(total)
    return {"status": "ok", "reflected": len(new_lines),
            "lessons_found": len(lessons), "added": added}
