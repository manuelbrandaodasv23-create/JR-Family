import time
from datetime import timedelta
from sqlalchemy.orm import Session
from .config import settings
from .models import Location, Emergency, Alert, AuditLog, NotificationLog, RateBucket, AuthSession, now

def check_unavailable(db):
    from .models import Device, FamilyMember, Alert
    from .push import notify_guardians
    cutoff = now() - timedelta(minutes=30)
    devices = db.query(Device).join(FamilyMember, Device.family_member_id == FamilyMember.id).filter(
        Device.active.is_(True), Device.offline_notified.is_(False),
        FamilyMember.location_sharing_enabled.is_(True), Device.last_seen_at < cutoff).all()
    for device in devices:
        member = db.get(FamilyMember, device.family_member_id)
        device.offline_notified = True
        db.add(Alert(family_id=member.family_id, family_member_id=member.id, kind="location_unavailable",
                     title="Localização indisponível", message="Sem atualização há mais de 30 minutos. GPS, permissões ou conexão podem estar indisponíveis."))
        notify_guardians(db, member.family_id, title="Localização indisponível", body="Sem atualização há mais de 30 minutos. Confira o aplicativo.", data={"kind":"location_unavailable", "family_id":member.family_id})

def purge_old_locations(db: Session) -> int:
    cutoff = now() - timedelta(days=settings.history_retention_days)
    count = db.query(Location).filter(Location.captured_at < cutoff).delete(synchronize_session=False)
    for model in (Emergency, Alert, AuditLog, NotificationLog):
        db.query(model).filter(model.created_at < cutoff).delete(synchronize_session=False)
    db.query(RateBucket).filter(RateBucket.expires_at < now()).delete(synchronize_session=False)
    db.query(AuthSession).filter(AuthSession.expires_at < now()).delete(synchronize_session=False)
    return count

if __name__ == "__main__":
    import logging
    from .db import SessionLocal
    while True:
        try:
            with SessionLocal() as db:
                check_unavailable(db)
                purge_old_locations(db)
                db.commit()
        except Exception:
            logging.exception("Falha no processo de retenção")
        time.sleep(60)
