from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, EmailStr
import os
from datetime import datetime, timedelta, timezone
import jwt
from sqlalchemy.orm import Session

from .. import models, audit
from ..auth import (
    hash_password,
    verify_password,
    create_access_token,
)
from ..database import get_db
from ..deps import (
    get_current_user,
    CurrentUser,
    auth_required,
)
from ..supabase_auth import (
    SUPABASE_URL,
    SUPABASE_PUBLISHABLE_KEY,
    enabled as supabase_auth_enabled,
    verify_access_token,
    sync_organization_claim,
    update_authenticated_password,
)

router = APIRouter(
    prefix="/api/auth",
    tags=["auth"],
)


class RegisterIn(BaseModel):
    organization_name: str
    username: str
    email: EmailStr
    password: str
    full_name: str | None = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class WorkerLoginIn(BaseModel):
    username: str


class PasswordChangeIn(BaseModel):
    new_password: str

class SupabaseSyncIn(BaseModel):
    organization_name: str | None = None
    username: str | None = None
    full_name: str | None = None
    registration_mode: bool = False


class AuthOut(BaseModel):
    access_token: str
    user_id: int
    username: str
    organization_id: int
    organization_name: str
    role: str


@router.get("/status")
def auth_status():
    return {
        "auth_required": auth_required(),
    }


@router.get("/public-config")
def public_auth_config():
    """Return only browser-safe Supabase configuration.

    This is intentionally limited to the Supabase project URL and publishable
    key. The server-only secret key is never exposed to the frontend.
    Desktop builds use this endpoint when Vite build-time variables are not
    available inside the packaged Electron application.
    """
    if not supabase_auth_enabled():
        raise HTTPException(status_code=503, detail="Supabase Auth is not configured on the backend")
    return {
        "supabase_url": SUPABASE_URL,
        "supabase_publishable_key": SUPABASE_PUBLISHABLE_KEY,
    }


@router.post(
    "/register",
    response_model=AuthOut,
)
def register(
    payload: RegisterIn,
    db: Session = Depends(get_db),
):
    if (
        db.query(models.User)
        .filter_by(email=payload.email)
        .first()
    ):
        raise HTTPException(
            status_code=400,
            detail="an account with that email already exists",
        )

    if (
        db.query(models.User)
        .filter_by(username=payload.username)
        .first()
    ):
        raise HTTPException(
            status_code=400,
            detail="that username is taken",
        )

    organization = models.Organization(
        name=payload.organization_name,
    )

    db.add(organization)
    db.commit()
    db.refresh(organization)

    user = models.User(
        username=payload.username,
        full_name=payload.full_name,
        email=payload.email,
        password_hash=hash_password(
            payload.password,
        ),
        organization_id=organization.id,
        role=models.UserRole.admin,
        active=True,
    )

    db.add(user)
    db.flush()
    db.add(models.UserApplicationAccess(
        user_id=user.id,
        application="engineering",
        enabled=True,
    ))
    db.commit()
    db.refresh(user)

    audit.log_event(
        db,
        "organization",
        organization.id,
        "created",
        f"Organization '{organization.name}' "
        f"registered by {user.username}",
    )

    token = create_access_token(
        user.id,
        organization.id,
    )

    return AuthOut(
        access_token=token,
        user_id=user.id,
        username=user.username,
        organization_id=organization.id,
        organization_name=organization.name,
        role=user.role.value,
    )


@router.post(
    "/login",
    response_model=AuthOut,
)
def login(
    payload: LoginIn,
    db: Session = Depends(get_db),
):
    user = (
        db.query(models.User)
        .filter_by(email=payload.email)
        .first()
    )

    if (
        not user
        or not user.active
        or not user.password_hash
        or not verify_password(
            payload.password,
            user.password_hash,
        )
    ):
        raise HTTPException(
            status_code=401,
            detail="incorrect email, password, or inactive account",
        )

    organization = db.get(
        models.Organization,
        user.organization_id,
    )

    if not organization:
        raise HTTPException(
            status_code=401,
            detail="account organization not found",
        )

    token = create_access_token(
        user.id,
        user.organization_id,
    )

    return AuthOut(
        access_token=token,
        user_id=user.id,
        username=user.username,
        organization_id=user.organization_id,
        organization_name=organization.name,
        role=user.role.value,
    )


@router.post(
    "/worker-login",
    response_model=AuthOut,
)
def worker_login(
    payload: WorkerLoginIn,
    db: Session = Depends(get_db),
):
    if auth_required() or supabase_auth_enabled():
        raise HTTPException(
            status_code=410,
            detail="Worker username login is disabled when authenticated identity login is enabled",
        )

    username = payload.username.strip()

    if not username:
        raise HTTPException(
            status_code=400,
            detail="username is required",
        )

    user = (
        db.query(models.User)
        .filter(
            models.User.username == username,
        )
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="invalid worker username",
        )

    if not user.active:
        raise HTTPException(
            status_code=401,
            detail="worker account is inactive",
        )

    if user.role != models.UserRole.technician:
        raise HTTPException(
            status_code=403,
            detail="this account is not a worker account",
        )

    organization = db.get(
        models.Organization,
        user.organization_id,
    )

    if not organization:
        raise HTTPException(
            status_code=401,
            detail="worker organization not found",
        )

    token = create_access_token(
        user.id,
        user.organization_id,
    )

    return AuthOut(
        access_token=token,
        user_id=user.id,
        username=user.username,
        organization_id=user.organization_id,
        organization_name=organization.name,
        role=user.role.value,
    )


@router.post("/supabase/sync")
def sync_supabase_user(
    payload: SupabaseSyncIn,
    authorization: str | None = Header(default=None),
    x_maintain_application: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    if not supabase_auth_enabled():
        raise HTTPException(status_code=503, detail="Supabase Auth is not configured on the backend")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Supabase access token required")

    token = authorization.removeprefix("Bearer ").strip()
    claims = verify_access_token(token)
    if not claims or not claims.get("sub"):
        raise HTTPException(status_code=401, detail="Supabase access token is invalid or expired")

    application = (x_maintain_application or "engineering").strip().lower()
    if application not in {"engineering", "android", "workforce"}:
        raise HTTPException(status_code=400, detail="invalid application context")

    try:
        sid = str(claims["sub"])
        email = claims.get("email")
        user = db.query(models.User).filter_by(supabase_user_id=sid).first()
        if not user and email:
            user = db.query(models.User).filter_by(email=email).first()

        if user and payload.registration_mode:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"This Google/Apple account already belongs to the "
                    f"'{db.get(models.Organization, user.organization_id).name if user.organization_id else 'existing'}' "
                    "organization. Sign in instead, or use a different identity to create a new organization."
                ),
            )

        if not user and (not payload.organization_name or not payload.username):
            return {
                "needs_onboarding": True,
                "email": email,
                "full_name": payload.full_name or claims.get("user_metadata", {}).get("full_name"),
            }

        if not user:
            base = (payload.username or (email.split("@")[0] if email else "user")).strip() or "user"
            username = base
            suffix = 2
            while db.query(models.User).filter_by(username=username).first():
                username = f"{base}{suffix}"
                suffix += 1

            organization = models.Organization(
                name=(payload.organization_name or "My Organization").strip()
            )
            db.add(organization)
            db.flush()

            user = models.User(
                username=username,
                full_name=payload.full_name,
                email=email,
                supabase_user_id=sid,
                organization_id=organization.id,
                role=models.UserRole.admin,
                active=True,
            )
            db.add(user)
            db.flush()
            db.add(models.UserApplicationAccess(
                user_id=user.id,
                application=application,
                enabled=True,
            ))
            db.commit()
        else:
            user.supabase_user_id = sid
            if payload.full_name:
                user.full_name = payload.full_name
            db.commit()

        organization = db.get(models.Organization, user.organization_id)
        if not organization:
            raise HTTPException(status_code=500, detail="Your account is not linked to an organization")

        requested_access = db.query(models.UserApplicationAccess).filter(
            models.UserApplicationAccess.user_id == user.id,
            models.UserApplicationAccess.application == application,
        ).first()
        if not requested_access or not requested_access.enabled:
            raise HTTPException(
                status_code=403,
                detail=f"account is not enabled for the {application} application",
            )

        try:
            sync_organization_claim(sid, user.organization_id)
        except Exception:
            pass

        return {
            "user_id": user.id,
            "username": user.username,
            "organization_id": user.organization_id,
            "organization_name": organization.name,
            "role": user.role.value,
        }
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail=f"Account synchronization could not be completed: {type(exc).__name__}",
        ) from exc

@router.post("/password-change")
def password_change(
    payload: PasswordChangeIn,
    authorization: str | None = Header(default=None),
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Supabase access token required")
    new_password = payload.new_password
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="password must be at least 8 characters")
    if len(new_password) > 128:
        raise HTTPException(status_code=400, detail="password is too long")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        update_authenticated_password(token, new_password)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    user = db.get(models.User, current.id) if current.id is not None else None
    if not user:
        raise HTTPException(status_code=401, detail="user account not found")
    user.password_change_required = False
    db.commit()
    return {"success": True, "password_change_required": False}


@router.post("/realtime-token")
def realtime_token(
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_maintain_application: str | None = Header(default=None),
):
    secret = os.getenv("SUPABASE_JWT_SECRET", "").strip()
    if not secret:
        raise HTTPException(status_code=503, detail="Supabase Realtime signing is not configured")

    user = db.get(models.User, current.id) if current.id is not None else None
    if not user or not user.active or not user.supabase_user_id:
        raise HTTPException(status_code=401, detail="Supabase identity is not linked to this account")

    application = (x_maintain_application or "engineering").strip().lower()
    if application not in {"engineering", "android", "workforce"}:
        raise HTTPException(status_code=400, detail="invalid application context")
    visible_machine_query = db.query(models.Machine.id).filter(
        models.Machine.organization_id == current.organization_id,
        models.Machine.archived.is_(False),
    )
    if current.role == models.UserRole.technician.value:
        visible_machine_query = visible_machine_query.join(
            models.UserMachineAssignment,
            models.UserMachineAssignment.machine_id == models.Machine.id,
        ).filter(models.UserMachineAssignment.user_id == current.id)
    machine_ids = [row[0] for row in visible_machine_query.all()]

    payload = {
        "sub": str(user.supabase_user_id),
        "role": "authenticated",
        "aud": "authenticated",
        "org_id": str(current.organization_id),
        "maintain_user_id": str(current.id),
        "maintain_application": application,
        "machine_ids": [str(machine_id) for machine_id in machine_ids],
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=55),
    }
    return {"access_token": jwt.encode(payload, secret, algorithm="HS256"), "expires_in": 3300}

@router.get("/me")
def me(
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    organization = db.get(
        models.Organization,
        current.organization_id,
    )

    user = db.get(models.User, current.id) if current.id is not None else None
    return {
        "user_id": current.id,
        "username": current.username,
        "role": current.role,
        "organization_id": current.organization_id,
        "password_change_required": bool(user.password_change_required) if user else False,
        "organization_name": (
            organization.name
            if organization
            else None
        ),
    }