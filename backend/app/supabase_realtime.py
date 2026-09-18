import asyncio
import json
import os
import urllib.request
import urllib.parse

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY", "")

async def broadcast(topic: str, event: str, payload: dict, private: bool = True):
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY: return False
    url = SUPABASE_URL + "/realtime/v1/api/broadcast/" + urllib.parse.quote(topic, safe="") + "/events/" + urllib.parse.quote(event, safe="")
    if private: url += "?private=true"
    body = json.dumps(payload).encode("utf-8")
    def send():
        req = urllib.request.Request(url, data=body, method="POST", headers={"apikey": SUPABASE_SECRET_KEY, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=3) as response: return 200 <= response.status < 300
    try: return await asyncio.to_thread(send)
    except Exception: return False
