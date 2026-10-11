# Phase 3 PostgreSQL operations

PostgreSQL is authoritative for accounts, sessions, RBAC, incidents, reviews,
assignments, notifications, timelines, and audit logs. SQLite is retained only
as a legacy import source and can be used by old tests when explicitly enabled.
Firestore is not an operational write target for Phase 3 routes.
The remaining Firestore use is limited to legacy read-only dashboard views and
the non-authoritative live-preview collaboration document on the Samples page.
Detection results are never written to Firestore by the frontend.

## Local setup

Install backend dependencies:

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-phase3.txt
```

Start PostgreSQL using either a local PostgreSQL 17 service or Docker:

```powershell
$env:POSTGRES_PASSWORD = '<generate-a-local-password>'
docker compose -f docker-compose.postgres.yml up -d
$env:DATABASE_URL = "postgresql://crashguard:$env:POSTGRES_PASSWORD@localhost:5432/crashguard"
$env:TEST_DATABASE_URL = "postgresql://crashguard:$env:POSTGRES_PASSWORD@localhost:5432/crashguard_test"
```

This workstation uses the official EDB PostgreSQL 16 portable binaries at
`%LOCALAPPDATA%\CrashGuard\PostgreSQL16`. Start that user-owned cluster with:

```powershell
& "$env:LOCALAPPDATA\CrashGuard\PostgreSQL16\pgsql\bin\pg_ctl.exe" start `
  -D "$env:LOCALAPPDATA\CrashGuard\PostgreSQL16\data-cluster" `
  -l "$env:LOCALAPPDATA\CrashGuard\PostgreSQL16\postgres.log" `
  -o '"-p 55432 -h 127.0.0.1"' -w
$env:DATABASE_URL = [Environment]::GetEnvironmentVariable('DATABASE_URL', 'User')
```

The committed setup remains the Docker Compose path; neither local database
passwords nor generated application secrets are stored in this repository.

Migrate, optionally import legacy operational data, then seed accounts:

```powershell
.\backend\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
.\backend\.venv\Scripts\python.exe -m backend.scripts.import_legacy_sqlite
.\backend\.venv\Scripts\python.exe -m backend.scripts.seed_initial_accounts
```

The seeder prints newly generated temporary passwords once. Re-running it does
not reset accounts. Use `--reset-existing` only for an intentional local reset.

Run destructive integration tests only against the dedicated test database:

```powershell
$env:DATABASE_URL = $env:TEST_DATABASE_URL
python -m unittest backend.tests.test_phase3_postgres -v
```

## Recovery

Before importing, back up PostgreSQL with `pg_dump`. Alembic supports
`downgrade base`, but that removes Phase 3 tables and is destructive. Legacy
SQLite data is never deleted or modified by the importer.
