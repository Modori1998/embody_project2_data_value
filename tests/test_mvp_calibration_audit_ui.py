from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from build_mvp_calibration_audit_ui import build_page


class CalibrationAuditUITests(unittest.TestCase):
    def test_interactive_blind_page_contract(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            formal = root / "formal"
            formal.mkdir()
            fields = [
                "audit_order", "audit_item_id", "query_segment_id", "candidate_segment_id",
                "query_duration_sec", "query_gripper_start_state", "query_gripper_end_state",
                "query_gripper_transition_present", "query_eef_displacement_xyz",
                "query_coarse_direction_change_rad", "candidate_duration_sec",
                "candidate_gripper_start_state", "candidate_gripper_end_state",
                "candidate_gripper_transition_present", "candidate_eef_displacement_xyz",
                "candidate_coarse_direction_change_rad", "review_label", "query_bad_segment",
            ]
            with (formal / "calibration_human_audit_pairs.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerow({field: "" for field in fields} | {"audit_order": "1", "audit_item_id": "CAL-0001", "query_segment_id": "q1", "candidate_segment_id": "c1"})
            (formal / "m2").mkdir()
            (formal / "m2/q.png").touch()
            (formal / "m2/c.png").touch()
            with (formal / "m2/keyframe_manifest.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["segment_id", "source_episode_id", "frame_index", "roles", "png_relpath"])
                writer.writeheader()
                writer.writerows([
                    {"segment_id": "q1", "source_episode_id": "e1", "frame_index": "0", "roles": "START", "png_relpath": "q.png"},
                    {"segment_id": "c1", "source_episode_id": "e2", "frame_index": "0", "roles": "START", "png_relpath": "c.png"},
                ])
            output = root / "ui"
            result = build_page(formal, output)
            page = (output / "index.html").read_text(encoding="utf-8")
            self.assertEqual(result["audit_items"], 1)
            for label in ("RELEVANT", "PARTIAL", "NOT_RELEVANT", "BAD_SEGMENT", "UNSURE"):
                self.assertIn(label, page)
            for text in ("上一条", "下一条", "未完成", "导出填写好的 CSV", "localStorage"):
                self.assertIn(text, page)
            self.assertNotIn("hidden_repeat", page)
            self.assertNotIn("copy_index", page)


if __name__ == "__main__":
    unittest.main()
