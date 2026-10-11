"""Execute the actual live worker body without importing app/DB/model startup.

Only external inference, persistence and media I/O are stubbed. Production
filtering, pair iteration, hit-window mutation and decision helper execute.
"""
import ast
from collections import deque
from datetime import datetime
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import uuid

import numpy as np
from backend.services import live_collision_diagnostics as diagnostic


SOURCE = Path(__file__).resolve().parents[1] / 'main.py'


def load_worker(strip_diagnostics=False):
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    functions = {
        'get_env_int', 'get_env_float', 'normalize_confidence_fraction',
        'normalize_detection_label', 'normalize_box_label', 'box_center',
        'parse_crash_roi', 'filter_boxes_in_roi', 'boxes_iou', 'boxes_edge_distance',
        'crash_like_vehicle_interaction', 'evaluate_crash_case_decision',
        'extract_vehicle_boxes_from_results', 'detect_vehicle_boxes',
        'count_labels_from_results', 'scale_detection_boxes', 'dominant_object_label',
    }
    constants = {
        '_raw_crash_ui_threshold', '_raw_crash_case_threshold',
        'CRASH_UI_CONFIDENCE_THRESHOLD', 'CRASH_CASE_CONFIDENCE_THRESHOLD',
        'LIVE_CAMERA_REQUIRED_HITS', 'CRASH_TEMPORAL_WINDOW_SECONDS',
        'LIVE_CAMERA_FREEZE_TIMEOUT_SECONDS', 'LIVE_CAMERA_VEHICLE_CONFIDENCE_THRESHOLD',
        'LIVE_CAMERA_PERSON_CONFIDENCE_THRESHOLD', 'LIVE_CAMERA_ALERT_COOLDOWN_SECONDS',
        'VEHICLE_BOX_LABELS', 'PERSON_LABELS',
    }
    body = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in functions]
    body += [n for n in tree.body if isinstance(n, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id in constants for t in n.targets)]
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'LiveCameraMonitor')
    cls.body = [n for n in cls.body if isinstance(n, ast.FunctionDef)
                and n.name in {'__init__', 'analyze_current_frame', '_analyze_current_frame'}]
    body.append(cls)
    module = ast.Module(body=body, type_ignores=[])
    if strip_diagnostics:
        class Strip(ast.NodeTransformer):
            def visit_Expr(self, node):
                if isinstance(node.value, ast.Call) and ast.unparse(node.value.func) == 'live_collision_diagnostics.emit':
                    return None
                return self.generic_visit(node)

            def visit_FunctionDef(self, node):
                node.decorator_list = [d for d in node.decorator_list
                                       if ast.unparse(d) != 'live_collision_diagnostics.observe']
                return self.generic_visit(node)
        module = Strip().visit(module)
    namespace = dict(np=np, os=os, time=time, datetime=datetime, threading=threading,
                     deque=deque, uuid=uuid, Path=Path, live_collision_diagnostics=diagnostic,
                     bounded_inference=lambda fn: fn)
    exec(compile(ast.fix_missing_locations(module), str(SOURCE), 'exec'), namespace)
    return namespace


def raw(label, score=.95, bbox=(0, 0, 20, 20)):
    ids = {'car': 0, 'motorcycle': 1, 'person': 2}
    return SimpleNamespace(cls=np.array([ids[label]]), conf=np.array([score]), xyxy=np.array([bbox]))


class LiveDiagnosticsTests(unittest.TestCase):
    def run_sequence(self, scores, enabled, *, strip=False, boxes=None, times=None, quality=None,
                     sink=None, box_sequences=None, qualities=None, roi='', frame_sink=None,
                     frame_capture=False):
        with patch.dict(os.environ, {'LIVE_COLLISION_DIAGNOSTICS': '1' if enabled else '0',
                                   'LIVE_COLLISION_FRAME_CAPTURE': '1' if frame_capture else '0',
                                   'CRASH_ROI_NORMALIZED': roi}, clear=True):
            app = load_worker(strip)
            self.assertEqual(app['LIVE_CAMERA_REQUIRED_HITS'], 3)
            self.assertEqual(app['CRASH_CASE_CONFIDENCE_THRESHOLD'], .9)
            monitor = app['LiveCameraMonitor'](monitor_key='test', camera_id='CAM-TEST', camera_ip=None,
                stream_url='rtsp://username:password@host/live', label='Test', area_id='test', barangay=None,
                road_name=None, latitude=None, longitude=None, location='test',
                redacted_stream_url='rtsp://host/live', output_base='http://testserver')
            good_quality = dict(frameQualityStatus='good', qualityRejectionReason=None,
                                blurScore=100, brightnessScore=100, contrastScore=100)
            current = {'score': .95, 'time': 1000.0, 'quality': quality or good_quality}
            names = {0: 'car', 1: 'motorcycle', 2: 'person'}
            results = [SimpleNamespace(boxes=boxes if boxes is not None else [raw('car'), raw('motorcycle', bbox=(19, 0, 39, 20))])]
            prediction = Mock(return_value=results)
            app.update(model=SimpleNamespace(predict=Mock(return_value=[]), names=names),
                vehicle_model=SimpleNamespace(predict=prediction, names=names),
                analyze_frame_quality=lambda _: current['quality'],
                extract_detections=lambda _: ([], False, 0),
                classify_crash_frame=lambda _: dict(crashClass='accident', accidentProbability=current['score']),
                find_unresolved_camera_case=lambda *a, **k: None,
                persist_sqlite_crash_case=Mock(return_value=dict(caseId='NEW', casePersistenceStatus='created')),
                log_crash_decision=lambda **k: None, log_stream=lambda *a: None,
                draw_detection_boxes_overlay=lambda frame, boxes: frame,
                build_output_url_from_base=lambda *a: None,
                cv2=SimpleNamespace(imwrite=lambda *a: False), OUTPUTS=Path('unused-test-output'),
                QUALITY_REJECTION_MESSAGES={'low_quality_blurry_frame': 'blur'})
            records = []
            sink = sink if sink is not None else SimpleNamespace(submit=records.append)
            outputs = []
            frame_sink = frame_sink if frame_sink is not None else Mock()
            with patch.object(diagnostic, '_get_sink', return_value=sink), patch.object(diagnostic, '_get_frame_sink', return_value=frame_sink), patch.object(time, 'time', side_effect=lambda: current['time']):
                for i, score in enumerate(scores):
                    current.update(score=score, time=(times[i] if times else 1000+i))
                    if box_sequences is not None:
                        results[0].boxes = box_sequences[i]
                    if qualities is not None:
                        current['quality'] = qualities[i] or good_quality
                    monitor.frame_seq = i+1
                    monitor.last_frame_at = current['time']-.01
                    monitor.latest_frame = np.zeros((80, 100, 3), dtype=np.uint8)
                    result = monitor.analyze_current_frame()
                    outputs.append((result['finalDecision'], result['consecutiveCrashHits'],
                                    result['accident_detected'], result['rejectionReason'],
                                    result['temporalCrashCandidate'], result['caseCreated']))
            return outputs, records, prediction.call_count

    def test_off_on_and_uninstrumented_decisions_identical(self):
        for scores in ([.95, .95, .89], [.95, .95, .95]):
            baseline, _, n0 = self.run_sequence(scores, False, strip=True)
            off, records_off, n1 = self.run_sequence(scores, False)
            on, records_on, n2 = self.run_sequence(scores, True)
            self.assertEqual(baseline, off)
            self.assertEqual(off, on)
            self.assertEqual((n0, n1, n2), (3, 3, 3))
            self.assertEqual(records_off, [])
            self.assertEqual(len(records_on), 3)

    def test_synchronized_frame_capture_preserves_decisions_and_sequence(self):
        frame_sink = Mock()
        off, _, n0 = self.run_sequence([.95, .95, .89], False)
        on, rows, n1 = self.run_sequence([.95, .95, .89], True,
                                         frame_capture=True, frame_sink=frame_sink)
        self.assertEqual(off, on)
        self.assertEqual(n0, n1)
        self.assertEqual(frame_sink.submit.call_count, 3)
        for number, call in enumerate(frame_sink.submit.call_args_list, 1):
            record, frame = call.args
            self.assertEqual(record['observation_sequence'], number)
            self.assertEqual(record['timestamp'], rows[number - 1]['timestamp'])
            self.assertEqual(frame.shape, (80, 100, 3))
            self.assertGreaterEqual(record['frame_snapshot_copy_ms'], 0)

    def test_qualify_qualify_fail_records_exact_reset(self):
        _, rows, _ = self.run_sequence([.95, .95, .89], True)
        self.assertEqual([(r['streak_before'], r['streak_after']) for r in rows], [(0,1), (1,2), (2,0)])
        self.assertEqual([r['streak_action'] for r in rows], ['START', 'INCREMENT', 'RESET'])
        self.assertEqual(rows[-1]['reset_reasons'], ['below_case_threshold'])
        self.assertFalse(rows[-1]['observation_qualified'])
        # Interaction is NOT a qualification gate.
        self.assertTrue(rows[-1]['motion_valid'])

    def test_three_hits_confirm_and_capture_timing(self):
        output, rows, _ = self.run_sequence([.95]*3, True)
        self.assertEqual(output[-1][0], 'confirmed_crash')
        self.assertEqual(rows[-1]['streak_action'], 'CONFIRM')
        self.assertTrue(rows[-1]['accident_detected'])
        self.assertEqual(rows[-1]['seconds_since_previous_analyzed_observation'], 1)
        for r in rows:
            self.assertTrue(r['telemetry_complete'])
            self.assertLessEqual(r['frame_receive_time'], r['inference_start'])
            self.assertLessEqual(r['inference_start'], r['inference_end'])
            self.assertLessEqual(r['inference_end'], r['decision_time'])

    @unittest.expectedFailure
    def test_distinct_physical_pairs_must_not_share_three_hit_confirmation(self):
        """Production safety gate: known failure until pair ownership is implemented."""
        pair_ab = [raw('car', bbox=(0, 0, 20, 20)), raw('car', bbox=(19, 0, 39, 20))]
        pair_cd = [raw('car', bbox=(30, 30, 50, 50)), raw('car', bbox=(49, 30, 69, 50))]
        pair_ef = [raw('car', bbox=(55, 0, 75, 20)), raw('car', bbox=(74, 0, 94, 20))]
        outcomes, rows, _ = self.run_sequence([.95] * 3, True,
                                               box_sequences=[pair_ab, pair_cd, pair_ef])
        self.assertEqual([row['observation_qualified'] for row in rows], [True] * 3)
        self.assertEqual([row['streak_after'] for row in rows], [1, 2, 3])
        self.assertNotEqual(outcomes[-1][0], 'confirmed_crash')

    def test_one_vehicle_qualifies_but_aftermath_not_confirmation(self):
        out, rows, _ = self.run_sequence([.95]*3, True, boxes=[raw('motorcycle')])
        self.assertEqual(out[-1][0], 'possible_crash_aftermath')
        self.assertFalse(out[-1][2])
        self.assertTrue(all(r['observation_qualified'] for r in rows))
        self.assertEqual(rows[-1]['qualification_failures'], [])
        self.assertEqual(rows[-1]['evaluated_pairs'], [])

    def test_vehicle_rejection_and_actual_pair_short_circuit(self):
        boxes = [raw('car'), raw('motorcycle', .3), raw('person'),
                 raw('car', bbox=(0,0,0,0)), raw('motorcycle', bbox=(19,0,39,20)),
                 raw('car', bbox=(70,60,90,80))]
        _, rows, _ = self.run_sequence([.95], True, boxes=boxes)
        self.assertEqual([v['rejection_reason'] for v in rows[0]['vehicles']],
                         [None, 'below_vehicle_confidence', 'class_not_vehicle', 'invalid_bbox', None, None])
        self.assertEqual(len(rows[0]['evaluated_pairs']), 1)
        pair = rows[0]['evaluated_pairs'][0]
        self.assertEqual(pair['vehicle_indices'], [0,1])
        self.assertTrue(pair['qualifies'])
        self.assertEqual(rows[0]['accepted_vehicles'][1]['proposal_id'], 4)

    def test_all_failing_pairs_are_logged(self):
        boxes = [raw('car', bbox=(0,0,10,10)), raw('motorcycle', bbox=(40,0,50,10)), raw('car', bbox=(80,0,90,10))]
        _, rows, _ = self.run_sequence([.95], True, boxes=boxes)
        self.assertEqual([p['vehicle_indices'] for p in rows[0]['evaluated_pairs']], [[0,1],[0,2],[1,2]])
        self.assertTrue(all(not p['qualifies'] for p in rows[0]['evaluated_pairs']))

    def test_window_expiration_is_visible_even_with_qualifying_frame(self):
        off, _, _ = self.run_sequence([.95]*3, False, times=[1000,1001,1007])
        on, rows, _ = self.run_sequence([.95]*3, True, times=[1000,1001,1007])
        self.assertEqual(off, on)
        self.assertEqual(rows[-1]['streak_action'], 'RESET')
        self.assertEqual(rows[-1]['reset_reasons'], ['temporal_window_expired'])
        self.assertEqual(rows[-1]['streak_after'], 1)
        self.assertTrue(rows[-1]['observation_qualified'])

    def test_sink_failure_cannot_change_decisions(self):
        off, _, _ = self.run_sequence([.95]*3, False)
        on, _, _ = self.run_sequence([.95]*3, True, sink=SimpleNamespace(submit=Mock(side_effect=OSError('private failure'))))
        self.assertEqual(off, on)

    def test_no_credentials_or_pixels_in_records(self):
        _, rows, _ = self.run_sequence([.95]*3, True)
        text = json.dumps(rows, allow_nan=False)
        for forbidden in ('rtsp', 'username', 'password', 'http://', 'latest_frame'):
            self.assertNotIn(forbidden, text)
        self.assertIsNone(diagnostic._identifier('rtsp://user:password@host'))

    def test_quality_vehicle_and_roi_reset_reasons(self):
        pair = [raw('car'), raw('motorcycle', bbox=(19,0,39,20))]
        bad = dict(frameQualityStatus='bad', qualityRejectionReason='low_quality_blurry_frame',
                   blurScore=1, brightnessScore=100, contrastScore=100)
        cases = [
            ({'qualities': [None, None, bad]}, ['low_quality_blurry_frame']),
            ({'box_sequences': [pair, pair, []]}, ['no_vehicle_detected']),
            ({'roi': '0,0,0.5,1', 'box_sequences': [pair, pair, [raw('car', bbox=(70,0,90,20))]]},
             ['no_vehicle_detected', 'vehicle_outside_roi']),
        ]
        for kwargs, reasons in cases:
            off, _, _ = self.run_sequence([.95]*3, False, **kwargs)
            on, rows, _ = self.run_sequence([.95]*3, True, **kwargs)
            self.assertEqual(off, on)
            self.assertEqual(rows[-1]['reset_reasons'], reasons)
            self.assertEqual(rows[-1]['streak_after'], 0)
            if 'roi' in kwargs:
                self.assertEqual(rows[-1]['vehicles'][0]['rejection_reason'], 'vehicle_outside_roi')

    def test_empty_vehicle_retry_records_both_real_passes(self):
        off, _, n0 = self.run_sequence([.95], False, boxes=[raw('motorcycle', .3)])
        on, rows, n1 = self.run_sequence([.95], True, boxes=[raw('motorcycle', .3)])
        self.assertEqual(off, on)
        self.assertEqual((n0,n1), (2,2))
        self.assertEqual(len(rows[0]['detector_passes']), 2)
        self.assertEqual([v['accepted'] for v in rows[0]['vehicles']], [False,True])
        self.assertEqual([v['acceptance_threshold'] for v in rows[0]['vehicles']], [.4,.15])

    def test_collection_failure_is_isolated_and_context_cleared(self):
        off, _, _ = self.run_sequence([.95]*3, False)
        for method in ('pair', 'decision'):
            with patch.object(diagnostic.Observation, method, side_effect=ValueError('test')):
                on, rows, _ = self.run_sequence([.95]*3, True)
            self.assertEqual(off, on)
            self.assertEqual(len(rows), 3)
            self.assertTrue(all(not r['telemetry_complete'] for r in rows))
        self.assertIsNone(diagnostic._current.get())

    def test_disabled_decorator_does_not_create_sink(self):
        @diagnostic.observe
        def work(monitor):
            diagnostic.emit('before', [])
            return 'unchanged'
        with patch.dict(os.environ, {'LIVE_COLLISION_DIAGNOSTICS': '0'}), patch.object(diagnostic, '_get_sink') as sink:
            self.assertEqual(work(SimpleNamespace()), 'unchanged')
            sink.assert_not_called()

    def test_queue_overflow_is_bounded_nonblocking(self):
        with patch.object(threading.Thread, 'start'):
            sink = diagnostic.RotatingSink()
        for n in range(9):
            sink.submit({'sequence': n})
        self.assertEqual(sink.pending.qsize(), 8)
        self.assertEqual(sink.dropped, 1)

    def test_unwritable_destination_does_not_raise_in_producer(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / 'file'
            destination.write_text('not a directory')
            sink = diagnostic.RotatingSink(destination)
            sink.submit({'sequence': 1})
            sink.pending.join()
            self.assertEqual(sink.write_errors, 1)
            sink.pending.put(None)
            sink.thread.join(3)

    def test_rotating_sink_bounded_and_valid_jsonl(self):
        with tempfile.TemporaryDirectory() as directory:
            sink = diagnostic.RotatingSink(directory, max_bytes=600, backups=2)
            for n in range(30):
                sink.submit({'observation_sequence': n, 'padding': 'x'*100})
                sink.pending.join()
            sink.pending.put(None)
            sink.thread.join(3)
            files = list(Path(directory).glob('observations.jsonl*'))
            self.assertEqual(len(files), 3)
            for p in files:
                self.assertLessEqual(p.stat().st_size, 600)
                for line in p.read_text().splitlines():
                    json.loads(line)

    def test_synchronized_frame_is_lossless_and_bound_to_decision(self):
        with tempfile.TemporaryDirectory() as directory:
            sink = diagnostic.SynchronizedFrameSink(Path(directory) / 'session')
            frame = np.arange(80 * 100 * 3, dtype=np.uint8).reshape(80, 100, 3)
            expected = frame.copy()
            record = dict(camera_id='CAM-TEST', observation_sequence=17,
                          decision_time=1000.125, timestamp='test-time',
                          vehicles=[], evaluated_pairs=[], observation_qualified=False,
                          streak_before=0, streak_after=0, streak_action='UNCHANGED')
            sink.submit(record, expected)
            sink.pending.join()
            session = Path(directory) / 'session'
            row = json.loads((session / 'observations.jsonl').read_text().strip())
            saved = session / row['frame_file']
            self.assertEqual(row['observation_sequence'], 17)
            self.assertEqual(row['decision_time'], 1000.125)
            self.assertTrue(np.array_equal(np.load(saved, allow_pickle=False), frame))
            self.assertEqual(row['frame_sha256'], __import__('hashlib').sha256(saved.read_bytes()).hexdigest())
            self.assertGreaterEqual(row['frame_save_duration_ms'], 0)
            self.assertEqual(json.loads((session / 'manifest.json').read_text())['saved_frames'], 1)
            sink.pending.put(None)
            sink.thread.join(3)

    def test_synchronized_frame_sink_is_bounded(self):
        with patch.object(threading.Thread, 'start'):
            sink = diagnostic.SynchronizedFrameSink(Path('unused-test-output'))
        frame = np.zeros((2, 2, 3), dtype=np.uint8)
        for n in range(9):
            sink.submit({'observation_sequence': n}, frame)
        self.assertEqual(sink.pending.qsize(), 8)
        self.assertEqual(sink.dropped, 1)

    def test_synchronized_writer_error_identifies_stage_without_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            sink = diagnostic.SynchronizedFrameSink(Path(directory) / 'session')
            original_replace = Path.replace

            def fail_manifest_replace(source, target):
                if source.name == 'manifest.json.tmp':
                    raise OSError(13, 'rtsp://user:password@host/private?token=SECRET')
                return original_replace(source, target)

            with patch.object(Path, 'replace', fail_manifest_replace):
                sink.submit({'camera_id': 'CAM-TEST', 'observation_sequence': 19,
                             'decision_time': 1000.5}, np.zeros((2, 2, 3), dtype=np.uint8))
                sink.pending.join()
            session = Path(directory) / 'session'
            event_text = (session / 'writer_errors.jsonl').read_text()
            event = json.loads(event_text)
            self.assertEqual((event['stage'], event['exception_type'], event['observation_sequence']),
                             ('manifest_replace', 'PermissionError', 19))
            self.assertNotIn('rtsp', event_text)
            self.assertNotIn('SECRET', event_text)
            self.assertEqual(sink.write_errors, 1)
            sink.pending.put(None)
            sink.thread.join(3)


if __name__ == '__main__':
    unittest.main()
