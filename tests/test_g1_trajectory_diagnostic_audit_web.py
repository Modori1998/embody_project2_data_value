"""DESIGN_DIAGNOSTIC Audit Web materialization: contract, blinding, review.

Covers the additive G1-P3 Trajectory Mechanism Diagnostic Set Web run:

* the blinded manifest is the only event source and is internally consistent;
* the new run_stage / set_role pair is accepted, and any other pairing is not;
* Calibration Export / Canonical GT / Evaluation are hard-blocked;
* no reviewer-facing payload leaks a diagnostic-design token;
* the 20 events review as VALID / REDUNDANT / MISALIGNED and persist
  append-only;
* the pre-existing stages are untouched.
"""

from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TESTS = Path(__file__).resolve().parent
for path in (SRC, TESTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from fastapi.testclient import TestClient

from g1_audit_web_fixtures import write_synthetic_run
from project2_g1.trajectory_diagnostic_run import (
    BLINDED_MANIFEST_RELPATH,
    EXPECTED_EVENT_COUNT,
    TrajectoryDiagnosticRunError,
    audit_blinding_rows,
    audit_blinding_run_folder,
    blinding_violations,
    load_blinded_manifest,
)
from project2_g1_audit_web.calibration_export import (
    HumanCalibrationExportService,
    resolve_export_role,
)
from project2_g1_audit_web.contract import (
    ALLOWED_RUN_STAGES,
    ALLOWED_SET_ROLES,
    CONTRACT_VERSION,
    DESIGN_DIAGNOSTIC_RUN_STAGE,
    DESIGN_DIAGNOSTIC_SET_ROLE,
    STAGE_TO_SET_ROLE,
    blocked_downstreams,
    is_design_diagnostic,
    validate_g1_audit_folder,
)
from project2_g1_audit_web.input import load_run
from project2_g1_audit_web.registry import (
    auto_register,
    default_owner_db_path,
    default_registry_path,
    load_registry,
)
from project2_g1_audit_web.app import create_app
from project2_g1_audit_web.service import G1AuditWebInput

BLINDED_MANIFEST = ROOT / BLINDED_MANIFEST_RELPATH

# Diagnostic-design tokens that must never reach a reviewer-facing payload.
FORBIDDEN_PROBES = (
    "ARM_A",
    "ARM_B",
    "arm",
    "P12",
    "C12",
    "coherence",
    "pair_id",
    "match_distance",
    "selection_reason",
    "LOW_C12_QUARTILE_EPISODE_DIVERSE_TARGET",
)


class _FakeIdent:
    def __init__(self, digest: str):
        self.source_sha256 = digest
        self.needs_proxy = False
        self.proxy_profile_version = "v1"
        self.proxy_url = ""


# ---------------------------------------------------------------------------
# 1. Blinding primitives
# ---------------------------------------------------------------------------


class TestBlindingPrimitives(unittest.TestCase):
    def test_forbidden_tokens_are_detected(self) -> None:
        for probe in FORBIDDEN_PROBES:
            with self.subTest(probe=probe):
                self.assertTrue(
                    blinding_violations(probe),
                    f"blinding scan missed {probe!r}",
                )

    def test_legitimate_detector_vocabulary_is_not_flagged(self) -> None:
        # ``target_boundary_id`` is an existing frozen Detector column.
        self.assertEqual(blinding_violations("target_boundary_id"), [])
        self.assertEqual(blinding_violations("boundary_decisions.csv"), [])
        self.assertEqual(blinding_violations("controls"), [])

    def test_review_labels_are_not_flagged(self) -> None:
        for label in ("VALID", "REDUNDANT", "MISALIGNED", "NOT_REVIEWED"):
            with self.subTest(label=label):
                self.assertEqual(blinding_violations(label), [])

    def test_selection_reason_leaks_through_segment_split(self) -> None:
        hits = blinding_violations("LOW_C12_QUARTILE_EPISODE_DIVERSE_TARGET")
        self.assertTrue(any("c12" in hit for hit in hits))
        self.assertTrue(any("target" in hit for hit in hits))

    def test_audit_blinding_rows_scans_keys_and_values(self) -> None:
        rows = [{"episode_id": "data/demo_1", "note": "arm_a"}]
        violations = audit_blinding_rows(rows, source="unit")
        self.assertTrue(violations)
        self.assertTrue(all(v.startswith("unit:") for v in violations))


# ---------------------------------------------------------------------------
# 2. Blinded manifest integrity (frozen input)
# ---------------------------------------------------------------------------


@unittest.skipUnless(BLINDED_MANIFEST.is_file(), "blinded manifest not present")
class TestBlindedManifest(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = load_blinded_manifest(BLINDED_MANIFEST)

    def test_event_and_episode_counts(self) -> None:
        self.assertEqual(len(self.rows), EXPECTED_EVENT_COUNT)
        self.assertEqual(len({row["episode_id"] for row in self.rows}), EXPECTED_EVENT_COUNT)

    def test_one_event_per_episode(self) -> None:
        episodes = [row["episode_id"] for row in self.rows]
        self.assertEqual(len(episodes), len(set(episodes)))

    def test_manifest_carries_no_forbidden_token(self) -> None:
        self.assertEqual(audit_blinding_rows(self.rows, source="blinded"), [])

    def test_single_diagnostic_set_id(self) -> None:
        self.assertEqual(len({row["diagnostic_set_id"] for row in self.rows}), 1)

    def test_manifest_rejects_missing_file(self) -> None:
        with self.assertRaises(TrajectoryDiagnosticRunError):
            load_blinded_manifest(ROOT / "does_not_exist_blinded.csv")


# ---------------------------------------------------------------------------
# 3. Contract: additive DESIGN_DIAGNOSTIC stage
# ---------------------------------------------------------------------------


class TestDesignDiagnosticContract(unittest.TestCase):
    def test_stage_and_role_are_allowed(self) -> None:
        self.assertIn(DESIGN_DIAGNOSTIC_RUN_STAGE, ALLOWED_RUN_STAGES)
        self.assertIn(DESIGN_DIAGNOSTIC_SET_ROLE, ALLOWED_SET_ROLES)
        self.assertEqual(
            STAGE_TO_SET_ROLE[DESIGN_DIAGNOSTIC_RUN_STAGE], DESIGN_DIAGNOSTIC_SET_ROLE
        )

    def test_existing_stages_are_preserved(self) -> None:
        self.assertEqual(
            ALLOWED_RUN_STAGES,
            frozenset({"EXPLORATORY_AUDIT", "CALIBRATION", "EVALUATION", "DESIGN_DIAGNOSTIC"}),
        )
        self.assertEqual(
            STAGE_TO_SET_ROLE["EXPLORATORY_AUDIT"], "EXPLORATORY"
        )
        self.assertEqual(STAGE_TO_SET_ROLE["CALIBRATION"], "CALIBRATION")
        self.assertEqual(STAGE_TO_SET_ROLE["EVALUATION"], "EVALUATION")

    def test_is_design_diagnostic(self) -> None:
        self.assertTrue(is_design_diagnostic("DESIGN_DIAGNOSTIC"))
        self.assertFalse(is_design_diagnostic("CALIBRATION"))
        self.assertFalse(is_design_diagnostic(""))

    def test_blocked_downstreams(self) -> None:
        self.assertEqual(
            blocked_downstreams("DESIGN_DIAGNOSTIC"),
            ("CALIBRATION_EXPORT_ELIGIBLE", "CANONICAL_GT_ELIGIBLE", "EVALUATION_ELIGIBLE"),
        )
        self.assertEqual(blocked_downstreams("CALIBRATION"), ())

    def test_stage_role_pairing_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp)
            run_root = write_synthetic_run(
                root / "runs",
                run_id="g1_design_diagnostic_pairing_test",
                n_episodes=2,
                run_stage="DESIGN_DIAGNOSTIC",
                set_role="CALIBRATION",
            )
            with self.assertRaises(Exception):
                validate_g1_audit_folder(run_root)

    def test_valid_design_diagnostic_folder_passes(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp)
            run_root = write_synthetic_run(
                root / "runs",
                run_id="g1_design_diagnostic_contract_ok",
                n_episodes=2,
                run_stage="DESIGN_DIAGNOSTIC",
                set_role="DESIGN_DIAGNOSTIC",
            )
            validated = validate_g1_audit_folder(run_root)
            self.assertEqual(validated["run_stage"], "DESIGN_DIAGNOSTIC")
            self.assertEqual(
                {row["set_role"] for row in validated["episodes"]}, {"DESIGN_DIAGNOSTIC"}
            )


# ---------------------------------------------------------------------------
# 4. Calibration Export must be hard-blocked
# ---------------------------------------------------------------------------


class TestDesignDiagnosticExportBlocked(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self._tmp.name)
        self.run_root = write_synthetic_run(
            self.root / "runs",
            run_id="g1_design_diagnostic_export_block",
            n_episodes=2,
            run_stage="DESIGN_DIAGNOSTIC",
            set_role="DESIGN_DIAGNOSTIC",
        )
        self.loaded = load_run(self.run_root)
        self.exporter = HumanCalibrationExportService(
            project_root=self.root, owner_db_path=self.root / "web" / "owner.sqlite3"
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_resolve_export_role_returns_none(self) -> None:
        self.assertIsNone(resolve_export_role(self.loaded))

    def test_assess_is_not_ready(self) -> None:
        assessment = self.exporter.assess(self.loaded)
        self.assertFalse(assessment["ready"])
        self.assertFalse(assessment["export_eligible"])
        self.assertFalse(assessment["effective_export_ready"])
        self.assertTrue(
            any("not eligible" in message for message in assessment["errors"]),
            assessment["errors"],
        )

    def test_create_export_raises(self) -> None:
        from project2_g1_audit_web.calibration_export import ExportBlocked

        with self.assertRaises(ExportBlocked):
            self.exporter.create_export(self.loaded)

    def test_exploratory_run_is_still_export_eligible(self) -> None:
        # Regression: the additive block must not leak into other stages.
        exploratory = write_synthetic_run(
            self.root / "runs2",
            run_id="g1_exploratory_audit_still_ok",
            n_episodes=2,
        )
        self.assertEqual(resolve_export_role(load_run(exploratory)), "CALIBRATION_SEED")


# ---------------------------------------------------------------------------
# 5. Web behaviour on a synthetic DESIGN_DIAGNOSTIC run
# ---------------------------------------------------------------------------


class TestDesignDiagnosticWeb(unittest.TestCase):
    RUN_ID = "g1_design_diagnostic_web_test_00000000"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self._tmp.name)
        self.registry = default_registry_path(self.root)
        self.owner_db = default_owner_db_path(self.root)
        self.run_root = write_synthetic_run(
            self.root / "outputs" / "g1_audit_runs",
            run_id=self.RUN_ID,
            n_episodes=20,
            run_stage="DESIGN_DIAGNOSTIC",
            set_role="DESIGN_DIAGNOSTIC",
        )
        auto_register(self.registry, self.run_root, owner_db_path=self.owner_db)
        self.service = G1AuditWebInput(
            project_root=self.root,
            registry_path=self.registry,
            owner_db_path=self.owner_db,
        )
        self.client = self._client()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _client(self) -> TestClient:
        proxy = Mock()
        proxy.register_video.side_effect = lambda source, run_id, episode_id: _FakeIdent("b" * 64)
        proxy.ensure_proxy_file.side_effect = lambda sha, profile: Path(
            self.run_root / "media/demo_0/video.mp4"
        )
        app = create_app(project_root=self.root, web_input=self.service, video_proxy=proxy)
        return TestClient(app)

    def _form(self, **overrides: str) -> dict[str, str]:
        data = {"action": "save"}
        data.update(overrides)
        return data

    def _open(self, index: int = 0):
        return self.client.get(
            f"/audit/{self.RUN_ID}/episode/data--demo_{index}", follow_redirects=True
        )

    @staticmethod
    def _boundary_id(index: int) -> str:
        return f"demo_{index}-B0001"

    def test_index_lists_the_design_diagnostic_run(self) -> None:
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn(self.RUN_ID, page.text)

    def test_run_opens_and_redirects_to_first_episode(self) -> None:
        opened = self.client.get(f"/audit/{self.RUN_ID}", follow_redirects=False)
        self.assertEqual(opened.status_code, 303)
        self.assertIn("data--demo_", opened.headers["location"])

    def test_twenty_episodes_are_browsable(self) -> None:
        for index in range(20):
            with self.subTest(index=index):
                page = self._open(index)
                self.assertEqual(page.status_code, 200)
                self.assertIn(f"data/demo_{index}", page.text)

    def test_banner_and_stage_are_rendered(self) -> None:
        page = self._open(0)
        self.assertIn("design-diagnostic-banner", page.text)
        self.assertIn("DESIGN_DIAGNOSTIC", page.text)

    def test_export_is_visibly_blocked(self) -> None:
        page = self._open(0)
        self.assertIn("EXPORT_BLOCKED", page.text)
        self.assertNotIn("/export", page.text.split("Human Calibration Export")[0][-200:])

    def test_export_post_is_blocked(self) -> None:
        response = self.client.post(
            f"/audit/{self.RUN_ID}/episode/data--demo_0/export", follow_redirects=True
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("EXPORT_BLOCKED", response.text)

    def test_reviewer_payload_leaks_no_diagnostic_token(self) -> None:
        for index in (0, 7, 19):
            with self.subTest(index=index):
                page = self._open(index)
                for probe in FORBIDDEN_PROBES:
                    self.assertNotIn(probe.lower(), page.text.lower(), probe)

    def test_index_payload_leaks_no_diagnostic_token(self) -> None:
        page = self.client.get("/")
        for probe in FORBIDDEN_PROBES:
            self.assertNotIn(probe.lower(), page.text.lower(), probe)

    def test_initial_state_is_not_reviewed(self) -> None:
        page = self._open(0)
        self.assertIn("NOT_REVIEWED", page.text)
        for probe in ("REDUNDANT", "MISALIGNED"):
            self.assertNotIn(f'value="{probe}" selected', page.text)

    def test_three_labels_can_be_submitted(self) -> None:
        cases = {
            "VALID": ("signal_TRANSLATION_decision", "PASS"),
            "REDUNDANT": ("signal_TRANSLATION_decision", "PASS"),
            "MISALIGNED": ("signal_TRANSLATION_decision", "PASS"),
        }
        for index, (label, (signal_field, signal_value)) in enumerate(cases.items()):
            with self.subTest(label=label):
                bid = self._boundary_id(index)
                payload = {signal_field: signal_value, f"bound_{bid}_decision": label}
                if label == "REDUNDANT":
                    payload[f"bound_{bid}_reason_code"] = "REDUNDANT_DIRECTION_JITTER"
                elif label == "MISALIGNED":
                    payload[f"bound_{bid}_reason_code"] = "MISALIGNED_GRIPPER"
                    payload[f"bound_{bid}_corrected_frame"] = "4"
                saved = self.client.post(
                    f"/audit/{self.RUN_ID}/episode/data--demo_{index}/review",
                    data=self._form(**payload),
                    follow_redirects=True,
                )
                self.assertEqual(saved.status_code, 200, saved.text[:400])

    def test_review_persists_across_reload(self) -> None:
        bid = self._boundary_id(3)
        self.client.post(
            f"/audit/{self.RUN_ID}/episode/data--demo_3/review",
            data=self._form(
                **{
                    "signal_TRANSLATION_decision": "PASS",
                    f"bound_{bid}_decision": "REDUNDANT",
                    f"bound_{bid}_reason_code": "REDUNDANT_DIRECTION_JITTER",
                }
            ),
            follow_redirects=True,
        )
        reloaded = self._open(3)
        self.assertIn('value="REDUNDANT" selected', reloaded.text)
        self.assertIn('value="PASS" selected', reloaded.text)

    def test_review_store_is_append_only(self) -> None:
        url = f"/audit/{self.RUN_ID}/episode/data--demo_4/review"
        bid = self._boundary_id(4)
        for decision in ("VALID", "REDUNDANT", "MISALIGNED"):
            payload = {f"bound_{bid}_decision": decision}
            if decision == "REDUNDANT":
                payload[f"bound_{bid}_reason_code"] = "REDUNDANT_ROTATION"
            if decision == "MISALIGNED":
                payload[f"bound_{bid}_reason_code"] = "MISALIGNED_GRIPPER"
                payload[f"bound_{bid}_corrected_frame"] = "4"
            self.client.post(url, data=self._form(**payload), follow_redirects=True)
        import sqlite3

        connection = sqlite3.connect(str(self.owner_db))
        try:
            rows = connection.execute(
                "SELECT decision FROM predicted_boundary_review_history "
                "WHERE run_id = ? AND episode_id = ? ORDER BY review_id",
                (self.RUN_ID, "data/demo_4"),
            ).fetchall()
        finally:
            connection.close()
        self.assertEqual([row[0] for row in rows], ["VALID", "REDUNDANT", "MISALIGNED"])

    def test_progress_filters_reflect_review(self) -> None:
        bid = self._boundary_id(5)
        self.client.post(
            f"/audit/{self.RUN_ID}/episode/data--demo_5/review",
            data=self._form(
                **{
                    "signal_TRANSLATION_decision": "PASS",
                    f"bound_{bid}_decision": "VALID",
                }
            ),
            follow_redirects=True,
        )
        page = self.client.get(f"/audit/{self.RUN_ID}?filter=IN_PROGRESS", follow_redirects=True)
        self.assertIn("data/demo_5", page.text)


# ---------------------------------------------------------------------------
# 6. Real materialized run (skipped until it exists)
# ---------------------------------------------------------------------------


class TestMaterializedDiagnosticRun(unittest.TestCase):
    def _locate(self) -> Path | None:
        registry = default_registry_path(ROOT)
        if not registry.is_file():
            return None
        payload = load_registry(registry)
        for run_id, raw in payload.get("runs", {}).items():
            if str(raw.get("run_stage") or "") != DESIGN_DIAGNOSTIC_RUN_STAGE:
                continue
            folder = Path(str(raw.get("audit_folder_path") or ""))
            if folder.is_dir():
                return folder
        return None

    def setUp(self) -> None:
        self.run_root = self._locate()
        if self.run_root is None:
            self.skipTest("DESIGN_DIAGNOSTIC run not materialized yet")
        self.loaded = load_run(self.run_root)

    def test_run_is_valid_and_design_diagnostic(self) -> None:
        self.assertEqual(self.loaded["run_stage"], DESIGN_DIAGNOSTIC_RUN_STAGE)
        self.assertEqual(len(self.loaded["episodes"]), EXPECTED_EVENT_COUNT)

    def test_twenty_distinct_episodes(self) -> None:
        episodes = [item.episode_id for item in self.loaded["episodes"]]
        self.assertEqual(len(episodes), EXPECTED_EVENT_COUNT)
        self.assertEqual(len(set(episodes)), EXPECTED_EVENT_COUNT)

    def test_each_episode_has_exactly_one_review_target(self) -> None:
        for item in self.loaded["episodes"]:
            with self.subTest(episode=item.episode_id):
                with item.boundaries_path.open("r", encoding="utf-8", newline="") as handle:
                    rows = list(csv.DictReader(handle))
                self.assertEqual(len(rows), 1)
                self.assertEqual(int(item.final_boundary_count), 1)

    def test_selected_boundary_matches_blinded_manifest(self) -> None:
        rows = load_blinded_manifest(BLINDED_MANIFEST)
        expected = {
            row["episode_id"]: (row["boundary_id"], int(row["event_frame"]))
            for row in rows
        }
        seen = 0
        for item in self.loaded["episodes"]:
            with item.boundaries_path.open("r", encoding="utf-8", newline="") as handle:
                boundary = next(csv.DictReader(handle))
            self.assertEqual(boundary["boundary_id"], expected[item.episode_id][0])
            self.assertEqual(int(boundary["frame"]), expected[item.episode_id][1])
            seen += 1
        self.assertEqual(seen, EXPECTED_EVENT_COUNT)

    def test_run_folder_carries_no_diagnostic_token(self) -> None:
        self.assertEqual(audit_blinding_run_folder(self.run_root), [])

    def test_no_prior_review_is_copied_in(self) -> None:
        run_id = str(self.loaded["run_id"])
        import sqlite3

        db = default_owner_db_path(ROOT)
        if not db.is_file():
            self.skipTest("owner db absent")
        connection = sqlite3.connect(str(db))
        try:
            boundary_reviews = connection.execute(
                "SELECT COUNT(*) FROM predicted_boundary_review_history WHERE run_id = ?",
                (run_id,),
            ).fetchone()[0]
            signal_reviews = connection.execute(
                "SELECT COUNT(*) FROM signal_review_history WHERE source_run_id = ?",
                (run_id,),
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(int(boundary_reviews), 0)
        self.assertEqual(int(signal_reviews), 0)


# ---------------------------------------------------------------------------
# 7. Regression: pre-existing stages unchanged
# ---------------------------------------------------------------------------


class TestExistingStagesRegression(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_exploratory_run_still_validates_and_renders(self) -> None:
        run_root = write_synthetic_run(self.root / "runs", n_episodes=6)
        validated = validate_g1_audit_folder(run_root)
        self.assertEqual(validated["run_stage"], "EXPLORATORY_AUDIT")
        self.assertEqual(validated["run_meta"]["contract_version"], CONTRACT_VERSION)

    def test_exploratory_run_has_no_design_diagnostic_banner(self) -> None:
        registry = default_registry_path(self.root)
        owner_db = default_owner_db_path(self.root)
        run_root = write_synthetic_run(self.root / "outputs" / "g1_audit_runs", n_episodes=2)
        auto_register(registry, run_root, owner_db_path=owner_db)
        service = G1AuditWebInput(
            project_root=self.root, registry_path=registry, owner_db_path=owner_db
        )
        proxy = Mock()
        proxy.register_video.side_effect = lambda source, run_id, episode_id: _FakeIdent("c" * 64)
        proxy.ensure_proxy_file.side_effect = lambda sha, profile: Path(
            run_root / "media/demo_0/video.mp4"
        )
        client = TestClient(create_app(project_root=self.root, web_input=service, video_proxy=proxy))
        page = client.get(
            f"/audit/{run_root.name}/episode/data--demo_0", follow_redirects=True
        )
        self.assertEqual(page.status_code, 200)
        self.assertNotIn("design-diagnostic-banner", page.text)
        self.assertIn("exploratory-banner", page.text)

    def test_calibration_stage_is_untouched(self) -> None:
        run_root = write_synthetic_run(
            self.root / "runs2",
            run_id="g1_calibration_untouched_test",
            n_episodes=2,
            run_stage="CALIBRATION",
            set_role="CALIBRATION",
        )
        validated = validate_g1_audit_folder(run_root)
        self.assertEqual(validated["run_stage"], "CALIBRATION")
        self.assertEqual(blocked_downstreams("CALIBRATION"), ())


if __name__ == "__main__":
    unittest.main()
