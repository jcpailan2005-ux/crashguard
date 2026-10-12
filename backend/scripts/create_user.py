"""Retired legacy account creator.

Phase 3 accounts are SQLite-backed and must be created through the Admin API
or the explicit initial-account seeder.
"""

raise SystemExit(
    "Legacy account creation is retired. Use the Admin User Management screen "
    "or `python -m backend.scripts.seed_initial_accounts` for initial setup."
)
