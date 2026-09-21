from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import CurrentUser, get_current_user
from ..notification_service import firebase_diagnostics

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class DeviceRegistration(BaseModel):
    device_token: str
    platform: str = "android"
    app_version: str | None = None


@router.post("/register-device")
def register_device(
    payload: DeviceRegistration,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current.id:
        raise HTTPException(401, "authenticated worker required")
    token = payload.device_token.strip()
    if not token:
        raise HTTPException(400, "device_token is required")

    device = db.query(models.NotificationDevice).filter_by(device_token=token).first()
    if device is None:
        device = models.NotificationDevice(
            user_id=current.id,
            device_token=token,
            platform=payload.platform,
            app_version=payload.app_version,
            active=True,
        )
        db.add(device)
    else:
        device.user_id = current.id
        device.platform = payload.platform
        device.app_version = payload.app_version
        device.active = True
        device.last_seen_at = datetime.utcnow()
    db.commit()
    return {"registered": True, "device_id": device.id}


@router.delete("/device")
def unregister_device(
    device_token: str,
    current: CurrentUser = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    device = (
        db.query(models.NotificationDevice)
        .filter(
            models.NotificationDevice.device_token == device_token,
            models.NotificationDevice.user_id == current.id,
        )
        .first()
    )
    if device:
        device.active = False
        db.commit()
    return {"registered": False}


@router.get("")
def list_notifications(
    unread_only: bool = False,
    limit: int = 100,
    current: CurrentUser = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    limit = max(1, min(limit, 100))
    query = db.query(models.InAppNotification).filter(models.InAppNotification.user_id == current.id)
    if unread_only:
        query = query.filter(models.InAppNotification.read.is_(False))
    rows = query.order_by(models.InAppNotification.created_at.desc()).limit(limit).all()
    return [
        {
            "id": row.id,
            "notification_type": row.notification_type,
            "title": row.title,
            "body": row.body,
            "data": row.data_json,
            "read": row.read,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


@router.get("/diagnostics")
def notification_diagnostics(
    current: CurrentUser = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    if not current.id:
        raise HTTPException(401, "authenticated worker required")
    return firebase_diagnostics(db, current)


@router.post("/{notification_id}/read")
def mark_read(
    notification_id: int,
    current: CurrentUser = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(models.InAppNotification)
        .filter(
            models.InAppNotification.id == notification_id,
            models.InAppNotification.user_id == current.id,
        )
        .first()
    )
    if not row:
        raise HTTPException(404, "notification not found")
    row.read = True
    db.commit()
    return {"read": True}


@router.post("/read-all")
def mark_all_read(
    current: CurrentUser = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    count = (
        db.query(models.InAppNotification)
        .filter(
            models.InAppNotification.user_id == current.id,
            models.InAppNotification.read.is_(False),
        )
        .update({models.InAppNotification.read: True}, synchronize_session=False)
    )
    db.commit()
    return {"read": True, "updated": count}
