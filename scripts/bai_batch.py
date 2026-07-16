#!/usr/bin/env python3
"""BAI batch claim + API key generator"""
import subprocess, json, sys, os

OUTPUT_FILE = os.path.expanduser('~/ai-agent/data/bai_keys.txt')

def process(cookie_json_path):
    with open(cookie_json_path) as f:
        cookies_list = json.load(f)
    
    cookie_dict = {}
    for c in cookies_list:
        cookie_dict[c['name']] = c['value']
    
    csrf = cookie_dict['__Host-authjs.csrf-token'].split('%7C')[0]
    cookie_str = '; '.join([f'{k}={v}' for k,v in cookie_dict.items()])
    
    # 1. Cek status
    r = subprocess.run([
        'curl', '-s',
        '-H', 'Cookie: ' + cookie_str,
        '-H', f'x-csrf-token: {csrf}',
        'https://chat.b.ai/trpc/lambda/user.hasClaimedSignupBonus,usage.points?batch=1&input=%7B%220%22%3A%7B%22json%22%3Anull%2C%22meta%22%3A%7B%22values%22%3A%5B%22undefined%22%5D%2C%22v%22%3A1%7D%7D%2C%221%22%3A%7B%22json%22%3Anull%2C%22meta%22%3A%7B%22values%22%3A%5B%22undefined%22%5D%2C%22v%22%3A1%7D%7D%7D'
    ], capture_output=True, text=True, timeout=15)
    
    try:
        data = json.loads(r.stdout)
        claimed = data[0]['result']['data']['json']['hasClaimed']
        credits = data[1]['result']['data']['json']['points_balance']
        print(f"Claimed: {claimed} | Credits: {credits}")
    except:
        print(f"Status parse error: {r.stdout[:200]}")
        return
    
    # 2. Create API key
    r = subprocess.run([
        'curl', '-s', '-X', 'POST',
        '-H', 'Cookie: ' + cookie_str,
        '-H', 'Content-Type: application/json',
        '-H', f'x-csrf-token: {csrf}',
        'https://chat.b.ai/trpc/lambda/apiKey.createApiKey?batch=1',
        '-d', '{"0":{"json":{"name":"kai-auto"}}}'
    ], capture_output=True, text=True, timeout=15)
    
    try:
        result = json.loads(r.stdout)
        if isinstance(result, list) and 'result' in result[0]:
            key_data = result[0]['result']['data']['json']
            api_key = key_data['key']
            with open(OUTPUT_FILE, 'a') as f:
                f.write(f"{api_key}\n")
            print(f"✅ Key: [REDACTED_OPENAI_KEY] | ID: {key_data['id']}")
        elif 'error' in r.stdout.lower():
            print(f"❌ Error: {r.stdout[:300]}")
        else:
            print(f"⚠️ Unexpected: {r.stdout[:300]}")
    except Exception as e:
        print(f"Parse error: {e} | Raw: {r.stdout[:300]}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 bai_batch.py <cookie_file.json>")
        sys.exit(1)
    process(sys.argv[1])
