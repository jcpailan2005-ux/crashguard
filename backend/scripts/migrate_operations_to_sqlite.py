"""One-time, read-only import from the former PostgreSQL operational store.

Requires the optional requirements-migration.txt packages. The running backend
never imports this module or connects to PostgreSQL. Set LEGACY_DATABASE_URL or
DATABASE_URL privately; values and rows are never printed. Refuses populated
SQLite destinations. Stop the old backend before importing the final snapshot.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID
from ipaddress import IPv4Address, IPv6Address

from backend.phase3 import database

TABLES = ('areas', 'roles', 'permissions', 'users', 'user_roles', 'role_permissions',
          'sessions', 'cameras', 'incidents', 'review_cases', 'assignments', 'alerts',
          'notifications', 'audit_logs', 'incident_timeline', 'system_settings',
          'user_preferences')


def convert(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, default=str)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (IPv4Address, IPv6Address)):
        return str(value)
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return value


def migrate(destination: Path) -> dict[str, int]:
    import psycopg  # Optional, offline migration dependency only.
    url = os.getenv('LEGACY_DATABASE_URL') or os.getenv('DATABASE_URL')
    if not url:
        raise RuntimeError('Set the private legacy database URL for this import.')
    database.init_db()
    counts = {}
    with psycopg.connect(url, options='-c default_transaction_read_only=on', connect_timeout=10) as source:
        source.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        with database.connection() as target, target.transaction():
            for table in TABLES:
                if table not in {'roles', 'permissions', 'role_permissions'}:
                    if target.execute(f'SELECT count(*) AS n FROM {table}').fetchone()['n']:
                        raise RuntimeError('Destination has operational records; import refused.')
            target.execute('PRAGMA defer_foreign_keys=ON')
            for table in ('role_permissions', 'permissions', 'roles'):
                target.execute(f'DELETE FROM {table}')
            for table in TABLES:
                cursor = source.execute(f'SELECT * FROM {table}')
                columns = [column.name for column in cursor.description]
                rows = cursor.fetchall()
                # Table/column identifiers come exclusively from the trusted
                # source schema and fixed table list; values remain bound.
                names = ','.join('"' + c.replace('"', '""') + '"' for c in columns)
                placeholders = ','.join('?' for _ in columns)
                for row in rows:
                    target.raw.execute(f'INSERT INTO {table}({names}) VALUES ({placeholders})',
                                       tuple(convert(value) for value in row))
                counts[table] = len(rows)
            if target.execute('PRAGMA foreign_key_check').fetchone():
                raise RuntimeError('Imported foreign keys failed validation.')
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    os.environ['CRASHGUARD_SQLITE_PATH'] = str(args.destination.resolve())
    try:
        counts = migrate(args.destination)
    except Exception as error:
        # Drivers can include private connection details in exception text.
        print(f'Import failed: {type(error).__name__}; no credential details printed.')
        raise SystemExit(1)
    print(json.dumps({'engine': 'sqlite', 'imported_counts': counts}))


if __name__ == '__main__':
    main()
