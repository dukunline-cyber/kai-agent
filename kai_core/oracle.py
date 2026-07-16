"""Split from telegram_agent monolith — behavior preserved."""
from __future__ import annotations

from kai_core.config import *  # noqa: F401,F403


def is_status_query(text: str) -> bool:
    t = (text or "").lower().strip().rstrip("!?.").strip()
    if not t or len(t) > 50:
        return False
    if t in STATUS_QUERY_KEYWORDS:
        return True
    return any(t == k or t.startswith(k + " ") for k in STATUS_QUERY_KEYWORDS)
ORACLE_CONFIG_FILE = DATA_DIR / "oracle_config.json"

def load_oracle_config() -> dict:
    if ORACLE_CONFIG_FILE.exists():
        try:
            return json.loads(ORACLE_CONFIG_FILE.read_text())
        except:
            pass
    return {}

def save_oracle_config(data: dict):
    ORACLE_CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    ORACLE_CONFIG_FILE.chmod(0o600)

def try_launch_instance(config: dict) -> tuple:
    if not OCI_AVAILABLE:
        return False, "error: oci library not installed"
    try:
        oci_config = {
            "user": config["user_ocid"],
            "key_content": config["private_key"],
            "fingerprint": config["fingerprint"],
            "tenancy": config["tenancy_ocid"],
            "region": config["region"],
        }
        compute = oci.core.ComputeClient(oci_config)
        details = oci.core.models.LaunchInstanceDetails(
            compartment_id=config["compartment_id"],
            availability_domain=config["availability_domain"],
            shape=config.get("shape", "VM.Standard.A1.Flex"),
            shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(
                ocpus=float(config.get("ocpus", 4)),
                memory_in_gbs=float(config.get("memory_gb", 24))
            ),
            display_name=config.get("instance_name", "free-arm"),
            source_details=oci.core.models.InstanceSourceViaImageDetails(
                source_type="image",
                image_id=config["image_id"]
            ),
            create_vnic_details=oci.core.models.CreateVnicDetails(
                subnet_id=config["subnet_id"],
                assign_public_ip=True
            ),
            metadata={"ssh_authorized_keys": config.get("ssh_public_key", "")}
        )
        response = compute.launch_instance(details)
        inst = response.data
        return True, f"\u2705 BERHASIL! Instance dibuat!\n\nID: {inst.id}\nNama: {inst.display_name}\nShape: {inst.shape}\nState: {inst.lifecycle_state}"
    except Exception as e:
        err = str(e)
        if "Out of host capacity" in err or "capacity" in err.lower():
            return False, "out_of_capacity"
        elif "LimitExceeded" in err:
            return False, f"limit_exceeded: {err}"
        else:
            return False, f"error: {err[:200]}"

def oracle_war_loop(chat_id: int, config: dict, notify_fn, interval: int = 30):
    attempt = 0
    start_time = time.time()
    while oracle_war_running.get(chat_id):
        attempt += 1
        elapsed = int(time.time() - start_time)
        success, msg = try_launch_instance(config)
        if success:
            notify_fn(chat_id, msg)
            oracle_war_running.pop(chat_id, None)
            return
        if msg.startswith("limit_exceeded") or (msg.startswith("error:") and "capacity" not in msg):
            notify_fn(chat_id, f"\u26a0\ufe0f War dihentikan.\nAlasan: {msg}")
            oracle_war_running.pop(chat_id, None)
            return
        if attempt % 20 == 0:
            h, m = elapsed // 3600, (elapsed % 3600) // 60
            notify_fn(chat_id, f"\U0001f504 War jalan... Attempt: {attempt} | Waktu: {h}j {m}m | Status: out of capacity, terus retry")
        time.sleep(interval)
    elapsed = int(time.time() - start_time)
    notify_fn(chat_id, f"\u23f9\ufe0f War dihentikan.\nTotal attempt: {attempt} | Waktu: {elapsed//3600}j {(elapsed%3600)//60}m")

# ========================
# SECRET REDACTION
# ========================

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

