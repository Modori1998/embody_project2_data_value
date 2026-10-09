from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from project2_mvp.core_retrieval import (
    build_blind_audit_items,
    candidate_segment_rows,
    select_query_segments,
)


def segment(episode: str, number: int, transition: bool) -> dict:
    return {
        "source_episode_id": episode,
        "segment_id": f"{episode.split('/')[-1]}-S{number:04d}",
        "gripper_transition_present": transition,
    }


class FormalCoreRetrievalTests(unittest.TestCase):
    def test_query_assignment_balance_fallback_and_selection_are_deterministic(self) -> None:
        episodes = [f"data/demo_{index}" for index in range(9)]
        rows = [segment(episodes[0], 1, True), segment(episodes[1], 1, False)]
        for episode in episodes[2:]:
            rows.extend((segment(episode, 1, True), segment(episode, 2, False)))
        first, balance = select_query_segments(rows, episodes, cohort="CALIBRATION_QUERY", target_true=4)
        second, second_balance = select_query_segments(list(reversed(rows)), episodes, cohort="CALIBRATION_QUERY", target_true=4)
        self.assertEqual(first, second)
        self.assertEqual(balance, {"TRUE": 4, "FALSE": 5})
        self.assertEqual(balance, second_balance)
        self.assertEqual(len({row["episode_id"] for row in first}), 9)

        forced_rows = [segment(episode, 1, True) for episode in episodes[:6]]
        forced_rows += [segment(episode, 1, False) for episode in episodes[6:]]
        _, forced_balance = select_query_segments(
            forced_rows, episodes, cohort="CALIBRATION_QUERY", target_true=4
        )
        self.assertEqual(forced_balance, {"TRUE": 6, "FALSE": 3})

    def test_final_target_balance(self) -> None:
        episodes = [f"data/demo_{index}" for index in range(18)]
        rows = [item for episode in episodes for item in (segment(episode, 1, True), segment(episode, 2, False))]
        selected, balance = select_query_segments(rows, episodes, cohort="FINAL_QUERY", target_true=9)
        self.assertEqual(len(selected), 18)
        self.assertEqual(balance, {"TRUE": 9, "FALSE": 9})

    def test_blind_union_repeat_selection_order_and_method_hiding(self) -> None:
        motion = []
        visual = []
        for query in range(3):
            for rank in range(5):
                motion.append({"query_segment_id": f"q{query}", "candidate_segment_id": f"m{query}-{rank}", "rank": rank + 1, "similarity": 0.9})
                visual.append({"query_segment_id": f"q{query}", "candidate_segment_id": f"v{query}-{rank}", "rank": rank + 1, "similarity": 0.8})
        first, repeats, unique = build_blind_audit_items(motion, visual)
        second, repeats2, unique2 = build_blind_audit_items(list(reversed(motion)), list(reversed(visual)))
        self.assertEqual((first, repeats, unique), (second, repeats2, unique2))
        self.assertEqual(len(repeats), 12)
        self.assertEqual(len(first), unique + 12)
        self.assertTrue(all(set(row) == {"audit_order", "audit_item_id", "query_segment_id", "candidate_segment_id"} for row in first))

    def test_stage1_scope_declares_no_final_retrieval(self) -> None:
        runner = (Path(__file__).resolve().parents[1] / "scripts/run_mvp_core_retrieval_formal_stage1.py").read_text(encoding="utf-8")
        self.assertIn('"final_retrieval_executed": False', runner)

    def test_candidate_only_scaler_and_index_source_isolation(self) -> None:
        rows = [
            segment("data/candidate", 1, True),
            segment("data/calibration", 1, False),
            segment("data/final", 1, True),
        ]
        selected = candidate_segment_rows(rows, ["data/candidate"])
        self.assertEqual([row["source_episode_id"] for row in selected], ["data/candidate"])


if __name__ == "__main__":
    unittest.main()
