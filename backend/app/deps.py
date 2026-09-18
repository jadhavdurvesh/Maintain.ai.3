import os
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from . import models
from .auth import decode_access_token
from .bootstrap import BOOTSTRAP_ORG_ID
from .database import get_db
from .supabase_auth import enabled as supabase_auth_enabled, verify_access_token


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


def _supabase_user_from_token(authorization: str | None, db: Session):
    if not supabase_auth_enabled() or not authorization or not authorization.startswith("Bearer "): return None
    claims = verify_access_token(authorization.removeprefix("Bearer ").strip())
    if not claims or not claims.get("sub"): return None
    user = db.query(models.User).filter_by(supabase_user_id=str(claims["sub"])).first()
    if not user and claims.get("email"): user = db.query(models.User).filter_by(email=claims["email"]).first()
    if not user or not user.active: return None
    if not user.supabase_user_id:
        user.supabase_user_id = str(claims["sub"]); db.commit()
    return CurrentUser(id=user.id, organization_id=user.organization_id or BOOTSTRAP_ORG_ID, username=user.username, role=user.role.value)
def get_current_user(
    authorization: str | None = Header(
        default=None,
    ),
    x_maintain_application: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> CurrentUser:
    supabase_user = _supabase_user_from_token(authorization, db)
    if supabase_user:
        application = (x_maintain_application or "engineering").strip().lower()
        if application not in {"engineering", "android", "workforce"}:
            raise HTTPException(status_code=400, detail="invalid application context")
        access = db.query(models.UserApplicationAccess).filter(
            models.UserApplicationAccess.user_id == supabase_user.id,
            models.UserApplicationAccess.application == application,
            models.UserApplicationAccess.enabled.is_(True),
        ).first()
        if not access:
            raise HTTPException(status_code=403, detail=f"account is not enabled for the {application} application")
        return supabase_user
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