import json
import os
import urllib.request
from functools import lru_cache

import jwt
from jwt import PyJWKClient

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY", "")

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



def sync_organization_claim(supabase_user_id: str, organization_id: int):
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        return False
    url = f"{SUPABASE_URL}/auth/v1/admin/users/{supabase_user_id}"
    payload = json.dumps({"app_metadata": {"organization_id": str(organization_id)}}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        method="PUT",
        headers={
            "apikey": SUPABASE_SECRET_KEY,
            "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return 200 <= response.status < 300
    except Exception:
        return False
