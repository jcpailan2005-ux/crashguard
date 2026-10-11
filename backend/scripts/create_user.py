"""Retired SQLite account creator.

Phase 3 accounts are PostgreSQL-backed and must be created through the Admin API
or the explicit initial-account seeder.
"""

raise SystemExit(
    "SQLite account creation is retired. Use the Admin User Management screen "
    "or `python -m backend.scripts.seed_initial_accounts` for initial setup."
)
