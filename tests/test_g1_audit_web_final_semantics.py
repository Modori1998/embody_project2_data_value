"""G1 Audit Web: Final Boundary Primary / Merged Evidence display."""

from __future__ import annotations

import sqlite3
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

from g1_audit_web_fixtures import write_merge_semantics_run, write_synthetic_run
from project2_g1_audit_web.app import create_app
from project2_g1_audit_web.registry import auto_register
from project2_g1_audit_web.reviews import BOUNDARY_DECISIONS, SIGNAL_NAMES
from project2_g1_audit_web.service import G1AuditWebInput


class _FakeIdent:
    def __init__(self, digest: str = "b" * 64):
        self.source_sha256 = digest
        self.needs_proxy = True
        self.proxy_profile_version = "H264_BROWSER_V1"
        self.proxy_url = f"/proxy/video/{digest}/H264_BROWSER_V1.mp4"


class FinalSemanticsWebTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self._tmp.name)
        self.registry = self.root / "web" / "g1_audit_run_registry.json"
        self.owner_db = self.root / "web" / "owner.sqlite3"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _client(self, run_root: Path) -> tuple[TestClient, str]:
        auto_register(self.registry, run_root, owner_db_path=self.owner_db)
        service = G1AuditWebInput(
            project_root=self.root,
            registry_path=self.registry,
            owner_db_path=self.owner_db,
        )
        proxy = Mock()
        proxy.register_video.side_effect = lambda source, run_id, episode_id: _FakeIdent()
        proxy.ensure_proxy_file.side_effect = lambda sha, profile: Path(
            run_root / "media/demo_0/video.mp4"
        )
        app = create_app(
            project_root=self.root,
            web_input=service,
            video_proxy=proxy,
            reviewer="TEMP_SEMANTICS_TEST",
        )
        return TestClient(app), run_root.name

    def _p2(self, client: TestClient, run_id: str) -> str:
        resp = client.get(f"/audit/{run_id}/episode/data--demo_0?tab=p2")
        self.assertEqual(resp.status_code, 200)
        return resp.text

    def test_materialized_run_renders_primary_and_two_member_merge(self) -> None:
        run_root = write_merge_semantics_run(self.root / "runs", materialized=True)
        client, run_id = self._client(run_root)
        html = self._p2(client, run_id)
        self.assertIn("Primary｜代表事件", html)
        self.assertIn("GRIPPER_TRANSITION｜夹爪切换", html)
        self.assertIn("@56", html)
        self.assertIn("Merged Evidence｜合并证据", html)
        self.assertIn("DIRECTION_CHANGE｜主方向变化", html)
        self.assertIn("@57", html)
        self.assertIn('data-boundary-id="demo_0-B0002"', html)
        self.assertIn('data-member-count="2"', html)
        self.assertNotIn("Legacy Run｜成员语义由 Candidate 表 join 展示", html)

    def test_materialized_three_member_merge(self) -> None:
        run_root = write_merge_semantics_run(self.root / "runs", materialized=True)
        client, run_id = self._client(run_root)
        html = self._p2(client, run_id)
        self.assertIn('data-boundary-id="demo_0-B0003"', html)
        self.assertIn('data-member-count="3"', html)
        self.assertIn("GRIPPER_TRANSITION｜夹爪切换", html)
        self.assertIn("@112", html)
        self.assertIn("MOVE_TO_IDLE｜运动→静止", html)
        self.assertIn("@113", html)
        self.assertIn("DIRECTION_CHANGE｜主方向变化", html)
        self.assertIn("@114", html)

    def test_single_member_has_no_redundant_merged_evidence(self) -> None:
        run_root = write_merge_semantics_run(self.root / "runs", materialized=True)
        client, run_id = self._client(run_root)
        html = self._p2(client, run_id)
        b1_start = html.find('data-boundary-id="demo_0-B0001" data-decision')
        b2_start = html.find('data-boundary-id="demo_0-B0002" data-decision')
        self.assertGreater(b1_start, 0)
        self.assertGreater(b2_start, b1_start)
        card = html[b1_start:b2_start]
        self.assertIn("Primary｜代表事件", card)
        self.assertIn("GRIPPER_TRANSITION｜夹爪切换", card)
        self.assertIn("@4", card)
        self.assertNotIn("Merged Evidence｜合并证据", card)
        self.assertIn('data-member-count="1"', card)

    def test_legacy_run_still_loads_and_joins_member_semantics(self) -> None:
        run_root = write_merge_semantics_run(self.root / "runs", materialized=False)
        client, run_id = self._client(run_root)
        html = self._p2(client, run_id)
        self.assertNotIn("VALIDATION_FAILED", html)
        self.assertIn("Legacy Run｜成员语义由 Candidate 表 join 展示", html)
        self.assertIn("GRIPPER_TRANSITION｜夹爪切换", html)
        self.assertIn("@56", html)
        self.assertIn("DIRECTION_CHANGE｜主方向变化", html)
        self.assertIn("@57", html)
        self.assertIn("Merged Evidence｜合并证据", html)

    def test_unknown_member_type_is_visible(self) -> None:
        run_root = write_merge_semantics_run(
            self.root / "runs",
            materialized=True,
            unknown_member=True,
        )
        client, run_id = self._client(run_root)
        html = self._p2(client, run_id)
        self.assertIn("UNKNOWN_CODE::WEIRD_UNREGISTERED_TYPE", html)
        self.assertIn("WEIRD_UNREGISTERED_TYPE", html)

    def test_p2_review_form_and_save_unchanged(self) -> None:
        run_root = write_merge_semantics_run(self.root / "runs", materialized=True)
        client, run_id = self._client(run_root)
        html = self._p2(client, run_id)
        for decision in BOUNDARY_DECISIONS:
            self.assertIn(f">{decision}｜", html.replace("&gt;", ">"))
        self.assertIn('name="bound_demo_0-B0002_decision"', html)
        self.assertIn('id="btn-save"', html)
        self.assertIn('id="btn-save-next"', html)
        self.assertNotIn("bound_demo_0-C0002_decision", html)
        self.assertNotIn("bound_demo_0-C0003_decision", html)
        data = {
            "action": "save",
            "active_tab": "p2",
            "episode_note": "",
            "bound_demo_0-B0001_decision": "VALID",
            "bound_demo_0-B0001_reason_code": "",
            "bound_demo_0-B0001_corrected_frame": "",
            "bound_demo_0-B0001_comment": "",
            "bound_demo_0-B0002_decision": "NOT_REVIEWED",
            "bound_demo_0-B0002_reason_code": "",
            "bound_demo_0-B0002_corrected_frame": "",
            "bound_demo_0-B0002_comment": "",
            "bound_demo_0-B0003_decision": "NOT_REVIEWED",
            "bound_demo_0-B0003_reason_code": "",
            "bound_demo_0-B0003_corrected_frame": "",
            "bound_demo_0-B0003_comment": "",
        }
        for name in SIGNAL_NAMES:
            data.setdefault(f"signal_{name}_decision", "NOT_REVIEWED")
            data.setdefault(f"signal_{name}_comment", "")
        saved = client.post(
            f"/audit/{run_id}/episode/data--demo_0/review",
            data=data,
            follow_redirects=True,
        )
        self.assertEqual(saved.status_code, 200)
        self.assertIn("saved=1", str(saved.url) + saved.text)
        conn = sqlite3.connect(self.owner_db)
        n = conn.execute("SELECT COUNT(*) FROM predicted_boundary_review_history").fetchone()[0]
        conn.close()
        self.assertEqual(n, 1)

    def test_p1_layout_and_diagnostics_unchanged(self) -> None:
        run_root = write_synthetic_run(self.root / "runs", n_episodes=2)
        client, run_id = self._client(run_root)
        p1 = client.get(f"/audit/{run_id}/episode/data--demo_0?tab=p1")
        self.assertEqual(p1.status_code, 200)
        self.assertIn('data-mode="p1"', p1.text)
        self.assertIn('id="p1-plot-col"', p1.text)
        self.assertIn('id="p1-review-col"', p1.text)
        self.assertIn("P1 Signal Review", p1.text)
        diag = client.get(f"/audit/{run_id}/episode/data--demo_0?tab=diag")
        self.assertEqual(diag.status_code, 200)
        self.assertIn("<h3>Final Boundary</h3>", diag.text)
        self.assertIn("<h3>Candidate</h3>", diag.text)
        self.assertIn("<h3>Decisions</h3>", diag.text)
        self.assertIn("<h3>Segments</h3>", diag.text)
        self.assertIn('id="tbl-candidate"', diag.text)
        self.assertIn('id="tbl-decision"', diag.text)


if __name__ == "__main__":
    unittest.main()
