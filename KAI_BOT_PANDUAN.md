# Kai Bot — Panduan Penggunaan

> AI asisten pribadi yang jalan langsung di VPS.  
> Telegram: [@Jarmokbot](https://t.me/Jarmokbot)  
> VPS: 13.212.56.127 (AWS Singapore)  
> Owner: Gutluc (@Gutluc)

---

## Daftar Isi

1. [Chat & AI](#chat--ai)
2. [Model & LLM](#model--llm)
3. [VPS & Server](#vps--server)
4. [Voice](#voice)
5. [Reminder](#reminder)
6. [Media](#media)
7. [LLM Error & Retry](#llm-error--retry)
8. [Self-Learning](#self-learning)
9. [Memory](#memory)
10. [Konfigurasi](#konfigurasi)
11. [Troubleshooting](#troubleshooting)

---

## Chat & AI

Cukup kirim pesan teks biasa. Bot akan memproses dengan LLM dan membalas.

```
Halo, apa kabar?
Bikinin script Python buat cek harga Bitcoin
Jelasin apa itu recursion
```

Bot mendukung **agentic loop** — bisa mengeksekusi command, mencari di internet, dan menjalankan tool secara otomatis dalam satu percakapan.

### Commands

| Command | Fungsi |
|---------|--------|
| `/start` | Mulai / sapa bot |
| `/help` | Lihat semua command |
| `/reset` | Reset history percakapan |
| `/cancel` | Batalkan task yang sedang berjalan |

---

## Model & LLM

Bot menggunakan 9router proxy (port 20128) untuk akses multiple LLM providers.

### Commands

| Command | Fungsi |
|---------|--------|
| `/model` | Lihat model yang sedang aktif |
| `/models` | Lihat daftar semua model tersedia |
| `/setmodel [nama]` | Ganti model aktif |

### Contoh

```
/model              → "Model aktif: ag/claude-sonnet-4-6"
/models             → Daftar semua model dari semua provider
/setmodel ag/gemini-3-flash  → Ganti ke Gemini Flash
```

### Model yang Tersedia

| Provider | Model | Status |
|----------|-------|--------|
| `ag/` (Antigravity) | `ag/claude-sonnet-4-6` | ✅ Default |
| `ag/` | `ag/claude-opus-4-6-thinking` | ✅ |
| `ag/` | `ag/gemini-3-flash` | ✅ Fallback |
| `ag/` | `ag/gemini-3-flash-agent` | ✅ |
| `ag/` | `ag/gpt-oss-120b-medium` | ✅ |
| `kimchi/` | `kimchi/kimi-k2.7` | ✅ Fallback |
| `kimchi/` | `kimchi/deepseek-v4-flash` | ✅ |
| `nvidia/` | `nvidia/deepseek-ai/deepseek-v4-pro` | ✅ |
| `AliAI/` | Semua model | ❌ 403 AccessDenied |
| `kr/` (kiro) | Semua model | ❌ 404 No credentials |

> **Catatan:** Model `AliAI/` dan `kr/` sedang mati. Provider credentials perlu diperbarui di 9router.

---

## LLM Error & Retry

### Cara Kerja

Ketika LLM call gagal (model error, timeout, 403, dll):

1. Bot mengirim pesan error ke user dengan detail:
   ```
   ⚠️ Error model ag/claude-sonnet-4-6: 403 AccessDenied.Unpurchased
   ```

2. Error tersimpan di memori bot (per chat).

3. User bisa retry dengan fallback model:
   ```
   /retry
   ```
   Bot akan:
   - Ambil fallback model dari config (`FALLBACK_MODELS` di `.env`)
   - Kirim pesan "🔄 Retry dengan fallback: ag/gemini-3-flash"
   - Proses ulang pesan terakhir dengan model fallback
   - **Restore model asli** setelah selesai (model user tidak berubah permanen)

4. Jika fallback juga gagal:
   ```
   ⚠️ Fallback ag/gemini-3-flash juga gagal: [error message]
   ```

5. Jika tidak ada error terakhir:
   ```
   Ga ada error terakhir buat di-retry.
   ```

### Konfigurasi Fallback

File: `~/ai-agent/.env`

```env
FALLBACK_MODELS=ag/gemini-3-flash,kimchi/kimi-k2.7
```

Urutan = prioritas. Model pertama dicoba dulu, kalau sama dengan model yang gagal, lanjut ke berikutnya.

### Error Logging

Semua error LLM di-log ke journald:

```bash
journalctl -u kai-bot.service | grep "[LLM]"
```

---

## VPS & Server

### Commands

| Command | Fungsi |
|---------|--------|
| `/aws [cmd]` | Jalankan command di VPS lokal |
| `/remote [cmd]` | Jalankan command di remote VPS |
| `/setremote` | Set konfigurasi remote VPS |
| `/setremote_key` | Set SSH key remote VPS |
| `/remote_status` | Cek status remote VPS |
| `/search [query]` | Cari di internet (DuckDuckGo) |

### Contoh

```
/aws df -h                    → Cek disk space VPS
/aws docker ps                → Lihat container Docker
/aws systemctl status kai-bot → Cek status service
/search cara setup nginx      → Cari di internet
```

### Natural Language Command

Bot juga paham bahasa natural untuk command VPS:

```
Cek disk space di server
Restart service kai-bot
Lihat log nginx 10 baris terakhir
```

Bot akan menerjemahkan ke command dan meminta konfirmasi untuk high-risk command.

---

## Voice

### Text-to-Speech (TTS)

```
/tts Halo, ini adalah test text to speech
bacain Halo, selamat datang
suarakan Pesan ini akan diubah jadi suara
```

Bot akan mengirim voice note (MP3) dengan suara Bahasa Indonesia.

### Speech-to-Text (STT)

Kirim voice note langsung ke bot. Bot akan:
1. Transcribe voice note ke teks
2. Proses teks dengan AI
3. Kirim balasan

---

## Reminder

### Set Reminder

Kirim pesan natural dengan kata kunci: `ingetin`, `ingatkan`, `remind`, `reminder`, `alarm`

```
ingetin 5 menit lagi cek harga XAUUSD
ingatkan besok jam 9 pagi backup database
remind 30 menit lagi restart server
```

### Commands

| Command | Fungsi |
|---------|--------|
| `/reminders` | Lihat semua reminder aktif |
| `/delreminder [id]` | Hapus reminder by ID |

---

## Media

### Foto/Gambar

Kirim foto ke bot. Bot akan:
1. Analisis gambar dengan vision model (`ag/gemini-3-flash`)
2. Ekstrak semua teks yang terlihat
3. Proses dengan caption yang dikirim

### Video

Kirim video ke bot. Bot akan:
1. Extract frame dari video
2. Analisis frame dengan vision model
3. Proses dengan caption

### Document/File

Kirim file ke bot. Bot akan:
1. Baca isi file (text, code, PDF, CSV, dll)
2. Proses isi file dengan AI

### Image Generation

Minta bot untuk generate gambar:

```
gambarin kucing pakai topi
generate image pemandangan gunung saat sunset
```

Bot akan generate gambar via Pollinations AI dan mengirim ke chat.

---

## Self-Learning

Bot punya 3 layer self-learning:

### Layer 1: Experience Logging
Setiap task yang dieksekusi dicatat ke `data/experience.jsonl`:
- Konteks task
- Aksi yang diambil
- Hasil (sukses/gagal)
- Durasi
- Error (jika ada)

### Layer 2: Reflection (LLM-driven)
Setiap 6 jam, bot merefleksi pengalaman:
- Baca experience log baru
- Ekstrak lesson actionable via LLM
- Simpan ke `data/memory.json` → `learned_patterns`
- Inject lesson ke system prompt untuk percakapan berikutnya

### Layer 3: Pattern Recall
Sebelum eksekusi task, bot mengambil learned patterns yang relevan dan inject ke konteks.

### Cek Stats

```bash
# Via SSH
cd ~/ai-agent
venv/bin/python self_learning.py stats
venv/bin/python self_learning.py patterns
```

---

## Memory

Bot punya 3 jenis memory:

### 1. JSON Memory (`data/memory.json`)
Identitas, gaya komunikasi, aturan otonomi, boundaries.

### 2. SQLite DB (`data/kai.db`)
History percakapan, reminder, metadata.

### 3. Mem0 + Qdrant (Semantic Memory)
Memory semantik untuk recall konteks relevan. Bot otomatis search memory sebelum merespon.

### Commands

| Command | Fungsi |
|---------|--------|
| `/memory` | Lihat isi memory |
| `/remember [hal]` | Simpan ke memory |
| `/forget` | Hapus memory |
| `/dbstats` | Lihat statistik database |
| `/soul` | Lihat SOUL.md (personality config) |
| `/soul_reload` | Reload SOUL.md |
| `/creds` | Lihat credential files tersedia |

---

## Konfigurasi

### File Penting

| File | Lokasi | Fungsi |
|------|--------|--------|
| `.env` | `~/ai-agent/.env` | Config utama (token, model, fallback) |
| `SOUL.md` | `~/ai-agent/SOUL.md` | Personality & behavior config |
| `telegram_agent.py` | `~/ai-agent/telegram_agent.py` | Main bot code |
| `self_learning.py` | `~/ai-agent/self_learning.py` | Self-learning module |
| `adapter_healer.py` | `~/ai-agent/adapter_healer.py` | Adapter self-heal |
| `chat_models.json` | `~/ai-agent/data/chat_models.json` | Model per chat |
| `memory.json` | `~/ai-agent/data/memory.json` | Bot memory |
| `experience.jsonl` | `~/ai-agent/data/experience.jsonl` | Experience log |

### `.env` Reference

```env
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
ALLOWED_TELEGRAM_USER_ID=your_user_id

# LLM Proxy (9router)
OPENAI_BASE_URL=http://127.0.0.1:20128/v1
OPENAI_API_KEY=your_api_key
MODEL_NAME=ag/claude-sonnet-4-6

# Fallback Models (urutan = prioritas)
FALLBACK_MODELS=ag/gemini-3-flash,kimchi/kimi-k2.7

# FreeModel (optional)
FREEMODEL_API_KEY=your_freemodel_key

# Remote VPS
REMOTE_SSH_HOST=
REMOTE_SSH_PORT=22
REMOTE_SSH_USER=root
REMOTE_SSH_KEY=/home/ubuntu/.ssh/remote_vps_key
REMOTE_AUTO_EXECUTE=true

# Local VPS
AWS_LOCAL_AUTO_EXECUTE=true
```

### Services di VPS

| Service | Fungsi | Status |
|---------|--------|--------|
| `kai-bot` | Telegram bot utama | ✅ Active |
| `superagent-trader` | XAUUSD paper trading | ✅ Active |
| `9router` (Docker) | LLM proxy | ✅ Running |
| `mem0-qdrant` (Docker) | Vector DB untuk memory | ✅ Running |
| `headroom` (Docker) | Rate limiter untuk 9router | ✅ Healthy |
| `n8n` | Workflow automation | ✅ Active |
| `nginx` | Web server | ✅ Active |
| `9proxyd` | Proxy daemon | ✅ Active |
| `commandcode-proxy` | CommandCode OpenAI proxy | ✅ Active |
| `qoder-shim` | Qoder bridge | ✅ Active |
| `9router-tunnel` | Cloudflare tunnel 9router | ✅ Active |
| `kai-cf` | Cloudflare tunnel n8n | ✅ Active |
| `soul-preview-tunnel` | Cloudflare tunnel SOUL preview | ✅ Active |
| `fail2ban` | Brute force protection | ✅ Active |
| `tailscaled` | Tailscale VPN | ✅ Active |
| `syncthing@ubuntu` | File sync | ✅ Active |

---

## Troubleshooting

### Bot Tidak Respon

```bash
# 1. Cek status service
sudo systemctl status kai-bot.service

# 2. Cek logs
journalctl -u kai-bot.service -n 30 --no-pager

# 3. Cek konflik polling
curl -s 'https://api.telegram.org/bot<TOKEN>/getUpdates?timeout=2&limit=1'

# 4. Restart bot
sudo systemctl restart kai-bot.service

# 5. Jika masih konflik, reset polling
curl -s 'https://api.telegram.org/bot<TOKEN>/deleteWebhook?drop_pending_updates=true'
sudo systemctl restart kai-bot.service
```

### LLM Error

```bash
# 1. Cek 9router
docker ps | grep 9router
curl -s http://127.0.0.1:20128/v1/models -H "Authorization: Bearer <KEY>" | python3 -m json.tool

# 2. Test model
curl -s http://127.0.0.1:20128/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <KEY>" \
  -d '{"model":"ag/claude-sonnet-4-6","messages":[{"role":"user","content":"hi"}],"stream":false}'

# 3. Cek 9router logs
docker logs 9router --tail 30

# 4. Di Telegram, kirim /retry untuk coba fallback model
```

### Memory/Qdrant Error

```bash
# Cek Qdrant
docker ps | grep qdrant
curl -s http://127.0.0.1:6333/health
curl -s http://127.0.0.1:6333/collections | python3 -m json.tool

# Restart Qdrant
docker restart mem0-qdrant
```

### Service Tidak Mau Start

```bash
# Cek syntax
cd ~/ai-agent
venv/bin/python -m py_compile telegram_agent.py

# Cek .env
cat .env

# Cek venv
venv/bin/python -c "import telegram; print('OK')"

# Manual test
venv/bin/python telegram_agent.py
```

### Ganti Model Default

Edit `.env`:
```bash
nano ~/ai-agent/.env
# Ubah MODEL_NAME=ag/claude-sonnet-4-6
sudo systemctl restart kai-bot.service
```

Atau via Telegram:
```
/setmodel ag/gemini-3-flash
```

### Ganti Fallback Models

Edit `.env`:
```bash
nano ~/ai-agent/.env
# Ubah FALLBACK_MODELS=model1,model2,model3
sudo systemctl restart kai-bot.service
```

### Restore Backup

```bash
# Lihat backup tersedia
ls -la ~/ai-agent/telegram_agent.py.bak.*

# Restore
cp ~/ai-agent/telegram_agent.py.bak.fallback_20260702_234054 ~/ai-agent/telegram_agent.py
sudo systemctl restart kai-bot.service
```

---

## Backup Files

| File | Tanggal | Alasan |
|------|---------|--------|
| `.env.bak.20260702_084902` | 2 Jul 2026 | Sebelum ganti model |
| `self_learning.py.bak.20260702_084902` | 2 Jul 2026 | Sebelum fix model |
| `adapter_healer.py.bak.20260702_084920` | 2 Jul 2026 | Sebelum fix model |
| `telegram_agent.py.bak.fallback_20260702_234054` | 2 Jul 2026 | Sebelum tambah fallback & retry |

---

## Arsitektur Singkat

```
User (Telegram)
    ↓
@Jarmokbot (telegram_agent.py)
    ↓
9router (port 20128) → LLM providers (Antigravity, Kimchi, Nvidia)
    ↓
Response → User

Side services:
- Qdrant (port 6333) → Semantic memory (Mem0)
- self_learning.py → Experience log + reflection
- adapter_healer.py → Self-heal adapter specs
- n8n → Workflow automation
- superagent-trader → XAUUSD paper trading
```

---

*Panduan ini di-generate pada 3 Juli 2026. Untuk update terbaru, cek source code langsung.*
