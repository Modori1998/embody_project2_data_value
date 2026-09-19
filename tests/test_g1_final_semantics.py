"""Final Boundary member-semantics materialization (schema only; no detector retune)."""

from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TESTS = Path(__file__).resolve().parent
for path in (SRC, TESTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from g1_audit_web_fixtures import write_synthetic_run
from project2_g1.boundary_config import G1P2Config
from project2_g1.boundary_engine import (
    CANDIDATE_DIRECTION,
    CANDIDATE_GRIPPER,
    CANDIDATE_IDLE_TO_MOVE,
    BoundaryCandidate,
    EngineResult,
    _pick_representative,
    consolidate_candidates,
    debounce_candidates,
)
from project2_g1.boundary_io import write_episode_audit_tables
from project2_g1.final_semantics import (
    FINAL_BOUNDARY_SEMANTICS_V1,
    FinalSemanticsError,
    SEMANTICS_LINEAGE_ONLY,
    SEMANTICS_MATERIALIZED,
    candidate_index_from_rows,
    materialize_final_row,
    validate_materialized_final_row,
)
from project2_g1_audit_web.contract import ContractError, validate_g1_audit_folder
from project2_g1_audit_web.hashes import tree_fingerprint
from project2_g1_audit_web.materialize_final_semantics import materialize_parent_run

import numpy as np


def _load_cfg() -> G1P2Config:
    return G1P2Config(
        config_version="test",
        segmentation_version="test-seg",
        debounce_frames=1,
        boundary_consolidation_window=8,
        motion_speed_threshold=0.02,
        gripper_state_threshold=0.02,
        gripper_persistence_frames=2,
        motion_persistence_frames=2,
        direction_persistence_frames=2,
        pause_bridge_duration=8,
        min_segment_length=8,
        max_segment_length=80,
        support_window_frames=4,
        rotation_support_threshold=0.2,
        action_support_threshold=0.2,
        direction_window_frames=4,
        direction_min_window_displacement_m=0.01,
        direction_compatibility_threshold=1.0,
    )


def _candidate(**kwargs) -> BoundaryCandidate:
    payload = {
        "episode_id": "data/demo_c",
        "candidate_id": "demo_c-C0001",
        "frame": 4,
        "candidate_type": CANDIDATE_GRIPPER,
        "primary_reason": "PERSISTENT_GRIPPER_OPEN_TO_CLOSE",
        "supporting_reasons": [],
        "evidence_value": 0.04,
        "persistence_status": "PERSISTENT",
        "source_signal": "gripper_aperture",
        "config_version": "test",
        "polarity": "OPEN_TO_CLOSE",
    }
    payload.update(kwargs)
    return BoundaryCandidate(**payload)


class EngineMaterializationTests(unittest.TestCase):
    def test_single_member_writes_aligned_fields(self) -> None:
        cand = _candidate()
        events = consolidate_candidates([cand], debounce_candidates([cand], _load_cfg()), _load_cfg())
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.frame, 4)
        self.assertEqual(event.candidate_type, CANDIDATE_GRIPPER)
        self.assertEqual(event.representative_candidate_id, "demo_c-C0001")
        self.assertEqual(event.member_candidate_ids, ["demo_c-C0001"])
        self.assertEqual(event.member_candidate_types, [CANDIDATE_GRIPPER])
        self.assertEqual(event.member_candidate_frames, [4])
        self.assertEqual(event.member_candidate_count, 1)

    def test_two_member_merge_keeps_gripper_frame(self) -> None:
        hard = _candidate(candidate_id="demo_c-C0002", frame=56)
        soft = _candidate(
            candidate_id="demo_c-C0003",
            frame=57,
            candidate_type=CANDIDATE_DIRECTION,
            primary_reason="PERSISTENT_DIRECTION_CHANGE",
            source_signal="direction_change_evidence",
            polarity="DIRECTION_CHANGE",
            supporting_reasons=["ACTION_SUPPORT"],
        )
        cfg = _load_cfg()
        events = consolidate_candidates([hard, soft], debounce_candidates([hard, soft], cfg), cfg)
        event = events[0]
        self.assertEqual(event.frame, 56)
        self.assertEqual(event.candidate_type, CANDIDATE_GRIPPER)
        self.assertEqual(event.representative_candidate_id, "demo_c-C0002")
        self.assertEqual(event.member_candidate_ids, ["demo_c-C0002", "demo_c-C0003"])
        self.assertEqual(event.member_candidate_types, [CANDIDATE_GRIPPER, CANDIDATE_DIRECTION])
        self.assertEqual(event.member_candidate_frames, [56, 57])
        self.assertEqual(event.member_candidate_count, 2)
        self.assertEqual(event.supporting_reasons, ["ACTION_SUPPORT"])
        self.assertNotIn(CANDIDATE_DIRECTION, event.supporting_reasons)

    def test_three_member_alignment(self) -> None:
        grip = _candidate(candidate_id="demo_c-C0003", frame=71)
        direction = _candidate(
            candidate_id="demo_c-C0004",
            frame=73,
            candidate_type=CANDIDATE_DIRECTION,
            primary_reason="PERSISTENT_DIRECTION_CHANGE",
            source_signal="direction_change_evidence",
            polarity="DIRECTION_CHANGE",
        )
        idle = _candidate(
            candidate_id="demo_c-C0005",
            frame=78,
            candidate_type=CANDIDATE_IDLE_TO_MOVE,
            primary_reason="PERSISTENT_IDLE_TO_MOVE",
            source_signal="translation_speed",
            polarity="IDLE_TO_MOVE",
        )
        cfg = _load_cfg()
        items = [grip, direction, idle]
        events = consolidate_candidates(items, debounce_candidates(items, cfg), cfg)
        event = events[0]
        self.assertEqual(event.representative_candidate_id, "demo_c-C0003")
        self.assertEqual(event.member_candidate_count, 3)
        self.assertEqual(event.member_candidate_ids, ["demo_c-C0003", "demo_c-C0004", "demo_c-C0005"])
        self.assertEqual(
            event.member_candidate_types,
            [CANDIDATE_GRIPPER, CANDIDATE_DIRECTION, CANDIDATE_IDLE_TO_MOVE],
        )
        self.assertEqual(event.member_candidate_frames, [71, 73, 78])

    def test_representative_is_not_first_sorted_member(self) -> None:
        earlier = _candidate(
            candidate_id="demo_c-C0001",
            frame=50,
            candidate_type=CANDIDATE_DIRECTION,
            primary_reason="PERSISTENT_DIRECTION_CHANGE",
            source_signal="direction_change_evidence",
            polarity="DIRECTION_CHANGE",
        )
        later = _candidate(candidate_id="demo_c-C0002", frame=56)
        picked = _pick_representative([earlier, later])
        self.assertEqual(picked.candidate_id, "demo_c-C0002")
        cfg = _load_cfg()
        events = consolidate_candidates([earlier, later], debounce_candidates([earlier, later], cfg), cfg)
        event = events[0]
        self.assertEqual(event.frame, 56)
        self.assertEqual(event.candidate_type, CANDIDATE_GRIPPER)
        self.assertEqual(event.representative_candidate_id, "demo_c-C0002")
        self.assertEqual(event.member_candidate_ids[0], "demo_c-C0001")
        self.assertNotEqual(event.representative_candidate_id, event.member_candidate_ids[0])


class ValidatorMaterializationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_legacy_synthetic_run_still_readable(self) -> None:
        run_root = write_synthetic_run(self.root)
        loaded = validate_g1_audit_folder(run_root)
        self.assertEqual(loaded["final_member_semantics"], SEMANTICS_LINEAGE_ONLY)

    def _write_materialized(self, **final_overrides):
        run_root = write_synthetic_run(self.root / "mat", run_id="g1_exploratory_audit_mat_00000000")
        fieldnames = [
            "boundary_id",
            "episode_id",
            "frame",
            "candidate_type",
            "reason",
            "representative_candidate_id",
            "member_candidate_ids",
            "member_candidate_types",
            "member_candidate_frames",
            "member_candidate_count",
            "supporting_reasons",
            "review_flags",
            "polarity",
            "config_version",
            "segmentation_version",
        ]
        first_row = None
        first_by_id = None
        for bound in sorted((run_root / "diagnostic").glob("*/final_boundaries.csv")):
            cand = bound.parent / "candidate_boundaries.csv"
            with cand.open("r", encoding="utf-8", newline="") as handle:
                by_id = candidate_index_from_rows(list(csv.DictReader(handle)))
            with bound.open("r", encoding="utf-8", newline="") as handle:
                source_rows = list(csv.DictReader(handle))
            rewritten = []
            for index, row in enumerate(source_rows):
                materialized = materialize_final_row(row, by_id)
                if bound.parent.name == "demo_0" and index == 0:
                    materialized.update(final_overrides)
                    first_row = materialized
                    first_by_id = by_id
                rewritten.append(materialized)
            with bound.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                for item in rewritten:
                    writer.writerow(item)
        meta_path = run_root / "run_meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["final_boundary_semantics"] = FINAL_BOUNDARY_SEMANTICS_V1
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        if first_row is None or first_by_id is None:
            raise AssertionError("demo_0 final row was not materialized")
        return run_root, first_row, first_by_id

    def test_materialized_run_validates(self) -> None:
        run_root, _, _ = self._write_materialized()
        loaded = validate_g1_audit_folder(run_root)
        self.assertEqual(loaded["final_member_semantics"], SEMANTICS_MATERIALIZED)

    def test_type_mismatch_rejected(self) -> None:
        run_root, row, by_id = self._write_materialized(member_candidate_types="DIRECTION_CHANGE")
        with self.assertRaises(FinalSemanticsError):
            validate_materialized_final_row(row, by_id)
        with self.assertRaises(ContractError):
            validate_g1_audit_folder(run_root)

    def test_frame_mismatch_rejected(self) -> None:
        run_root, _, _ = self._write_materialized(member_candidate_frames="99")
        with self.assertRaises(ContractError) as ctx:
            validate_g1_audit_folder(run_root)
        self.assertIn("materialized frame", str(ctx.exception))

    def test_missing_member_id_rejected(self) -> None:
        run_root, _, _ = self._write_materialized(
            member_candidate_ids="demo_0-C9999",
            representative_candidate_id="demo_0-C9999",
            member_candidate_types="GRIPPER_TRANSITION",
            member_candidate_frames="4",
            member_candidate_count="1",
        )
        with self.assertRaises(ContractError) as ctx:
            validate_g1_audit_folder(run_root)
        self.assertIn("not in candidate table", str(ctx.exception))

    def test_length_mismatch_rejected(self) -> None:
        run_root, _, _ = self._write_materialized(member_candidate_count="2")
        with self.assertRaises(ContractError) as ctx:
            validate_g1_audit_folder(run_root)
        self.assertIn("length mismatch", str(ctx.exception))

    def test_representative_not_member_rejected(self) -> None:
        run_root, _, _ = self._write_materialized(representative_candidate_id="demo_0-C9999")
        with self.assertRaises(ContractError) as ctx:
            validate_g1_audit_folder(run_root)
        self.assertIn("not in member_candidate_ids", str(ctx.exception))


class ChildRunCopyTests(unittest.TestCase):
    def test_materialize_parent_does_not_touch_parent_tree(self) -> None:
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        try:
            root = Path(tmp.name)
            parent = write_synthetic_run(root / "runs", run_id="g1_exploratory_audit_parent_00000000")
            before = tree_fingerprint(parent)
            result = materialize_parent_run(
                project_root=root,
                parent_run_root=parent,
                dest_parent=root / "runs",
                register=False,
            )
            after = tree_fingerprint(parent)
            self.assertEqual(before["tree_fingerprint"], after["tree_fingerprint"])
            child = Path(result["run_root"])
            loaded = validate_g1_audit_folder(child)
            self.assertEqual(loaded["final_member_semantics"], SEMANTICS_MATERIALIZED)
            self.assertEqual(loaded["run_meta"]["parent_run_id"], parent.name)
            self.assertEqual(loaded["run_meta"]["final_boundary_semantics"], FINAL_BOUNDARY_SEMANTICS_V1)
            with (child / "diagnostic" / "demo_0" / "final_boundaries.csv").open(
                encoding="utf-8", newline=""
            ) as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["representative_candidate_id"], "demo_0-C0001")
            self.assertEqual(row["member_candidate_types"], "GRIPPER_TRANSITION")
            self.assertEqual(row["member_candidate_frames"], "4")
            self.assertEqual(row["member_candidate_count"], "1")
        finally:
            tmp.cleanup()


class WriterColumnTests(unittest.TestCase):
    def test_write_episode_tables_include_materialized_columns(self) -> None:
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        try:
            cand = _candidate()
            cfg = _load_cfg()
            decisions = debounce_candidates([cand], cfg)
            events = consolidate_candidates([cand], decisions, cfg)
            result = EngineResult(
                episode_id="data/demo_c",
                native_episode_key="demo_c",
                n_frames=10,
                dt_s=0.05,
                motion_state=np.zeros(10),
                gripper_state=np.zeros(10),
                candidates=[cand],
                decisions=decisions,
                events=events,
                segments=[],
                config_metadata={},
                review_required=False,
            )
            dest = Path(tmp.name) / "ep"
            paths = write_episode_audit_tables(dest, result)
            with Path(paths["final_boundaries"]).open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                self.assertIn("representative_candidate_id", reader.fieldnames or [])
                row = next(reader)
            self.assertEqual(row["member_candidate_count"], "1")
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
