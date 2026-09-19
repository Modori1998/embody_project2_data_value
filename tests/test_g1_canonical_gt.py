"""Contract tests for Combined Canonical Human Boundary GT snapshot builder."""

from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from project2_g1.canonical_gt import (
    ADDED_FIELDS,
    CANONICAL_GT_FIELDS,
    CanonicalGTBlocked,
    DATA_FILES,
    KNOWN_FP_FIELDS,
    PREDICTED_FIELDS,
    SIGNAL_FIELDS,
    SIGNAL_NAMES,
    build_combined_canonical_gt,
    classify_protected_class,
    validate_export_disk,
    SEED_ROLE,
    FRESH_ROLE,
)
from project2_g1_audit_web.hashes import sha256_file, tree_fingerprint


def _write_csv(path: Path, fieldnames: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _signals(export_id: str, run_id: str, episode_ids: list[str], *, decision: str = "PASS") -> list[dict[str, str]]:
    rows = []
    review_id = 1
    for episode_id in episode_ids:
        for name in SIGNAL_NAMES:
            rows.append({
                "export_id": export_id, "episode_id": episode_id,
                "signal_contract_version": "g1_p1_signal_contract.v0",
                "signal_contract_hash": "24c62aef1f7bdbd14f0c1a075e8ecaafa762d4bcce454ad25842d54a2f34232d",
                "signal_name": name, "decision": decision, "comment": "",
                "effective_review_id": str(review_id), "reviewer": "TEST",
                "reviewed_at": "2026-09-18T00:00:00+08:00",
                "review_origin": "DIRECT_REVIEW", "review_source_run_id": run_id,
            })
            review_id += 1
    return rows


def _predicted(
    export_id: str, run_id: str, episode_id: str, boundary: str, frame: int, *,
    decision: str, candidate_type: str = "GRIPPER_TRANSITION",
    members: str | None = None, count: int = 1, reason: str = "", corrected: str = "",
    review_id: str = "1",
) -> dict[str, str]:
    member_types = members or candidate_type
    return {
        "export_id": export_id, "source_run_id": run_id, "episode_id": episode_id,
        "boundary_id": boundary, "predicted_frame": str(frame),
        "candidate_type": candidate_type, "representative_candidate_id": boundary.replace("B", "C"),
        "member_candidate_ids": boundary.replace("B", "C"),
        "member_candidate_types": member_types, "member_candidate_frames": str(frame),
        "member_candidate_count": str(count), "human_decision": decision,
        "reason_code": reason, "corrected_frame": corrected, "comment": "",
        "effective_review_id": review_id, "reviewer": "TEST",
        "reviewed_at": "2026-09-18T00:00:00+08:00",
    }


def write_export(
    root: Path, *, export_id: str, run_id: str, role: dict, episode_ids: list[str],
    predicted: list[dict[str, str]], added: list[dict[str, str]] | None = None,
    signal_decision: str = "PASS", extra_meta: dict | None = None,
) -> Path:
    path = root / export_id
    path.mkdir(parents=True)
    added = list(added or [])
    signals = _signals(export_id, run_id, episode_ids, decision=signal_decision)
    _write_csv(path / DATA_FILES[0], SIGNAL_FIELDS, signals)
    _write_csv(path / DATA_FILES[1], PREDICTED_FIELDS, predicted)
    _write_csv(path / DATA_FILES[2], ADDED_FIELDS, added)
    meta = {
        "export_contract": "P2_G1_HUMAN_CALIBRATION_EXPORT_V1",
        "export_id": export_id,
        "source_run_id": run_id,
        "source_run_stage": role["source_run_stage"],
        "source_set_role": role["source_set_role"],
        "episode_count": len(episode_ids),
        "signal_review_row_count": len(signals),
        "predicted_boundary_review_row_count": len(predicted),
        "human_added_boundary_row_count": len(added),
        "intended_role": role["intended_role"],
        "must_not_feed_evaluation": True,
        "files_sha256": {name: sha256_file(path / name) for name in DATA_FILES},
    }
    if role.get("calibration_role"):
        meta["calibration_role"] = role["calibration_role"]
        meta["calibration_config_role"] = role["calibration_config_role"]
    if extra_meta:
        meta.update(extra_meta)
        meta["files_sha256"] = {name: sha256_file(path / name) for name in DATA_FILES}
    (path / "export_meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return path


def _pair(tmp: Path, seed_kwargs: dict, fresh_kwargs: dict) -> tuple[Path, Path, Path]:
    seed = write_export(tmp, **seed_kwargs)
    fresh = write_export(tmp, **fresh_kwargs)
    return seed, fresh, tmp / "snapshots"


class CanonicalGTTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _seed_fresh(
        self, *, seed_pred: list[dict[str, str]], fresh_pred: list[dict[str, str]],
        seed_added: list[dict[str, str]] | None = None,
        fresh_added: list[dict[str, str]] | None = None,
        seed_episodes: list[str] | None = None,
        fresh_episodes: list[str] | None = None,
        seed_signals: str = "PASS",
        fresh_signals: str = "PASS",
        seed_extra: dict | None = None,
        fresh_extra: dict | None = None,
    ) -> tuple[Path, Path, Path]:
        seed_episodes = seed_episodes or ["data/demo_s0", "data/demo_s1"]
        fresh_episodes = fresh_episodes or ["data/demo_f0", "data/demo_f1"]
        seed = write_export(
            self.root, export_id="g1_cal_seed_export_test", run_id="g1_exploratory_audit_test",
            role=SEED_ROLE, episode_ids=seed_episodes, predicted=seed_pred, added=seed_added,
            signal_decision=seed_signals, extra_meta=seed_extra,
        )
        fresh = write_export(
            self.root, export_id="g1_cal_export_test", run_id="g1_calibration_test",
            role=FRESH_ROLE, episode_ids=fresh_episodes, predicted=fresh_pred, added=fresh_added,
            signal_decision=fresh_signals, extra_meta=fresh_extra,
        )
        return seed, fresh, self.root / "snapshots"

    def _build(self, seed: Path, fresh: Path, snapshots: Path, **kwargs):
        return build_combined_canonical_gt(
            seed_export_path=seed, fresh_export_path=fresh, snapshot_root=snapshots,
            required_seed_count=kwargs.pop("required_seed_count", 2),
            required_fresh_count=kwargs.pop("required_fresh_count", 2),
            **kwargs,
        )

    def test_valid_becomes_gt_redundant_becomes_fp_only(self) -> None:
        seed_pred = [
            _predicted("g1_cal_seed_export_test", "g1_exploratory_audit_test", "data/demo_s0", "demo_s0-B0001", 4, decision="VALID"),
            _predicted("g1_cal_seed_export_test", "g1_exploratory_audit_test", "data/demo_s0", "demo_s0-B0002", 10, decision="REDUNDANT", candidate_type="DIRECTION_CHANGE", reason="REDUNDANT_DIRECTION_JITTER", review_id="2"),
            _predicted("g1_cal_seed_export_test", "g1_exploratory_audit_test", "data/demo_s1", "demo_s1-B0001", 7, decision="VALID", review_id="3"),
        ]
        fresh_pred = [
            _predicted("g1_cal_export_test", "g1_calibration_test", "data/demo_f0", "demo_f0-B0001", 3, decision="VALID"),
            _predicted("g1_cal_export_test", "g1_calibration_test", "data/demo_f1", "demo_f1-B0001", 8, decision="REDUNDANT", candidate_type="DIRECTION_CHANGE", reason="REDUNDANT_SHORT_PAUSE", review_id="2"),
        ]
        seed, fresh, snapshots = self._seed_fresh(seed_pred=seed_pred, fresh_pred=fresh_pred)
        result = self._build(seed, fresh, snapshots)
        gt = list(csv.DictReader((Path(result["snapshot_path"]) / "canonical_human_boundary_gt.csv").open(encoding="utf-8")))
        fp = list(csv.DictReader((Path(result["snapshot_path"]) / "known_false_positive_anchor.csv").open(encoding="utf-8")))
        self.assertEqual([row["gt_source"] for row in gt], ["VALID_INHERIT"] * 3)
        self.assertEqual({int(row["gt_frame"]) for row in gt}, {4, 7, 3})
        self.assertEqual(len(fp), 2)
        self.assertEqual({row["episode_id"] for row in fp}, {"data/demo_s0", "data/demo_f1"})
        self.assertTrue(all(row["gt_id"] != row["source_boundary_id"] for row in gt))
        self.assertTrue(all(row["gt_id"].endswith("-HGT0001") or row["gt_id"].endswith("-HGT0002") for row in gt))

    def test_misaligned_uses_corrected_frame(self) -> None:
        seed_pred = [
            _predicted("g1_cal_seed_export_test", "g1_exploratory_audit_test", "data/demo_s0", "demo_s0-B0001", 20, decision="MISALIGNED", reason="MISALIGNED_GRIPPER", corrected="18"),
            _predicted("g1_cal_seed_export_test", "g1_exploratory_audit_test", "data/demo_s1", "demo_s1-B0001", 5, decision="VALID", review_id="2"),
        ]
        fresh_pred = [
            _predicted("g1_cal_export_test", "g1_calibration_test", "data/demo_f0", "demo_f0-B0001", 1, decision="VALID"),
            _predicted("g1_cal_export_test", "g1_calibration_test", "data/demo_f1", "demo_f1-B0001", 2, decision="VALID", review_id="2"),
        ]
        seed, fresh, snapshots = self._seed_fresh(seed_pred=seed_pred, fresh_pred=fresh_pred)
        result = self._build(seed, fresh, snapshots)
        gt = list(csv.DictReader((Path(result["snapshot_path"]) / "canonical_human_boundary_gt.csv").open(encoding="utf-8")))
        mis = [row for row in gt if row["gt_source"] == "MISALIGNED_CORRECTED"]
        self.assertEqual(len(mis), 1)
        self.assertEqual(int(mis[0]["gt_frame"]), 18)
        self.assertNotEqual(int(mis[0]["gt_frame"]), 20)

    def test_human_added_becomes_gt_other(self) -> None:
        seed_pred = [
            _predicted("g1_cal_seed_export_test", "g1_exploratory_audit_test", "data/demo_s0", "demo_s0-B0001", 4, decision="VALID"),
            _predicted("g1_cal_seed_export_test", "g1_exploratory_audit_test", "data/demo_s1", "demo_s1-B0001", 5, decision="VALID", review_id="2"),
        ]
        added = [{
            "export_id": "g1_cal_seed_export_test", "source_run_id": "g1_exploratory_audit_test",
            "episode_id": "data/demo_s0", "added_group_id": "demo_s0-H0001",
            "human_added_frame": "40", "reason_code": "MISSED_GRIPPER_TRANSITION",
            "comment": "", "review_id": "9", "reviewer": "TEST", "reviewed_at": "2026-09-18T00:00:00+08:00",
        }]
        fresh_pred = [
            _predicted("g1_cal_export_test", "g1_calibration_test", "data/demo_f0", "demo_f0-B0001", 1, decision="VALID"),
            _predicted("g1_cal_export_test", "g1_calibration_test", "data/demo_f1", "demo_f1-B0001", 2, decision="VALID", review_id="2"),
        ]
        seed, fresh, snapshots = self._seed_fresh(seed_pred=seed_pred, fresh_pred=fresh_pred, seed_added=added)
        result = self._build(seed, fresh, snapshots)
        gt = list(csv.DictReader((Path(result["snapshot_path"]) / "canonical_human_boundary_gt.csv").open(encoding="utf-8")))
        added_rows = [row for row in gt if row["gt_source"] == "HUMAN_ADDED"]
        self.assertEqual(len(added_rows), 1)
        self.assertEqual(int(added_rows[0]["gt_frame"]), 40)
        self.assertEqual(added_rows[0]["protected_class"], "OTHER")
        self.assertEqual(added_rows[0]["source_boundary_id"], "")

    def test_not_reviewed_blocks(self) -> None:
        seed_pred = [
            _predicted("g1_cal_seed_export_test", "g1_exploratory_audit_test", "data/demo_s0", "demo_s0-B0001", 4, decision="NOT_REVIEWED"),
            _predicted("g1_cal_seed_export_test", "g1_exploratory_audit_test", "data/demo_s1", "demo_s1-B0001", 5, decision="VALID", review_id="2"),
        ]
        fresh_pred = [
            _predicted("g1_cal_export_test", "g1_calibration_test", "data/demo_f0", "demo_f0-B0001", 1, decision="VALID"),
            _predicted("g1_cal_export_test", "g1_calibration_test", "data/demo_f1", "demo_f1-B0001", 2, decision="VALID", review_id="2"),
        ]
        seed, fresh, snapshots = self._seed_fresh(seed_pred=seed_pred, fresh_pred=fresh_pred)
        with self.assertRaisesRegex(CanonicalGTBlocked, "NOT_REVIEWED"):
            self._build(seed, fresh, snapshots)
        self.assertFalse(snapshots.exists() and any(snapshots.iterdir()))

    def test_p1_non_pass_blocks(self) -> None:
        seed_pred = [
            _predicted("g1_cal_seed_export_test", "g1_exploratory_audit_test", "data/demo_s0", "demo_s0-B0001", 4, decision="VALID"),
            _predicted("g1_cal_seed_export_test", "g1_exploratory_audit_test", "data/demo_s1", "demo_s1-B0001", 5, decision="VALID", review_id="2"),
        ]
        fresh_pred = [
            _predicted("g1_cal_export_test", "g1_calibration_test", "data/demo_f0", "demo_f0-B0001", 1, decision="VALID"),
            _predicted("g1_cal_export_test", "g1_calibration_test", "data/demo_f1", "demo_f1-B0001", 2, decision="VALID", review_id="2"),
        ]
        seed, fresh, snapshots = self._seed_fresh(seed_pred=seed_pred, fresh_pred=fresh_pred, seed_signals="FAIL")
        with self.assertRaisesRegex(CanonicalGTBlocked, "P1 gate failed"):
            self._build(seed, fresh, snapshots)

    def test_same_frame_deterministic_dedupe(self) -> None:
        seed_pred = [
            _predicted("g1_cal_seed_export_test", "g1_exploratory_audit_test", "data/demo_s0", "demo_s0-B0001", 10, decision="VALID"),
            _predicted("g1_cal_seed_export_test", "g1_exploratory_audit_test", "data/demo_s0", "demo_s0-B0002", 12, decision="MISALIGNED", reason="MISALIGNED_MOTION_CHANGE", corrected="10", review_id="2"),
            _predicted("g1_cal_seed_export_test", "g1_exploratory_audit_test", "data/demo_s1", "demo_s1-B0001", 5, decision="VALID", review_id="3"),
        ]
        fresh_pred = [
            _predicted("g1_cal_export_test", "g1_calibration_test", "data/demo_f0", "demo_f0-B0001", 1, decision="VALID"),
            _predicted("g1_cal_export_test", "g1_calibration_test", "data/demo_f1", "demo_f1-B0001", 2, decision="VALID", review_id="2"),
        ]
        seed, fresh, snapshots = self._seed_fresh(seed_pred=seed_pred, fresh_pred=fresh_pred)
        result = self._build(seed, fresh, snapshots)
        gt = list(csv.DictReader((Path(result["snapshot_path"]) / "canonical_human_boundary_gt.csv").open(encoding="utf-8")))
        same = [row for row in gt if row["episode_id"] == "data/demo_s0"]
        self.assertEqual(len(same), 1)
        self.assertEqual(same[0]["gt_source"], "MISALIGNED_CORRECTED")
        self.assertEqual(int(same[0]["gt_frame"]), 10)
        self.assertEqual(result["meta"]["deduped_count"], 1)

    def test_same_priority_conflict_blocks(self) -> None:
        seed_pred = [
            _predicted("g1_cal_seed_export_test", "g1_exploratory_audit_test", "data/demo_s0", "demo_s0-B0001", 10, decision="VALID"),
            _predicted("g1_cal_seed_export_test", "g1_exploratory_audit_test", "data/demo_s0", "demo_s0-B0002", 10, decision="VALID", review_id="2"),
            _predicted("g1_cal_seed_export_test", "g1_exploratory_audit_test", "data/demo_s1", "demo_s1-B0001", 5, decision="VALID", review_id="3"),
        ]
        fresh_pred = [
            _predicted("g1_cal_export_test", "g1_calibration_test", "data/demo_f0", "demo_f0-B0001", 1, decision="VALID"),
            _predicted("g1_cal_export_test", "g1_calibration_test", "data/demo_f1", "demo_f1-B0001", 2, decision="VALID", review_id="2"),
        ]
        seed, fresh, snapshots = self._seed_fresh(seed_pred=seed_pred, fresh_pred=fresh_pred)
        with self.assertRaisesRegex(CanonicalGTBlocked, "CANONICAL_GT_CONFLICT"):
            self._build(seed, fresh, snapshots)
        if snapshots.exists():
            self.assertFalse(any(item.is_dir() and not item.name.startswith(".tmp-") for item in snapshots.iterdir()))

    def test_gt_id_deterministic_and_snapshot_immutable(self) -> None:
        seed_pred = [
            _predicted("g1_cal_seed_export_test", "g1_exploratory_audit_test", "data/demo_s0", "demo_s0-B0001", 4, decision="VALID"),
            _predicted("g1_cal_seed_export_test", "g1_exploratory_audit_test", "data/demo_s1", "demo_s1-B0001", 9, decision="VALID", candidate_type="DIRECTION_CHANGE", review_id="2"),
        ]
        fresh_pred = [
            _predicted("g1_cal_export_test", "g1_calibration_test", "data/demo_f0", "demo_f0-B0001", 1, decision="VALID", candidate_type="GRIPPER_TRANSITION", members="GRIPPER_TRANSITION|DIRECTION_CHANGE", count=2),
            _predicted("g1_cal_export_test", "g1_calibration_test", "data/demo_f1", "demo_f1-B0001", 2, decision="VALID", review_id="2"),
        ]
        seed, fresh, snapshots = self._seed_fresh(seed_pred=seed_pred, fresh_pred=fresh_pred)
        first = self._build(seed, fresh, snapshots)
        second = self._build(seed, fresh, snapshots)
        self.assertNotEqual(first["snapshot_id"], second["snapshot_id"])
        first_gt = list(csv.DictReader((Path(first["snapshot_path"]) / "canonical_human_boundary_gt.csv").open(encoding="utf-8")))
        second_gt = list(csv.DictReader((Path(second["snapshot_path"]) / "canonical_human_boundary_gt.csv").open(encoding="utf-8")))
        self.assertEqual([row["gt_id"] for row in first_gt], [row["gt_id"] for row in second_gt])
        first_hash = tree_fingerprint(first["snapshot_path"])["tree_fingerprint"]
        self.assertEqual(first_hash, tree_fingerprint(first["snapshot_path"])["tree_fingerprint"])
        classes = {row["protected_class"] for row in first_gt}
        self.assertIn("GRIPPER_PRIMARY", classes)
        self.assertIn("VALID_DIRECTION_PRIMARY", classes)
        self.assertIn("MERGED_GRIPPER_CLUSTER", classes)

    def test_atomic_build_cleans_temp_on_rename_failure(self) -> None:
        seed_pred = [
            _predicted("g1_cal_seed_export_test", "g1_exploratory_audit_test", "data/demo_s0", "demo_s0-B0001", 4, decision="VALID"),
            _predicted("g1_cal_seed_export_test", "g1_exploratory_audit_test", "data/demo_s1", "demo_s1-B0001", 5, decision="VALID", review_id="2"),
        ]
        fresh_pred = [
            _predicted("g1_cal_export_test", "g1_calibration_test", "data/demo_f0", "demo_f0-B0001", 1, decision="VALID"),
            _predicted("g1_cal_export_test", "g1_calibration_test", "data/demo_f1", "demo_f1-B0001", 2, decision="VALID", review_id="2"),
        ]
        seed, fresh, snapshots = self._seed_fresh(seed_pred=seed_pred, fresh_pred=fresh_pred)
        with patch("project2_g1.canonical_gt.os.rename", side_effect=OSError("rename failed")):
            with self.assertRaises(OSError):
                self._build(seed, fresh, snapshots)
        leftover = list(snapshots.glob("*")) if snapshots.exists() else []
        self.assertEqual(leftover, [])

    def test_wrong_intended_role_and_overlap_block(self) -> None:
        seed_pred = [
            _predicted("g1_cal_seed_export_test", "g1_exploratory_audit_test", "data/demo_s0", "demo_s0-B0001", 4, decision="VALID"),
            _predicted("g1_cal_seed_export_test", "g1_exploratory_audit_test", "data/demo_s1", "demo_s1-B0001", 5, decision="VALID", review_id="2"),
        ]
        fresh_pred = [
            _predicted("g1_cal_export_test", "g1_calibration_test", "data/demo_s0", "demo_s0-B0001", 1, decision="VALID"),
            _predicted("g1_cal_export_test", "g1_calibration_test", "data/demo_f1", "demo_f1-B0001", 2, decision="VALID", review_id="2"),
        ]
        seed, fresh, snapshots = self._seed_fresh(
            seed_pred=seed_pred, fresh_pred=fresh_pred,
            fresh_episodes=["data/demo_s0", "data/demo_f1"],
        )
        with self.assertRaisesRegex(CanonicalGTBlocked, "EPISODE_OVERLAP"):
            self._build(seed, fresh, snapshots)

    def test_fresh_seed_role_mismatch_blocks(self) -> None:
        seed_pred = [
            _predicted("g1_cal_seed_export_test", "g1_exploratory_audit_test", "data/demo_s0", "demo_s0-B0001", 4, decision="VALID"),
            _predicted("g1_cal_seed_export_test", "g1_exploratory_audit_test", "data/demo_s1", "demo_s1-B0001", 5, decision="VALID", review_id="2"),
        ]
        fresh_pred = [
            _predicted("g1_cal_export_test", "g1_calibration_test", "data/demo_f0", "demo_f0-B0001", 1, decision="VALID"),
            _predicted("g1_cal_export_test", "g1_calibration_test", "data/demo_f1", "demo_f1-B0001", 2, decision="VALID", review_id="2"),
        ]
        seed, fresh, snapshots = self._seed_fresh(
            seed_pred=seed_pred, fresh_pred=fresh_pred,
            fresh_extra={"intended_role": "CALIBRATION_SEED"},
        )
        with self.assertRaisesRegex(CanonicalGTBlocked, "intended_role"):
            self._build(seed, fresh, snapshots)

    def test_error_mode_map_seed_kept_unmapped_unassigned(self) -> None:
        seed_pred = [
            _predicted("g1_cal_seed_export_test", "g1_exploratory_audit_test", "data/demo_s0", "demo_s0-B0001", 4, decision="REDUNDANT", candidate_type="DIRECTION_CHANGE", reason="REDUNDANT_DIRECTION_JITTER"),
            _predicted("g1_cal_seed_export_test", "g1_exploratory_audit_test", "data/demo_s1", "demo_s1-B0001", 5, decision="VALID", review_id="2"),
        ]
        fresh_pred = [
            _predicted("g1_cal_export_test", "g1_calibration_test", "data/demo_f0", "demo_f0-B0001", 8, decision="REDUNDANT", candidate_type="DIRECTION_CHANGE", reason="REDUNDANT_SHORT_PAUSE"),
            _predicted("g1_cal_export_test", "g1_calibration_test", "data/demo_f1", "demo_f1-B0001", 2, decision="VALID", review_id="2"),
        ]
        mapping = self.root / "modes.csv"
        _write_csv(mapping, ("run_id", "episode_id", "boundary_id", "human_decision", "error_mode"), [
            {"run_id": "g1_exploratory_audit_test", "episode_id": "data/demo_s0", "boundary_id": "demo_s0-B0001", "human_decision": "REDUNDANT", "error_mode": "MODE_01"},
        ])
        seed, fresh, snapshots = self._seed_fresh(seed_pred=seed_pred, fresh_pred=fresh_pred)
        result = self._build(seed, fresh, snapshots, error_mode_map_path=mapping)
        fp = list(csv.DictReader((Path(result["snapshot_path"]) / "known_false_positive_anchor.csv").open(encoding="utf-8")))
        by_ep = {row["episode_id"]: row["error_mode"] for row in fp}
        self.assertEqual(by_ep["data/demo_s0"], "MODE_01")
        self.assertEqual(by_ep["data/demo_f0"], "UNASSIGNED")

    def test_module_does_not_read_sqlite(self) -> None:
        text = (ROOT / "src" / "project2_g1" / "canonical_gt.py").read_text(encoding="utf-8")
        self.assertNotIn("sqlite3", text)
        self.assertNotIn("ReviewStore", text)
        self.assertNotIn("g1_audit_web_owner.sqlite3", text)

    def test_source_exports_unchanged_and_round_trip(self) -> None:
        seed_pred = [
            _predicted("g1_cal_seed_export_test", "g1_exploratory_audit_test", "data/demo_s0", "demo_s0-B0001", 4, decision="VALID"),
            _predicted("g1_cal_seed_export_test", "g1_exploratory_audit_test", "data/demo_s1", "demo_s1-B0001", 5, decision="VALID", review_id="2"),
        ]
        fresh_pred = [
            _predicted("g1_cal_export_test", "g1_calibration_test", "data/demo_f0", "demo_f0-B0001", 1, decision="VALID"),
            _predicted("g1_cal_export_test", "g1_calibration_test", "data/demo_f1", "demo_f1-B0001", 2, decision="VALID", review_id="2"),
        ]
        seed, fresh, snapshots = self._seed_fresh(seed_pred=seed_pred, fresh_pred=fresh_pred)
        before_seed = tree_fingerprint(seed)["tree_fingerprint"]
        before_fresh = tree_fingerprint(fresh)["tree_fingerprint"]
        result = self._build(seed, fresh, snapshots)
        self.assertEqual(before_seed, tree_fingerprint(seed)["tree_fingerprint"])
        self.assertEqual(before_fresh, tree_fingerprint(fresh)["tree_fingerprint"])
        meta = json.loads((Path(result["snapshot_path"]) / "canonical_gt_meta.json").read_text(encoding="utf-8"))
        self.assertFalse(meta["matching_executed"])
        self.assertFalse(meta["tolerance_applied"])
        self.assertEqual(meta["matching_rule_id"], "MAX_CARDINALITY_MIN_TOTAL_DISTANCE_ONE_TO_ONE_V1")
        self.assertEqual(meta["tolerance_frames"], 3)
        self.assertEqual(list(CANONICAL_GT_FIELDS), list(csv.DictReader((Path(result["snapshot_path"]) / "canonical_human_boundary_gt.csv").open(encoding="utf-8")).fieldnames))
        self.assertEqual(list(KNOWN_FP_FIELDS), list(csv.DictReader((Path(result["snapshot_path"]) / "known_false_positive_anchor.csv").open(encoding="utf-8")).fieldnames))

    def test_official_two_export_twelve_episode_exact_set(self) -> None:
        export_root = ROOT / "outputs" / "g1_audit_web" / "human_calibration_export"
        seed = export_root / "g1_cal_seed_export_20260917_214637_2f8d8802"
        fresh = export_root / "g1_cal_export_20260918_120335_81c068bf"
        if not seed.is_dir() or not fresh.is_dir():
            self.skipTest("official exports not present")
        seed_before = tree_fingerprint(seed)["tree_fingerprint"]
        fresh_before = tree_fingerprint(fresh)["tree_fingerprint"]
        sqlite = ROOT / "outputs" / "g1_audit_web" / "g1_audit_web_owner.sqlite3"
        sqlite_before = sha256_file(sqlite) if sqlite.is_file() else None
        validate_export_disk(seed, expected_role=SEED_ROLE)
        validate_export_disk(fresh, expected_role=FRESH_ROLE)
        snapshots = self.root / "official"
        mapping = ROOT / "outputs" / "g1_human_review_analysis" / "20260917_error_attribution" / "boundary_error_attribution.csv"
        result = build_combined_canonical_gt(
            seed_export_path=seed, fresh_export_path=fresh, snapshot_root=snapshots,
            error_mode_map_path=mapping if mapping.is_file() else None,
            expected_seed_episode_ids=[
                "data/demo_0", "data/demo_32", "data/demo_179",
                "data/demo_230", "data/demo_242", "data/demo_278",
            ],
            expected_fresh_episode_ids=[
                "data/demo_150", "data/demo_162", "data/demo_213",
                "data/demo_255", "data/demo_260", "data/demo_270",
            ],
        )
        meta = result["meta"]
        self.assertEqual(meta["episode_count"], 12)
        self.assertEqual(meta["canonical_gt_count"], 56)
        self.assertEqual(meta["known_fp_anchor_count"], 10)
        self.assertEqual(meta["valid_inherit_gt_count"], 56)
        self.assertEqual(meta["misaligned_gt_count"], 0)
        self.assertEqual(meta["human_added_gt_count"], 0)
        self.assertEqual(meta["deduped_count"], 0)
        self.assertEqual(meta["p1_pass_count"], 72)
        fp = list(csv.DictReader((Path(result["snapshot_path"]) / "known_false_positive_anchor.csv").open(encoding="utf-8")))
        self.assertEqual(sum(1 for row in fp if row["source_package"] == "SEED"), 7)
        self.assertEqual(sum(1 for row in fp if row["source_package"] == "FRESH"), 3)
        self.assertTrue(all(row["error_mode"] in {"MODE_01", "MODE_02", "MODE_03"} for row in fp if row["source_package"] == "SEED"))
        self.assertTrue(all(row["error_mode"] == "UNASSIGNED" for row in fp if row["source_package"] == "FRESH"))
        self.assertEqual(seed_before, tree_fingerprint(seed)["tree_fingerprint"])
        self.assertEqual(fresh_before, tree_fingerprint(fresh)["tree_fingerprint"])
        if sqlite_before is not None:
            self.assertEqual(sqlite_before, sha256_file(sqlite))

    def test_protected_class_helper(self) -> None:
        self.assertEqual(classify_protected_class({"candidate_type": "GRIPPER_TRANSITION", "member_candidate_types": "GRIPPER_TRANSITION", "member_candidate_count": "1"}, gt_source="VALID_INHERIT"), "GRIPPER_PRIMARY")
        self.assertEqual(classify_protected_class({"candidate_type": "DIRECTION_CHANGE", "member_candidate_types": "DIRECTION_CHANGE", "member_candidate_count": "1"}, gt_source="VALID_INHERIT"), "VALID_DIRECTION_PRIMARY")
        self.assertEqual(classify_protected_class({"candidate_type": "GRIPPER_TRANSITION", "member_candidate_types": "GRIPPER_TRANSITION|DIRECTION_CHANGE", "member_candidate_count": "2"}, gt_source="VALID_INHERIT"), "MERGED_GRIPPER_CLUSTER")
        self.assertEqual(classify_protected_class({}, gt_source="HUMAN_ADDED"), "OTHER")


if __name__ == "__main__":
    unittest.main()
