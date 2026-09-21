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
from ..supabase_auth import enabled as supabase_auth_enabled, verify_access_token, sync_organization_claim

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


class SupabaseSyncIn(BaseModel):
    organization_name: str | None = None
    username: str | None = None
    full_name: str | None = None
    # True when the OAuth button was clicked from "New organization".
    # This survives the provider redirect and prevents an existing account
    # from being silently treated as a normal sign-in.
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

        # OAuth is intentionally identity-driven rather than button-driven:
        # an existing identity signs in, while a new identity is sent to the
        # organization/username onboarding step. This keeps Google/Apple
        # behavior identical from either auth tab.
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

        # Organization claim refresh is deliberately non-fatal. The Neon
        # organization remains the application authorization source.
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

@router.post("/realtime-token")
def realtime_token(
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_maintain_application: str | None = Header(default=None),
):
    """Issue a short-lived Supabase Realtime JWT carrying the Neon tenant context."""
    secret = os.getenv("SUPABASE_JWT_SECRET", "").strip()
    if not secret:
        raise HTTPException(status_code=503, detail="Supabase Realtime signing is not configured")

    user = db.get(models.User, current.id) if current.id is not None else None
    if not user or not user.active or not user.supabase_user_id:
        raise HTTPException(status_code=401, detail="Supabase identity is not linked to this account")

    application = (x_maintain_application or "engineering").strip().lower()
    if application not in {"engineering", "android", "workforce"}:
        raise HTTPException(status_code=400, detail="invalid application context")
    # The token is intentionally short-lived and contains no secret application data.
    payload = {
        "sub": str(user.supabase_user_id),
        "role": "authenticated",
        "aud": "authenticated",
        "org_id": str(current.organization_id),
        "maintain_user_id": str(current.id),
        "maintain_application": application,
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

    return {
        "user_id": current.id,
        "username": current.username,
        "role": current.role,
        "organization_id": current.organization_id,
        "organization_name": (
            organization.name
            if organization
            else None
        ),
    }