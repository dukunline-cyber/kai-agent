#!/bin/bash
# SatMiner Monitor v2 - with heartbeat

source /home/ubuntu/ai-agent/credentials/telegram_satminer.env
BOT_TOKEN="$TELEGRAM_SATMINER_BOT_TOKEN"
CHAT_ID="5698128340"
HEARTBEAT_INTERVAL=300  # 5 menit

send_tg() {
    local msg="$1"
    curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
        -d chat_id="$CHAT_ID" -d text="$msg" -d parse_mode="HTML" >>/tmp/satminer_debug.log 2>&1
}

strip_ansi() {
    sed 's/\x1b\[[0-9;]*m//g'
}

monitor_instance() {
    local name="$1"
    local host="$2"
    local port="$3"
    local prev_sent=0
    local prev_success=0
    local prev_fail=0

    ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30 -p "$port" root@"$host" 'tail -f /root/satminer.log' 2>/dev/null | while IFS= read -r line; do
        clean=$(echo "$line" | strip_ansi)

        # Detect GPU startup
        if echo "$clean" | grep -q "GPU 设备"; then
            gpu=$(echo "$clean" | grep -oP 'GPU 设备: \K.*?(?=  batch)')
            send_tg "🟢 <b>[$name] Miner Started</b>%0AGPU: $gpu"
        fi

        # Mint success
        if echo "$clean" | grep -q "成功 mint"; then
            send_tg "✅ <b>[$name] MINT SUCCESS!</b>%0A$clean"
        fi

        # Mint fail
        if echo "$clean" | grep -q "失败\|revert\|FAIL"; then
            if ! echo "$clean" | grep -q "钱包统计\|合计"; then
                send_tg "❌ <b>[$name] Mint Failed</b>%0A$clean"
            fi
        fi

        # Skipped
        if echo "$clean" | grep -q "跳过\|skip"; then
            if ! echo "$clean" | grep -q "钱包统计\|合计"; then
                send_tg "⏭ <b>[$name] Skipped</b>%0A$clean"
            fi
        fi

        # Stats update
        if echo "$clean" | grep -q "合计.*发出"; then
            sent=$(echo "$clean" | grep -oP '发出 \K[0-9]+')
            success=$(echo "$clean" | grep -oP '成功 \K[0-9]+')
            fail=$(echo "$clean" | grep -oP '失败.浪费gas. \K[0-9]+')
            if [ "$sent" != "$prev_sent" ] || [ "$success" != "$prev_success" ] || [ "$fail" != "$prev_fail" ]; then
                send_tg "📊 <b>[$name] Stats Update</b>%0ASent: $sent | Success: $success | Failed: $fail"
                prev_sent=$sent
                prev_success=$success
                prev_fail=$fail
            fi
        fi

        # Hashrate
        if echo "$clean" | grep -q "算力"; then
            hashrate=$(echo "$clean" | grep -oP '算力: \K[0-9.]+ [A-Z]+/s')
            send_tg "⚡ <b>[$name] Hashrate</b>%0A$hashrate"
        fi

        # Errors
        if echo "$clean" | grep -qi "error\|exception\|disconnect"; then
            if ! echo "$clean" | grep -q "连接失败"; then
                send_tg "⚠️ <b>[$name] Error</b>%0A$clean"
            fi
        fi
    done
}

heartbeat() {
    while true; do
        sleep $HEARTBEAT_INTERVAL
        local status=""
        for entry in "4090:ssh7.vast.ai:25922" "A4000:ssh2.vast.ai:28760" "3090:ssh8.vast.ai:34074"; do
            IFS=: read -r name host port <<< "$entry"
            # Cek apakah miner masih jalan
            alive=$(ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -p "$port" root@"$host" 'ps aux | grep "python3 gpu_miner" | grep -v grep | wc -l' 2>/dev/null)
            lastline=$(ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -p "$port" root@"$host" 'tail -1 /root/satminer.log' 2>/dev/null | strip_ansi)
            if [ "$alive" -gt 0 ] 2>/dev/null; then
                status="${status}✅ $name: running%0A"
            else
                status="${status}❌ $name: STOPPED%0A"
            fi
        done
        send_tg "💓 <b>Heartbeat</b>%0A${status}"
    done
}

# Startup
send_tg "🤖 <b>SatMiner Monitor v2 Started</b>%0AMonitoring: RTX 4090, RTX A4000, RTX 3090%0AHeartbeat: every 5min"

# Run monitors in parallel
monitor_instance "4090" "ssh7.vast.ai" "25922" &
monitor_instance "A4000" "ssh2.vast.ai" "28760" &
monitor_instance "3090" "ssh8.vast.ai" "34074" &
heartbeat &

wait
