"""Contract tests for the immutable Fresh Calibration baseline Audit Run."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastapi.testclient import TestClient

from project2_g1.fresh_calibration_run import (
    EXPECTED_CONFIG_HASH,
    EXPECTED_SIGNAL_HASH,
    compare_screening,
)
from project2_g1_audit_web.app import create_app
from project2_g1_audit_web.contract import validate_g1_audit_folder
from project2_g1_audit_web.hashes import config_hash_from_path


def _calibration_record() -> tuple[str, dict]:
    registry = json.loads((ROOT / "outputs/g1_audit_web/g1_audit_run_registry.json").read_text(encoding="utf-8"))
    readable: list[tuple[str, dict]] = []
    for rid, row in registry["runs"].items():
        if row.get("run_stage") != "CALIBRATION":
            continue
        meta = Path(row["audit_folder_path"]) / "run_meta.json"
        try:
            exists = meta.is_file()
        except OSError:
            continue
        if exists:
            readable.append((rid, row))
    if not readable:
        raise AssertionError("no readable CALIBRATION run in registry")
    readable.sort(key=lambda item: str(item[1].get("created_at") or ""))
    return readable[-1]


class FreshCalibrationRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            (ROOT / "outputs/g1_p3_calibration_selection/fresh_calibration_manifest_v1.json").read_text(encoding="utf-8")
        )
        cls.run_id, cls.record = _calibration_record()
        cls.run_root = Path(cls.record["audit_folder_path"])
        cls.loaded = validate_g1_audit_folder(cls.run_root)

    def test_manifest_exact_set_stage_role_and_no_seed_overlap(self) -> None:
        actual = {row["episode_id"] for row in self.loaded["episodes"]}
        self.assertEqual(actual, set(self.manifest["fresh_episode_ids"]))
        self.assertEqual(len(actual), 6)
        self.assertFalse(actual & set(self.manifest["existing_seed_episode_ids"]))
        self.assertEqual(self.loaded["run_meta"]["run_stage"], "CALIBRATION")
        self.assertEqual({row["set_role"] for row in self.loaded["episodes"]}, {"CALIBRATION"})

    def test_baseline_identity_parameter_zero_and_materialized_final(self) -> None:
        meta = self.loaded["run_meta"]
        self.assertEqual(meta["config_hash"], EXPECTED_CONFIG_HASH)
        self.assertEqual(meta["signal_contract_hash"], EXPECTED_SIGNAL_HASH)
        self.assertEqual(meta["parameter_diff_count"], 0)
        self.assertFalse(meta["parameter_search_executed"])
        self.assertEqual(meta["final_boundary_semantics"], "MATERIALIZED_V1")
        self.assertEqual(self.loaded["final_member_semantics"], "MATERIALIZED")
        self.assertEqual(config_hash_from_path(self.run_root / "config_snapshot.json"), EXPECTED_CONFIG_HASH)

    def test_screening_formal_run_consistency(self) -> None:
        formal = {}
        for row in self.loaded["episodes"]:
            with (self.run_root / row["boundaries_relpath"]).open("r", encoding="utf-8", newline="") as handle:
                finals = list(csv.DictReader(handle))
            with (self.run_root / row["segments_relpath"]).open("r", encoding="utf-8", newline="") as handle:
                segments = list(csv.DictReader(handle))
            counts = {}
            for item in finals:
                counts[item["candidate_type"]] = counts.get(item["candidate_type"], 0) + 1
            formal[row["episode_id"]] = {
                "episode_length": int(row["length"]),
                "candidate_count": int(row["candidate_count"]),
                "final_boundary_count": int(row["final_boundary_count"]),
                "gripper_primary_count": counts.get("GRIPPER_TRANSITION", 0),
                "direction_primary_count": counts.get("DIRECTION_CHANGE", 0),
                "merged_boundary_count": sum(int(item["member_candidate_count"]) > 1 for item in finals),
                "short_segment_count": sum(item["short_segment_flag"].lower() == "true" for item in segments),
            }
        check = compare_screening(
            formal, ROOT / "outputs/g1_p3_calibration_selection/fresh_calibration_screening_v1_20260917.csv"
        )
        self.assertEqual(check, {"status": "PASS", "differences": []})

    def test_registry_and_no_export_or_gt_artifacts(self) -> None:
        self.assertEqual(self.record["status"], "AUTO_REGISTERED")
        self.assertTrue(self.record["enabled"])
        forbidden = {
            "canonical_human_boundary_gt.csv", "known_false_positive_anchor.csv",
            "matching_result.csv", "human_calibration_export",
        }
        self.assertFalse({path.name for path in self.run_root.rglob("*")} & forbidden)

    def test_web_loads_all_six_as_not_reviewed_using_temp_db(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            db = temp_root / "owner.sqlite3"
            shutil.copy2(ROOT / "outputs/g1_audit_web/g1_audit_web_owner.sqlite3", db)
            before = hashlib.sha256(db.read_bytes()).hexdigest()
            app = create_app(project_root=ROOT, owner_db_path=db, proxy_cache_root=temp_root / "proxy")
            client = TestClient(app)
            home = client.get("/")
            self.assertEqual(home.status_code, 200)
            self.assertIn(self.run_id, home.text)
            for episode_id in self.manifest["fresh_episode_ids"]:
                page = client.get(f"/audit/{self.run_id}/episode/{episode_id.replace('/', '--')}")
                self.assertEqual(page.status_code, 200)
                self.assertIn("BASELINE HUMAN AUDIT", page.text)
                self.assertIn("NOT_REVIEWED", page.text)
                self.assertIn("Merged Evidence", page.text)
                video_match = re.search(r'<video[^>]+src="([^"]+)"', page.text)
                self.assertIsNotNone(video_match)
                video = client.get(video_match.group(1), headers={"Range": "bytes=0-1023"})
                self.assertIn(video.status_code, {200, 206})
                self.assertTrue(video.headers.get("content-type", "").startswith("video/mp4"))
                encoded = episode_id.replace("/", "--")
                for media_key in ("signal_plot", "signal_boundary_plot"):
                    media = client.get(f"/media/{self.run_id}/{encoded}/{media_key}")
                    self.assertEqual(media.status_code, 200)
                    self.assertEqual(media.headers.get("content-type"), "image/png")
            self.assertEqual(hashlib.sha256(db.read_bytes()).hexdigest(), before)


if __name__ == "__main__":
    unittest.main()
