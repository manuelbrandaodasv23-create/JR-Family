import hashlib
import secrets
from datetime import timedelta
from fastapi import HTTPException, Request
from sqlalchemy import update
from sqlalchemy.orm import Session
from .models import AuthSession, RateBucket, now
from .config import settings
from .security import make_token
from .schemas import TokenOut


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def issue(db, user, scope="mobile"):
    token = secrets.token_urlsafe(48)
    session = AuthSession(user_id=user.id, refresh_hash=digest(token), scope=scope,
                          expires_at=now()+timedelta(days=settings.refresh_token_days))
    db.add(session)
    db.flush()
    result = TokenOut(access_token=make_token(user.id, session.id, scope), refresh_token=token,
                      expires_in=settings.access_token_minutes*60)
    db.commit()
    return result


def throttle(db: Session, request: Request, category: str, limit: int = 20):
    # Shared database counter; do not trust client-supplied X-Forwarded-For.
    address = request.client.host if request.client else "unknown"
    key = digest(category+":"+address)
    current = now()
    db.query(RateBucket).filter(RateBucket.expires_at <= current).delete(synchronize_session=False)
    db.commit()
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
    statement = insert(RateBucket).values(key=key, count=1, expires_at=current+timedelta(minutes=15))
    statement = statement.on_conflict_do_update(index_elements=[RateBucket.key], set_={"count": RateBucket.count+1})
    db.execute(statement)
    db.commit()
    count = db.get(RateBucket, key).count
    if count > limit:
        raise HTTPException(429, "Muitas tentativas. Aguarde 15 minutos.", headers={"Retry-After": "900"})
