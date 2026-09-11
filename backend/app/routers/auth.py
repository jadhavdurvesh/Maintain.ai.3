from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
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