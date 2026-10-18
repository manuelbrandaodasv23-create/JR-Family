from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from .db import get_db
from .models import User, FamilyMember, AuthSession
from .config import settings
from .models import now
import jwt
from .security import decode_token

bearer = HTTPBearer(auto_error=False)


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(401, "Autenticação necessária")
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=["HS256"], options={"require": ["sub", "exp", "iat", "sid", "scope"]})
        uid = payload["sub"]
        session = db.get(AuthSession, payload["sid"])
        if not session or session.revoked or session.user_id != uid or session.expires_at <= now():
            raise ValueError("Sessão encerrada")
    except Exception:
        raise HTTPException(401, "Token inválido ou expirado")
    user = db.get(User, uid)
    if not user or user.is_blocked:
        raise HTTPException(401, "Usuário não encontrado")
    return user


def admin_user(u: User = Depends(current_user), credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> User:
    payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=["HS256"])
    if not u.is_admin or payload.get("scope") != "admin":
        raise HTTPException(403, "Acesso administrativo necessário")
    return u


def membership(db: Session, user_id: str, family_id: str, guardian_only: bool = False) -> FamilyMember:
    m = db.query(FamilyMember).filter_by(user_id=user_id, family_id=family_id).first()
    if not m:
        raise HTTPException(403, "Sem acesso a esta família")
    if guardian_only and m.role != "guardian":
        raise HTTPException(403, "Apenas responsáveis")
    return m
