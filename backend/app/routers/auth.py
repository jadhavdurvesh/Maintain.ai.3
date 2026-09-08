from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from .. import models, audit
from ..auth import hash_password, verify_password, create_access_token
from ..database import get_db
from ..deps import get_current_user, CurrentUser, auth_required

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterIn(BaseModel):
    organization_name: str
    username: str
    email: EmailStr
    password: str
    full_name: str | None = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class AuthOut(BaseModel):
    access_token: str
    user_id: int
    username: str
    organization_id: int
    organization_name: str
    role: str


@router.get("/status")
def auth_status():
    """Lets the frontend decide whether to show a login screen at all —
    in local/desktop mode (the default) this is always false."""
    return {"auth_required": auth_required()}


@router.post("/register", response_model=AuthOut)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    if db.query(models.User).filter_by(email=payload.email).first():
        raise HTTPException(400, "an account with that email already exists")
    if db.query(models.User).filter_by(username=payload.username).first():
        raise HTTPException(400, "that username is taken")

    org = models.Organization(name=payload.organization_name)
    db.add(org)
    db.commit()
    db.refresh(org)

    user = models.User(
        username=payload.username,
        full_name=payload.full_name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        organization_id=org.id,
        role=models.UserRole.admin,  # whoever registers the org is its first admin
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    audit.log_event(db, "organization", org.id, "created", f"Organization '{org.name}' registered by {user.username}")

    token = create_access_token(user.id, org.id)
    return AuthOut(
        access_token=token, user_id=user.id, username=user.username,
        organization_id=org.id, organization_name=org.name, role=user.role.value,
    )


@router.post("/login", response_model=AuthOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.query(models.User).filter_by(email=payload.email).first()
    if not user or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "incorrect email or password")

    org = db.get(models.Organization, user.organization_id)
    token = create_access_token(user.id, user.organization_id)
    return AuthOut(
        access_token=token, user_id=user.id, username=user.username,
        organization_id=org.id, organization_name=org.name, role=user.role.value,
    )


@router.get("/me")
def me(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = db.get(models.Organization, current.organization_id)
    return {
        "user_id": current.id,
        "username": current.username,
        "role": current.role,
        "organization_id": current.organization_id,
        "organization_name": org.name if org else None,
    }
