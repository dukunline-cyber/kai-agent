"""Mem0 integration layer for Kai.

Isolated module — kalau Mem0 bermasalah, cukup comment import di telegram_agent.py.
"""
import logging
import sys
from pathlib import Path

# Add mem0 dir to path
_mem0_dir = Path(__file__).parent / "mem0"
if str(_mem0_dir) not in sys.path:
    sys.path.insert(0, str(_mem0_dir))

MEM0_AVAILABLE = False
_search_fn = None
_add_fn = None

try:
    from mem0_config import search_memory as _search, add_memory as _add
    MEM0_AVAILABLE = True
    _search_fn = _search
    _add_fn = _add
except Exception as e:
    logging.warning(f"Mem0 not available: {e}")


def search_relevant(query: str, limit: int = 5) -> str:
    """Search Qdrant via Mem0, return formatted string for system prompt.

    Returns empty string if unavailable or no results.
    """
    if not MEM0_AVAILABLE:
        return ""
    try:
        raw = _search_fn(query, limit=limit)
        # Handle both dict {"results": [...]} and plain list [...]
        if isinstance(raw, dict):
            results = raw.get("results", [])
        elif isinstance(raw, list):
            results = raw
        else:
            return ""
        if not results:
            return ""
        lines = []
        for r in results:
            mem = r.get("memory", "") if isinstance(r, dict) else str(r)
            score = r.get("score", 0) if isinstance(r, dict) else 0
            # Filter low relevance (score < 0.05)
            if mem and score >= 0.05:
                lines.append(f"- {mem}")
        if lines:
            return "\n\nRelevant memories (semantic search from Mem0/Qdrant):\n" + "\n".join(lines)
    except Exception as e:
        logging.warning(f"Mem0 search error: {e}")
    return ""


def add_to_memory(text: str, metadata: dict = None) -> bool:
    """Add a memory to Mem0. Returns True on success."""
    if not MEM0_AVAILABLE:
        return False
    try:
        _add_fn(text, metadata=metadata)
        return True
    except Exception as e:
        logging.warning(f"Mem0 add error: {e}")
        return False
