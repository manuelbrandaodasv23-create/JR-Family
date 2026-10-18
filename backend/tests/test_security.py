import os
os.environ.setdefault("JWT_SECRET","test-secret-key-that-is-at-least-32-bytes-long")
from app.security import hash_password, verify_password, make_token, decode_token

def test_password_roundtrip():
    h=hash_password("uma-senha-segura-123")
    assert verify_password("uma-senha-segura-123",h)
    assert not verify_password("errada",h)

def test_jwt_roundtrip():
    token=make_token("abc")
    assert decode_token(token)=="abc"
