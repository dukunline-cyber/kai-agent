#!/bin/bash
# notify_tunnels.sh - After boot, wait for tunnel URLs and notify via Telegram
# Also updates n8n WEBHOOK_URL with fresh tunnel URL

BOT_TOKEN="$(grep TELEGRAM_BOT_TOKEN /home/ubuntu/ai-agent/.env | cut -d= -f2)"
CHAT_ID="5698128340"

# Wait for tunnels to establish
sleep 30

# Collect tunnel URLs from journal
get_tunnel_url() {
    local service="$1"
    journalctl -u "$service" --since "5 min ago" --no-pager 2>/dev/null | grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -1
}

URL_9ROUTER=$(get_tunnel_url "9router-tunnel.service")
URL_N8N=$(get_tunnel_url "kai-cf.service")
URL_PREVIEW=$(get_tunnel_url "soul-preview-tunnel.service")

# Update n8n WEBHOOK_URL if new tunnel URL available
if [ -n "$URL_N8N" ]; then
    sudo sed -i "s|Environment=WEBHOOK_URL=.*|Environment=WEBHOOK_URL=${URL_N8N}/|" /etc/systemd/system/n8n.service
    sudo sed -i "s|Environment=N8N_EDITOR_BASE_URL=.*|Environment=N8N_EDITOR_BASE_URL=${URL_N8N}/|" /etc/systemd/system/n8n.service
    sudo systemctl daemon-reload
    sudo systemctl restart n8n.service
fi

# Build message
MSG="🔄 VPS Rebooted — Tunnel URLs updated:

"
[ -n "$URL_9ROUTER" ] && MSG+="9Router: $URL_9ROUTER
"
[ -n "$URL_N8N" ] && MSG+="n8n: $URL_N8N
"
[ -n "$URL_PREVIEW" ] && MSG+="Preview: $URL_PREVIEW
"

# Save to file for quick reference
echo "$(date -Iseconds)" > /home/ubuntu/ai-agent/data/tunnel_urls.txt
[ -n "$URL_9ROUTER" ] && echo "9Router: $URL_9ROUTER" >> /home/ubuntu/ai-agent/data/tunnel_urls.txt
[ -n "$URL_N8N" ] && echo "n8n: $URL_N8N" >> /home/ubuntu/ai-agent/data/tunnel_urls.txt
[ -n "$URL_PREVIEW" ] && echo "Preview: $URL_PREVIEW" >> /home/ubuntu/ai-agent/data/tunnel_urls.txt

# Send to Telegram
curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
    -d chat_id="$CHAT_ID" \
    -d text="$MSG" > /dev/null 2>&1
