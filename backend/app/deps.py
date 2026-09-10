"""
The get_current_user dependency scopes every request to the active user
organization. Auth remains optional for the local/desktop mode.
"""
import os
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from . import models
from .auth import decode_access_token
from .bootstrap import BOOTSTRAP_ORG_ID
from .database import get_db


def auth_required() -> bool:
    return os.getenv("REQUIRE_AUTH", "false").lower() == "true"


@dataclass
class CurrentUser:
    id: int | None
    organization_id: int
    username: str
    role: str


def get_current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> CurrentUser:
    if not auth_required():
        return CurrentUser(id=None, organization_id=BOOTSTRAP_ORG_ID, username="local", role="admin")

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "not authenticated")

    token = authorization.removeprefix("Bearer ").strip()
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(401, "invalid or expired token")

    user = db.get(models.User, int(payload["sub"]))
    if not user or not user.active or user.organization_id != payload.get("org"):
        raise HTTPException(401, "account is inactive or invalid")

    return CurrentUser(id=user.id, organization_id=user.organization_id, username=user.username, role=user.role.value)
