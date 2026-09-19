"""G1 Audit Web P1/P2 layout patch tests. UI only; uses a temp review DB."""

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

from g1_audit_web_fixtures import write_synthetic_run
from project2_g1.paths import PROJECT2_ROOT
from project2_g1_audit_web.app import create_app
from project2_g1_audit_web.registry import auto_register, default_owner_db_path
from project2_g1_audit_web.reviews import SIGNAL_NAMES
from project2_g1_audit_web.service import G1AuditWebInput
from project2_g1_audit_web.vocab import PRIVILEGED_SUBPLOT_HINT, SIGNAL_AUDIT_QUESTIONS, SIGNAL_REVIEW_GUIDES


class _FakeIdent:
    def __init__(self, digest: str = "b" * 64):
        self.source_sha256 = digest
        self.needs_proxy = True
        self.proxy_profile_version = "H264_BROWSER_V1"
        self.proxy_url = f"/proxy/video/{digest}/H264_BROWSER_V1.mp4"


class LayoutPatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self._tmp.name)
        self.registry = self.root / "web" / "g1_audit_run_registry.json"
        self.owner_db = self.root / "web" / "layout_test.sqlite3"
        self.run_root = write_synthetic_run(self.root / "runs", n_episodes=6)
        auto_register(self.registry, self.run_root, owner_db_path=self.owner_db)
        self.service = G1AuditWebInput(
            project_root=self.root,
            registry_path=self.registry,
            owner_db_path=self.owner_db,
        )
        proxy = Mock()
        proxy.register_video.side_effect = lambda source, run_id, episode_id: _FakeIdent()
        proxy.ensure_proxy_file.side_effect = lambda sha, profile: Path(self.run_root / "media/demo_0/video.mp4")
        app = create_app(
            project_root=self.root,
            web_input=self.service,
            video_proxy=proxy,
            reviewer="TEMP_LAYOUT_TEST",
        )
        self.client = TestClient(app)
        self.run_id = self.run_root.name

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _page(self, tab: str = "p1") -> str:
        resp = self.client.get(f"/audit/{self.run_id}/episode/data--demo_0?tab={tab}")
        self.assertEqual(resp.status_code, 200)
        return resp.text

    def test_p1_mode_renders_video_signal_plot_and_review(self) -> None:
        html = self._page("p1")
        self.assertIn('id="audit-workspace"', html)
        self.assertIn('data-mode="p1"', html)
        self.assertIn('id="p1-plot-col"', html)
        self.assertIn('id="p1-review-col"', html)
        self.assertIn('data-media-key="video"', html)
        self.assertIn('preload="none"', html)
        self.assertIn('data-media-key="signal_plot"', html)
        self.assertIn("class=\"plot p1-plot\"", html)
        self.assertIn("P1 Signal Review｜信号审核", html)
        self.assertIn("这里不是判断 Boundary 切得对不对", html)
        for name in SIGNAL_NAMES:
            self.assertIn(f'signal_{name}_decision', html)
            self.assertIn(SIGNAL_AUDIT_QUESTIONS[name], html)
        self.assertIn(PRIVILEGED_SUBPLOT_HINT, html)
        for name, guide in SIGNAL_REVIEW_GUIDES.items():
            self.assertIn(guide.primary, html)
            if guide.support:
                self.assertIn(guide.support, html)
        self.assertIn("主要看：子图 1「末端位置」", html)
        self.assertIn("主要看：子图 3「主方向变化证据」", html)
        self.assertIn("主要看：子图 4「实际夹爪状态」", html)
        self.assertIn("主要看：子图 6「末端旋转变化」", html)
        self.assertIn("主要看：子图 7「控制指令变化幅度」", html)
        self.assertIn("主要看：子图 1–7", html)
        self.assertNotIn("主要看：子图 8", html)
        self.assertIn("Current Frame:", html)
        self.assertIn("Jump to Frame", html)
        self.assertIn('data-frame-delta="-1"', html)
        self.assertIn('data-frame-delta="5"', html)

    def test_p2_mode_preserves_split_and_boundary_plot_primary(self) -> None:
        html = self._page("p2")
        self.assertIn('data-mode="p2"', html)
        self.assertIn("audit-split-media", html)
        self.assertIn("audit-split-tables", html)
        self.assertIn("P2 Boundary Review", html)
        self.assertIn('id="p2-mode-plots"', html)
        self.assertIn('data-media-key="signal_boundary_plot"', html)
        self.assertIn("p2-primary-plot", html)
        self.assertIn("次级查看", html)
        self.assertIn("btn-save", html)
        self.assertIn("btn-save-next", html)

    def test_tab_switch_js_keeps_form_and_does_not_reload(self) -> None:
        html = self._page("p1")
        js = self.client.get("/static/review_ui.js").text
        self.assertIn('id="review-form"', html)
        self.assertIn('name="signal_TRANSLATION_decision"', html)
        self.assertIn('name="bound_demo_0-B0001_decision"', html)
        self.assertIn("workspace.dataset.mode", js)
        self.assertNotIn("location.reload", js)
        self.assertNotIn("form.submit()", js)

    def test_save_still_works_on_layout_page(self) -> None:
        data = {
            "action": "save",
            "active_tab": "p1",
            "episode_note": "",
            "signal_TRANSLATION_decision": "PASS",
            "signal_TRANSLATION_comment": "",
            "bound_demo_0-B0001_decision": "NOT_REVIEWED",
            "bound_demo_0-B0001_reason_code": "",
            "bound_demo_0-B0001_corrected_frame": "",
            "bound_demo_0-B0001_comment": "",
        }
        for name in SIGNAL_NAMES:
            data.setdefault(f"signal_{name}_decision", "NOT_REVIEWED")
            data.setdefault(f"signal_{name}_comment", "")
        saved = self.client.post(
            f"/audit/{self.run_id}/episode/data--demo_0/review",
            data=data,
            follow_redirects=True,
        )
        self.assertEqual(saved.status_code, 200)
        self.assertIn("saved=1", str(saved.url) + saved.text)
        conn = sqlite3.connect(self.owner_db)
        n = conn.execute("SELECT COUNT(*) FROM signal_review_history").fetchone()[0]
        conn.close()
        self.assertGreaterEqual(n, 1)

    def test_owner_sqlite_not_used_by_layout_tests(self) -> None:
        real_owner = default_owner_db_path(PROJECT2_ROOT)
        self.assertNotEqual(Path(self.owner_db).resolve(), Path(real_owner).resolve())
        if not real_owner.is_file():
            return
        conn = sqlite3.connect(real_owner)
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "signal_review_history" in tables:
            n = conn.execute(
                "SELECT COUNT(*) FROM signal_review_history WHERE reviewer = ?",
                ("TEMP_LAYOUT_TEST",),
            ).fetchone()[0]
            self.assertEqual(n, 0)
        conn.close()


if __name__ == "__main__":
    unittest.main()
