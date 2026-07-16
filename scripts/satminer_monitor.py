import os, time, subprocess, requests, re

# Config
CHECK_INTERVAL = 60  # cek tiap 60 detik
SUMMARY_INTERVAL = 600  # kirim summary tiap 10 menit
CHAT_ID = "5698128340"
CREDS_FILE = os.path.expanduser("~/ai-agent/credentials/telegram_satminer.env")
SSH_CMD = "ssh -p 19038 -o StrictHostKeyChecking=no -o ConnectTimeout=15 root@ssh7.vast.ai"
LOG_FILE = "/root/satminer.log"
LAST_LINES_FILE = "/tmp/satminer_last_line_count.txt"

# Load bot token
def load_token():
    with open(CREDS_FILE) as f:
        for line in f:
            if line.startswith("TELEGRAM_SATMINER_BOT_TOKEN="):
                return line.strip().split("=", 1)[1]
    return None

BOT_TOKEN = load_token()
if not BOT_TOKEN:
    raise RuntimeError("Bot token not found")

def send_tg(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": text}, timeout=10)
    except Exception as e:
        print(f"TG send error: {e}")

def ssh_cmd(cmd):
    try:
        result = subprocess.run(
            f'{SSH_CMD} "{cmd}"',
            shell=True, capture_output=True, text=True, timeout=30
        )
        return result.stdout.strip()
    except Exception as e:
        return f"SSH error: {e}"

def get_log_tail(n=50):
    raw = ssh_cmd(f"tail -{n} {LOG_FILE} 2>/dev/null | strings")
    # Strip ANSI codes
    clean = re.sub(r'\x1b\[[0-9;]*m', '', raw)
    return clean

def get_process_status():
    raw = ssh_cmd("ps aux | grep gpu_miner | grep -v grep | awk '{print $3, $4, $6}'")
    if raw:
        parts = raw.split()
        if len(parts) >= 3:
            return {"cpu": parts[0], "mem_pct": parts[1], "mem_kb": parts[2]}
    return None

def parse_mining_events(log_text):
    events = []
    for line in log_text.split("\n"):
        line_lower = line.lower()
        if any(kw in line_lower for kw in ["solve", "submit", "mint", "nonce", "found", "tx", "success", "fail", "error", "revert"]):
            events.append(line.strip())
    return events

def main():
    send_tg("SatMiner Monitor started. Checking every 60s, summary every 10min.")
    last_summary = time.time()
    seen_events = set()
    
    while True:
        try:
            # Get latest log
            log = get_log_tail(50)
            
            # Check for new mining events
            events = parse_mining_events(log)
            new_events = [e for e in events if e not in seen_events]
            
            if new_events:
                for e in new_events:
                    seen_events.add(e)
                msg = "Mining events:\n" + "\n".join(new_events[-10:])  # max 10
                send_tg(msg)
            
            # Periodic summary
            if time.time() - last_summary >= SUMMARY_INTERVAL:
                proc = get_process_status()
                if proc:
                    summary = (
                        f"SatMiner Status:\n"
                        f"CPU: {proc['cpu']}%\n"
                        f"MEM: {proc['mem_pct']}% ({int(int(proc['mem_kb'])/1024)}MB)\n"
                        f"Total events tracked: {len(seen_events)}\n"
                        f"Miner: RUNNING"
                    )
                else:
                    summary = "SatMiner Status: PROCESS NOT FOUND! Miner may have crashed."
                send_tg(summary)
                last_summary = time.time()
            
        except Exception as e:
            print(f"Monitor error: {e}")
        
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
