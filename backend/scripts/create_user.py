from __future__ import annotations

import argparse
import hashlib
import re
import secrets
import sys
import uuid
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.db import init_db  # noqa: E402
from backend.repositories.crash_cases import get_user_profile_by_email, upsert_user_profile  # noqa: E402


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
VALID_ROLES = {"user", "responder", "admin"}
PASSWORD_ITERATIONS = 210_000


def hash_password(password: str) -> tuple[str, str]:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )
    return digest.hex(), salt.hex()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a persistent SQLite CrashGuard user.")
    parser.add_argument("--email", required=True, help="User email address.")
    parser.add_argument("--password", required=True, help="User password. It will be hashed before saving.")
    parser.add_argument("--name", default="", help="Display name.")
    parser.add_argument("--role", required=True, choices=sorted(VALID_ROLES), help="user, responder, or admin.")
    parser.add_argument("--area-id", default=None, help="Responder area, for example talomo.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    email = args.email.strip().lower()
    role = args.role.strip().lower()

    if not EMAIL_RE.match(email):
        print("Invalid email address.", file=sys.stderr)
        return 2
    if len(args.password) < 8:
        print("Password must be at least 8 characters.", file=sys.stderr)
        return 2
    if role not in VALID_ROLES:
        print("Role must be user, responder, or admin.", file=sys.stderr)
        return 2

    init_db()
    if get_user_profile_by_email(email) is not None:
        print(f"An account with email {email} already exists.", file=sys.stderr)
        return 1

    password_hash, password_salt = hash_password(args.password)
    timestamp = datetime.now().isoformat()
    profile = upsert_user_profile(
        {
            "uid": f"USR-{uuid.uuid4().hex}",
            "email": email,
            "displayName": args.name.strip() or email.split("@", 1)[0],
            "role": role,
            "areaId": args.area_id if role == "responder" else None,
            "passwordHash": password_hash,
            "passwordSalt": password_salt,
            "isActive": True,
            "createdAt": timestamp,
            "updatedAt": timestamp,
        }
    )

    print("Created SQLite user:")
    print(f"  uid: {profile['uid']}")
    print(f"  email: {profile['email']}")
    print(f"  displayName: {profile.get('displayName') or ''}")
    print(f"  role: {profile['role']}")
    print(f"  areaId: {profile.get('areaId') or ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
