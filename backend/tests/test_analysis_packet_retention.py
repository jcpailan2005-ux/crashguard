"""Exact-frame delivery can be stale without becoming live tracking evidence."""
import base64
import json
import time
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from backend.validation.live_cctv_implementation_stage1_20261001.test_stage1 import worker, frame


class AnalysisPacketRetentionTests(unittest.TestCase):
    def prepare(self):
        monitor, namespace = worker()
        namespace.update(base64=base64, json=json)
        monitor.seed_first_frame(frame(80))
        monitor.analyze_current_frame()
        source, metadata, published = monitor.latest_box_frame
        metadata['boxes'] = [{'label': 'car', 'confidence': .9, 'x': 10, 'y': 12, 'width': 20, 'height': 22}]
        monitor.latest_box_frame = (source, metadata, published)
        return monitor, namespace, published

    def test_delayed_packet_keeps_exact_pixels_boxes_and_marks_freshness_expired(self):
        monitor, namespace, published = self.prepare()
        with patch.object(namespace['time'], 'perf_counter', return_value=published + 1.2):
            packet = monitor.latest_box_packet()
        self.assertIsNotNone(packet)
        self.assertEqual(packet['validForMs'], 0)
        self.assertAlmostEqual(packet['retentionForMs'], 3800, places=3)
        self.assertEqual(packet['boxes'], monitor.latest_box_frame[1]['boxes'])
        self.assertEqual(packet['sourceFrame'], monitor.latest_box_frame[1]['sourceFrame'])
        pixels = cv2.imdecode(np.frombuffer(base64.b64decode(packet['imageDataUrl'].split(',', 1)[1]), np.uint8), 1)
        self.assertEqual(pixels.shape, (48, 64, 3))
        namespace['persist_sqlite_crash_case'].assert_not_called()

    def test_delivery_expiration_is_bounded_at_five_seconds(self):
        monitor, namespace, published = self.prepare()
        with patch.object(namespace['time'], 'perf_counter', return_value=published + 5):
            self.assertIsNone(monitor.latest_box_packet())

    def test_reconnection_cannot_deliver_retired_epoch(self):
        monitor, _, _ = self.prepare()
        monitor.frame_epoch = 'replacement-session'
        self.assertIsNone(monitor.latest_box_packet())

    def test_fresh_packet_has_both_independent_deadlines(self):
        monitor, namespace, published = self.prepare()
        with patch.object(namespace['time'], 'perf_counter', return_value=published + .1):
            packet = monitor.latest_box_packet()
        self.assertAlmostEqual(packet['validForMs'], 400, places=3)
        self.assertAlmostEqual(packet['retentionForMs'], 4900, places=3)


if __name__ == '__main__':
    unittest.main()
