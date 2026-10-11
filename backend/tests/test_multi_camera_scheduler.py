import unittest

from backend.services.inference_execution import FairLatestFrameScheduler


class FairLatestFrameSchedulerTests(unittest.TestCase):
    def setUp(self):
        self.scheduler = FairLatestFrameScheduler(autostart=False)
        self.calls = []

    def submit(self, camera, session, sequence):
        self.scheduler.submit(
            camera, session, sequence,
            lambda: self.calls.append((camera, session, sequence)),
        )

    def test_latest_frame_replaces_without_unbounded_queue(self):
        for sequence in range(1, 101):
            self.submit("FAST", "S1", sequence)
        self.assertEqual(self.scheduler.pending_count(), 1)
        self.assertEqual(self.scheduler.run_next(), ("FAST", "S1", 100))
        self.assertEqual(self.calls, [("FAST", "S1", 100)])

    def test_waiting_camera_keeps_round_robin_position(self):
        self.submit("FAST", "F1", 1)
        self.submit("SLOW", "S1", 1)
        self.submit("FAST", "F1", 2)
        self.assertEqual(self.scheduler.run_next(), ("FAST", "F1", 2))
        self.submit("FAST", "F1", 3)
        self.assertEqual(self.scheduler.run_next(), ("SLOW", "S1", 1))
        self.assertEqual(self.scheduler.run_next(), ("FAST", "F1", 3))

    def test_camera_and_session_are_independent_and_cancellable(self):
        self.submit("A", "OLD", 4)
        self.submit("B", "B1", 7)
        self.scheduler.cancel("A", "OLD")
        self.submit("A", "NEW", 1)
        self.assertEqual(self.scheduler.run_next(), ("B", "B1", 7))
        self.assertEqual(self.scheduler.run_next(), ("A", "NEW", 1))
        self.assertEqual(self.calls, [("B", "B1", 7), ("A", "NEW", 1)])

    def test_three_cameras_remain_bounded_and_keep_first_waiting_order(self):
        self.submit("A", "A1", 1)
        self.submit("B", "B1", 1)
        self.submit("C", "C1", 1)
        self.submit("A", "A1", 9)
        self.submit("B", "B1", 4)
        self.assertEqual(self.scheduler.pending_count(), 3)
        self.assertEqual(self.scheduler.run_next(), ("A", "A1", 9))
        self.assertEqual(self.scheduler.run_next(), ("B", "B1", 4))
        self.assertEqual(self.scheduler.run_next(), ("C", "C1", 1))


if __name__ == "__main__":
    unittest.main()
