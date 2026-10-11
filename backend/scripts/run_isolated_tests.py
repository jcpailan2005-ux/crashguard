"""Run tests without importing the application against operational SQLite.

PostgreSQL suites require DATABASE_URL naming crashguard_test, explicitly supplied
by the operator. Never derives or changes an operational database URL.
"""
import os
import pathlib
import sys
import tempfile
import unittest

def main():
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
    import backend.db as db

    with tempfile.TemporaryDirectory(prefix='crashguard-tests-', ignore_cleanup_errors=True) as directory:
        db.DATA_DIR = pathlib.Path(directory)
        db.DATABASE_PATH = db.DATA_DIR / 'crashguard.sqlite'
        # No automatic synchronization into an operational PostgreSQL database.
        if os.getenv('DATABASE_URL') and not os.environ['DATABASE_URL'].rstrip('/').endswith('/crashguard_test'):
            raise RuntimeError('Tests require an explicit isolated crashguard_test database.')
        modules = sys.argv[1:] or [
            'backend.tests.' + path.stem
            for path in sorted(pathlib.Path('backend/tests').glob('test_*.py'))
        ]
        suite = unittest.TestLoader().loadTestsFromNames(modules)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        raise SystemExit(not result.wasSuccessful())


if __name__ == '__main__':
    main()
