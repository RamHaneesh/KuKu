"""Verify Google Gemini API connectivity and credentials with a minimal ping."""

import json
import os
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

env_path = Path(__file__).resolve().parent / ".env"
if env_path.is_file():
    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        k, sep, v = line.partition("=")
        if sep:
            os.environ[k.strip()] = v.strip().strip("'\"")

key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

print("--- Gemini API Connectivity Test ---")
if not key:
    print("Error: No GEMINI_API_KEY found in .env")
    sys.exit(1)

print("Key loaded: Yes")
print(f"Target model: {model}")

# Minimal ping test
endpoint = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
payload = {
    "model": model,
    "messages": [{"role": "user", "content": "Respond only with the single word: PONG"}],
    "max_tokens": 500
}

try:
    req = Request(
        endpoint,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        data=json.dumps(payload).encode("utf-8")
    )
    with urlopen(req, timeout=15) as resp:
        res = json.load(resp)
        reply = res["choices"][0]["message"].get("content", "").strip()
        print(f"Status: 200 OK")
        print(f"Model response: '{reply}'")
        print("Verdict: API IS CONNECTED AND WORKING!")
except HTTPError as e:
    print(f"HTTP Error {e.code}: {e.reason}")
    print(e.read().decode('utf-8', errors='replace'))
except Exception as e:
    print(f"Connection Error: {e}")
