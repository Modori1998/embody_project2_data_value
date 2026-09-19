"""G1 Audit Web Batch 2: Human Review persistence and validation."""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TESTS = Path(__file__).resolve().parent
for path in (SRC, TESTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from g1_audit_web_fixtures import write_synthetic_run
from project2_g1.paths import PROJECT2_ROOT
from project2_g1_audit_web.app import create_app
from project2_g1_audit_web.hashes import tree_fingerprint
from project2_g1_audit_web.registry import auto_register
from project2_g1_audit_web.reviews import (
    ADDED_TABLE,
    SIGNAL_NAMES,
    ReviewStore,
    ValidationFailed,
)
from project2_g1_audit_web.service import G1AuditWebInput

from test_g1_audit_web_web import _FakeIdent


def _signals(**overrides: str) -> dict[str, dict[str, str]]:
    payload = {name: {"decision": "NOT_REVIEWED", "comment": ""} for name in SIGNAL_NAMES}
    for name, decision in overrides.items():
        payload[name] = {"decision": decision, "comment": payload[name]["comment"]}
    return payload


class ReviewStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self._tmp.name)
        self.store = ReviewStore(self.root / "owner.sqlite3", reviewer="TEST_REVIEWER")
        self.run_id = "run_a"
        self.episode_id = "data/demo_0"
        self.hash = "a" * 64
        self.version = "g1_p1_signal_contract.v0"
        self.predicted = {"demo_0-B0001": 4}

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _save(self, **kwargs):
        defaults = {
            "run_id": self.run_id,
            "episode_id": self.episode_id,
            "signal_contract_version": self.version,
            "signal_contract_hash": self.hash,
            "episode_length": 10,
            "predicted": self.predicted,
            "signals": _signals(),
            "boundaries": {},
            "added": [],
            "episode_note": "",
        }
        defaults.update(kwargs)
        self.store.save_episode(**defaults)

    def test_pass_fail_uncertain_comment_reload(self) -> None:
        self._save(
            signals=_signals(TRANSLATION="PASS", DIRECTION="FAIL", GRIPPER="UNCERTAIN"),
        )
        current = self.store.current_signals(
            episode_id=self.episode_id,
            signal_contract_hash=self.hash,
            signal_contract_version=self.version,
        )
        self.assertEqual(current["TRANSLATION"].decision, "PASS")
        self.assertEqual(current["DIRECTION"].decision, "FAIL")
        self.assertEqual(current["GRIPPER"].decision, "UNCERTAIN")
        self._save(
            signals={
                **_signals(TRANSLATION="PASS"),
                "TRANSLATION": {"decision": "PASS", "comment": "ok with video"},
            }
        )
        current = self.store.current_signals(
            episode_id=self.episode_id,
            signal_contract_hash=self.hash,
            signal_contract_version=self.version,
        )
        self.assertEqual(current["TRANSLATION"].comment, "ok with video")
        self.assertEqual(current["TRANSLATION"].source_run_id, self.run_id)

    def test_same_hash_cross_run_reuse_and_different_hash_no_reuse(self) -> None:
        self._save(signals=_signals(ROTATION="PASS"))
        reused = self.store.current_signals(
            episode_id=self.episode_id,
            signal_contract_hash=self.hash,
            signal_contract_version=self.version,
        )
        self.assertEqual(reused["ROTATION"].source_run_id, "run_a")
        other_hash = self.store.current_signals(
            episode_id=self.episode_id,
            signal_contract_hash="b" * 64,
            signal_contract_version=self.version,
        )
        self.assertEqual(other_hash, {})

    def test_boundary_valid_redundant_misaligned(self) -> None:
        self._save(boundaries={"demo_0-B0001": {"decision": "VALID", "reason_code": "", "corrected_frame": "", "comment": ""}})
        current = self.store.current_boundaries(run_id=self.run_id, episode_id=self.episode_id)
        self.assertEqual(current["demo_0-B0001"].decision, "VALID")
        self.assertEqual(current["demo_0-B0001"].predicted_frame, 4)
        self._save(
            boundaries={
                "demo_0-B0001": {
                    "decision": "REDUNDANT",
                    "reason_code": "REDUNDANT_SHORT_PAUSE",
                    "corrected_frame": "",
                    "comment": "",
                }
            }
        )
        current = self.store.current_boundaries(run_id=self.run_id, episode_id=self.episode_id)
        self.assertEqual(current["demo_0-B0001"].decision, "REDUNDANT")
        self._save(
            boundaries={
                "demo_0-B0001": {
                    "decision": "MISALIGNED",
                    "reason_code": "MISALIGNED_GRIPPER",
                    "corrected_frame": "7",
                    "comment": "shift",
                }
            }
        )
        current = self.store.current_boundaries(run_id=self.run_id, episode_id=self.episode_id)
        self.assertEqual(current["demo_0-B0001"].corrected_frame, 7)
        self.assertEqual(current["demo_0-B0001"].predicted_frame, 4)

    def test_invalid_reason_pairing_and_frames(self) -> None:
        with self.assertRaises(ValidationFailed):
            self._save(
                boundaries={
                    "demo_0-B0001": {
                        "decision": "REDUNDANT",
                        "reason_code": "MISALIGNED_GRIPPER",
                        "corrected_frame": "",
                        "comment": "",
                    }
                }
            )
        with self.assertRaises(ValidationFailed):
            self._save(
                boundaries={
                    "demo_0-B0001": {
                        "decision": "MISALIGNED",
                        "reason_code": "MISALIGNED_GRIPPER",
                        "corrected_frame": "",
                        "comment": "",
                    }
                }
            )
        with self.assertRaises(ValidationFailed):
            self._save(
                boundaries={
                    "demo_0-B0001": {
                        "decision": "MISALIGNED",
                        "reason_code": "MISALIGNED_GRIPPER",
                        "corrected_frame": "99",
                        "comment": "",
                    }
                }
            )
        with self.assertRaises(ValidationFailed):
            self._save(
                boundaries={
                    "demo_0-B0001": {
                        "decision": "REDUNDANT",
                        "reason_code": "OTHER",
                        "corrected_frame": "",
                        "comment": "",
                    }
                }
            )
        with self.assertRaises(ValidationFailed):
            self._save(boundaries={"unknown-B9": {"decision": "VALID", "reason_code": "", "corrected_frame": "", "comment": ""}})

    def test_human_added_and_invalid(self) -> None:
        self._save(
            added=[{"added_group_id": "", "human_added_frame": "3", "reason_code": "MISSED_MOVE_STOP", "comment": "gap"}]
        )
        added = self.store.current_added(run_id=self.run_id, episode_id=self.episode_id)
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0].human_added_frame, 3)
        group = added[0].added_group_id
        self._save(
            added=[{"added_group_id": group, "human_added_frame": "5", "reason_code": "MISSED_MOVE_STOP", "comment": "moved"}]
        )
        added2 = self.store.current_added(run_id=self.run_id, episode_id=self.episode_id)
        self.assertEqual(len(added2), 1)
        self.assertEqual(added2[0].human_added_frame, 5)
        conn = sqlite3.connect(str(self.store.sqlite_path))
        n = conn.execute(f"SELECT COUNT(*) FROM {ADDED_TABLE}").fetchone()[0]
        conn.close()
        self.assertEqual(n, 2)
        with self.assertRaises(ValidationFailed):
            self._save(added=[{"added_group_id": "", "human_added_frame": "", "reason_code": "MISSED_MOVE_STOP", "comment": ""}])
        with self.assertRaises(ValidationFailed):
            self._save(added=[{"added_group_id": "", "human_added_frame": "3", "reason_code": "OTHER", "comment": ""}])
        with self.assertRaises(ValidationFailed):
            self._save(added=[{"added_group_id": "", "human_added_frame": "99", "reason_code": "MISSED_MOVE_STOP", "comment": ""}])

    def test_history_two_reviews_latest_resolved(self) -> None:
        self._save(signals=_signals(ACTION="PASS"), episode_note="first")
        self._save(signals=_signals(ACTION="FAIL"), episode_note="second")
        current = self.store.current_signals(
            episode_id=self.episode_id,
            signal_contract_hash=self.hash,
            signal_contract_version=self.version,
        )
        self.assertEqual(current["ACTION"].decision, "FAIL")
        counts = self.store.history_counts(
            run_id=self.run_id,
            episode_id=self.episode_id,
            signal_contract_hash=self.hash,
        )
        self.assertGreaterEqual(counts["signal"], 2)
        self.assertEqual(self.store.current_note(run_id=self.run_id, episode_id=self.episode_id).comment, "second")
        conn = sqlite3.connect(str(self.store.sqlite_path))
        note_n = conn.execute("SELECT COUNT(*) FROM episode_note_history").fetchone()[0]
        conn.close()
        self.assertEqual(note_n, 2)

    def test_transaction_rollback(self) -> None:
        self.store.fail_after_signal = True
        with self.assertRaises(ValidationFailed):
            self._save(signals=_signals(VIDEO_ALIGNMENT="PASS"))
        self.store.fail_after_signal = False
        current = self.store.current_signals(
            episode_id=self.episode_id,
            signal_contract_hash=self.hash,
            signal_contract_version=self.version,
        )
        self.assertEqual(current, {})


class ReviewWebTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self._tmp.name)
        self.registry = self.root / "web" / "g1_audit_run_registry.json"
        self.owner_db = self.root / "web" / "owner.sqlite3"
        self.run_root = write_synthetic_run(self.root / "runs", n_episodes=6)
        auto_register(self.registry, self.run_root, owner_db_path=self.owner_db)
        self.service = G1AuditWebInput(
            project_root=self.root,
            registry_path=self.registry,
            owner_db_path=self.owner_db,
        )
        proxy = Mock()
        proxy.register_video.side_effect = lambda source, run_id, episode_id: _FakeIdent("b" * 64)
        proxy.ensure_proxy_file.side_effect = lambda sha, profile: Path(self.run_root / "media/demo_0/video.mp4")
        app = create_app(
            project_root=self.root,
            web_input=self.service,
            video_proxy=proxy,
            reviewer="TEMP_TEST_REVIEWER",
        )
        self.client = TestClient(app)
        self.run_id = self.run_root.name

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _form(self, **extra):
        data = {
            "action": "save",
            "active_tab": "p2",
            "episode_note": "",
        }
        for name in SIGNAL_NAMES:
            data[f"signal_{name}_decision"] = "NOT_REVIEWED"
            data[f"signal_{name}_comment"] = ""
        data["bound_demo_0-B0001_decision"] = "NOT_REVIEWED"
        data["bound_demo_0-B0001_reason_code"] = ""
        data["bound_demo_0-B0001_corrected_frame"] = ""
        data["bound_demo_0-B0001_comment"] = ""
        data.update(extra)
        return data

    def test_six_signal_controls_and_progress_filters(self) -> None:
        page = self.client.get(f"/audit/{self.run_id}/episode/data--demo_0")
        self.assertEqual(page.status_code, 200)
        for name in SIGNAL_NAMES:
            self.assertIn(f"signal_{name}_decision", page.text)
        self.assertIn("P1 Signal Review", page.text)
        self.assertIn("P2 Boundary Review", page.text)
        self.assertIn("btn-save", page.text)
        self.assertIn("btn-save-next", page.text)
        self.assertIn("Human Calibration Export", page.text)
        self.assertIn("btn-add-missed", page.text)
        self.assertIn("末端平移 / 速度是否与视频中的实际运动对应", page.text)
        data = self._form(
            **{
                "signal_TRANSLATION_decision": "FAIL",
                "bound_demo_0-B0001_decision": "REDUNDANT",
                "bound_demo_0-B0001_reason_code": "REDUNDANT_DIRECTION_JITTER",
            }
        )
        saved = self.client.post(f"/audit/{self.run_id}/episode/data--demo_0/review", data=data, follow_redirects=True)
        self.assertEqual(saved.status_code, 200)
        fail_q = self.client.get(f"/audit/{self.run_id}?filter=SIGNAL_FAIL", follow_redirects=True)
        self.assertIn("data/demo_0", fail_q.text)
        red_q = self.client.get(f"/audit/{self.run_id}?filter=HAS_REDUNDANT", follow_redirects=True)
        self.assertIn("data/demo_0", red_q.text)
        in_prog = self.client.get(f"/audit/{self.run_id}?filter=IN_PROGRESS", follow_redirects=True)
        self.assertIn("data/demo_0", in_prog.text)

    def test_save_and_save_next(self) -> None:
        data = self._form(
            **{
                "signal_GRIPPER_decision": "PASS",
                "bound_demo_0-B0001_decision": "VALID",
            }
        )
        saved = self.client.post(f"/audit/{self.run_id}/episode/data--demo_0/review", data=data, follow_redirects=False)
        self.assertEqual(saved.status_code, 303)
        again = self.client.get(f"/audit/{self.run_id}/episode/data--demo_0")
        self.assertIn('name="signal_GRIPPER_decision"', again.text)
        self.assertIn('value="PASS" selected', again.text)
        nxt = self._form(
            **{
                "action": "save_next",
                "signal_GRIPPER_decision": "PASS",
                "bound_demo_0-B0001_decision": "VALID",
            }
        )
        jumped = self.client.post(f"/audit/{self.run_id}/episode/data--demo_0/review", data=nxt, follow_redirects=False)
        self.assertEqual(jumped.status_code, 303)
        self.assertIn("data--demo_1", jumped.headers["location"])

    def test_validation_keeps_input(self) -> None:
        data = self._form(
            **{
                "bound_demo_0-B0001_decision": "MISALIGNED",
                "bound_demo_0-B0001_reason_code": "MISALIGNED_GRIPPER",
            }
        )
        failed = self.client.post(f"/audit/{self.run_id}/episode/data--demo_0/review", data=data, follow_redirects=True)
        self.assertEqual(failed.status_code, 400)
        self.assertIn("VALIDATION_FAILED", failed.text)
        self.assertIn("MISALIGNED", failed.text)

    def test_missed_save_and_progress(self) -> None:
        data = self._form(
            missed_0_group_id="",
            missed_0_frame="2",
            missed_0_reason_code="MISSED_GRIPPER_TRANSITION",
            missed_0_comment="add",
        )
        saved = self.client.post(f"/audit/{self.run_id}/episode/data--demo_0/review", data=data, follow_redirects=True)
        self.assertEqual(saved.status_code, 200)
        self.assertIn("HUMAN_ADD_1", saved.text)
        missed_q = self.client.get(f"/audit/{self.run_id}?filter=HAS_MISSED", follow_redirects=True)
        self.assertIn("data/demo_0", missed_q.text)


class ReviewImmutabilityTests(unittest.TestCase):
    def test_save_does_not_touch_run_or_legacy(self) -> None:
        legacy = PROJECT2_ROOT / "outputs" / "g1_p2_boundary_audit"
        versioned = PROJECT2_ROOT / "outputs" / "g1_audit_runs" / "g1_exploratory_audit_20260916_214523_1ba11d9d"
        if not (legacy / "episode_manifest.csv").is_file():
            self.skipTest("legacy missing")
        if not (versioned / "run_meta.json").is_file():
            self.skipTest("bootstrap run missing")
        before_legacy = tree_fingerprint(legacy)
        before_run = tree_fingerprint(versioned)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            store = ReviewStore(Path(tmp) / "x.sqlite3", reviewer="TEMP_TEST_REVIEWER")
            store.save_episode(
                run_id="g1_exploratory_audit_20260916_214523_1ba11d9d",
                episode_id="data/demo_0",
                signal_contract_version="g1_p1_signal_contract.v0",
                signal_contract_hash="24c62aef1f7bdbd14f0c1a075e8ecaafa762d4bcce454ad25842d54a2f34232d",
                episode_length=118,
                predicted={"demo_0-B0001": 4},
                signals=_signals(TRANSLATION="PASS"),
                boundaries={"demo_0-B0001": {"decision": "VALID", "reason_code": "", "corrected_frame": "", "comment": ""}},
                added=[],
                episode_note="temp",
            )
        self.assertEqual(tree_fingerprint(legacy)["tree_fingerprint"], before_legacy["tree_fingerprint"])
        self.assertEqual(tree_fingerprint(versioned)["tree_fingerprint"], before_run["tree_fingerprint"])


if __name__ == "__main__":
    unittest.main()
