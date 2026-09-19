"""Tests for 12-Episode Calibration Baseline discovery and identity gates."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from project2_g1.baseline_calibration_run import (
    EXPECTED_CONFIG_HASH,
    EXPECTED_SIGNAL_HASH,
    compare_prediction_episodes,
    discover_existing_baseline_run,
    identity_errors,
    load_combined_manifest,
)
from project2_g1.fresh_calibration_run import EXPECTED_CONFIG_HASH as FRESH_CONFIG
from project2_g1_audit_web.contract import validate_g1_audit_folder
from project2_g1_audit_web.hashes import sha256_file, tree_fingerprint


EXPECTED_EPISODES = {
    "data/demo_0", "data/demo_32", "data/demo_179", "data/demo_230", "data/demo_242", "data/demo_278",
    "data/demo_150", "data/demo_162", "data/demo_213", "data/demo_255", "data/demo_260", "data/demo_270",
}


def _meta(**overrides) -> dict:
    payload = {
        "run_stage": "CALIBRATION",
        "episode_count": 12,
        "search_stage": "BASELINE",
        "config_hash": EXPECTED_CONFIG_HASH,
        "signal_contract_hash": EXPECTED_SIGNAL_HASH,
        "final_boundary_semantics": "MATERIALIZED_V1",
        "calibration_config_role": "BASELINE_UNMODIFIED",
        "parameter_search_executed": False,
        "parameter_diff_count": 0,
    }
    payload.update(overrides)
    return payload


class BaselineDiscoveryTests(unittest.TestCase):
    def test_identity_accepts_qualifying_run(self) -> None:
        errors = identity_errors(
            _meta(), sorted(EXPECTED_EPISODES), ["CALIBRATION"] * 12,
            expected_episodes=EXPECTED_EPISODES,
            expected_config_hash=EXPECTED_CONFIG_HASH,
            expected_signal_hash=EXPECTED_SIGNAL_HASH,
        )
        self.assertEqual(errors, [])

    def test_wrong_episode_count_rejected(self) -> None:
        errors = identity_errors(
            _meta(episode_count=6), list(EXPECTED_EPISODES)[:6], ["CALIBRATION"] * 6,
            expected_episodes=EXPECTED_EPISODES,
            expected_config_hash=EXPECTED_CONFIG_HASH,
            expected_signal_hash=EXPECTED_SIGNAL_HASH,
        )
        self.assertTrue(any("episode_count" in item for item in errors))

    def test_wrong_episode_set_rejected(self) -> None:
        ids = sorted(EXPECTED_EPISODES - {"data/demo_0"} | {"data/demo_999"})
        errors = identity_errors(
            _meta(), ids, ["CALIBRATION"] * 12,
            expected_episodes=EXPECTED_EPISODES,
            expected_config_hash=EXPECTED_CONFIG_HASH,
            expected_signal_hash=EXPECTED_SIGNAL_HASH,
        )
        self.assertTrue(any("exact-set" in item for item in errors))

    def test_wrong_config_hash_rejected(self) -> None:
        errors = identity_errors(
            _meta(config_hash="0" * 64), sorted(EXPECTED_EPISODES), ["CALIBRATION"] * 12,
            expected_episodes=EXPECTED_EPISODES,
            expected_config_hash=EXPECTED_CONFIG_HASH,
            expected_signal_hash=EXPECTED_SIGNAL_HASH,
        )
        self.assertTrue(any("config_hash" in item for item in errors))

    def test_wrong_signal_hash_rejected(self) -> None:
        errors = identity_errors(
            _meta(signal_contract_hash="1" * 64), sorted(EXPECTED_EPISODES), ["CALIBRATION"] * 12,
            expected_episodes=EXPECTED_EPISODES,
            expected_config_hash=EXPECTED_CONFIG_HASH,
            expected_signal_hash=EXPECTED_SIGNAL_HASH,
        )
        self.assertTrue(any("signal_contract_hash" in item for item in errors))

    def test_wrong_search_stage_rejected(self) -> None:
        errors = identity_errors(
            _meta(search_stage="A"), sorted(EXPECTED_EPISODES), ["CALIBRATION"] * 12,
            expected_episodes=EXPECTED_EPISODES,
            expected_config_hash=EXPECTED_CONFIG_HASH,
            expected_signal_hash=EXPECTED_SIGNAL_HASH,
        )
        self.assertTrue(any("search_stage" in item for item in errors))

    def test_discover_existing_official_runs_not_found(self) -> None:
        manifest = load_combined_manifest(
            ROOT / "outputs/g1_p3_canonical_gt/g1_canonical_gt_20260918_131636_c9916b89/combined_calibration_manifest.json"
        )
        discovered = discover_existing_baseline_run(
            runs_root=ROOT / "outputs/g1_audit_runs",
            registry_path=ROOT / "outputs/g1_audit_web/g1_audit_run_registry.json",
            combined_manifest=manifest,
        )
        qualifying = [item for item in discovered["audits"] if item.get("qualifies")]
        if discovered["status"] == "FOUND":
            self.assertEqual(len(qualifying), 1)
            return
        self.assertEqual(discovered["status"], "NOT_FOUND")
        self.assertFalse(qualifying)
        reasons = " ".join(" ".join(item.get("reasons") or []) for item in discovered["audits"])
        self.assertTrue("episode_count" in reasons or "search_stage" in reasons)

    def test_compare_prediction_detects_frame_mismatch(self) -> None:
        temp = tempfile.TemporaryDirectory()
        try:
            left = Path(temp.name) / "left"
            right = Path(temp.name) / "right"
            for root, frame in ((left, "4"), (right, "5")):
                (root / "diagnostic" / "demo_0").mkdir(parents=True)
                (root / "run_meta.json").write_text(json.dumps({
                    "manifest_path": "episode_manifest.csv",
                }), encoding="utf-8")
                (root / "episode_manifest.csv").write_text(
                    "episode_id,native_episode_key,length\ndata/demo_0,demo_0,10\n", encoding="utf-8"
                )
                header = "frame,candidate_type,member_candidate_types,member_candidate_frames\n"
                (root / "diagnostic" / "demo_0" / "final_boundaries.csv").write_text(
                    header + f"{frame},GRIPPER_TRANSITION,GRIPPER_TRANSITION,{frame}\n", encoding="utf-8"
                )
                (root / "diagnostic" / "demo_0" / "candidate_boundaries.csv").write_text("candidate_id\nC1\n", encoding="utf-8")
                (root / "diagnostic" / "demo_0" / "segment_manifest.csv").write_text("start_frame,end_frame\n0,3\n", encoding="utf-8")
            result = compare_prediction_episodes(left, right, ["data/demo_0"])
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any(item["field"] == "finals" for item in result["differences"]))
        finally:
            temp.cleanup()


class OfficialTwelveEpisodeBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = load_combined_manifest(
            ROOT / "outputs/g1_p3_canonical_gt/g1_canonical_gt_20260918_131636_c9916b89/combined_calibration_manifest.json"
        )
        discovered = discover_existing_baseline_run(
            runs_root=ROOT / "outputs/g1_audit_runs",
            registry_path=ROOT / "outputs/g1_audit_web/g1_audit_run_registry.json",
            combined_manifest=cls.manifest,
        )
        cls.discovered = discovered
        if discovered["status"] != "FOUND":
            raise unittest.SkipTest("12-Episode baseline run not materialized yet")
        cls.run_root = Path(discovered["run"]["run_root"])
        cls.loaded = validate_g1_audit_folder(cls.run_root)

    def test_twelve_exact_set_and_roles(self) -> None:
        actual = {row["episode_id"] for row in self.loaded["episodes"]}
        self.assertEqual(actual, set(self.manifest["episode_ids"]))
        self.assertEqual(len(actual), 12)
        self.assertEqual({row["set_role"] for row in self.loaded["episodes"]}, {"CALIBRATION"})
        self.assertEqual(self.loaded["run_meta"]["run_stage"], "CALIBRATION")
        self.assertEqual(self.loaded["run_meta"]["search_stage"], "BASELINE")

    def test_parameter_diff_zero_materialized_and_hashes(self) -> None:
        meta = self.loaded["run_meta"]
        self.assertEqual(meta["config_hash"], FRESH_CONFIG)
        self.assertEqual(meta["signal_contract_hash"], EXPECTED_SIGNAL_HASH)
        self.assertEqual(int(meta["parameter_diff_count"]), 0)
        self.assertFalse(meta["parameter_search_executed"])
        self.assertEqual(meta["final_boundary_semantics"], "MATERIALIZED_V1")
        self.assertEqual(self.loaded["final_member_semantics"], "MATERIALIZED")

    def test_validator_pass(self) -> None:
        self.assertEqual(self.loaded["run_id"], self.discovered["run"]["run_id"])

    def test_seed_and_fresh_prediction_consistency(self) -> None:
        seed = compare_prediction_episodes(
            self.run_root,
            ROOT / "outputs/g1_audit_runs/g1_exploratory_audit_20260917_141541_fe251439",
            self.manifest["seed_episode_ids"],
        )
        fresh = compare_prediction_episodes(
            self.run_root,
            ROOT / "outputs/g1_audit_runs/g1_calibration_20260918_094455_df2ce8b2",
            self.manifest["fresh_episode_ids"],
        )
        self.assertEqual(seed["status"], "PASS", seed)
        self.assertEqual(fresh["status"], "PASS", fresh)

    def test_source_immutability_fingerprints_still_match_known_values(self) -> None:
        export_root = ROOT / "outputs/g1_audit_web/human_calibration_export"
        self.assertEqual(
            tree_fingerprint(export_root / "g1_cal_seed_export_20260917_214637_2f8d8802")["tree_fingerprint"],
            "8ba31e9721ee3554b3b56b3bc46ff041c175b39865ea76c918f931b0a6d355c7",
        )
        self.assertEqual(
            tree_fingerprint(export_root / "g1_cal_export_20260918_120335_81c068bf")["tree_fingerprint"],
            "01a3c732ae8b193a72ede845363105d0742b2f8357685e1f61d0a1b52dc3eb1f",
        )
        self.assertEqual(
            tree_fingerprint(ROOT / "outputs/g1_p3_canonical_gt/g1_canonical_gt_20260918_131636_c9916b89")["tree_fingerprint"],
            "335a8d62d9871e26f34a6e887206cbb48504dfc551337c024086e7252ac399ef",
        )
        sqlite = ROOT / "outputs/g1_audit_web/g1_audit_web_owner.sqlite3"
        self.assertEqual(
            sha256_file(sqlite),
            "076b3fe1504b23334cc861b32fb3145efaa92f187aa4002be1afcee7bc96c718",
        )
        self.assertEqual(
            sha256_file(ROOT / "outputs/g1_audit_runs/g1_exploratory_audit_20260917_141541_fe251439/run_meta.json"),
            "15f06215aab21648bd0091e93d9322c98145a8ca774a7b76ed7afb191759cda7",
        )
        self.assertEqual(
            sha256_file(ROOT / "outputs/g1_audit_runs/g1_calibration_20260918_094455_df2ce8b2/run_meta.json"),
            "cc10f11f90bd7148bda9d33626d546c7578c5a4c7de61c19685db255a68ad864",
        )


if __name__ == "__main__":
    unittest.main()
