import os
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from . import models
from .auth import decode_access_token
from .bootstrap import BOOTSTRAP_ORG_ID
from .database import get_db


def auth_required() -> bool:
    return os.getenv(
        "REQUIRE_AUTH",
        "false",
    ).lower() == "true"


@dataclass
class CurrentUser:
    id: int | None
    organization_id: int
    username: str
    role: str


def _user_from_token(
    authorization: str | None,
    db: Session,
) -> CurrentUser:
    if (
        not authorization
        or not authorization.startswith("Bearer ")
    ):
        raise HTTPException(
            status_code=401,
            detail="not authenticated",
        )

    token = authorization.removeprefix(
        "Bearer "
    ).strip()

    payload = decode_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=401,
            detail="invalid or expired token",
        )

    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=401,
            detail="invalid authentication token",
        )

    organization_id = payload.get("org")

    if organization_id is None:
        raise HTTPException(
            status_code=401,
            detail="invalid authentication token",
        )

    user = db.get(
        models.User,
        user_id,
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="user account not found",
        )

    if not user.active:
        raise HTTPException(
            status_code=401,
            detail="account is inactive",
        )

    if user.organization_id != organization_id:
        raise HTTPException(
            status_code=401,
            detail="invalid organization context",
        )

    return CurrentUser(
        id=user.id,
        organization_id=user.organization_id,
        username=user.username,
        role=user.role.value,
    )


def get_current_user(
    authorization: str | None = Header(
        default=None,
    ),
    db: Session = Depends(get_db),
) -> CurrentUser:
    # A valid token always takes precedence over local mode.
    if authorization and authorization.startswith("Bearer "):
        return _user_from_token(
            authorization,
            db,
        )

    # Preserve the existing desktop/local behavior.
    if not auth_required():
        return CurrentUser(
            id=None,
            organization_id=BOOTSTRAP_ORG_ID,
            username="local",
            role="admin",
        )

    raise HTTPException(
        status_code=401,
        detail="not authenticated",
    )


def get_authenticated_user(
    authorization: str | None = Header(
        default=None,
    ),
    db: Session = Depends(get_db),
) -> CurrentUser:
    return _user_from_token(
        authorization,
        db,
    )