#!/bin/bash
# agent_repair.sh - Multi-Agent Repair System
# Kai as supervisor: monitor, diagnose, fix, and report on all agents
# Usage: agent_repair.sh [check|repair <agent>|diagnose <agent>|status|list]

set -uo pipefail

BOT_TOKEN="$(grep TELEGRAM_BOT_TOKEN /home/ubuntu/ai-agent/.env | cut -d= -f2)"
CHAT_ID="5698128340"
REGISTRY="/home/ubuntu/ai-agent/data/agent_registry.json"
REPAIR_LOG="/home/ubuntu/ai-agent/data/repair.log"
STATE_FILE="/home/ubuntu/ai-agent/data/repair_state.json"

# --- Helpers ---

log() {
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $1" | tee -a "$REPAIR_LOG"
}

notify() {
    local msg="$1"
    curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
        -d chat_id="$CHAT_ID" \
        -d text="$msg" > /dev/null 2>&1
}

get_agent_field() {
    local agent="$1"
    local field="$2"
    python3 -c "
import json
r = json.load(open('$REGISTRY'))
v = r['agents'].get('$agent', {}).get('$field')
print(v if v is not None else '')
" 2>/dev/null
}

get_config() {
    local field="$1"
    python3 -c "
import json
r = json.load(open('$REGISTRY'))
print(r['config'].get('$field', ''))
" 2>/dev/null
}

list_agents() {
    python3 -c "
import json
r = json.load(open('$REGISTRY'))
for name, a in sorted(r['agents'].items(), key=lambda x: x[1].get('priority', 99)):
    print(f\"{name}|{a['service']}|{a.get('description', '')}|{a.get('priority', 99)}\")
" 2>/dev/null
}

get_restart_count() {
    local agent="$1"
    python3 -c "
import json, time
from pathlib import Path
p = Path('$STATE_FILE')
s = json.loads(p.read_text()) if p.exists() else {}
restarts = s.get('restarts', {}).get('$agent', [])
# Count restarts in last 10 minutes
now = time.time()
recent = [t for t in restarts if now - t < 600]
print(len(recent))
" 2>/dev/null
}

record_restart() {
    local agent="$1"
    python3 -c "
import json, time
from pathlib import Path
p = Path('$STATE_FILE')
s = json.loads(p.read_text()) if p.exists() else {}
s.setdefault('restarts', {}).setdefault('$agent', []).append(time.time())
# Keep only last hour
now = time.time()
s['restarts']['$agent'] = [t for t in s['restarts']['$agent'] if now - t < 3600]
p.write_text(json.dumps(s, indent=2))
" 2>/dev/null
}

# --- Core Functions ---

check_agent_health() {
    local agent="$1"
    local health_cmd=$(get_agent_field "$agent" "health_check")
    
    if [ -z "$health_cmd" ]; then
        echo "unknown"
        return
    fi
    
    if eval "$health_cmd" > /dev/null 2>&1; then
        echo "healthy"
    else
        echo "down"
    fi
}

get_agent_errors() {
    local agent="$1"
    local log_cmd=$(get_agent_field "$agent" "log_cmd")
    local error_pattern=$(get_agent_field "$agent" "error_pattern")
    
    if [ -z "$log_cmd" ]; then
        return
    fi
    
    eval "$log_cmd" 2>/dev/null | grep -iE "${error_pattern:-Error}" | tail -10
}

restart_agent() {
    local agent="$1"
    local service=$(get_agent_field "$agent" "service")
    local max_restarts=$(get_config "max_restart_attempts")
    
    # Check crash loop
    local recent_restarts=$(get_restart_count "$agent")
    if [ "${recent_restarts:-0}" -ge "${max_restarts:-3}" ]; then
        log "CRASH LOOP: $agent restarted ${recent_restarts}x in 10min, NOT restarting"
        echo "crash_loop"
        return 1
    fi
    
    log "RESTART: $agent ($service)"
    sudo systemctl restart "$service"
    record_restart "$agent"
    sleep 5
    
    if check_agent_health "$agent" | grep -q "healthy"; then
        log "RESTART: $agent recovered"
        echo "recovered"
        return 0
    else
        log "RESTART: $agent still unhealthy after restart"
        echo "still_down"
        return 1
    fi
}

backup_agent() {
    local agent="$1"
    local workdir=$(get_agent_field "$agent" "workdir")
    local entrypoint=$(get_agent_field "$agent" "entrypoint")
    local backup_dir=$(get_agent_field "$agent" "backup_dir")
    local max_backups=$(get_config "max_backups_per_agent")
    
    if [ -z "$workdir" ] || [ -z "$entrypoint" ] || [ -z "$backup_dir" ]; then
        log "BACKUP: $agent - no backup config"
        return 1
    fi
    
    mkdir -p "$backup_dir"
    local ts=$(date +%Y%m%d_%H%M%S)
    cp "$workdir/$entrypoint" "$backup_dir/${entrypoint%.py}_${ts}.py" 2>/dev/null || \
    cp "$workdir/$entrypoint" "$backup_dir/${entrypoint%.js}_${ts}.js" 2>/dev/null
    
    # Rotate
    local count=$(ls -1 "$backup_dir"/ 2>/dev/null | wc -l)
    if [ "$count" -gt "${max_backups:-5}" ]; then
        ls -1t "$backup_dir"/ | tail -n +$((max_backups + 1)) | while read f; do
            rm -f "$backup_dir/$f"
        done
    fi
    
    log "BACKUP: $agent snapshot $ts"
    echo "$ts"
}

rollback_agent() {
    local agent="$1"
    local workdir=$(get_agent_field "$agent" "workdir")
    local entrypoint=$(get_agent_field "$agent" "entrypoint")
    local backup_dir=$(get_agent_field "$agent" "backup_dir")
    local service=$(get_agent_field "$agent" "service")
    
    if [ -z "$backup_dir" ]; then
        log "ROLLBACK: $agent - no backup dir configured"
        return 1
    fi
    
    local latest=$(ls -1t "$backup_dir"/ 2>/dev/null | head -1)
    if [ -z "$latest" ]; then
        log "ROLLBACK: $agent - no backup found"
        return 1
    fi
    
    cp "$backup_dir/$latest" "$workdir/$entrypoint"
    sudo systemctl restart "$service"
    sleep 5
    
    if check_agent_health "$agent" | grep -q "healthy"; then
        log "ROLLBACK: $agent restored from $latest, healthy"
        return 0
    else
        log "ROLLBACK: $agent still unhealthy after rollback"
        return 1
    fi
}

diagnose_agent() {
    local agent="$1"
    local service=$(get_agent_field "$agent" "service")
    local workdir=$(get_agent_field "$agent" "workdir")
    local runtime=$(get_agent_field "$agent" "runtime")
    local description=$(get_agent_field "$agent" "description")
    
    echo "=== DIAGNOSIS: $agent ==="
    echo "Description: $description"
    echo "Service: $service"
    echo "Runtime: $runtime"
    echo "Workdir: $workdir"
    echo ""
    
    echo "--- Health ---"
    local health=$(check_agent_health "$agent")
    echo "Status: $health"
    echo ""
    
    echo "--- Service Info ---"
    systemctl status "$service" --no-pager 2>&1 | head -10
    echo ""
    
    echo "--- Recent Errors ---"
    get_agent_errors "$agent"
    echo ""
    
    echo "--- Memory ---"
    local pid=$(systemctl show "$service" -p MainPID --value 2>/dev/null)
    if [ -n "$pid" ] && [ "$pid" != "0" ]; then
        local mem=$(ps -p "$pid" -o rss= 2>/dev/null | awk '{printf "%.0fMB", $1/1024}')
        echo "PID: $pid, Memory: $mem"
    else
        echo "Not running"
    fi
    echo ""
    
    echo "--- Restart History (last hour) ---"
    local restarts=$(get_restart_count "$agent")
    echo "Restarts in last 10min: $restarts"
}

repair_agent() {
    local agent="$1"
    local can_patch=$(get_agent_field "$agent" "can_patch")
    
    log "REPAIR: starting repair for $agent"
    
    # Level 1: Restart
    local result=$(restart_agent "$agent")
    
    if [ "$result" = "recovered" ]; then
        notify "⚠️ Agent '$agent' was down, auto-restarted. Running OK now."
        return 0
    fi
    
    if [ "$result" = "crash_loop" ]; then
        # Get error info for alert
        local errors=$(get_agent_errors "$agent" | tail -5)
        notify "🔴 Agent '$agent' in crash loop (3+ restarts in 10min). Service stopped.

Recent errors:
$errors

Manual intervention needed."
        local service=$(get_agent_field "$agent" "service")
        sudo systemctl stop "$service"
        return 1
    fi
    
    # Level 2: Diagnose
    log "REPAIR: $agent still down after restart, diagnosing"
    local errors=$(get_agent_errors "$agent")
    
    if [ -z "$errors" ]; then
        notify "🟡 Agent '$agent' down, restart failed, no errors in log. Manual check needed."
        return 1
    fi
    
    # Level 3: Can we patch?
    if [ "$can_patch" != "True" ]; then
        notify "🟡 Agent '$agent' down with errors. Cannot auto-patch (can_patch=false).

Errors:
$(echo "$errors" | tail -5)

Run: agent_repair.sh diagnose $agent"
        return 1
    fi
    
    # Alert with diagnosis — Kai (via Telegram) can then decide to patch
    notify "🟡 Agent '$agent' down, restart failed.

Errors:
$(echo "$errors" | tail -5)

Kai can fix via:
  agent_repair.sh patch $agent <patch_file.py>

Or diagnose:
  agent_repair.sh diagnose $agent"
    
    return 1
}

# --- Check All Agents ---

check_all() {
    local issues=""
    local fixes=""
    
    while IFS='|' read -r name service description priority; do
        local health=$(check_agent_health "$name")
        
        if [ "$health" = "down" ]; then
            log "CHECK: $name is DOWN"
            local result=$(restart_agent "$name")
            
            if [ "$result" = "recovered" ]; then
                fixes="${fixes}$name: was down, restarted OK\n"
            elif [ "$result" = "crash_loop" ]; then
                issues="${issues}$name: CRASH LOOP, service stopped\n"
                sudo systemctl stop "$service" 2>/dev/null
            else
                issues="${issues}$name: down, restart failed\n"
            fi
        fi
    done < <(list_agents)
    
    # Report
    if [ -n "$issues" ]; then
        local msg=$(printf "🔴 Agent Repair Report:\n\nFailed:\n%b" "$issues")
        [ -n "$fixes" ] && msg=$(printf "%s\n\nAuto-fixed:\n%b" "$msg" "$fixes")
        notify "$msg"
        log "CHECK-ALL: issues found"
    elif [ -n "$fixes" ]; then
        notify "$(printf "⚠️ Agent Repair Report:\n\n%b\nAll agents healthy now." "$fixes")"
        log "CHECK-ALL: auto-fixed"
    else
        log "CHECK-ALL: all agents healthy"
    fi
}

patch_agent() {
    local agent="$1"
    local patch_file="$2"
    local can_patch=$(get_agent_field "$agent" "can_patch")
    local workdir=$(get_agent_field "$agent" "workdir")
    local entrypoint=$(get_agent_field "$agent" "entrypoint")
    local runtime=$(get_agent_field "$agent" "runtime")
    local service=$(get_agent_field "$agent" "service")
    
    if [ "$can_patch" != "True" ]; then
        log "PATCH: $agent is not patchable"
        echo "Agent $agent cannot be patched (can_patch=false)"
        return 1
    fi
    
    if [ ! -f "$patch_file" ]; then
        echo "Patch file not found: $patch_file"
        return 1
    fi
    
    log "PATCH: $agent from $patch_file"
    
    # Backup
    local backup_ts=$(backup_agent "$agent")
    
    # Apply patch
    local output
    output=$(python3 "$patch_file" 2>&1)
    local exit_code=$?
    
    if [ $exit_code -ne 0 ]; then
        log "PATCH: $agent patch script failed: $output"
        notify "🔴 Patch failed for $agent: $output"
        return 1
    fi
    
    # Syntax check (Python only)
    if [ "$runtime" = "python" ]; then
        if ! python3 -c "import py_compile; py_compile.compile('$workdir/$entrypoint', doraise=True)" 2>/dev/null; then
            log "PATCH: $agent syntax error, rolling back"
            rollback_agent "$agent"
            notify "🔴 Patch for $agent had syntax error. Rolled back."
            return 1
        fi
    fi
    
    # Node syntax check
    if [ "$runtime" = "node" ]; then
        if ! node --check "$workdir/$entrypoint" 2>/dev/null; then
            log "PATCH: $agent syntax error (node), rolling back"
            rollback_agent "$agent"
            notify "🔴 Patch for $agent had syntax error. Rolled back."
            return 1
        fi
    fi
    
    # Restart
    sudo systemctl restart "$service"
    sleep 10
    
    # Health check
    if check_agent_health "$agent" | grep -q "healthy"; then
        log "PATCH: $agent patched and healthy"
        notify "✅ Agent '$agent' patched successfully (backup: $backup_ts)"
        rm -f "$patch_file"
        return 0
    else
        log "PATCH: $agent unhealthy after patch, rolling back"
        rollback_agent "$agent"
        notify "⚠️ Agent '$agent' patch applied but unhealthy. Rolled back to $backup_ts."
        return 1
    fi
}

# --- Main ---

case "${1:-help}" in
    check)
        check_all
        ;;
    repair)
        if [ -z "${2:-}" ]; then
            echo "Usage: agent_repair.sh repair <agent_name>"
            echo "Agents: $(list_agents | cut -d'|' -f1 | tr '\n' ' ')"
            exit 1
        fi
        repair_agent "$2"
        ;;
    diagnose)
        if [ -z "${2:-}" ]; then
            echo "Usage: agent_repair.sh diagnose <agent_name>"
            exit 1
        fi
        diagnose_agent "$2"
        ;;
    patch)
        if [ -z "${2:-}" ] || [ -z "${3:-}" ]; then
            echo "Usage: agent_repair.sh patch <agent_name> <patch_file.py>"
            exit 1
        fi
        patch_agent "$2" "$3"
        ;;
    rollback)
        if [ -z "${2:-}" ]; then
            echo "Usage: agent_repair.sh rollback <agent_name>"
            exit 1
        fi
        rollback_agent "$2"
        if [ $? -eq 0 ]; then
            notify "✅ Agent '$2' rolled back successfully."
        else
            notify "🔴 Rollback failed for '$2'."
        fi
        ;;
    restart)
        if [ -z "${2:-}" ]; then
            echo "Usage: agent_repair.sh restart <agent_name>"
            exit 1
        fi
        restart_agent "$2"
        ;;
    list)
        echo "=== Registered Agents ==="
        printf "%-12s %-28s %-6s %s\n" "NAME" "SERVICE" "PRIO" "DESCRIPTION"
        printf "%-12s %-28s %-6s %s\n" "----" "-------" "----" "-----------"
        while IFS='|' read -r name service description priority; do
            health=$(check_agent_health "$name")
            icon="✅"
            [ "$health" = "down" ] && icon="❌"
            [ "$health" = "unknown" ] && icon="❓"
            printf "%-12s %-28s %-6s %s %s\n" "$name" "$service" "$priority" "$icon" "$description"
        done < <(list_agents)
        ;;
    status)
        echo "=== Agent Health Status ==="
        while IFS='|' read -r name service description priority; do
            health=$(check_agent_health "$name")
            icon="✅"
            [ "$health" = "down" ] && icon="❌"
            printf "%s %-12s %s\n" "$icon" "$name" "$health"
        done < <(list_agents)
        echo ""
        echo "=== Last 10 Repair Log ==="
        tail -10 "$REPAIR_LOG" 2>/dev/null || echo "No log yet"
        ;;
    help|*)
        echo "Kai Multi-Agent Repair System"
        echo ""
        echo "Usage: agent_repair.sh <command> [args]"
        echo ""
        echo "Commands:"
        echo "  check              - Check all agents, auto-restart if down"
        echo "  repair <agent>     - Full repair cycle (restart → diagnose → alert)"
        echo "  diagnose <agent>   - Show detailed diagnosis"
        echo "  patch <agent> <f>  - Apply patch file with backup + rollback"
        echo "  rollback <agent>   - Restore agent from latest backup"
        echo "  restart <agent>    - Simple restart with crash-loop protection"
        echo "  list               - List all registered agents + status"
        echo "  status             - Quick health overview + recent log"
        echo ""
        echo "Registry: $REGISTRY"
        echo "Log: $REPAIR_LOG"
        ;;
esac
