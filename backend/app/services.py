from math import radians, sin, cos, sqrt, atan2
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from .models import Alert, AuditLog, Device, FamilyMember, Geofence, GeofenceState, Location
from .config import settings


def meters(a_lat, a_lon, b_lat, b_lon):
    r = 6371000
    p1, p2 = radians(a_lat), radians(b_lat)
    dp = radians(b_lat - a_lat)
    dl = radians(b_lon - a_lon)
    h = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * r * atan2(sqrt(h), sqrt(1 - h))


def audit(db: Session, user_id: str | None, action: str, entity: str, entity_id: str | None = None, detail: str | None = None):
    db.add(AuditLog(user_id=user_id, action=action, entity=entity, entity_id=entity_id, detail=detail))


def process_location_alerts(db: Session, device: Device, loc: Location) -> list[Alert]:
    created: list[Alert] = []
    member = db.get(FamilyMember, device.family_member_id)
    if not member:
        return created

    if loc.battery_percent is not None and loc.battery_percent <= settings.low_battery_percent:
        recent = (
            db.query(Alert)
            .filter(
                Alert.family_id == member.family_id,
                Alert.family_member_id == member.id,
                Alert.kind == "battery_low",
            )
            .order_by(Alert.created_at.desc())
            .first()
        )
        if not recent or (datetime.now(timezone.utc).replace(tzinfo=None) - recent.created_at).total_seconds() > 3 * 3600:
            alert = Alert(
                family_id=member.family_id,
                family_member_id=member.id,
                kind="battery_low",
                title="Bateria baixa",
                message=f"{member.display_name} está com {loc.battery_percent}% de bateria.",
            )
            db.add(alert)
            created.append(alert)

    fences = db.query(Geofence).filter_by(family_id=member.family_id, enabled=True).all()
    for fence in fences:
        inside = meters(loc.latitude, loc.longitude, fence.latitude, fence.longitude) <= fence.radius_m
        state = db.query(GeofenceState).filter_by(geofence_id=fence.id, device_id=device.id).first()
        if state is None:
            db.add(GeofenceState(geofence_id=fence.id, device_id=device.id, inside=inside))
            continue
        if state.inside != inside:
            state.inside = inside
            state.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            verb = "chegou a" if inside else "saiu de"
            alert = Alert(
                family_id=member.family_id,
                family_member_id=member.id,
                kind="geofence_enter" if inside else "geofence_exit",
                title=f"{member.display_name} {verb} {fence.name}",
                message=f"Evento registrado em {fence.name}.",
            )
            db.add(alert)
            created.append(alert)
    return created
