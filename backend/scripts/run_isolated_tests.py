"""Run tests without importing the application against operational SQLite.

All operational storage is redirected to temporary SQLite files.
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
        os.environ['CRASHGUARD_SQLITE_PATH'] = str(db.DATA_DIR / 'operations.sqlite')
        modules = sys.argv[1:] or [
            'backend.tests.' + path.stem
            for path in sorted(pathlib.Path('backend/tests').glob('test_*.py'))
        ]
        suite = unittest.TestLoader().loadTestsFromNames(modules)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        raise SystemExit(not result.wasSuccessful())


if __name__ == '__main__':
    main()
