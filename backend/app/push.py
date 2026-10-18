from __future__ import annotations
import os
from typing import Iterable
from sqlalchemy.orm import Session
from .config import settings
from .models import Device, FamilyMember, NotificationLog

_firebase_ready = False
_firebase_error: str | None = None


def initialize_firebase() -> tuple[bool, str | None]:
    global _firebase_ready, _firebase_error
    if _firebase_ready:
        return True, None
    if not settings.firebase_enabled:
        _firebase_error = "Firebase desativado por configuração"
        return False, _firebase_error
    try:
        import firebase_admin
        from firebase_admin import credentials

        if not firebase_admin._apps:
            if settings.firebase_credentials_path:
                cred = credentials.Certificate(settings.firebase_credentials_path)
                firebase_admin.initialize_app(cred, {"projectId": settings.firebase_project_id} if settings.firebase_project_id else None)
            else:
                # Application Default Credentials / GOOGLE_APPLICATION_CREDENTIALS
                firebase_admin.initialize_app(options={"projectId": settings.firebase_project_id} if settings.firebase_project_id else None)
        _firebase_ready = True
        _firebase_error = None
        return True, None
    except Exception as exc:
        _firebase_error = f"{type(exc).__name__}: {exc}"
        return False, _firebase_error


def status() -> dict:
    ok, err = initialize_firebase()
    return {"enabled": settings.firebase_enabled, "ready": ok, "error": err}


def _guardian_devices(db: Session, family_id: str) -> list[Device]:
    guardians = db.query(FamilyMember).filter_by(family_id=family_id, role="guardian").all()
    ids = [m.id for m in guardians]
    if not ids:
        return []
    return (
        db.query(Device)
        .filter(Device.family_member_id.in_(ids), Device.active.is_(True), Device.push_token.is_not(None))
        .all()
    )


def send_to_devices(
    db: Session,
    devices: Iterable[Device],
    *,
    family_id: str | None,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> int:
    devices = [d for d in devices if d.push_token]
    if not devices:
        return 0
    ok, err = initialize_firebase()
    if not ok:
        for d in devices:
            db.add(NotificationLog(family_id=family_id, device_id=d.id, status="skipped", detail=err))
        return 0

    from firebase_admin import messaging

    sent = 0
    payload = {str(k): str(v) for k, v in (data or {}).items()}
    for d in devices:
        try:
            message = messaging.Message(
                notification=messaging.Notification(title="JR Family • SOS" if payload.get("kind") == "sos" else "JR Family", body="Há uma atualização para sua família. Abra o aplicativo."),
                data=payload,
                token=d.push_token,
                android=messaging.AndroidConfig(priority="high"),
                apns=messaging.APNSConfig(
                    headers={"apns-priority": "10"},
                    payload=messaging.APNSPayload(aps=messaging.Aps(sound="default")),
                ),
            )
            message_id = messaging.send(message)
            db.add(NotificationLog(family_id=family_id, device_id=d.id, status="sent", detail=message_id))
            sent += 1
        except Exception as exc:
            db.add(NotificationLog(family_id=family_id, device_id=d.id, status="error", detail=type(exc).__name__))
    return sent


def notify_guardians(
    db: Session,
    family_id: str,
    *,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> int:
    return send_to_devices(db, _guardian_devices(db, family_id), family_id=family_id, title=title, body=body, data=data)
