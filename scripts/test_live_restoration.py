"""Run relevant unit tests with disposable SQLite and no PostgreSQL connection."""
import argparse
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backend.db as db

parser = argparse.ArgumentParser()
parser.add_argument('--baseline-main')
parser.add_argument('modules', nargs='*')
args = parser.parse_args()
os.environ.pop('DATABASE_URL', None)
os.environ.pop('PHASE3_TEST_DATABASE_URL', None)
with tempfile.TemporaryDirectory(prefix='crashguard-unit-') as directory:
    db.DATABASE_PATH = Path(directory) / 'unit.sqlite'
    if args.baseline_main:
        spec = importlib.util.spec_from_file_location('backend.main', args.baseline_main)
        module = importlib.util.module_from_spec(spec)
        # Preserve resource resolution without editing the original source file.
        module.__file__ = str(Path('backend/main.py').resolve())
        sys.modules['backend.main'] = module
        spec.loader.exec_module(module)
    modules = args.modules or [
        'test_live_monitor_restoration', 'test_camera_performance', 'test_camera_health',
        'test_camera_role_permissions', 'test_camera_security', 'test_auth_cookie_contract',
        'test_crash_decision', 'test_phase2_decision_contract', 'test_dual_path_aftermath',
        'test_temporal_crash_verifier', 'test_crash_aftermath_detector',
        'test_vehicle_tracking', 'test_vehicle_detection_tiers',
        'test_logical_vehicle_continuity', 'test_collision_pair_classifier',
        'test_crash_event_state', 'test_detector_preprocessing',
    ]
    suite = unittest.defaultTestLoader.loadTestsFromNames(['backend.tests.' + name for name in modules])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(not result.wasSuccessful())
