import argparse
from .db import SessionLocal, Base, engine
from .models import User


def make_admin(email: str, enabled: bool = True) -> None:
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(email=email.lower()).first()
        if not user:
            raise SystemExit(f"Usuário não encontrado: {email}")
        user.is_admin = enabled
        db.commit()
        print(f"Admin {'ativado' if enabled else 'desativado'} para {user.email}")
    finally:
        db.close()


def main() -> None:
    p = argparse.ArgumentParser(prog="python -m app.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("make-admin")
    a.add_argument("email")
    r = sub.add_parser("remove-admin")
    r.add_argument("email")
    args = p.parse_args()
    make_admin(args.email, enabled=args.cmd == "make-admin")


if __name__ == "__main__":
    main()
