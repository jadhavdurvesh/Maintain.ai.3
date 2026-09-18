import json
import os
import urllib.request
from functools import lru_cache

import jwt
from jwt import PyJWKClient

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")

def enabled():
    return bool(SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY)

@lru_cache(maxsize=1)
def _jwks_client():
    return PyJWKClient(f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json")

def verify_access_token(token: str):
    if not enabled(): return None
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg")
        if alg and alg != "HS256":
            key = _jwks_client().get_signing_key_from_jwt(token).key
            return jwt.decode(token, key, algorithms=[alg], audience="authenticated", options={"verify_iss": False})
        req = urllib.request.Request(f"{SUPABASE_URL}/auth/v1/user", headers={"apikey": SUPABASE_PUBLISHABLE_KEY, "Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=5) as response:
            user = json.loads(response.read().decode("utf-8"))
        return {"sub": user.get("id"), "email": user.get("email"), "user": user}
    except Exception:
        return None
