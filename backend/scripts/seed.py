"""
Demo data for local runs and the hackathon demo. Safe to run many times (skips what exists).

Run:  docker compose exec api python -m scripts.seed
      (or locally from backend/:  python -m scripts.seed)

Password for every demo user comes from SEED_PASSWORD (default only outside production).
"""

import os
import sys
from decimal import Decimal

from app.core.config import settings
from app.core.enums import UserRole
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.repositories import users as user_repo

DEV_DEFAULT_PASSWORD = "SunPower@2026"

DEMO_USERS = [
    {"full_name": "Admin User", "email": "admin@sunpower.in", "role": UserRole.ADMIN},
    {"full_name": "Divya Director", "email": "director@sunpower.in", "role": UserRole.DIRECTOR},
    {"full_name": "Asha Office", "email": "office@sunpower.in", "role": UserRole.OFFICE},
    {"full_name": "Sameer Surveyor", "email": "surveyor@sunpower.in", "role": UserRole.SURVEYOR},
    {"full_name": "Wasim Warehouse", "email": "warehouse@sunpower.in", "role": UserRole.WAREHOUSE},
    {"full_name": "Sunita Support", "email": "support@sunpower.in", "role": UserRole.SUPPORT},
    {
        "full_name": "Raju Technician",
        "email": "tech1@sunpower.in",
        "role": UserRole.TECHNICIAN,
        "hourly_rate": Decimal("250.00"),
    },
    {
        "full_name": "Kiran Technician",
        "email": "tech2@sunpower.in",
        "role": UserRole.TECHNICIAN,
        "hourly_rate": Decimal("250.00"),
    },
]


def _seed_password() -> str:
    password = os.environ.get("SEED_PASSWORD")
    if password:
        return password
    if settings.env.lower() == "production":
        sys.exit("Refusing to seed production without SEED_PASSWORD")
    return DEV_DEFAULT_PASSWORD


def seed_users(db, password: str) -> int:
    """Create missing demo users. Returns how many were created."""
    password_hash = hash_password(password)
    created = 0
    for spec in DEMO_USERS:
        if user_repo.get_by_email(db, spec["email"]) is None:
            user_repo.create(db, {**spec, "password_hash": password_hash, "is_active": True})
            created += 1
    return created


def main() -> None:
    password = _seed_password()
    with SessionLocal() as db:
        created = seed_users(db, password)
        db.commit()
    print(f"Users: {created} created, {len(DEMO_USERS) - created} already existed")


if __name__ == "__main__":
    main()