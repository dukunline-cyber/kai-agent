#!/usr/bin/env python3
"""Kai Telegram bot entrypoint (thin). Logic: kai_core/ + kai_handlers/."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kai_core.app import main

if __name__ == "__main__":
    main()
