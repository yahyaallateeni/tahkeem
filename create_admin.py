#!/usr/bin/env python3
import os
import sys
from pathlib import Path
import argparse
from flask import Flask

# Ensure project root on path
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from src.models.user import db, User  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Provision an admin user if missing")
    parser.add_argument("--username", default=os.environ.get("ADMIN_USERNAME"))
    parser.add_argument("--password", default=os.environ.get("ADMIN_PASSWORD"))
    parser.add_argument("--email", default=os.environ.get("ADMIN_EMAIL", "admin@example.com"))
    args = parser.parse_args()

    if not args.username or not args.password:
        raise RuntimeError("ADMIN_USERNAME and ADMIN_PASSWORD must be provided via env or args")

    app = Flask(__name__)
    db_path = ROOT_DIR / "src" / "database" / "app.db"
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    with app.app_context():
        db.create_all()
        admin = User.query.filter_by(username=args.username).first()
        if admin:
            print("Admin user already exists")
            return
        admin = User(username=args.username, user_type='admin', email=args.email)
        if hasattr(admin, 'set_password') and callable(admin.set_password):
            admin.set_password(args.password)
        else:
            from werkzeug.security import generate_password_hash
            admin.password_hash = generate_password_hash(args.password)
        db.session.add(admin)
        db.session.commit()
        print(f"Admin user {args.username} created successfully")


if __name__ == "__main__":
    main()
