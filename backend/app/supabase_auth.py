import json
import os
import urllib.request
from urllib.error import HTTPError
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


def create_user_with_password(email: str, password: str, user_metadata: dict | None = None, app_metadata: dict | None = None):
    """Create an Auth user server-side without sending an email."""
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        raise RuntimeError("Supabase server credentials are not configured")
    payload = {
        "email": email,
        "password": password,
        "email_confirm": True,
    }
    if user_metadata:
        payload["user_metadata"] = user_metadata
    if app_metadata:
        payload["app_metadata"] = app_metadata
    req = urllib.request.Request(
        f"{SUPABASE_URL}/auth/v1/admin/users",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "apikey": SUPABASE_SECRET_KEY,
            "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace").strip()
        except Exception:
            detail = ""
        if len(detail) > 1000:
            detail = detail[:1000] + "…"
        message = f"Supabase user creation failed (HTTP {exc.code})"
        if detail:
            message += f": {detail}"
        raise RuntimeError(message) from exc
    except Exception as exc:
        raise RuntimeError(f"Supabase user creation failed: {exc}") from exc


def delete_user(supabase_user_id: str):
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        return False
    req = urllib.request.Request(
        f"{SUPABASE_URL}/auth/v1/admin/users/{supabase_user_id}",
        method="DELETE",
        headers={
            "apikey": SUPABASE_SECRET_KEY,
            "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return 200 <= response.status < 300
    except Exception:
        return False


def update_authenticated_password(access_token: str, new_password: str):
    """Change the password for the currently authenticated Supabase user."""
    if not SUPABASE_URL or not SUPABASE_PUBLISHABLE_KEY:
        raise RuntimeError("Supabase Auth is not configured")
    req = urllib.request.Request(
        f"{SUPABASE_URL}/auth/v1/user",
        data=json.dumps({"password": new_password}).encode("utf-8"),
        method="PUT",
        headers={
            "apikey": SUPABASE_PUBLISHABLE_KEY,
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace").strip()
        except Exception:
            detail = ""
        if len(detail) > 1000:
            detail = detail[:1000] + "…"
        message = f"Supabase password update failed (HTTP {exc.code})"
        if detail:
            message += f": {detail}"
        raise RuntimeError(message) from exc
    except Exception as exc:
        raise RuntimeError(f"Supabase password update failed: {exc}") from exc


def invite_user_by_email(email: str, redirect_to: str | None = None, metadata: dict | None = None):
    """Create an invited Supabase Auth identity using the server-only secret key."""
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        raise RuntimeError("Supabase server credentials are not configured")
    payload = {"email": email}
    if metadata:
        payload["data"] = metadata
    if redirect_to:
        payload["redirect_to"] = redirect_to
    req = urllib.request.Request(
        f"{SUPABASE_URL}/auth/v1/invite",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "apikey": SUPABASE_SECRET_KEY,
            "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace").strip()
        except Exception:
            detail = ""
        if len(detail) > 1000:
            detail = detail[:1000] + "…"
        message = f"Supabase invitation failed (HTTP {exc.code})"
        if detail:
            message += f": {detail}"
        raise RuntimeError(message) from exc
    except Exception as exc:
        raise RuntimeError(f"Supabase invitation failed: {exc}") from exc
