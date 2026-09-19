"""G1 Audit Web Batch 1: registry + owner override tests."""

from __future__ import annotations

import json
import sqlite3
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
from project2_g1_audit_web.contract import ContractError
from project2_g1_audit_web.registry import (
    active_records,
    auto_register,
    load_registry,
    owner_override,
    restore_run,
)
from project2_g1_audit_web.service import G1AuditWebInput, OwnerPathError


class RegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile

        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self._tmp.name)
        self.registry = self.root / "g1_audit_web" / "g1_audit_run_registry.json"
        self.owner_db = self.root / "g1_audit_web" / "g1_audit_web_owner.sqlite3"
        self.generator_registry = self.root / "generator_registry.json"
        self.generator_registry.write_text(json.dumps({"untouched": True}) + "\n", encoding="utf-8")
        self.generator_before = self.generator_registry.read_bytes()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_register_once_and_duplicate_blocked(self) -> None:
        run_root = write_synthetic_run(self.root / "runs")
        record = auto_register(self.registry, run_root, owner_db_path=self.owner_db)
        self.assertEqual(record.status, "AUTO_REGISTERED")
        with self.assertRaises(ContractError) as ctx:
            auto_register(self.registry, run_root, owner_db_path=self.owner_db)
        self.assertIn("duplicate run_id", str(ctx.exception))

    def test_disabled_run_hidden_and_restore(self) -> None:
        run_root = write_synthetic_run(self.root / "runs")
        auto_register(self.registry, run_root, owner_db_path=self.owner_db)
        owner_override(
            self.registry,
            run_id=run_root.name,
            status="DISABLED_BY_OWNER",
            reason="owner hide for test",
            owner_db_path=self.owner_db,
        )
        payload = load_registry(self.registry)
        self.assertEqual(active_records(payload), [])
        service = G1AuditWebInput(
            project_root=self.root,
            registry_path=self.registry,
            owner_db_path=self.owner_db,
        )
        self.assertEqual(service.list_effective_runs(), [])
        with self.assertRaises(OwnerPathError) as ctx:
            service.load_validated_run(run_root.name)
        self.assertIn("DISABLED_BY_OWNER", str(ctx.exception))
        restore_run(
            self.registry,
            run_id=run_root.name,
            reason="restore for test",
            owner_db_path=self.owner_db,
        )
        restored = service.list_effective_runs()
        self.assertEqual(len(restored), 1)
        self.assertTrue(restored[0].enabled)

    def test_manual_override_does_not_modify_generator_registry(self) -> None:
        run_root = write_synthetic_run(self.root / "runs")
        auto_register(self.registry, run_root, owner_db_path=self.owner_db)
        owner_override(
            self.registry,
            run_id=run_root.name,
            status="MANUAL_OVERRIDE",
            reason="path override for test",
            owner_db_path=self.owner_db,
            run_root=run_root,
        )
        self.assertEqual(self.generator_registry.read_bytes(), self.generator_before)
        conn = sqlite3.connect(self.owner_db)
        try:
            rows = conn.execute("SELECT event_type FROM owner_override_event").fetchall()
        finally:
            conn.close()
        self.assertTrue(rows)


if __name__ == "__main__":
    unittest.main()
