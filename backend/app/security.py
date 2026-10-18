from datetime import datetime, timedelta, timezone
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from .config import settings

ph = PasswordHasher()

def hash_password(password: str) -> str: return ph.hash(password)
def verify_password(password: str, password_hash: str) -> bool:
    try: return ph.verify(password_hash, password)
    except VerifyMismatchError: return False

def make_token(user_id: str, session_id: str | None = None, scope: str = "mobile") -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode({"sub": user_id, "sid": session_id, "scope": scope, "exp": exp, "iat": datetime.now(timezone.utc)}, settings.jwt_secret, algorithm="HS256")

def decode_token(token: str) -> str:
    data = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    return str(data["sub"])
