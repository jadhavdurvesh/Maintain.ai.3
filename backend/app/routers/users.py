from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user, CurrentUser

router = APIRouter(
    prefix="/api/users",
    tags=["users"],
)


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
        raise HTTPException(
            status_code=403,
            detail="administrator access required",
        )


def get_org_user(
    user_id: int,
    current: CurrentUser,
    db: Session,
) -> models.User:
    user = (
        db.query(models.User)
        .filter(
            models.User.id == user_id,
            models.User.organization_id == current.organization_id,
        )
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="user not found",
        )

    return user


def get_org_machine(
    machine_id: int,
    current: CurrentUser,
    db: Session,
) -> models.Machine:
    machine = (
        db.query(models.Machine)
        .filter(
            models.Machine.id == machine_id,
            models.Machine.organization_id == current.organization_id,
        )
        .first()
    )

    if not machine:
        raise HTTPException(
            status_code=404,
            detail="machine not found",
        )

    if machine.archived:
        raise HTTPException(
            status_code=400,
            detail="cannot assign an archived machine",
        )

    return machine


@router.get(
    "",
    response_model=List[UserOut],
)
def list_users(
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(models.User)
        .filter(
            models.User.organization_id == current.organization_id,
        )
        .order_by(
            models.User.full_name.asc(),
            models.User.username.asc(),
        )
        .all()
    )


@router.post(
    "",
    response_model=UserOut,
)
def create_user(
    payload: UserIn,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current)

    username = payload.username.strip()
    email = payload.email.strip() if payload.email else None

    if not username:
        raise HTTPException(
            status_code=400,
            detail="username is required",
        )

    if payload.role not in {
        "admin",
        "technician",
        "viewer",
    }:
        raise HTTPException(
            status_code=400,
            detail="invalid role",
        )

    if (
        db.query(models.User)
        .filter(models.User.username == username)
        .first()
    ):
        raise HTTPException(
            status_code=400,
            detail="username already exists",
        )

    if email and (
        db.query(models.User)
        .filter(models.User.email == email)
        .first()
    ):
        raise HTTPException(
            status_code=400,
            detail="email already exists",
        )

    user = models.User(
        username=username,
        full_name=(
            payload.full_name.strip()
            if payload.full_name
            else None
        ),
        email=email,
        role=models.UserRole(payload.role),
        organization_id=current.organization_id,
        active=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@router.patch(
    "/{user_id}",
    response_model=UserOut,
)
def update_user(
    user_id: int,
    payload: UserUpdate,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current)

    user = get_org_user(
        user_id,
        current,
        db,
    )

    changes = payload.model_dump(exclude_unset=True)

    if (
        user.id == current.id
        and changes.get("active") is False
    ):
        raise HTTPException(
            status_code=400,
            detail="you cannot deactivate your own administrator account",
        )

    if "role" in changes and changes["role"] is not None:
        if changes["role"] not in {
            "admin",
            "technician",
            "viewer",
        }:
            raise HTTPException(
                status_code=400,
                detail="invalid role",
            )

        changes["role"] = models.UserRole(changes["role"])

    if "email" in changes:
        changes["email"] = (
            changes["email"].strip()
            if changes["email"]
            else None
        )

        if changes["email"]:
            duplicate = (
                db.query(models.User)
                .filter(
                    models.User.email == changes["email"],
                    models.User.id != user.id,
                )
                .first()
            )

            if duplicate:
                raise HTTPException(
                    status_code=400,
                    detail="email already exists",
                )

    if "full_name" in changes:
        changes["full_name"] = (
            changes["full_name"].strip()
            if changes["full_name"]
            else None
        )

    for field, value in changes.items():
        setattr(user, field, value)

    # Remove machine access when the account is no longer an active technician.
    if (
        "role" in changes
        and changes["role"] != models.UserRole.technician
    ):
        db.query(models.UserMachineAssignment).filter(
            models.UserMachineAssignment.user_id == user.id
        ).delete(synchronize_session=False)

    if (
        "active" in changes
        and changes["active"] is False
    ):
        db.query(models.UserMachineAssignment).filter(
            models.UserMachineAssignment.user_id == user.id
        ).delete(synchronize_session=False)

    db.commit()
    db.refresh(user)

    return user


@router.get(
    "/{user_id}/machines",
    response_model=List[schemas.MachineOut],
)
def list_user_machines(
    user_id: int,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_org_user(
        user_id,
        current,
        db,
    )

    if (
        current.role != "admin"
        and current.id != user.id
    ):
        raise HTTPException(
            status_code=403,
            detail="you may only view your own machine assignments",
        )

    return (
        db.query(models.Machine)
        .join(
            models.UserMachineAssignment,
            models.UserMachineAssignment.machine_id
            == models.Machine.id,
        )
        .filter(
            models.UserMachineAssignment.user_id == user.id,
            models.Machine.organization_id
            == current.organization_id,
            models.Machine.archived.is_(False),
        )
        .order_by(models.Machine.name.asc())
        .all()
    )


@router.post(
    "/{user_id}/machines/{machine_id}",
)
def assign_machine(
    user_id: int,
    machine_id: int,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current)

    user = get_org_user(
        user_id,
        current,
        db,
    )

    machine = get_org_machine(
        machine_id,
        current,
        db,
    )

    if user.role != models.UserRole.technician:
        raise HTTPException(
            status_code=400,
            detail="only technician accounts can be assigned machines",
        )

    if not user.active:
        raise HTTPException(
            status_code=400,
            detail="cannot assign machines to an inactive user",
        )

    existing = (
        db.query(models.UserMachineAssignment)
        .filter(
            models.UserMachineAssignment.user_id == user.id,
            models.UserMachineAssignment.machine_id == machine.id,
        )
        .first()
    )

    if existing:
        return {
            "success": True,
            "already_assigned": True,
            "user_id": user.id,
            "username": user.username,
            "machine_id": machine.id,
            "machine_name": machine.name,
        }

    assignment = models.UserMachineAssignment(
        user_id=user.id,
        machine_id=machine.id,
    )

    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    return {
        "success": True,
        "already_assigned": False,
        "user_id": user.id,
        "username": user.username,
        "machine_id": machine.id,
        "machine_name": machine.name,
    }


@router.delete(
    "/{user_id}/machines/{machine_id}",
)
def unassign_machine(
    user_id: int,
    machine_id: int,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current)

    user = get_org_user(
        user_id,
        current,
        db,
    )

    get_org_machine(
        machine_id,
        current,
        db,
    )

    assignment = (
        db.query(models.UserMachineAssignment)
        .filter(
            models.UserMachineAssignment.user_id == user.id,
            models.UserMachineAssignment.machine_id == machine_id,
        )
        .first()
    )

    if not assignment:
        raise HTTPException(
            status_code=404,
            detail="machine is not assigned to this user",
        )

    db.delete(assignment)
    db.commit()

    return {
        "success": True,
        "user_id": user.id,
        "username": user.username,
        "machine_id": machine_id,
        "removed": True,
    }