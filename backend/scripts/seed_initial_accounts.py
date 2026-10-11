from __future__ import annotations

import argparse

from backend.phase3.database import connection
from backend.phase3.security import generate_temporary_password, hash_password
from backend.phase3.service import create_user


ACCOUNTS = (
    ("ADMIN", "admin@crashguard.local", "CrashGuard Administrator"),
    ("DISPATCHER", "dispatcher@crashguard.local", "CrashGuard Dispatcher"),
    ("RESPONDER", "responder@crashguard.local", "CrashGuard Responder"),
)


def reset_existing(email: str) -> str:
    temporary = generate_temporary_password()
    with connection() as conn, conn.transaction():
        user = conn.execute("SELECT id FROM users WHERE email=%s FOR UPDATE", (email,)).fetchone()
        if not user:
            raise RuntimeError(f"Cannot reset missing bootstrap account {email}.")
        conn.execute(
            """UPDATE users SET password_hash=%s,status='ACTIVE',must_change_password=TRUE,
               disabled_at=NULL,updated_at=now() WHERE id=%s""",
            (hash_password(temporary), user["id"]),
        )
        conn.execute(
            "UPDATE sessions SET revoked_at=now() WHERE user_id=%s AND revoked_at IS NULL",
            (user["id"],),
        )
        conn.execute(
            """INSERT INTO audit_logs(action,entity_type,entity_id,metadata)
               VALUES ('bootstrap.password_reset','user',%s,'{"source":"seed_initial_accounts"}'::jsonb)""",
            (str(user["id"]),),
        )
    return temporary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create the three fresh CrashGuard PostgreSQL development accounts."
    )
    parser.add_argument(
        "--reset-existing",
        action="store_true",
        help="Explicitly rotate bootstrap-account passwords and revoke sessions.",
    )
    args = parser.parse_args()

    with connection() as conn:
        existing = {
            str(row["email"]).lower()
            for row in conn.execute(
                "SELECT email FROM users WHERE email = ANY(%s)",
                ([email for _, email, _ in ACCOUNTS],),
            ).fetchall()
        }

    created: list[tuple[str, str, str]] = []
    skipped: list[str] = []
    for role, email, name in ACCOUNTS:
        if email in existing:
            if args.reset_existing:
                created.append((role, email, reset_existing(email)))
            else:
                skipped.append(email)
            continue
        result = create_user(None, email=email, full_name=name, role=role)
        created.append((role, email, result.pop("temporaryPassword")))

    if created:
        print("FRESH DEVELOPMENT ACCOUNTS")
        for role, email, password in created:
            print(f"\n{role}")
            print(f"Email: {email}")
            print(f"Temporary Password: {password}")
            print("Must change password: YES")
    if skipped:
        print("\nExisting accounts were not modified:")
        for email in skipped:
            print(f"- {email}")
        print("Use --reset-existing only when intentional password rotation is required.")


if __name__ == "__main__":
    main()
