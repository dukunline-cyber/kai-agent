#!/usr/bin/env python3
import json, os, sys, http.client, concurrent.futures

api_key = os.environ["COMMANDCODE_API_KEY"]

# Semua candidate provider/model dari Command Code
candidates = [
    # DeepSeek
    "deepseek/deepseek-v4-flash",
    "deepseek/deepseek-v4",
    "deepseek/deepseek-v4-pro",
    "deepseek/deepseek-chat",
    "deepseek/deepseek-reasoner",
    "deepseek/deepseek-r1",
    "deepseek/deepseek-v3",
    # Moonshot / Kimi
    "moonshotai/Kimi-K2.7-Code-Highspeed",
    "moonshotai/Kimi-K2.5",
    "moonshotai/Kimi-K2",
    "moonshotai/kimi-latest",
    # Anthropic/Claude
    "anthropic/claude-sonnet-4-20250514",
    "anthropic/claude-3-5-sonnet-20241022",
    "anthropic/claude-3-opus-20240229",
    "anthropic/claude-3-5-haiku-20241022",
    # OpenAI
    "openai/gpt-5",
    "openai/gpt-5-mini",
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
    "openai/gpt-4-turbo",
    "openai/o3-mini",
    # Google
    "google/gemini-2.5-flash",
    "google/gemini-2.5-pro",
    "google/gemini-2.0-flash",
    # Grok
    "grok/grok-3",
    "grok/grok-3-mini",
    # Qwen
    "qwen/qwen-max",
    "qwen/qwen-plus",
    # Mistral
    "mistral/mistral-large",
    "mistral/mistral-small",
    # Meta
    "meta/llama-4-maverick",
    "meta/llama-3.3-70b",
]

def test_one(model):
    payload = json.dumps({
        "memory": "",
        "params": {
            "model": model,
            "messages": [{"role": "user", "content": "hi"}],
            "maxOutputTokens": 5,
            "temperature": 0.7
        },
        "config": {
            "workingDir": "/home/ubuntu",
            "date": "2026-06-16T12:10:00Z",
            "environment": "linux-x64",
            "structure": [],
            "isGitRepo": False,
            "currentBranch": "",
            "mainBranch": "",
            "gitStatus": "",
            "recentCommits": []
        }
    })
    try:
        conn = http.client.HTTPSConnection("api.commandcode.ai", timeout=12)
        conn.request("POST", "/alpha/generate", payload, {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "x-command-code-version": "0.38.2"
        })
        resp = conn.getresponse()
        data = resp.read().decode()[:200]
        conn.close()
        if resp.status == 200:
            return (model, "ok", "")
        elif resp.status == 403:
            try:
                err = json.loads(data)
                msg = err.get("message", "")[:120]
            except:
                msg = data[:120]
            return (model, "forbidden", msg)
        else:
            return (model, "error", f"{resp.status} {data[:100]}")
    except Exception as e:
        return (model, "error", str(e)[:80])

ok, forbidden, errors = [], [], []

with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
    futures = {ex.submit(test_one, m): m for m in candidates}
    for f in concurrent.futures.as_completed(futures):
        model, status, detail = f.result()
        icon = "✅" if status == "ok" else ("❌" if status == "forbidden" else "⚠️")
        print(f"{icon} {model}")
        sys.stdout.flush()
        if status == "ok":
            ok.append(model)
        elif status == "forbidden":
            forbidden.append(model)
        else:
            errors.append((model, detail))

print()
print(f"=== HASIL SCAN ===")
print(f"Aktif ({len(ok)}):")
for m in sorted(ok):
    print(f"  ✅ {m}")
print(f"Forbidden ({len(forbidden)}):")
for m in sorted(forbidden):
    print(f"  ❌ {m}")
if errors:
    print(f"Error lain ({len(errors)}):")
    for m, e in errors:
        print(f"  ⚠️ {m} — {e}")
