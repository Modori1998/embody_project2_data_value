from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from build_mvp_calibration_temporal_audit import existing_segment_gif_paths, sampled_indices


class CalibrationTemporalAuditTests(unittest.TestCase):
    def test_uniform_temporal_sampling_keeps_segment_endpoints(self) -> None:
        self.assertEqual(sampled_indices(10, 20, 20.0, 10.0), [10, 12, 14, 16, 18, 20])
        self.assertEqual(sampled_indices(10, 19, 20.0, 10.0), [10, 12, 14, 16, 18, 19])
        self.assertEqual(sampled_indices(7, 7, 20.0, 10.0), [7])

    def test_existing_segment_gif_paths_reuses_manifest(self) -> None:
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            gif = output / "segment_gifs/demo_1/demo_1-S0001.gif"
            gif.parent.mkdir(parents=True)
            gif.write_bytes(b"GIF89a")
            (output / "segment_gif_manifest.json").write_text(
                json.dumps(
                    [
                        {
                            "segment_id": "demo_1-S0001",
                            "gif_relpath": "segment_gifs/demo_1/demo_1-S0001.gif",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                existing_segment_gif_paths(output),
                {"demo_1-S0001": "segment_gifs/demo_1/demo_1-S0001.gif"},
            )

    def test_temporal_evidence_addendum_is_frozen(self) -> None:
        path = ROOT / "0-doc/10-design-review/Project2_MVP_Human_Audit_Temporal_Evidence_Addendum_FROZEN_v1_20261010.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn("DOCUMENT_STATUS = FROZEN_v1", text)
        self.assertIn("RETRIEVAL_RERUN = NO", text)
        self.assertIn("HUMAN_LABELS_STARTED = NO", text)


if __name__ == "__main__":
    unittest.main()
