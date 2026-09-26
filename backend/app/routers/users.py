from typing import List
import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user, CurrentUser
from ..supabase_auth import (
    enabled as supabase_enabled,
    create_user_with_password,
    delete_user,
    invite_user_by_email,
    sync_organization_claim,
)

router = APIRouter(
    prefix="/api/users",
    tags=["users"],
)


class InvitationIn(BaseModel):
    email: str
    role: str = "technician"
    application: str = "workforce"
    username: str | None = None
    full_name: str | None = None


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


APPLICATIONS = {"engineering", "android", "workforce"}


def _applications(db: Session, user_id: int) -> list[str]:
    rows = db.query(models.UserApplicationAccess).filter(
        models.UserApplicationAccess.user_id == user_id,
        models.UserApplicationAccess.enabled.is_(True),
    ).all()
    return [row.application for row in rows]


@router.post("/accounts")
def create_account(
    payload: InvitationIn,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a real Supabase Auth account without sending an email."""
    require_admin(current)
    if not supabase_enabled():
        raise HTTPException(503, "Supabase Auth is not configured")

    email = payload.email.strip().lower()
    username = (payload.username or email.split("@")[0]).strip()[:40]
    full_name = (payload.full_name or "").strip() or None

    if not email or "@" not in email:
        raise HTTPException(400, "valid email is required")
    if not username:
        raise HTTPException(400, "username is required")
    if payload.role not in {"admin", "technician", "viewer"}:
        raise HTTPException(400, "invalid role")
    if payload.application not in APPLICATIONS:
        raise HTTPException(400, "invalid application")

    existing_email = db.query(models.User).filter(models.User.email == email).first()
    if existing_email:
        raise HTTPException(409, "an account with this email already exists")

    existing_username = db.query(models.User).filter(models.User.username == username).first()
    if existing_username:
        raise HTTPException(409, "that username is already taken")

    temporary_password = secrets.token_urlsafe(12)

    try:
        created = create_user_with_password(
            email=email,
            password=temporary_password,
            user_metadata={
                "full_name": full_name,
                "username": username,
                "organization_id": str(current.organization_id),
                "application": payload.application,
            },
            app_metadata={"organization_id": str(current.organization_id)},
        )
    except RuntimeError as exc:
        raise HTTPException(502, str(exc))

    supabase_id = str(created.get("id") or "")
    if not supabase_id:
        raise HTTPException(502, "Supabase created the account but did not return its user id")

    try:
        user = models.User(
            username=username,
            email=email,
            supabase_user_id=supabase_id,
            organization_id=current.organization_id,
            role=models.UserRole(payload.role),
            full_name=full_name,
            active=True,
            password_change_required=True,
        )
        db.add(user)
        db.flush()
        db.add(models.UserApplicationAccess(
            user_id=user.id,
            application=payload.application,
            enabled=True,
        ))
        db.commit()
        db.refresh(user)
    except Exception as exc:
        db.rollback()
        delete_user(supabase_id)
        raise HTTPException(503, f"Maintain.ai could not finish creating the account: {type(exc).__name__}") from exc

    sync_organization_claim(supabase_id, current.organization_id)

    return {
        "user_id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role.value,
        "organization_id": user.organization_id,
        "application": payload.application,
        "temporary_password": temporary_password,
        "password_change_required": True,
    }


@router.post("/invitations", response_model=schemas.OrganizationInvitationOut)
def invite_member(
    payload: InvitationIn,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current)
    if not supabase_enabled():
        raise HTTPException(503, "Supabase Auth is not configured")
    email = payload.email.strip().lower()
    if payload.role not in {"admin", "technician", "viewer"}:
        raise HTTPException(400, "invalid role")
    if payload.application not in APPLICATIONS:
        raise HTTPException(400, "invalid application")

    existing_local = db.query(models.User).filter(models.User.email == email).first()
    if existing_local and existing_local.organization_id != current.organization_id:
        raise HTTPException(409, "that email belongs to another organization")
    pending = db.query(models.OrganizationInvitation).filter(
        models.OrganizationInvitation.organization_id == current.organization_id,
        models.OrganizationInvitation.email == email,
        models.OrganizationInvitation.status == "pending",
    ).first()
    if pending:
        raise HTTPException(409, "an invitation is already pending for this email")

    username_base = (payload.username or email.split("@")[0])[:40].strip() or "user"
    username = username_base
    suffix = 2
    while db.query(models.User).filter(models.User.username == username).first():
        username = f"{username_base}{suffix}"
        suffix += 1

    try:
        invited = invite_user_by_email(
            email,
            redirect_to=None,
            metadata={"organization_id": str(current.organization_id), "application": payload.application, "username": username, "full_name": (payload.full_name or "").strip()},
        )
    except RuntimeError as exc:
        raise HTTPException(502, str(exc))

    supabase_id = str(invited.get("id") or "")

    if existing_local:
        user = existing_local
        user.supabase_user_id = supabase_id or user.supabase_user_id
        user.role = models.UserRole(payload.role)
        user.active = True
    else:
        user = models.User(
            username=username,
            email=email,
            supabase_user_id=supabase_id or None,
            organization_id=current.organization_id,
            role=models.UserRole(payload.role),
            full_name=(payload.full_name or "").strip() or None,
            active=True,
        )
        db.add(user)
        db.flush()

    access = db.query(models.UserApplicationAccess).filter(
        models.UserApplicationAccess.user_id == user.id,
        models.UserApplicationAccess.application == payload.application,
    ).first()
    if not access:
        db.add(models.UserApplicationAccess(user_id=user.id, application=payload.application, enabled=True))
    else:
        access.enabled = True

    invitation = models.OrganizationInvitation(
        organization_id=current.organization_id,
        email=email,
        role=models.UserRole(payload.role),
        application=payload.application,
        supabase_user_id=supabase_id or None,
        created_by=current.username,
        status="pending",
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    if supabase_id:
        sync_organization_claim(supabase_id, current.organization_id)
    return invitation


@router.get("/members", response_model=List[schemas.OrganizationMemberOut])
def list_members(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    require_admin(current)
    users = db.query(models.User).filter(
        models.User.organization_id == current.organization_id
    ).order_by(models.User.full_name.asc(), models.User.username.asc()).all()
    return [
        {"user_id": u.id, "username": u.username, "full_name": u.full_name,
         "email": u.email, "role": u.role.value, "applications": _applications(db, u.id)}
        for u in users
    ]


@router.post("/{user_id}/applications/{application}")
def set_application_access(
    user_id: int,
    application: str,
    enabled: bool = True,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current)
    if application not in APPLICATIONS:
        raise HTTPException(400, "invalid application")
    user = get_org_user(user_id, current, db)
    row = db.query(models.UserApplicationAccess).filter(
        models.UserApplicationAccess.user_id == user.id,
        models.UserApplicationAccess.application == application,
    ).first()
    if not row:
        row = models.UserApplicationAccess(user_id=user.id, application=application, enabled=enabled)
        db.add(row)
    else:
        row.enabled = enabled
    db.commit()
    return {"user_id": user.id, "application": application, "enabled": enabled}


@router.get(
    "",
    response_model=List[UserOut],
)
def list_users(
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(models.User).filter(
        models.User.organization_id == current.organization_id,
    )

    # User management remains administrator-only.  Non-admin clients may still
    # need the current user's basic identity for shared engineering screens,
    # but must never receive the organization's member directory.
    if current.role != "admin":
        if current.id is None:
            return []
        return query.filter(models.User.id == current.id).all()

    return query.order_by(
        models.User.full_name.asc(),
        models.User.username.asc(),
    ).all()


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
