import unittest

from backend.services.pair_hit_ledger import PairHitLedger


class PairHitLedgerTests(unittest.TestCase):
    def test_same_pair_hits_are_order_independent_and_ready_only_at_three(self):
        ledger = PairHitLedger()
        for seq, pair in enumerate(((1, 2), (2, 1), (1, 2)), 1):
            state = ledger.observe(pair, sequence=seq, timestamp=float(seq), qualified=True)
            self.assertEqual(state.streak, seq)
        self.assertTrue(ledger.ready((2, 1)))
        self.assertEqual(list(state.qualifying_observations), [1, 2, 3])

    def test_three_different_pairs_never_share_hits(self):
        ledger = PairHitLedger()
        for seq, pair in enumerate(((1, 2), (3, 4), (5, 6)), 1):
            ledger.observe(pair, sequence=seq, timestamp=float(seq), qualified=True)
        self.assertEqual(ledger.active_pair_count, 3)
        self.assertFalse(any(ledger.ready(pair) for pair in ((1, 2), (3, 4), (5, 6))))

    def test_interleaved_pairs_keep_independent_counts(self):
        ledger = PairHitLedger()
        for seq, pair in enumerate(((1, 2), (1, 3), (1, 2)), 1):
            ledger.observe(pair, sequence=seq, timestamp=float(seq), qualified=True)
        self.assertEqual(ledger.observe((1, 2), sequence=3, timestamp=3, qualified=True).streak, 2)
        self.assertFalse(ledger.ready((1, 2)))

    def test_duplicate_negative_expiry_and_track_expiry(self):
        ledger = PairHitLedger()
        ledger.observe((1, 2), sequence=1, timestamp=1, qualified=True)
        self.assertEqual(ledger.observe((1, 2), sequence=1, timestamp=1, qualified=True).streak, 1)
        self.assertEqual(ledger.observe((1, 2), sequence=2, timestamp=2, qualified=False).streak, 0)
        ledger.observe((1, 2), sequence=3, timestamp=3, qualified=True)
        ledger.expire_track(1)
        self.assertEqual(ledger.active_pair_count, 0)
        ledger.observe((1, 2), sequence=4, timestamp=10, qualified=True)
        self.assertEqual(ledger.active_pair_count, 1)
        ledger.expire(16)
        self.assertEqual(ledger.active_pair_count, 0)

    def test_missing_participant_invalid_pair_and_bounded_growth(self):
        ledger = PairHitLedger(max_pairs=2)
        with self.assertRaises(ValueError):
            ledger.observe((1, 1), sequence=1, timestamp=1, qualified=True)
        ledger.observe((1, 2), sequence=1, timestamp=1, qualified=True)
        ledger.observe((3, 4), sequence=2, timestamp=2, qualified=True)
        ledger.observe((5, 6), sequence=3, timestamp=3, qualified=True)
        self.assertEqual(ledger.active_pair_count, 2)
        self.assertFalse(ledger.ready((1, 2)))

    def test_identity_swap_cannot_inherit_old_pair_key(self):
        ledger = PairHitLedger()
        ledger.observe((1, 2), sequence=1, timestamp=1, qualified=True)
        ledger.expire_track(2)  # caller must revoke the compromised track identity
        ledger.observe((1, 3), sequence=2, timestamp=2, qualified=True)
        self.assertEqual(ledger.active_pair_count, 1)
        self.assertFalse(ledger.ready((1, 3)))
