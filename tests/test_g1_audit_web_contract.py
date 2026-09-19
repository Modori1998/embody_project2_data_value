"""G1 Audit Web Batch 1: config hash + P2_G1_AUDIT_FOLDER_V1 contract tests."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TESTS = Path(__file__).resolve().parent
for path in (SRC, TESTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from g1_audit_web_fixtures import write_synthetic_run
from project2_g1_audit_web.contract import CONTRACT_VERSION, ContractError, validate_g1_audit_folder
from project2_g1_audit_web.hashes import config_hash_from_payload, config_hash_from_path


class HashTests(unittest.TestCase):
    def test_same_content_different_key_order_same_hash(self) -> None:
        left = {"b": 1, "a": {"z": 2, "y": 3}}
        right = {"a": {"y": 3, "z": 2}, "b": 1}
        self.assertEqual(config_hash_from_payload(left), config_hash_from_payload(right))

    def test_threshold_change_changes_hash(self) -> None:
        base = {"parameters": {"motion_speed_threshold": {"value": 0.02}}}
        changed = {"parameters": {"motion_speed_threshold": {"value": 0.03}}}
        self.assertNotEqual(config_hash_from_payload(base), config_hash_from_payload(changed))


class ContractTests(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_valid_synthetic_run_passes(self) -> None:
        run_root = write_synthetic_run(self.root, n_episodes=2)
        loaded = validate_g1_audit_folder(run_root)
        self.assertEqual(loaded["run_meta"]["contract_version"], CONTRACT_VERSION)
        self.assertEqual(len(loaded["episodes"]), 2)

    def test_wrong_contract_version_fails(self) -> None:
        run_root = write_synthetic_run(self.root, contract_version="M07_AUDIT_FOLDER_V1_1")
        with self.assertRaises(ContractError) as ctx:
            validate_g1_audit_folder(run_root)
        self.assertIn("contract_version mismatch", str(ctx.exception))

    def test_duplicate_episode_fails(self) -> None:
        run_root = write_synthetic_run(self.root, duplicate_episode=True)
        with self.assertRaises(ContractError) as ctx:
            validate_g1_audit_folder(run_root)
        self.assertIn("duplicate episode_id", str(ctx.exception))

    def test_missing_plot_fails(self) -> None:
        run_root = write_synthetic_run(self.root, missing_plot=True)
        with self.assertRaises(ContractError) as ctx:
            validate_g1_audit_folder(run_root)
        self.assertIn("missing plot_relpath", str(ctx.exception))

    def test_path_escape_fails(self) -> None:
        run_root = write_synthetic_run(self.root, escape_path=True)
        with self.assertRaises(ContractError) as ctx:
            validate_g1_audit_folder(run_root)
        self.assertIn("..", str(ctx.exception))

    def test_hash_mismatch_fails(self) -> None:
        run_root = write_synthetic_run(self.root, mutate_hash=True)
        with self.assertRaises(ContractError) as ctx:
            validate_g1_audit_folder(run_root)
        self.assertIn("config_hash mismatch", str(ctx.exception))

    def test_file_key_order_same_hash(self) -> None:
        a = self.root / "a.json"
        b = self.root / "b.json"
        a.write_text('{"z": 1, "a": {"v": 2, "u": 3}}\n', encoding="utf-8")
        b.write_text('{"a": {"u": 3, "v": 2}, "z": 1}\n', encoding="utf-8")
        self.assertEqual(config_hash_from_path(a), config_hash_from_path(b))


if __name__ == "__main__":
    unittest.main()
