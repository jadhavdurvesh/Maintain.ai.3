from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import get_current_user, CurrentUser

router = APIRouter(prefix="/api/users", tags=["users"])


class UserIn(BaseModel):
    username: str
    full_name: str | None = None
    email: str | None = None
    role: str = "technician"


class UserUpdate(BaseModel):
    full_name: str | None = None
    email: str | None = None
    role: str | None = None
    active: bool | None = None


class UserOut(UserIn):
    id: int
    active: bool = True

    class Config:
        from_attributes = True


def require_admin(current: CurrentUser):
    if current.role != "admin":
        raise HTTPException(403, "administrator access required")


@router.get("", response_model=List[UserOut])
def list_users(
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(models.User)
        .filter(models.User.organization_id == current.organization_id)
        .order_by(models.User.full_name.asc(), models.User.username.asc())
        .all()
    )


@router.post("", response_model=UserOut)
def create_user(
    payload: UserIn,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current)
    if payload.role not in {"admin", "technician", "viewer"}:
        raise HTTPException(400, "invalid role")
    if db.query(models.User).filter(models.User.username == payload.username).first():
        raise HTTPException(400, "username already exists")
    if payload.email and db.query(models.User).filter(models.User.email == payload.email).first():
        raise HTTPException(400, "email already exists")

    user = models.User(
        username=payload.username.strip(),
        full_name=payload.full_name.strip() if payload.full_name else None,
        email=payload.email.strip() if payload.email else None,
        role=models.UserRole(payload.role),
        organization_id=current.organization_id,
        active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current)
    user = (
        db.query(models.User)
        .filter(models.User.id == user_id, models.User.organization_id == current.organization_id)
        .first()
    )
    if not user:
        raise HTTPException(404, "user not found")

    changes = payload.model_dump(exclude_unset=True)
    if "role" in changes and changes["role"] is not None:
        if changes["role"] not in {"admin", "technician", "viewer"}:
            raise HTTPException(400, "invalid role")
        changes["role"] = models.UserRole(changes["role"])
    if "email" in changes and changes["email"]:
        email = changes["email"].strip()
        duplicate = db.query(models.User).filter(models.User.email == email, models.User.id != user.id).first()
        if duplicate:
            raise HTTPException(400, "email already exists")
        changes["email"] = email
    if "full_name" in changes and changes["full_name"]:
        changes["full_name"] = changes["full_name"].strip()

    for field, value in changes.items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user
