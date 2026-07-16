#!/bin/bash
# self_upgrade.sh - Kai Self-Upgrade System
# Handles: dependency upgrades, skill updates, and code self-patching
# Usage: self_upgrade.sh [deps|skills|patch <patch_file>|rollback]

set -euo pipefail

BOT_TOKEN="$(grep TELEGRAM_BOT_TOKEN /home/ubuntu/ai-agent/.env | cut -d= -f2)"
CHAT_ID="5698128340"
AGENT_DIR="/home/ubuntu/ai-agent"
BACKUP_DIR="$AGENT_DIR/backups"
LOG_FILE="$AGENT_DIR/data/upgrade.log"
MAX_BACKUPS=5

# --- Helpers ---

log() {
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $1" | tee -a "$LOG_FILE"
}

notify() {
    local msg="$1"
    curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
        -d chat_id="$CHAT_ID" \
        -d text="$msg" > /dev/null 2>&1
}

ensure_backup_dir() {
    mkdir -p "$BACKUP_DIR"
}

rotate_backups() {
    # Keep only MAX_BACKUPS most recent
    local count=$(ls -1 "$BACKUP_DIR"/telegram_agent_*.py 2>/dev/null | wc -l)
    if [ "$count" -gt "$MAX_BACKUPS" ]; then
        ls -1t "$BACKUP_DIR"/telegram_agent_*.py | tail -n +$((MAX_BACKUPS + 1)) | xargs rm -f
        ls -1t "$BACKUP_DIR"/SOUL_*.md 2>/dev/null | tail -n +$((MAX_BACKUPS + 1)) | xargs rm -f 2>/dev/null
    fi
}

create_backup() {
    ensure_backup_dir
    local ts=$(date +%Y%m%d_%H%M%S)
    cp "$AGENT_DIR/telegram_agent.py" "$BACKUP_DIR/telegram_agent_${ts}.py"
    cp "$AGENT_DIR/SOUL.md" "$BACKUP_DIR/SOUL_${ts}.md" 2>/dev/null || true
    rotate_backups
    log "BACKUP: created snapshot $ts"
    echo "$ts"
}

syntax_check() {
    local file="$1"
    python3 -c "
import py_compile, sys
try:
    py_compile.compile('$file', doraise=True)
    sys.exit(0)
except py_compile.PyCompileError as e:
    print(f'SYNTAX ERROR: {e}', file=sys.stderr)
    sys.exit(1)
"
}

health_check() {
    # Wait and verify Kai started successfully
    local wait_time="${1:-30}"
    sleep "$wait_time"
    
    # Check process alive
    if ! systemctl is-active kai-bot > /dev/null 2>&1; then
        return 1
    fi
    
    # Check "Application started" in recent journal
    if ! journalctl -u kai-bot --since "${wait_time} sec ago" --no-pager 2>/dev/null | grep -q "Application started"; then
        return 1
    fi
    
    # Check no exceptions in recent log
    if journalctl -u kai-bot --since "${wait_time} sec ago" --no-pager 2>/dev/null | grep -qi "traceback\|exception\|error.*fatal"; then
        return 1
    fi
    
    return 0
}

rollback() {
    local reason="${1:-unknown}"
    log "ROLLBACK: triggered ($reason)"
    
    # Find most recent backup
    local latest=$(ls -1t "$BACKUP_DIR"/telegram_agent_*.py 2>/dev/null | head -1)
    if [ -z "$latest" ]; then
        log "ROLLBACK FAILED: no backup found"
        notify "🔴 Upgrade ROLLBACK FAILED: no backup found. Reason: $reason"
        return 1
    fi
    
    cp "$latest" "$AGENT_DIR/telegram_agent.py"
    sudo systemctl restart kai-bot
    sleep 10
    
    if systemctl is-active kai-bot > /dev/null 2>&1; then
        log "ROLLBACK: success, restored from $(basename $latest)"
        notify "⚠️ Upgrade rolled back (reason: $reason). Restored from $(basename $latest). Kai running OK."
    else
        log "ROLLBACK: CRITICAL - even backup won't start"
        notify "🔴 CRITICAL: Rollback failed, Kai won't start. Manual intervention needed."
    fi
}

# --- LEVEL 1: Dependency Upgrade ---

upgrade_deps() {
    log "DEPS: starting dependency upgrade"
    local issues=""
    
    # System packages (security only)
    log "DEPS: apt update"
    sudo apt-get update -qq 2>&1 | tail -3 >> "$LOG_FILE"
    
    local upgradable
    upgradable=$(apt list --upgradable 2>/dev/null | grep -ic "security" || true)
    upgradable=${upgradable:-0}
    if [ "$upgradable" -gt 0 ] 2>/dev/null; then
        log "DEPS: $upgradable security updates available, installing"
        sudo apt-get upgrade -y -qq --only-upgrade 2>&1 | tail -5 >> "$LOG_FILE"
    fi
    
    # Pip packages in venv
    log "DEPS: pip upgrade (ai-agent venv)"
    cd "$AGENT_DIR"
    source venv/bin/activate
    
    # Upgrade core packages only (safe list)
    local pip_upgrades=$(pip list --outdated --format=json 2>/dev/null | python3 -c "
import json, sys
try:
    pkgs = json.load(sys.stdin)
    safe = ['python-telegram-bot', 'openai', 'httpx', 'edge-tts', 'Pillow', 'openpyxl', 'python-docx', 'python-pptx', 'PyPDF2']
    upgradable = [p['name'] for p in pkgs if p['name'] in safe]
    print(' '.join(upgradable))
except: pass
" 2>/dev/null)
    
    if [ -n "$pip_upgrades" ]; then
        log "DEPS: upgrading pip packages: $pip_upgrades"
        pip install --upgrade $pip_upgrades 2>&1 | tail -5 >> "$LOG_FILE"
    else
        log "DEPS: all pip packages up to date"
    fi
    
    deactivate 2>/dev/null || true
    
    notify "✅ Dependency upgrade complete. System: ${upgradable:-0} security patches. Pip: ${pip_upgrades:-none}"
    log "DEPS: complete"
}

# --- LEVEL 2: Skill Upgrade ---

upgrade_skills() {
    log "SKILLS: checking for skill updates"
    
    local skills_dir="$AGENT_DIR/skills"
    local updated=0
    
    # Check if skills have a git repo
    if [ -d "$skills_dir/.git" ]; then
        cd "$skills_dir"
        git fetch origin 2>/dev/null
        local behind=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo "0")
        if [ "$behind" -gt 0 ]; then
            git pull origin main 2>&1 | tail -3 >> "$LOG_FILE"
            updated=$behind
            log "SKILLS: pulled $behind new commits"
        fi
    fi
    
    # List current skills
    local skill_count=$(find "$skills_dir" -maxdepth 1 -name "*.md" | wc -l)
    
    if [ "$updated" -gt 0 ]; then
        notify "✅ Skills updated: $updated changes pulled. Total skills: $skill_count"
    else
        log "SKILLS: all up to date ($skill_count skills)"
    fi
}

# --- LEVEL 3: Self-Patch Code ---

apply_patch() {
    local patch_file="$1"
    
    if [ ! -f "$patch_file" ]; then
        log "PATCH: file not found: $patch_file"
        notify "🔴 Patch failed: file not found ($patch_file)"
        return 1
    fi
    
    log "PATCH: starting self-patch from $patch_file"
    
    # Step 1: Backup
    local backup_ts=$(create_backup)
    
    # Step 2: Apply patch
    # Patch file format: Python script that modifies telegram_agent.py
    # It should read, modify, and write the file
    log "PATCH: applying..."
    local patch_output
    patch_output=$(python3 "$patch_file" 2>&1)
    local patch_exit=$?
    
    if [ $patch_exit -ne 0 ]; then
        log "PATCH: script failed: $patch_output"
        rollback "patch script error"
        return 1
    fi
    
    log "PATCH: applied, output: $patch_output"
    
    # Step 3: Syntax check
    if ! syntax_check "$AGENT_DIR/telegram_agent.py"; then
        log "PATCH: syntax check FAILED"
        rollback "syntax error after patch"
        return 1
    fi
    
    log "PATCH: syntax OK"
    
    # Step 4: Restart
    sudo systemctl restart kai-bot
    
    # Step 5: Health check (30s)
    if ! health_check 30; then
        log "PATCH: health check FAILED (30s)"
        rollback "failed health check after restart"
        return 1
    fi
    
    log "PATCH: health check passed (30s)"
    
    # Step 6: Extended verify (60s more)
    if ! health_check 60; then
        log "PATCH: extended health check FAILED (60s)"
        rollback "failed extended health check"
        return 1
    fi
    
    log "PATCH: all checks passed, upgrade SUCCESS"
    notify "✅ Self-patch applied successfully. Backup: $backup_ts"
    
    # Cleanup patch file
    rm -f "$patch_file"
}

# --- LEVEL 3b: Inline patch (string replacement) ---

apply_inline_patch() {
    local old_string="$1"
    local new_string="$2"
    local description="${3:-inline patch}"
    
    log "INLINE PATCH: $description"
    
    # Backup
    local backup_ts=$(create_backup)
    
    # Apply
    local target="$AGENT_DIR/telegram_agent.py"
    if ! grep -qF "$old_string" "$target"; then
        log "INLINE PATCH: old_string not found in target"
        notify "⚠️ Inline patch skipped: pattern not found ($description)"
        return 1
    fi
    
    python3 -c "
import sys
with open('$target', 'r') as f:
    content = f.read()
old = '''$old_string'''
new = '''$new_string'''
if old in content:
    content = content.replace(old, new, 1)
    with open('$target', 'w') as f:
        f.write(content)
    print('REPLACED')
else:
    print('NOT FOUND')
    sys.exit(1)
"
    
    # Syntax check
    if ! syntax_check "$target"; then
        rollback "syntax error ($description)"
        return 1
    fi
    
    # Restart + health
    sudo systemctl restart kai-bot
    if ! health_check 30; then
        rollback "health check failed ($description)"
        return 1
    fi
    
    log "INLINE PATCH: success"
    notify "✅ Inline patch applied: $description (backup: $backup_ts)"
}

# --- Main ---

case "${1:-help}" in
    deps)
        upgrade_deps
        ;;
    skills)
        upgrade_skills
        ;;
    patch)
        if [ -z "${2:-}" ]; then
            echo "Usage: self_upgrade.sh patch <patch_file.py>"
            exit 1
        fi
        apply_patch "$2"
        ;;
    inline)
        if [ -z "${2:-}" ] || [ -z "${3:-}" ]; then
            echo "Usage: self_upgrade.sh inline 'old_string' 'new_string' ['description']"
            exit 1
        fi
        apply_inline_patch "$2" "$3" "${4:-}"
        ;;
    rollback)
        rollback "manual rollback requested"
        ;;
    all)
        upgrade_deps
        upgrade_skills
        ;;
    status)
        echo "=== Last 10 log entries ==="
        tail -10 "$LOG_FILE" 2>/dev/null || echo "No log yet"
        echo ""
        echo "=== Backups ==="
        ls -lht "$BACKUP_DIR"/telegram_agent_*.py 2>/dev/null | head -5 || echo "No backups"
        ;;
    help|*)
        echo "Kai Self-Upgrade System"
        echo ""
        echo "Usage: self_upgrade.sh <command>"
        echo ""
        echo "Commands:"
        echo "  deps      - Upgrade system + pip dependencies (safe)"
        echo "  skills    - Pull latest skills from repo"
        echo "  patch <f> - Apply patch file (Python script that modifies code)"
        echo "  inline    - Apply string replacement patch"
        echo "  rollback  - Restore last backup"
        echo "  all       - Run deps + skills"
        echo "  status    - Show recent logs and backups"
        echo ""
        echo "Patch file format:"
        echo "  Python script that reads/modifies/writes telegram_agent.py"
        echo "  Exit 0 = success, non-zero = failure (triggers rollback)"
        ;;
esac
