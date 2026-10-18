from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from .config import settings
from .db import Base, engine, get_db
from .models import (
    Alert,
    AppVersion,
    AuditLog,
    Device,
    Emergency,
    Family,
    FamilyMember,
    Geofence,
    Invitation,
    Location,
    NotificationLog,
    User,
)
from .schemas import (
    AppVersionCreate,
    DeviceCreate,
    FamilyCreate,
    GeofenceCreate,
    InviteCreate,
    InviteJoin,
    LocationIn,
    LoginIn,
    PermissionUpdate,
    PushTokenUpdate,
    RegisterIn,
    SOSIn,
    TokenOut,
)
from .security import hash_password, verify_password, make_token
from .deps import admin_user, current_user, membership
from .services import audit, process_location_alerts
from .push import notify_guardians, status as push_status

from .sessions import issue, digest, throttle
from .models import AuthSession, now
from pydantic import BaseModel, Field
from sqlalchemy import update
import jwt

# Production schema is exclusively managed by Alembic.
if settings.environment != "production":
    Base.metadata.create_all(engine)
app = FastAPI(title="JR Family API", version="1.1.0")
origins = ["*"] if settings.cors_origins == "*" else [x.strip() for x in settings.cors_origins.split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def stamp(value):
    return value.replace(tzinfo=timezone.utc).isoformat() if value else None


def utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@app.get("/health")
def health():
    return {"ok": True, "service": "jr-family-api", "version": "1.1.0", "push": {"enabled": settings.firebase_enabled}}


@app.post("/auth/register", response_model=TokenOut)
def register(data: RegisterIn, request: Request, db: Session = Depends(get_db)):
    throttle(db, request, "register")
    email = data.email.lower()
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(409, "E-mail já cadastrado")
    user = User(name=data.name, email=email, password_hash=hash_password(data.password))
    db.add(user)
    db.flush()
    audit(db, user.id, "register", "user", user.id)
    db.commit()
    return issue(db, user)


@app.post("/auth/login", response_model=TokenOut)
def login(data: LoginIn, request: Request, db: Session = Depends(get_db)):
    throttle(db, request, "login")
    user = db.query(User).filter_by(email=data.email.lower()).first()
    if not user or user.is_blocked or not verify_password(data.password, user.password_hash):
        audit(db, None, "login_failed", "auth")
        db.commit()
        raise HTTPException(401, "Credenciais inválidas")
    audit(db, user.id, "login", "user", user.id)
    db.commit()
    return issue(db, user)


@app.get("/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    memberships = db.query(FamilyMember).filter_by(user_id=user.id).all()
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "is_admin": user.is_admin,
        "memberships": [
            {
                "family_id": m.family_id,
                "member_id": m.id,
                "role": m.role,
                "display_name": m.display_name,
                "sharing": m.location_sharing_enabled,
            }
            for m in memberships
        ],
    }


@app.post("/families")
def create_family(data: FamilyCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    family = Family(name=data.name, owner_user_id=user.id)
    db.add(family)
    db.flush()
    member = FamilyMember(
        family_id=family.id,
        user_id=user.id,
        role="guardian",
        display_name=user.name,
        location_sharing_enabled=False,
    )
    db.add(member)
    audit(db, user.id, "create", "family", family.id)
    db.commit()
    return {"id": family.id, "name": family.name, "member_id": member.id}


@app.get("/families/{family_id}")
def get_family(family_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    membership(db, user.id, family_id)
    members = db.query(FamilyMember).filter_by(family_id=family_id).all()
    output = []
    for member in members:
        devices = db.query(Device).filter_by(family_member_id=member.id, active=True).all()
        latest = None
        if devices and member.location_sharing_enabled:
            ids = [d.id for d in devices]
            latest = db.query(Location).filter(Location.device_id.in_(ids)).order_by(desc(Location.captured_at)).first()
        output.append(
            {
                "id": member.id,
                "display_name": member.display_name,
                "role": member.role,
                "sharing": member.location_sharing_enabled,
                "latest_location": None
                if not latest
                else {
                    "latitude": latest.latitude,
                    "longitude": latest.longitude,
                    "accuracy_m": latest.accuracy_m,
                    "speed_mps": latest.speed_mps,
                    "battery_percent": latest.battery_percent,
                    "captured_at": stamp(latest.captured_at),
                    "stale": latest.captured_at < utcnow_naive() - timedelta(minutes=15),
                },
            }
        )
    return {"id": family_id, "members": output}


@app.post("/families/{family_id}/invites")
def create_invite(family_id: str, data: InviteCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    membership(db, user.id, family_id, guardian_only=True)
    if data.role not in {"guardian", "dependent"}:
        raise HTTPException(400, "Papel inválido")
    code = secrets.token_hex(6).upper()
    digest = hashlib.sha256(code.encode()).hexdigest()
    invite = Invitation(
        family_id=family_id,
        code_hash=digest,
        role=data.role,
        expires_at=utcnow_naive() + timedelta(minutes=settings.invite_minutes),
        created_by=user.id,
    )
    db.add(invite)
    audit(db, user.id, "invite_create", "family", family_id)
    db.commit()
    return {"code": code, "expires_at": stamp(invite.expires_at)}


@app.post("/invites/join")
def join_invite(data: InviteJoin, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    throttle(db, request, "invite", 15)
    code = data.code.replace(" ", "").upper()
    digest = hashlib.sha256(code.encode()).hexdigest()
    invite = db.query(Invitation).filter_by(code_hash=digest, used_at=None).first()
    now = utcnow_naive()
    if not invite or invite.expires_at < now:
        raise HTTPException(400, "Convite inválido ou expirado")
    if db.query(FamilyMember).filter_by(family_id=invite.family_id, user_id=user.id).first():
        raise HTTPException(409, "Usuário já pertence à família")
    claimed = db.execute(update(Invitation).where(Invitation.id == invite.id, Invitation.used_at.is_(None)).values(used_at=now)).rowcount
    if claimed != 1:
        db.rollback()
        raise HTTPException(409, "Convite já utilizado")
    member = FamilyMember(
        family_id=invite.family_id,
        user_id=user.id,
        role=invite.role,
        display_name=data.display_name,
        location_sharing_enabled=False,
    )
    db.add(member)
    invite.used_at = now
    audit(db, user.id, "invite_join", "family", invite.family_id)
    db.commit()
    return {"family_id": invite.family_id, "member_id": member.id, "role": member.role}


@app.post("/families/{family_id}/devices")
def add_device(family_id: str, data: DeviceCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    mine = membership(db, user.id, family_id)
    target = db.get(FamilyMember, data.member_id)
    if not target or target.family_id != family_id:
        raise HTTPException(404, "Membro não encontrado")
    if target.user_id != user.id:
        raise HTTPException(403, "Sem permissão")
    # Um dependente só pode criar dispositivo para si; o responsável pode auxiliar no pareamento.
    device = Device(
        family_member_id=target.id,
        platform=data.platform,
        device_name=data.device_name,
        push_token=data.push_token,
        push_updated_at=utcnow_naive() if data.push_token else None,
        app_version=data.app_version,
        os_version=data.os_version,
    )
    db.add(device)
    db.flush()
    audit(db, user.id, "device_add", "device", device.id)
    db.commit()
    notify_guardians(db, family_id, title="Novo dispositivo vinculado", body="Um membro vinculou um aparelho. Abra o JR Family para conferir.", data={"kind":"device_added", "family_id":family_id})
    db.commit()
    return {"id": device.id}


@app.patch("/devices/{device_id}/push-token")
def update_push_token(device_id: str, data: PushTokenUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(404, "Dispositivo não encontrado")
    member = db.get(FamilyMember, device.family_member_id)
    if not member or member.user_id != user.id:
        raise HTTPException(403, "Este dispositivo não pertence ao usuário autenticado")
    device.push_token = data.push_token
    device.push_updated_at = utcnow_naive()
    if data.app_version is not None:
        device.app_version = data.app_version
    if data.os_version is not None:
        device.os_version = data.os_version
    device.last_seen_at = utcnow_naive()
    audit(db, user.id, "push_token_update", "device", device.id)
    db.commit()
    return {"ok": True}


@app.patch("/families/{family_id}/devices/{device_id}/permissions")
def update_permissions(
    family_id: str,
    device_id: str,
    data: PermissionUpdate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(404, "Dispositivo não encontrado")
    member = db.get(FamilyMember, device.family_member_id)
    if not member or member.family_id != family_id or member.user_id != user.id:
        raise HTTPException(403, "Somente o dono deste dispositivo pode alterar o compartilhamento")
    changed = (device.permission_location, device.permission_background, member.location_sharing_enabled) != (data.location, data.background, data.sharing_enabled)
    if data.sharing_enabled and data.location != "authorized":
        raise HTTPException(422, "Compartilhamento exige autorização de localização")
    device.permission_location = data.location
    device.permission_background = data.background
    member.location_sharing_enabled = data.sharing_enabled
    device.last_seen_at = utcnow_naive()
    audit(db, user.id, "permissions_update", "device", device.id)
    db.commit()
    if changed:
        notify_guardians(db, family_id, title="Compartilhamento atualizado", body="As permissões de um dispositivo foram alteradas.", data={"kind":"permissions_changed", "family_id":family_id})
        db.commit()
    return {"ok": True, "sharing": member.location_sharing_enabled}


@app.post("/devices/{device_id}/locations")
def upload_location(device_id: str, data: LocationIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    device = db.get(Device, device_id)
    if not device or not device.active:
        raise HTTPException(404, "Dispositivo não encontrado")
    member = db.get(FamilyMember, device.family_member_id)
    if not member or member.user_id != user.id:
        raise HTTPException(403, "Este dispositivo não pertence ao usuário autenticado")
    if not member.location_sharing_enabled:
        raise HTTPException(409, "Compartilhamento de localização está desativado")
    captured = data.captured_at or utcnow_naive()
    if captured.tzinfo:
        captured = captured.astimezone(timezone.utc).replace(tzinfo=None)
    if captured > utcnow_naive() + timedelta(minutes=5) or captured < utcnow_naive() - timedelta(days=settings.history_retention_days):
        raise HTTPException(422, "Horário fora do período permitido")
    previous = db.query(Location).filter_by(device_id=device.id).order_by(desc(Location.captured_at)).first()
    location = Location(
        device_id=device.id,
        latitude=data.latitude,
        longitude=data.longitude,
        accuracy_m=data.accuracy_m,
        speed_mps=data.speed_mps,
        battery_percent=data.battery_percent,
        source_mode=data.source_mode,
        captured_at=captured,
    )
    device.last_seen_at = utcnow_naive()
    restored = device.offline_notified
    device.offline_notified = False
    device.battery_percent = data.battery_percent
    db.add(location)
    db.flush()
    alerts = process_location_alerts(db, device, location) if (not previous or captured > previous.captured_at) and captured > utcnow_naive() - timedelta(minutes=15) else []
    db.commit()
    if restored:
        notify_guardians(db, member.family_id, title="Localização disponível", body="Um dispositivo voltou a enviar dados.", data={"kind":"location_available", "family_id":member.family_id})
    # Push falhar não invalida a gravação da localização.
    for alert in alerts:
        notify_guardians(
            db,
            member.family_id,
            title=alert.title,
            body=alert.message,
            data={"kind": alert.kind, "family_id": member.family_id, "member_id": member.id},
        )
    db.commit()
    return {"ok": True, "location_id": location.id, "alerts": len(alerts)}


@app.get("/families/{family_id}/members/{member_id}/location/latest")
def latest_location(family_id: str, member_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    membership(db, user.id, family_id)
    member = db.get(FamilyMember, member_id)
    if not member or member.family_id != family_id:
        raise HTTPException(404, "Membro não encontrado")
    ids = [d.id for d in db.query(Device).filter_by(family_member_id=member_id, active=True).all()]
    if not ids:
        return {"location": None}
    loc = db.query(Location).filter(Location.device_id.in_(ids)).order_by(desc(Location.captured_at)).first()
    return {
        "location": None
        if not loc
        else {
            "latitude": loc.latitude,
            "longitude": loc.longitude,
            "accuracy_m": loc.accuracy_m,
            "speed_mps": loc.speed_mps,
            "battery_percent": loc.battery_percent,
            "source_mode": loc.source_mode,
            "captured_at": stamp(loc.captured_at),
            "stale": loc.captured_at < utcnow_naive() - timedelta(minutes=15),
        }
    }


@app.get("/families/{family_id}/members/{member_id}/locations")
def history(
    family_id: str,
    member_id: str,
    hours: int = Query(24, ge=1, le=24 * 30),
    start: datetime | None = None,
    end: datetime | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    membership(db, user.id, family_id)
    member = db.get(FamilyMember, member_id)
    if not member or member.family_id != family_id:
        raise HTTPException(404, "Membro não encontrado")
    ids = [d.id for d in db.query(Device).filter_by(family_member_id=member_id, active=True).all()]
    def utc(value):
        return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value
    cutoff = utc(start) if start else utcnow_naive() - timedelta(hours=hours)
    finish = utc(end) if end else utcnow_naive()
    if cutoff > finish or finish - cutoff > timedelta(days=30):
        raise HTTPException(422, "Período inválido: máximo 30 dias")
    cutoff = max(cutoff, utcnow_naive() - timedelta(days=settings.history_retention_days))
    rows = [] if not ids else (
        db.query(Location)
        .filter(Location.device_id.in_(ids), Location.captured_at >= cutoff, Location.captured_at <= finish)
        .order_by(Location.captured_at.asc())
        .limit(5000)
        .all()
    )
    return {
        "items": [
            {
                "latitude": item.latitude,
                "longitude": item.longitude,
                "accuracy_m": item.accuracy_m,
                "speed_mps": item.speed_mps,
                "battery_percent": item.battery_percent,
                "source_mode": item.source_mode,
                "captured_at": stamp(item.captured_at),
            }
            for item in rows
        ]
    }


@app.post("/families/{family_id}/geofences")
def add_geofence(family_id: str, data: GeofenceCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    membership(db, user.id, family_id, guardian_only=True)
    geofence = Geofence(family_id=family_id, **data.model_dump())
    db.add(geofence)
    db.flush()
    audit(db, user.id, "create", "geofence", geofence.id)
    db.commit()
    return {"id": geofence.id}


@app.get("/families/{family_id}/geofences")
def list_geofences(family_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    membership(db, user.id, family_id)
    return {
        "items": [
            {
                "id": g.id,
                "name": g.name,
                "latitude": g.latitude,
                "longitude": g.longitude,
                "radius_m": g.radius_m,
                "enabled": g.enabled,
            }
            for g in db.query(Geofence).filter_by(family_id=family_id).all()
        ]
    }


@app.get("/families/{family_id}/alerts")
def list_alerts(family_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    membership(db, user.id, family_id)
    rows = db.query(Alert).filter_by(family_id=family_id).order_by(desc(Alert.created_at)).limit(200).all()
    return {
        "items": [
            {
                "id": alert.id,
                "kind": alert.kind,
                "title": alert.title,
                "message": alert.message,
                "created_at": stamp(alert.created_at),
                "read_at": stamp(alert.read_at),
            }
            for alert in rows
        ]
    }


@app.patch("/families/{family_id}/alerts/{alert_id}/read")
def mark_alert_read(family_id: str, alert_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    membership(db, user.id, family_id)
    alert = db.get(Alert, alert_id)
    if not alert or alert.family_id != family_id:
        raise HTTPException(404, "Alerta não encontrado")
    alert.read_at = utcnow_naive()
    db.commit()
    return {"ok": True}


@app.post("/families/{family_id}/members/{member_id}/sos")
def sos(family_id: str, member_id: str, data: SOSIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    member = db.get(FamilyMember, member_id)
    if not member or member.family_id != family_id or member.user_id != user.id:
        raise HTTPException(403, "SOS só pode ser acionado pelo próprio membro")
    emergency = Emergency(
        family_id=family_id,
        family_member_id=member_id,
        latitude=data.latitude,
        longitude=data.longitude,
    )
    db.add(emergency)
    db.flush()
    alert = Alert(
        family_id=family_id,
        family_member_id=member_id,
        kind="sos",
        title="EMERGÊNCIA — SOS",
        message=f"{member.display_name} acionou o SOS.",
    )
    db.add(alert)
    audit(db, user.id, "sos", "emergency", emergency.id)
    db.commit()
    notify_guardians(
        db,
        family_id,
        title=alert.title,
        body=alert.message,
        data={"kind": "sos", "family_id": family_id, "member_id": member_id, "emergency_id": emergency.id},
    )
    db.commit()
    return {"id": emergency.id, "created_at": stamp(emergency.created_at)}


@app.get("/app/version/latest")
def latest_app_version(platform: str = Query(pattern="^(android|ios)$"), db: Session = Depends(get_db)):
    row = (
        db.query(AppVersion)
        .filter_by(platform=platform, active=True)
        .order_by(AppVersion.build_number.desc())
        .first()
    )
    if not row:
        return {"version": None}
    return {
        "version": row.version,
        "build_number": row.build_number,
        "required": row.required,
        "store_url": row.store_url,
        "notes": row.notes,
    }


@app.delete("/me")
def delete_me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    owned = db.query(Family).filter_by(owner_user_id=user.id).count()
    if owned:
        raise HTTPException(409, "Transfira ou exclua as famílias sob sua responsabilidade antes de excluir a conta")
    audit(db, user.id, "delete_account", "user", user.id)
    db.delete(user)
    db.commit()
    return {"ok": True}


# ---------------------------
# Administração técnica
# ---------------------------
@app.get("/admin/summary")
def admin_summary(_: User = Depends(admin_user), db: Session = Depends(get_db)):
    cutoff = utcnow_naive() - timedelta(minutes=30)
    return {
        "users": db.query(func.count(User.id)).scalar() or 0,
        "families": db.query(func.count(Family.id)).scalar() or 0,
        "devices": db.query(func.count(Device.id)).scalar() or 0,
        "devices_online_30m": db.query(func.count(Device.id)).filter(Device.last_seen_at >= cutoff).scalar() or 0,
        "alerts_24h": db.query(func.count(Alert.id)).filter(Alert.created_at >= utcnow_naive() - timedelta(hours=24)).scalar() or 0,
        "sos_open": db.query(func.count(Emergency.id)).filter(Emergency.resolved_at.is_(None)).scalar() or 0,
        "push": push_status(),
        "privacy_note": "O painel administrativo não expõe coordenadas de localização por padrão.",
    }


@app.get("/admin/users")
def admin_users(limit: int = Query(100, ge=1, le=500), _: User = Depends(admin_user), db: Session = Depends(get_db)):
    rows = db.query(User).order_by(desc(User.created_at)).limit(limit).all()
    return {
        "items": [
            {"id": row.id, "name": row.name, "email": row.email, "is_admin": row.is_admin, "is_blocked": row.is_blocked, "created_at": stamp(row.created_at)}
            for row in rows
        ]
    }


@app.get("/admin/families")
def admin_families(limit: int = Query(100, ge=1, le=500), _: User = Depends(admin_user), db: Session = Depends(get_db)):
    rows = db.query(Family).order_by(desc(Family.created_at)).limit(limit).all()
    items = []
    for family in rows:
        items.append(
            {
                "id": family.id,
                "name": family.name,
                "members": db.query(func.count(FamilyMember.id)).filter_by(family_id=family.id).scalar() or 0,
                "created_at": stamp(family.created_at),
            }
        )
    return {"items": items}


@app.get("/admin/devices")
def admin_devices(limit: int = Query(200, ge=1, le=1000), _: User = Depends(admin_user), db: Session = Depends(get_db)):
    rows = db.query(Device).order_by(desc(Device.created_at)).limit(limit).all()
    return {
        "items": [
            {
                "id": row.id,
                "platform": row.platform,
                "device_name": row.device_name,
                "app_version": row.app_version,
                "os_version": row.os_version,
                "battery_percent": row.battery_percent,
                "permission_location": row.permission_location,
                "permission_background": row.permission_background,
                "last_seen_at": stamp(row.last_seen_at),
                "push_registered": bool(row.push_token),
                "active": row.active,
            }
            for row in rows
        ]
    }


@app.get("/admin/alerts")
def admin_alerts(limit: int = Query(200, ge=1, le=1000), _: User = Depends(admin_user), db: Session = Depends(get_db)):
    rows = db.query(Alert).order_by(desc(Alert.created_at)).limit(limit).all()
    return {
        "items": [
            {"id": row.id, "family_id": row.family_id, "kind": row.kind, "title": row.kind, "created_at": stamp(row.created_at)}
            for row in rows
        ]
    }


@app.get("/admin/notifications")
def admin_notifications(limit: int = Query(200, ge=1, le=1000), _: User = Depends(admin_user), db: Session = Depends(get_db)):
    rows = db.query(NotificationLog).order_by(desc(NotificationLog.created_at)).limit(limit).all()
    return {
        "items": [
            {
                "id": row.id,
                "family_id": row.family_id,
                "device_id": row.device_id,
                "status": row.status,
                "detail": row.detail,
                "created_at": stamp(row.created_at),
            }
            for row in rows
        ]
    }


@app.get("/admin/audit")
def admin_audit(limit: int = Query(200, ge=1, le=1000), _: User = Depends(admin_user), db: Session = Depends(get_db)):
    rows = db.query(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit).all()
    return {
        "items": [
            {
                "id": row.id,
                "user_id": row.user_id,
                "action": row.action,
                "entity": row.entity,
                "entity_id": row.entity_id,
                "detail": row.detail,
                "created_at": stamp(row.created_at),
            }
            for row in rows
        ]
    }


@app.post("/admin/app-versions")
def admin_create_app_version(data: AppVersionCreate, user: User = Depends(admin_user), db: Session = Depends(get_db)):
    row = AppVersion(**data.model_dump())
    db.add(row)
    db.flush()
    audit(db, user.id, "create", "app_version", row.id, f"{row.platform} {row.version}+{row.build_number}")
    db.commit()
    return {"id": row.id}



class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=32, max_length=200)

class BlockIn(BaseModel):
    blocked: bool

@app.post("/admin/auth/login", response_model=TokenOut)
def admin_login(data: LoginIn, request: Request, db: Session = Depends(get_db)):
    throttle(db, request, "admin_login", 10)
    user = db.query(User).filter_by(email=data.email.lower()).first()
    if not user or user.is_blocked or not user.is_admin or not verify_password(data.password, user.password_hash):
        audit(db, None, "admin_login_failed", "auth")
        db.commit()
        raise HTTPException(401, "Credenciais administrativas inválidas")
    audit(db, user.id, "admin_login", "auth")
    return issue(db, user, "admin")

@app.post("/auth/refresh", response_model=TokenOut)
def refresh(data: RefreshIn, request: Request, db: Session = Depends(get_db)):
    throttle(db, request, "refresh", 120)
    session = db.query(AuthSession).filter_by(refresh_hash=digest(data.refresh_token)).first()
    if not session or session.revoked or session.expires_at <= now():
        raise HTTPException(401, "Sessão expirada ou encerrada")
    user = db.get(User, session.user_id)
    if not user or user.is_blocked:
        raise HTTPException(401, "Conta indisponível")
    claimed = db.execute(update(AuthSession).where(AuthSession.id == session.id, AuthSession.revoked.is_(False)).values(revoked=True)).rowcount
    if claimed != 1:
        db.rollback()
        raise HTTPException(401, "Token já utilizado")
    return issue(db, user, session.scope)

@app.post("/auth/logout")
def logout(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    payload = jwt.decode(request.headers["Authorization"].split()[1], settings.jwt_secret, algorithms=["HS256"])
    db.get(AuthSession, payload["sid"]).revoked = True
    db.commit()
    return {"ok": True}

@app.post("/admin/users/{user_id}/revoke-sessions")
def revoke(user_id: str, admin: User = Depends(admin_user), db: Session = Depends(get_db)):
    db.query(AuthSession).filter_by(user_id=user_id).update({"revoked": True})
    audit(db, admin.id, "revoke_sessions", "user", user_id)
    db.commit()
    return {"ok": True}

@app.patch("/admin/users/{user_id}/blocked")
def block(user_id: str, data: BlockIn, admin: User = Depends(admin_user), db: Session = Depends(get_db)):
    if user_id == admin.id:
        raise HTTPException(409, "Não é possível bloquear a própria conta")
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, "Usuário não encontrado")
    target.is_blocked = data.blocked
    if data.blocked:
        db.query(AuthSession).filter_by(user_id=user_id).update({"revoked": True})
    audit(db, admin.id, "block" if data.blocked else "unblock", "user", user_id)
    db.commit()
    return {"ok": True}

@app.delete("/families/{family_id}")
def delete_family(family_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    family = db.get(Family, family_id)
    if not family or family.owner_user_id != user.id:
        raise HTTPException(403, "Somente o titular pode excluir a família")
    db.delete(family)
    audit(db, user.id, "delete_family", "family", family_id)
    db.commit()
    return {"ok": True}

@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'self'"
    return response



@app.get("/admin/sessions")
def sessions(_: User = Depends(admin_user), db: Session = Depends(get_db)):
    rows = db.query(AuthSession).order_by(desc(AuthSession.created_at)).limit(200).all()
    return {"items":[{"id":r.id,"user_id":r.user_id,"scope":r.scope,"revoked":r.revoked,
                      "expires_at":stamp(r.expires_at),"created_at":stamp(r.created_at)} for r in rows]}

@app.get("/admin/app-versions")
def versions(_: User = Depends(admin_user), db: Session = Depends(get_db)):
    rows = db.query(AppVersion).order_by(desc(AppVersion.created_at)).limit(100).all()
    return {"items":[{"platform":r.platform,"version":r.version,"build_number":r.build_number,"required":r.required} for r in rows]}

if settings.admin_panel_enabled:
    admin_dir = Path(__file__).resolve().parent.parent / "admin_web"
    if admin_dir.exists():
        app.mount("/admin-panel", StaticFiles(directory=str(admin_dir), html=True), name="admin-panel")
