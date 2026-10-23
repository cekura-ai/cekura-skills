"""A smaller proposal request must retain every original observation."""
import copy
import json
import unittest

from experiments.scenario_skills.proposal_transport.history import REFERENCE, decode, encode
from experiments.scenario_skills.proposer import training_payload


class HistoryTransportTests(unittest.TestCase):
    def test_cache_reuse_does_not_change_training_identity_or_original_evidence(self):
        row = {"split": "training", "task_id": "case", "trace": [], "initial_state": {},
               "final_state": {}, "grade": {"score": 1}, "candidate_body": "instructions", "cache_hit": False}
        normalized = training_payload([row])
        self.assertEqual(normalized, training_payload([dict(row, cache_hit=True)]))
        self.assertEqual(normalized[0]["grade"], {"score": 1})
        self.assertNotIn("cache_hit", normalized[0])
        self.assertFalse(row["cache_hit"])

    def test_full_unicode_traces_and_candidate_bodies_round_trip_without_case_loss(self):
        text = 'café "original"\n' * 1000
        history = [{"task_id": str(i), "candidate_body": text,
                    "trace": [{"arguments": {"instructions": text}, "response": text}],
                    "final_state": {"instructions": text}, "split": "training"} for i in range(24)]
        frozen = copy.deepcopy(history)
        packet = encode(history)
        self.assertEqual(decode(packet), frozen)
        self.assertEqual(history, frozen)
        self.assertLess(len(json.dumps(packet)), len(json.dumps(history)) // 10)
        self.assertEqual(len(packet["records"]), 24)
        self.assertEqual(len(packet["shared_text"]), 1)

    def test_corrupt_shared_text_and_reference_collisions_are_rejected(self):
        packet = encode(["policy" * 100] * 2)
        identifier = next(iter(packet["shared_text"]))
        packet["shared_text"][identifier] += "changed"
        with self.assertRaises(ValueError):
            decode(packet)
        with self.assertRaises(ValueError):
            encode([{REFERENCE: "existing customer data"}])


if __name__ == "__main__":
    unittest.main()
