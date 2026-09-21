"""Worker push + in-app notification service for MAINTAIN AI."""

import json
import os

from sqlalchemy.orm import Session

from . import models

_firebase_ready = False
_firebase_error: str | None = None


def _firebase_messaging():
    """Initialize Firebase Admin lazily and retry after transient failures."""
    global _firebase_ready, _firebase_error
    if _firebase_ready:
        try:
            from firebase_admin import messaging
            return messaging
        except Exception as exc:
            _firebase_ready = False
            _firebase_error = f"{type(exc).__name__}: {exc}"
            return None

    try:
        import firebase_admin
        from firebase_admin import credentials, messaging

        raw = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
        if not raw:
            _firebase_error = "FIREBASE_SERVICE_ACCOUNT_JSON is not configured"
            return None

        try:
            service_account = json.loads(raw)
        except json.JSONDecodeError as exc:
            _firebase_error = f"FIREBASE_SERVICE_ACCOUNT_JSON is invalid JSON: {exc.msg}"
            return None

        if not firebase_admin._apps:
            firebase_admin.initialize_app(credentials.Certificate(service_account))
        _firebase_ready = True
        _firebase_error = None
        return messaging
    except Exception as exc:
        # Do not permanently disable retries: Vercel instances can start while
        # environment configuration is still propagating.
        _firebase_ready = False
        _firebase_error = f"{type(exc).__name__}: {exc}"
        print(f"[notifications] Firebase Admin init failed: {_firebase_error}")
        return None


def _worker(db: Session, username: str | None):
    if not username:
        return None
    return (
        db.query(models.User)
        .filter(models.User.username == username, models.User.active.is_(True))
        .first()
    )


def _send_push(db: Session, user: models.User, title: str, body: str, data: dict):
    messaging = _firebase_messaging()
    if messaging is None:
        return

    devices = (
        db.query(models.NotificationDevice)
        .filter(
            models.NotificationDevice.user_id == user.id,
            models.NotificationDevice.active.is_(True),
        )
        .all()
    )
    if not devices:
        print(f"[notifications] No active FCM devices for user_id={user.id}")
        return

    messages = [
        messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data={k: str(v) for k, v in data.items()},
            token=device.device_token,
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    channel_id="maintain_ai_alerts",
                    sound="default",
                ),
            ),
        )
        for device in devices
    ]

    try:
        response = messaging.send_each(messages)
        print(
            f"[notifications] FCM delivery user_id={user.id} "
            f"success={response.success_count} failed={response.failure_count}"
        )
        changed = False
        for device, result in zip(devices, response.responses):
            if result.success:
                continue
            # Never log the complete token.
            print(
                f"[notifications] FCM device failure user_id={user.id} "
                f"token_suffix={device.device_token[-8:]} error={result.exception!r}"
            )
            error_text = str(result.exception).lower()
            if (
                "registration-token-not-registered" in error_text
                or "not a valid fcm registration token" in error_text
                or "unregistered" in error_text
            ):
                device.active = False
                changed = True
        if changed:
            db.commit()
    except Exception as exc:
        # Push delivery must never break the core API transaction.
        print(f"[notifications] FCM send failed: {type(exc).__name__}: {exc}")


def notify_worker(
    db: Session,
    username: str | None,
    notification_type: str,
    title: str,
    body: str,
    data: dict | None = None,
):
    """Persist a notification and best-effort deliver it through FCM."""
    user = _worker(db, username)
    if user is None:
        return None

    payload = data or {}
    notification = models.InAppNotification(
        user_id=user.id,
        notification_type=notification_type,
        title=title,
        body=body,
        data_json=json.dumps(payload, separators=(",", ":")),
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)

    _send_push(db, user, title, body, {"notification_id": notification.id, **payload})
    return notification


def notify_machine_workers(
    db: Session,
    machine_id: int,
    notification_type: str,
    title: str,
    body: str,
    data: dict | None = None,
):
    assignments = (
        db.query(models.UserMachineAssignment, models.User)
        .join(models.User, models.User.id == models.UserMachineAssignment.user_id)
        .join(models.Machine, models.Machine.id == models.UserMachineAssignment.machine_id)
        .filter(
            models.UserMachineAssignment.machine_id == machine_id,
            models.User.active.is_(True),
            models.User.role == models.UserRole.technician,
            models.User.organization_id == models.Machine.organization_id,
        )
        .all()
    )
    return [
        notify_worker(db, user.username, notification_type, title, body, data)
        for _, user in assignments
    ]


def notify_work_order_assigned(db: Session, work_order: models.WorkOrder, machine: models.Machine):
    if not work_order.assigned_to:
        return None
    priority = work_order.priority.value if hasattr(work_order.priority, "value") else str(work_order.priority)
    return notify_worker(
        db,
        work_order.assigned_to,
        "work_order_assigned",
        "New Work Order Assigned",
        f"{machine.name}: {work_order.problem}",
        {"route": "work_order", "work_order_id": work_order.id, "machine_id": machine.id, "priority": priority},
    )


def notify_fault(db: Session, fault: models.FaultRecord, machine: models.Machine):
    severity = fault.severity.value if hasattr(fault.severity, "value") else str(fault.severity)
    return notify_machine_workers(
        db,
        machine.id,
        "fault_reported",
        "Machine Fault Reported",
        f"{machine.name}: {fault.description}",
        {"route": "fault", "fault_id": fault.id, "machine_id": machine.id, "severity": severity},
    )


def notify_alert(db: Session, alert: models.Alert, machine: models.Machine):
    severity = alert.severity.value if hasattr(alert.severity, "value") else str(alert.severity)
    if severity not in {"high", "critical"}:
        return []
    notification_type = "critical_machine" if severity == "critical" else "machine_alert"
    return notify_machine_workers(
        db,
        machine.id,
        notification_type,
        "Critical Machine Alert" if severity == "critical" else "Machine Alert",
        alert.message,
        {"route": "machine_alert", "alert_id": alert.id, "machine_id": machine.id, "severity": severity},
    )


def firebase_diagnostics(db: Session, user: models.User) -> dict:
    devices = (
        db.query(models.NotificationDevice)
        .filter(models.NotificationDevice.user_id == user.id)
        .all()
    )
    _firebase_messaging()
    return {
        "firebase_configured": bool(os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()),
        "firebase_admin_ready": _firebase_ready,
        "firebase_error": _firebase_error,
        "registered_devices": len(devices),
        "active_devices": sum(1 for device in devices if device.active),
        "platforms": sorted({device.platform for device in devices}),
    }
