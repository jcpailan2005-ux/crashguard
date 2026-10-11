"""Safely reset one CrashGuard bootstrap account from an interactive terminal.

The password is read with ``getpass`` and is never accepted as a command-line
argument, printed, or written to disk. This command intentionally refuses to
reactivate disabled or locked accounts.
"""

from __future__ import annotations

import argparse
from getpass import getpass

from backend.phase3.database import connection
from backend.phase3.security import hash_password, validate_password


BOOTSTRAP_EMAILS = (
    "admin@crashguard.local",
    "dispatcher@crashguard.local",
    "responder@crashguard.local",
)


def reset_password(email: str, new_password: str) -> None:
    normalized_email = email.strip().lower()
    validate_password(new_password)

    with connection() as conn, conn.transaction():
        account = conn.execute(
            "SELECT id, status FROM users WHERE email=%s FOR UPDATE",
            (normalized_email,),
        ).fetchone()
        if not account:
            raise RuntimeError(f"Development account does not exist: {normalized_email}")
        if account["status"] != "ACTIVE":
            raise RuntimeError(
                f"Refusing to reset a {account['status']} account. Review its status first."
            )

        conn.execute(
            """UPDATE users
               SET password_hash=%s, must_change_password=TRUE, updated_at=now()
               WHERE id=%s""",
            (hash_password(new_password), account["id"]),
        )
        conn.execute(
            "UPDATE sessions SET revoked_at=now() WHERE user_id=%s AND revoked_at IS NULL",
            (account["id"],),
        )
        conn.execute(
            """INSERT INTO audit_logs(action,entity_type,entity_id,metadata)
               VALUES ('bootstrap.password_reset','user',%s,
                       '{"source":"reset_development_account_password"}'::jsonb)""",
            (str(account["id"]),),
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Interactively reset exactly one CrashGuard development account."
    )
    parser.add_argument("email", choices=BOOTSTRAP_EMAILS)
    args = parser.parse_args()

    password = getpass("New temporary password: ")
    confirmation = getpass("Confirm temporary password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match; no database changes were made.")

    try:
        reset_password(args.email, password)
    except (RuntimeError, ValueError) as error:
        raise SystemExit(str(error)) from error

    print(f"Password reset completed for {args.email}.")
    print("Existing sessions were revoked; password change is required at next login.")


if __name__ == "__main__":
    main()
