"""Kai shared config, clients, mutable globals."""
import os
import re
import html as _html_mod
import json
import shlex
import asyncio
import logging
import urllib.request
import urllib.parse
import subprocess
from datetime import datetime
from pathlib import Path

import base64
import tempfile
import sqlite3
import hashlib
import self_learning as sl  # experience-based learning layer
import mem0_integration  # semantic memory via Qdrant

try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False

try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    from docx import Document as DocxDocument
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    import openpyxl
    XLSX_AVAILABLE = True
except ImportError:
    XLSX_AVAILABLE = False

try:
    from pptx import Presentation as PptxPresentation
    PPTX_AVAILABLE = True
except ImportError:
    PPTX_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib.enums import TA_LEFT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

import threading
import time
try:
    import oci
    OCI_AVAILABLE = True
except ImportError:
    OCI_AVAILABLE = False

from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "http://127.0.0.1:20128/v1").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "dummy-key").strip()
DEFAULT_MODEL = os.getenv("MODEL_NAME", "ag/claude-opus-4-6-thinking").strip()
ALLOWED_TELEGRAM_USER_ID = os.getenv("ALLOWED_TELEGRAM_USER_ID", "").strip()
AGENT_NAME = os.getenv("AGENT_NAME", "Kai").strip()

AWS_LOCAL_AUTO_EXECUTE = os.getenv("AWS_LOCAL_AUTO_EXECUTE", "true").lower() == "true"
REMOTE_SSH_HOST = os.getenv("REMOTE_SSH_HOST", "").strip()
REMOTE_SSH_PORT = os.getenv("REMOTE_SSH_PORT", "22").strip()
REMOTE_SSH_USER = os.getenv("REMOTE_SSH_USER", "root").strip()
REMOTE_SSH_KEY = os.getenv("REMOTE_SSH_KEY", "/home/ubuntu/.ssh/remote_vps_key").strip()
REMOTE_AUTO_EXECUTE = os.getenv("REMOTE_AUTO_EXECUTE", "true").lower() == "true"

DATA_DIR = Path.home() / "ai-agent" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
MEMORY_FILE = DATA_DIR / "memory.json"
HISTORY_DIR = DATA_DIR / "history"
HISTORY_DIR.mkdir(parents=True, exist_ok=True)

SOUL_FILE = Path.home() / "ai-agent" / "SOUL.md"
CREDENTIALS_DIR = Path.home() / "ai-agent" / "credentials"
DB_PATH = DATA_DIR / "kai.db"

# ========================
# SQLite DATABASE

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN belum diisi")

client = OpenAI(base_url=OPENAI_BASE_URL, api_key=OPENAI_API_KEY)

FREEMODEL_API_KEY = os.getenv("FREEMODEL_API_KEY", "").strip()
freemodel_client = OpenAI(
    base_url="https://freemodel.dev/v1",
    api_key=FREEMODEL_API_KEY or "dummy"
) if FREEMODEL_API_KEY else None

FREEMODEL_MODELS = ["gpt-5.5", "gpt-5.4", "gpt-5.4-mini", "gpt-5.3-codex"]
FALLBACK_MODELS = [m.strip() for m in os.getenv("FALLBACK_MODELS", "").split(",") if m.strip()]
last_llm_error: dict = {}  # chat_id -> {"model": str, "error": str, "user_text": str, "extra_context": str}
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

# Suppress httpx/httpcore INFO logs yang expose bot token di setiap request
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

CHAT_MODELS_FILE = os.path.join(DATA_DIR, "chat_models.json")

def load_chat_models():
    if os.path.exists(CHAT_MODELS_FILE):
        try:
            with open(CHAT_MODELS_FILE, "r") as f:
                data = json.load(f)
                # JSON nyimpen key jadi string, kita ubah balik ke int buat chat_id
                return {str(k): v for k, v in data.items()}
        except Exception:
            return {}
    return {}

def save_chat_models():
    try:
        with open(CHAT_MODELS_FILE, "w") as f:
            json.dump(chat_models, f)
    except Exception:
        pass

chat_models = load_chat_models()

def model_key(chat_id, thread_id=None):
    return f"{chat_id}:{thread_id}" if thread_id else str(chat_id)

def resolve_model(chat_id, thread_id=None):
    k = model_key(chat_id, thread_id)
    if k in chat_models:
        return chat_models[k]
    ck = str(chat_id)
    if ck in chat_models:
        return chat_models[ck]
    return DEFAULT_MODEL
pending_aws_commands = {}
pending_remote_commands = {}
last_command_result = {}  # simpan hasil command terakhir per chat
oracle_war_running = {}   # chat_id -> True/False
chat_locks: dict = {}     # chat_id -> asyncio.Lock (serialize handling per chat)
chat_busy: dict = {}      # chat_id -> {"description": str, "start": float}
chat_cancel: dict = {}    # chat_id -> True kalau user minta /cancel
pending_keyboards: dict = {}  # chat_id -> InlineKeyboardMarkup for pending confirmations
model_button_map: dict = {}  # token -> model name (buat inline /models)
model_groups: dict = {}  # provider -> list token

STATUS_QUERY_KEYWORDS = (
    "gimana", "gmn", "udah", "udah belom", "udah belum", "udah beres",
    "udah selesai", "beres", "beres belum", "selesai", "selesai belum",
    "kelar", "kelar belum", "hasilnya", "hasil", "status", "progress",
    "bisa", "bisa ga", "bisa gak", "bisa kah", "oke?",
)


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


SECRET_PATTERNS = [
    (re.compile(r'ghp_[A-Za-z0-9]{20,}'), '[REDACTED_GITHUB_PAT]'),
    (re.compile(r'github_pat_[A-Za-z0-9_]{20,}'), '[REDACTED_GITHUB_PAT]'),
    (re.compile(r'gho_[A-Za-z0-9]{20,}'), '[REDACTED_GITHUB_OAUTH]'),
    (re.compile(r'\b0x[a-fA-F0-9]{64}\b'), '[REDACTED_HEX64_PRIVKEY]'),
    (re.compile(r'\bAKIA[A-Z0-9]{16}\b'), '[REDACTED_AWS_ACCESS_KEY]'),
    (re.compile(r'\bASIA[A-Z0-9]{16}\b'), '[REDACTED_AWS_TEMP_KEY]'),
    (re.compile(r'sk-[A-Za-z0-9_\-]{20,}'), '[REDACTED_OPENAI_KEY]'),
    (re.compile(r'-----BEGIN [A-Z ]+PRIVATE KEY-----.*?-----END [A-Z ]+PRIVATE KEY-----', re.DOTALL), '[REDACTED_PEM]'),
    (re.compile(r'xoxb-[A-Za-z0-9\-]{20,}'), '[REDACTED_SLACK_BOT]'),
    (re.compile(r'xoxp-[A-Za-z0-9\-]{20,}'), '[REDACTED_SLACK_USER]'),
]

