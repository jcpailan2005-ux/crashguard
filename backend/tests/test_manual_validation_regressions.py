"""Confirmation presentation and exact evidence at the real live-worker boundary."""
import base64
import json
from pathlib import Path
import time
import unittest
from unittest.mock import Mock, patch

from backend.validation.live_cctv_implementation_stage1_20261001.test_stage1 import worker, frame


class ManualValidationTests(unittest.TestCase):
    def confirmed_frame(self):
        monitor, ns = worker(camera_id='CAM-EXACT')
        monitor.seed_first_frame(frame(80))
        box = dict(label='car', classId=2, confidence=.96, x=10, y=12, width=20, height=22)
        ns.update(OUTPUTS=Path('unused-test-output'), base64=base64, json=json,
                  detect_vehicle_boxes=lambda *a, **k: [box],
                  classify_crash_frame=lambda _: dict(crashClass='accident', accidentProbability=.99),
                  draw_detection_boxes_overlay=Mock(side_effect=lambda pixels, boxes: pixels),
                  build_output_url_from_base=lambda base, name: base + '/outputs/' + name,
                  persist_sqlite_crash_case=Mock(return_value=dict(caseId='EXACT', incidentId='EXACT',
                      incidentCreated=True, casePersistenceStatus='created', detectionMode='temporal_collision')))
        # Verification itself has separate real-trajectory tests. This fixture
        # begins at the already-confirmed boundary reproduced by manual testing.
        monitor.collision_session.observe = Mock(return_value=dict(
            temporalCrashVerified=True, temporalCrashCandidate=False, aftermathCandidate=False,
            detectorEventId='CONFIRMATION', trackingSessionId=monitor.frame_epoch, involvedTrackIds=[1, 2]))
        with patch.object(ns['cv2'], 'imwrite', return_value=True):
            result = monitor.analyze_current_frame()
        return monitor, ns, result

    def test_confirmation_survives_next_candidate_and_reaches_status_and_sse(self):
        monitor, ns, result = self.confirmed_frame()
        monitor.collision_session.observe.return_value.update(temporalCrashVerified=False, temporalCrashCandidate=True)
        monitor.seed_first_frame(frame(120))
        candidate = monitor.analyze_current_frame()
        self.assertEqual(candidate['finalDecision'], 'candidate')
        status = monitor.snapshot_status()
        self.assertIs(status['latestResult'], candidate)
        receipt = status['collisionConfirmation']
        self.assertEqual(receipt['result'], result)
        self.assertEqual(receipt['result']['sourceFrame']['cameraId'], 'CAM-EXACT')
        monitor.running = True
        stream = monitor.detection_events()
        try:
            payload = json.loads(next(stream).split('data: ', 1)[1])
            self.assertEqual(payload['collisionConfirmation'], receipt)
        finally:
            stream.close()
            monitor.running = False
        with patch.object(ns['time'], 'time', return_value=receipt['expiresAt'] + .1):
            self.assertIsNone(monitor.snapshot_status()['collisionConfirmation'])
        monitor.frame_epoch = 'REPLACEMENT'
        self.assertIsNone(monitor.snapshot_status()['collisionConfirmation'])

    def test_saved_boxes_and_annotation_are_from_exact_analyzed_frame(self):
        monitor, ns, result = self.confirmed_frame()
        saved = ns['persist_sqlite_crash_case'].call_args.kwargs
        self.assertEqual(saved['boxes'], result['boxes'])
        self.assertEqual(saved['temporal_evidence']['boxes'], result['boxes'])
        self.assertEqual(saved['temporal_evidence']['sourceFrame'], result['sourceFrame'])
        box = saved['boxes'][0]
        self.assertEqual((box['label'], box['classId'], box['confidence']), ('car', 2, .96))
        self.assertEqual(box['sequence'], result['sourceFrame']['sequence'])
        self.assertEqual(box['sessionId'], result['sourceFrame']['sessionId'])
        self.assertIsInstance(box['trackId'], int)
        pixels, annotated_boxes = ns['draw_detection_boxes_overlay'].call_args.args
        self.assertEqual(pixels.shape, (48, 64, 3))
        self.assertEqual(int(pixels[0, 0, 0]), 80)
        self.assertEqual(annotated_boxes, saved['boxes'])
        monitor.seed_first_frame(frame(200))
        self.assertEqual(saved['temporal_evidence']['sourceFrame']['sequence'], 1)
        self.assertEqual(saved['boxes'][0]['sequence'], 1)

    def test_aftermath_and_stop_clear_the_confirmation_receipt(self):
        monitor, ns, _ = self.confirmed_frame()
        monitor.collision_session.observe.return_value.update(temporalCrashVerified=False,
            aftermathCandidate=True, detectorEventId='AFTERMATH')
        monitor.seed_first_frame(frame(100))
        with patch.object(ns['cv2'], 'imwrite', return_value=True):
            result = monitor.analyze_current_frame()
        self.assertEqual(result['finalDecision'], 'possible_crash_aftermath')
        self.assertIsNone(monitor.collision_confirmation)
        monitor, _, _ = self.confirmed_frame()
        monitor.stop()
        self.assertIsNone(monitor.collision_confirmation)


if __name__ == '__main__':
    unittest.main()
