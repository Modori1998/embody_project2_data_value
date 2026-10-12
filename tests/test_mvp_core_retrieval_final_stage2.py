from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from project2_mvp.core_retrieval import build_blind_audit_items


class FinalStage2ContractTests(unittest.TestCase):
    def test_final_blind_order_uses_final_cohort_and_fin_ids(self) -> None:
        motion = []
        visual = []
        for query in range(18):
            for rank in range(5):
                motion.append(
                    {
                        "query_segment_id": f"q{query}",
                        "candidate_segment_id": f"m{query}-{rank}",
                    }
                )
                visual.append(
                    {
                        "query_segment_id": f"q{query}",
                        "candidate_segment_id": f"v{query}-{rank}",
                    }
                )
        items, repeats, unique = build_blind_audit_items(
            motion,
            visual,
            cohort="FINAL",
            item_prefix="FIN",
        )
        self.assertEqual(len(repeats), 12)
        self.assertEqual(len(items), unique + 12)
        self.assertTrue(all(row["audit_item_id"].startswith("FIN-") for row in items))

    def test_stage2_runner_does_not_compute_p5(self) -> None:
        text = (
            ROOT / "scripts/run_mvp_core_retrieval_formal_stage2_final.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"p5_computed": False', text)
        self.assertIn('cohort="FINAL"', text)
        self.assertIn('item_prefix="FIN"', text)

    def test_final_temporal_audit_is_human_only(self) -> None:
        text = (
            ROOT / "scripts/build_mvp_final_temporal_audit.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"retrieval_input": False', text)
        self.assertIn('"gif_evidence_is_retrieval_input": False', text)


if __name__ == "__main__":
    unittest.main()
