from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from build_mvp_calibration_unsure_reaudit import (
    EXPECTED_FIRST_PASS_ITEMS,
    EXPECTED_UNSURE_ITEMS,
    select_unsure_rows,
)


class CalibrationUnsureReauditTests(unittest.TestCase):
    def test_selects_exact_unsure_items_and_blanks_prior_labels(self) -> None:
        rows = []
        for index in range(EXPECTED_FIRST_PASS_ITEMS):
            rows.append(
                {
                    "audit_item_id": f"CAL-{index + 1:04d}",
                    "query_segment_id": f"q{index}",
                    "candidate_segment_id": f"c{index}",
                    "review_label": "UNSURE" if index < EXPECTED_UNSURE_ITEMS else "RELEVANT",
                    "query_bad_segment": "",
                }
            )
        selected = select_unsure_rows(rows)
        self.assertEqual(len(selected), EXPECTED_UNSURE_ITEMS)
        self.assertTrue(all(row["review_label"] == "" for row in selected))
        self.assertTrue(all(row["query_bad_segment"] == "" for row in selected))


if __name__ == "__main__":
    unittest.main()
