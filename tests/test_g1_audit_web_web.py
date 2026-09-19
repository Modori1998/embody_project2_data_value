"""G1 Audit Web Batch 1: media, proxy identity, and read-only view tests."""

from __future__ import annotations

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

from unittest.mock import Mock

from fastapi.testclient import TestClient

from g1_audit_web_fixtures import write_merge_semantics_run, write_synthetic_run
from project2_g1.paths import PROJECT2_ROOT, ensure_project1_on_path
from project2_g1_audit_web.app import create_app
from project2_g1_audit_web.bootstrap import bootstrap_legacy_run
from project2_g1_audit_web.hashes import tree_fingerprint
from project2_g1_audit_web.input import EpisodeRecord
from project2_g1_audit_web.media import resolve_g1_media_file
from project2_g1_audit_web.registry import auto_register
from project2_g1_audit_web.service import G1AuditWebInput
from project2_g1_audit_web.view import (
    ITERATION_NOTE_CHILD,
    ITERATION_NOTE_MATERIALIZED,
    ITERATION_NOTE_ORIGINAL,
    build_episode_view,
    filter_episodes,
    iteration_note_from_meta,
)

ensure_project1_on_path()
from project1_benchmark.m07_audit_web_media import MediaAccessError
from project1_benchmark.m07_audit_web_video_proxy import PROXY_PROFILE_VERSION, sha256_file


class _FakeIdent:
    def __init__(self, digest: str):
        self.source_sha256 = digest
        self.needs_proxy = True
        self.proxy_profile_version = PROXY_PROFILE_VERSION
        self.proxy_url = f"/proxy/video/{digest}/{PROXY_PROFILE_VERSION}.mp4"


class WebTests(unittest.TestCase):
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

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _client(self) -> TestClient:
        proxy = Mock()
        proxy.register_video.side_effect = lambda source, run_id, episode_id: _FakeIdent("b" * 64)
        proxy.ensure_proxy_file.side_effect = lambda sha, profile: Path(self.run_root / "media/demo_0/video.mp4")
        app = create_app(
            project_root=self.root,
            web_input=self.service,
            video_proxy=proxy,
        )
        return TestClient(app)

    def test_home_and_six_episodes_render(self) -> None:
        client = self._client()
        home = client.get("/")
        self.assertEqual(home.status_code, 200)
        self.assertIn(self.run_root.name, home.text)
        self.assertIn("迭代说明", home.text)
        self.assertIn(ITERATION_NOTE_ORIGINAL, home.text)
        self.assertIn("iteration-note", home.text)
        opened = client.get(f"/audit/{self.run_root.name}", follow_redirects=True)
        self.assertEqual(opened.status_code, 200)
        self.assertNotIn("VALIDATION_FAILED", opened.text)
        self.assertIn("data/demo_0", opened.text)
        self.assertIn("data/demo_5", opened.text)
        self.assertIn("tbl-final", opened.text)
        self.assertIn("tbl-candidate", opened.text)
        self.assertIn("tbl-decision", opened.text)
        self.assertIn("tbl-segment", opened.text)
        self.assertIn("GRIPPER_TRANSITION｜夹爪切换", opened.text)
        loaded = self.service.load_validated_run(self.run_root.name)
        self.assertEqual([ep.episode_id for ep in loaded["episodes"]], [f"data/demo_{i}" for i in range(6)])
        queue = filter_episodes(loaded["episodes"], filter_name="ALL")
        self.assertEqual([item.episode_id for item in queue], [f"data/demo_{i}" for i in range(6)])
        _, view = build_episode_view(loaded, episode_id="data/demo_0")
        self.assertEqual(len(view.boundaries), 1)
        self.assertEqual(len(view.candidates), 1)
        self.assertEqual(len(view.decisions), 1)
        self.assertEqual(len(view.segments), 1)

    def test_manifest_media_allowed_and_range(self) -> None:
        client = self._client()
        encoded = "data--demo_0"
        full = client.get(f"/media/{self.run_root.name}/{encoded}/video")
        self.assertEqual(full.status_code, 200)
        body = (self.run_root / "media" / "demo_0" / "video.mp4").read_bytes()
        self.assertEqual(full.content, body)
        ranged = client.get(
            f"/media/{self.run_root.name}/{encoded}/video",
            headers={"Range": "bytes=0-3"},
        )
        self.assertEqual(ranged.status_code, 206)
        self.assertEqual(ranged.content, body[:4])
        png = client.get(f"/media/{self.run_root.name}/{encoded}/signal_boundary_plot")
        self.assertEqual(png.status_code, 200)
        self.assertTrue(png.headers.get("content-type", "").startswith("image/"))

    def test_path_traversal_rejected(self) -> None:
        client = self._client()
        encoded = "data--demo_0"
        blocked = client.get(f"/media/{self.run_root.name}/{encoded}/../run_meta.json")
        self.assertIn(blocked.status_code, {403, 404})
        loaded = self.service.load_validated_run(self.run_root.name)
        episode = loaded["episodes_by_id"]["data/demo_0"]
        bad = EpisodeRecord(**{**episode.__dict__, "video_relpath": "../secret.bin"})
        with self.assertRaises(MediaAccessError):
            resolve_g1_media_file(loaded["run_root"], bad, "video")

    def test_proxy_identity_stable_for_same_source(self) -> None:
        digest = sha256_file(self.run_root / "media" / "demo_0" / "video.mp4")
        ident_a = _FakeIdent(digest)
        ident_b = _FakeIdent(digest)
        self.assertEqual(ident_a.proxy_url, ident_b.proxy_url)
        self.assertIn(PROXY_PROFILE_VERSION, ident_a.proxy_url)
        self.assertEqual(ident_a.source_sha256, ident_b.source_sha256)


class LegacyBootstrapTests(unittest.TestCase):
    def test_real_legacy_bootstrap_six_episodes_and_unchanged_source(self) -> None:
        legacy = PROJECT2_ROOT / "outputs" / "g1_p2_boundary_audit"
        if not (legacy / "episode_manifest.csv").is_file():
            self.skipTest("legacy G1-P2 package missing")
        before = tree_fingerprint(legacy)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = bootstrap_legacy_run(
                project_root=PROJECT2_ROOT,
                dest_parent=root / "g1_audit_runs",
                register=False,
                salt="unittest",
            )
            self.assertEqual(result["episode_count"], 6)
            loaded = result["validated"]
            self.assertEqual(loaded["run_meta"]["run_stage"], "EXPLORATORY_AUDIT")
            self.assertEqual(loaded["episodes"][0]["set_role"], "EXPLORATORY")
            ids = [row["episode_id"] for row in loaded["episodes"]]
            self.assertEqual(
                ids,
                [
                    "data/demo_0",
                    "data/demo_32",
                    "data/demo_179",
                    "data/demo_278",
                    "data/demo_242",
                    "data/demo_230",
                ],
            )
        after = tree_fingerprint(legacy)
        self.assertEqual(before["tree_fingerprint"], after["tree_fingerprint"])


class RealProxyTests(unittest.TestCase):
    def test_mp4v_proxy_generation_reuses_same_artifact(self) -> None:
        source = PROJECT2_ROOT / "outputs" / "g1_p2_boundary_audit" / "demo_0" / "video.mp4"
        if not source.is_file():
            self.skipTest("legacy G1 video missing")
        from project2_g1_audit_web.video_proxy import G1AuditVideoProxy
        from project1_benchmark.m07_audit_web_video_proxy import FFMPEG_RUNTIME_MISSING, VideoProxyError

        source_sha = sha256_file(source)
        with tempfile.TemporaryDirectory() as tmp:
            try:
                proxy = G1AuditVideoProxy(Path(tmp) / "cache")
            except VideoProxyError as exc:
                if getattr(exc, "code", "") == FFMPEG_RUNTIME_MISSING:
                    self.skipTest("ffmpeg/ffprobe missing")
                raise
            ident = proxy.register_video(source, run_id="proxy-test", episode_id="data/demo_0")
            self.assertEqual(ident.source_sha256, source_sha)
            self.assertTrue(ident.needs_proxy)
            first = proxy.ensure_proxy_file(ident.source_sha256, f"{PROXY_PROFILE_VERSION}.mp4")
            second = proxy.ensure_proxy_file(ident.source_sha256, f"{PROXY_PROFILE_VERSION}.mp4")
            self.assertEqual(first.resolve(), second.resolve())
            self.assertGreater(first.stat().st_size, 0)
            self.assertEqual(sha256_file(source), source_sha)

    def test_proxy_skips_unreadable_stale_source_path(self) -> None:
        source = PROJECT2_ROOT / "outputs" / "g1_p2_boundary_audit" / "demo_0" / "video.mp4"
        if not source.is_file():
            self.skipTest("legacy G1 video missing")
        from project2_g1_audit_web.video_proxy import G1AuditVideoProxy
        from project1_benchmark.m07_audit_web_video_proxy import FFMPEG_RUNTIME_MISSING, VideoProxyError

        with tempfile.TemporaryDirectory() as tmp:
            try:
                proxy = G1AuditVideoProxy(Path(tmp) / "cache")
            except VideoProxyError as exc:
                if getattr(exc, "code", "") == FFMPEG_RUNTIME_MISSING:
                    self.skipTest("ffmpeg/ffprobe missing")
                raise
            ident = proxy.register_video(source, run_id="readable-run", episode_id="data/demo_0")
            locked = (
                PROJECT2_ROOT
                / "outputs"
                / "g1_audit_runs"
                / "g1_calibration_LOCKED"
                / "media"
                / "demo_0"
                / "video.mp4"
            )
            connection = proxy.manager._connect()
            try:
                connection.execute(
                    """
                    INSERT INTO allowed_sources (
                        source_sha256, source_path, source_codec, source_size,
                        run_id, case_id, media_key, registered_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ident.source_sha256,
                        str(locked),
                        ident.source_codec,
                        ident.source_size,
                        "locked-run",
                        "data/demo_0",
                        "video",
                        "1999-01-01T00:00:00",
                    ),
                )
                connection.commit()
            finally:
                connection.close()

            original_is_file = Path.is_file

            def _is_file(self: Path) -> bool:
                if "g1_calibration_LOCKED" in str(self):
                    raise PermissionError(5, "Access is denied", str(self))
                return original_is_file(self)

            Path.is_file = _is_file  # type: ignore[method-assign]
            try:
                generated = proxy.ensure_proxy_file(
                    ident.source_sha256, f"{PROXY_PROFILE_VERSION}.mp4"
                )
            finally:
                Path.is_file = original_is_file  # type: ignore[method-assign]
            self.assertGreater(generated.stat().st_size, 0)


class IterationNoteTests(unittest.TestCase):
    def test_iteration_note_from_meta(self) -> None:
        self.assertEqual(
            iteration_note_from_meta({"bootstrap": True, "parent_run_id": None}),
            ITERATION_NOTE_ORIGINAL,
        )
        self.assertEqual(
            iteration_note_from_meta({"final_boundary_semantics": "MATERIALIZED_V1"}),
            ITERATION_NOTE_MATERIALIZED,
        )
        self.assertEqual(
            iteration_note_from_meta(
                {"schema_materialization": "FINAL_BOUNDARY_MEMBER_SEMANTICS_V1", "parent_run_id": "parent"}
            ),
            ITERATION_NOTE_MATERIALIZED,
        )
        self.assertEqual(
            iteration_note_from_meta({"parent_run_id": "g1_parent"}),
            ITERATION_NOTE_CHILD,
        )
        self.assertEqual(
            iteration_note_from_meta({"iteration_note": "自定义短说明", "final_boundary_semantics": "MATERIALIZED_V1"}),
            "自定义短说明",
        )

    def test_home_lists_materialized_and_original_notes(self) -> None:
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        registry = root / "web" / "g1_audit_run_registry.json"
        owner_db = root / "web" / "owner.sqlite3"
        original = write_synthetic_run(root / "runs", run_id="g1_exploratory_audit_original", n_episodes=2)
        child = write_merge_semantics_run(
            root / "runs",
            materialized=True,
            run_id="g1_exploratory_audit_materialized",
        )
        auto_register(registry, original, owner_db_path=owner_db)
        auto_register(registry, child, owner_db_path=owner_db, owner_note="materialization child")
        service = G1AuditWebInput(project_root=root, registry_path=registry, owner_db_path=owner_db)
        app = create_app(project_root=root, web_input=service, video_proxy=Mock())
        home = TestClient(app).get("/")
        self.assertEqual(home.status_code, 200)
        self.assertIn('data-run-id="g1_exploratory_audit_original"', home.text)
        self.assertIn('data-run-id="g1_exploratory_audit_materialized"', home.text)
        self.assertIn(ITERATION_NOTE_ORIGINAL, home.text)
        self.assertIn(ITERATION_NOTE_MATERIALIZED, home.text)


if __name__ == "__main__":
    unittest.main()
