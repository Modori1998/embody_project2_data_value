"""Owner-only unblinded review mode for the G1-P3 DESIGN_DIAGNOSTIC run.

Covers the additive ``ADD_G1_P3_UNBLINDED_OWNER_REVIEW_MODE`` surface:

* the strict 1:1 join (exact episode_id + boundary_id, 20/20, no fuzzy match);
* every join failure mode fails fast rather than rendering a partial view;
* the blinded page stays blind — no Arm / P12 / C12 / pair_id leakage;
* the first blinded decision is preserved and a re-review is appended as a
  distinguishable ``OWNER_UNBLINDED_REVIEW`` revision;
* the unblinded page exposes exactly the required diagnostic fields;
* the mode never opens for a non-DESIGN_DIAGNOSTIC run.
"""

from __future__ import annotations

import csv
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
from project2_g1_audit_web.app import create_app
from project2_g1_audit_web.contract import DESIGN_DIAGNOSTIC_RUN_STAGE
from project2_g1_audit_web.input import load_run
from project2_g1_audit_web.registry import (
    auto_register,
    default_owner_db_path,
    default_registry_path,
    load_registry,
)
from project2_g1_audit_web.reviews import (
    ADDED_TABLE,
    BOUNDARY_TABLE,
    NOTE_TABLE,
    SIGNAL_TABLE,
    ReviewStore,
    ValidationFailed,
)
from project2_g1_audit_web.service import G1AuditWebInput
from project2_g1_audit_web.unblinded import (
    C12_GROUP_HIGH,
    C12_GROUP_LOW,
    EXPECTED_PAIR_COUNT,
    EXPECTED_UNBLIND_EVENT_COUNT,
    REQUIRED_UNBLIND_COLUMNS,
    REVIEW_PROVENANCE_FIRST_BLIND,
    REVIEW_PROVENANCE_OWNER_UNBLINDED,
    UNBLINDED_REVIEWER,
    UnblindedError,
    UnblindedNotApplicable,
    build_unblinded_join,
    c12_group_from_percentile,
    load_unblind_source,
    review_provenance,
)

# Diagnostic-design tokens that must never reach the blinded page.
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

EPISODES = 20


class _FakeIdent:
    def __init__(self, digest: str):
        self.source_sha256 = digest
        self.needs_proxy = False
        self.proxy_profile_version = "v1"
        self.proxy_url = ""


# ---------------------------------------------------------------------------
# Synthetic unblind source builder
# ---------------------------------------------------------------------------


def _unblind_row(
    index: int,
    *,
    arm: str,
    pair_id: str,
    episode_id: str | None = None,
    boundary_id: str | None = None,
    event_frame: str = "4",
    c12: str = "",
    c12_percentile: str = "",
) -> dict[str, str]:
    native = f"demo_{index}"
    low = arm == "A"
    return {
        "diagnostic_event_id": f"G1P3-DIAG-{index + 1:03d}",
        "arm": arm,
        "pair_id": pair_id,
        "episode_id": episode_id if episode_id is not None else f"data/{native}",
        "event_frame": event_frame,
        "boundary_id": boundary_id if boundary_id is not None else f"{native}-B0001",
        "representative_candidate_id": f"{native}-C0001",
        "P12": "0.10606848504157361" if low else "0.16364894854634177",
        "P12_percentile": "0.40000000000000002",
        "C12": c12 or ("0.11340125929715138" if low else "0.9900883915767094"),
        "C12_percentile": c12_percentile or ("0.01" if low else "0.90"),
        "direction_evidence": "2.5000000000000000",
        "direction_evidence_percentile": "0.80000000000000004",
        "run_length": "7",
        "run_length_percentile": "0.5",
        "match_distance": "0.40000000000000002",
        "distance_to_nearest_gripper_final": "50",
        "selection_reason": (
            "LOW_C12_QUARTILE_EPISODE_DIVERSE_TARGET"
            if low
            else "HIGH_C12_QUARTILE_MIN_MATCH_DISTANCE_CONTROL"
        ),
    }


def write_unblind_source(
    path: Path,
    *,
    n_episodes: int = EPISODES,
    drop_episode_index: int | None = None,
    extra_row: bool = False,
    duplicate_index: int | None = None,
    frame_override: dict[int, str] | None = None,
    fuzzy_episode_index: int | None = None,
    c12_percentile_override: dict[int, str] | None = None,
    omit_column: str | None = None,
) -> Path:
    """A matching internal selection table, with optional fault injection.

    Episodes are paired in manifest order: pair k = (demo_{2k}, demo_{2k+1}) with
    Arm A on the even index and Arm B on the odd index.
    """

    rows: list[dict[str, str]] = []
    for index in range(n_episodes):
        if index == drop_episode_index:
            continue
        pair_id = f"P{index // 2 + 1:02d}"
        row = _unblind_row(
            index,
            arm="A" if index % 2 == 0 else "B",
            pair_id=pair_id,
            event_frame=(frame_override or {}).get(index, "4"),
            c12_percentile=(c12_percentile_override or {}).get(index, ""),
        )
        if index == fuzzy_episode_index:
            row["episode_id"] = f"data/demo_fuzzy_{index}"
        rows.append(row)
    if extra_row:
        rows.append(
            _unblind_row(
                999,
                arm="A",
                pair_id="P99",
                episode_id="data/demo_999",
                boundary_id="demo_999-B0001",
            )
        )
    if duplicate_index is not None:
        rows.append(dict(rows[duplicate_index]))

    fieldnames = [name for name in REQUIRED_UNBLIND_COLUMNS if name != omit_column]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
    return path


# ---------------------------------------------------------------------------
# 1. Strict join validation
# ---------------------------------------------------------------------------


class TestUnblindedJoin(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self._tmp.name)
        self.run_root = write_synthetic_run(
            self.root / "runs",
            run_id="g1_design_diagnostic_unblinded_join",
            n_episodes=EPISODES,
            run_stage=DESIGN_DIAGNOSTIC_RUN_STAGE,
            set_role=DESIGN_DIAGNOSTIC_RUN_STAGE,
        )
        self.loaded = load_run(self.run_root)
        self.source = write_unblind_source(self.root / "unblind" / "02_selection_internal.csv")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _join(self, source: Path | None = None):
        return build_unblinded_join(
            loaded=self.loaded, source_path=source or self.source
        )

    def test_join_is_twenty_of_twenty(self) -> None:
        join = self._join()
        self.assertEqual(join.event_count, EXPECTED_UNBLIND_EVENT_COUNT)
        self.assertEqual(join.pair_count, EXPECTED_PAIR_COUNT)
        self.assertEqual(join.join_key, "episode_id+boundary_id")

    def test_low_and_high_are_ten_each(self) -> None:
        join = self._join()
        self.assertEqual(join.low_count, 10)
        self.assertEqual(join.high_count, 10)

    def test_each_pair_has_exactly_arm_a_and_arm_b(self) -> None:
        join = self._join()
        for pair in join.pairs:
            with self.subTest(pair=pair.pair_id):
                self.assertEqual(pair.arm_a.arm, "A")
                self.assertEqual(pair.arm_b.arm, "B")
                self.assertEqual(pair.arm_a.c12_group, C12_GROUP_LOW)
                self.assertEqual(pair.arm_b.c12_group, C12_GROUP_HIGH)

    def test_source_rows_are_read_from_the_exact_join_key(self) -> None:
        rows = load_unblind_source(self.source)
        self.assertEqual(len(rows), EXPECTED_UNBLIND_EVENT_COUNT)
        self.assertIn(("data/demo_0", "demo_0-B0001"), rows)

    def test_missing_row_fails_fast(self) -> None:
        broken = write_unblind_source(
            self.root / "broken_missing.csv", drop_episode_index=3
        )
        with self.assertRaises(UnblindedError) as ctx:
            self._join(broken)
        self.assertTrue(
            any("MISSING_IN_UNBLIND_SOURCE" in item for item in ctx.exception.errors),
            ctx.exception.errors,
        )

    def test_extra_row_fails_fast(self) -> None:
        broken = write_unblind_source(self.root / "broken_extra.csv", extra_row=True)
        with self.assertRaises(UnblindedError) as ctx:
            self._join(broken)
        self.assertTrue(
            any("EXTRA_IN_UNBLIND_SOURCE" in item for item in ctx.exception.errors),
            ctx.exception.errors,
        )

    def test_duplicate_join_key_fails_fast(self) -> None:
        broken = write_unblind_source(self.root / "broken_dup.csv", duplicate_index=0)
        with self.assertRaises(UnblindedError) as ctx:
            self._join(broken)
        self.assertTrue(
            any("duplicate join keys" in item for item in ctx.exception.errors),
            ctx.exception.errors,
        )

    def test_frame_mismatch_fails_fast(self) -> None:
        broken = write_unblind_source(
            self.root / "broken_frame.csv", frame_override={2: "99"}
        )
        with self.assertRaises(UnblindedError) as ctx:
            self._join(broken)
        self.assertTrue(
            any("frame mismatch" in item for item in ctx.exception.errors),
            ctx.exception.errors,
        )

    def test_boundary_mismatch_is_a_missing_key_not_a_silent_remap(self) -> None:
        # The source names the right episode but a boundary that is not in the run.
        rows = []
        with self.source.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        rows[0]["boundary_id"] = "demo_0-B9999"
        broken = self.root / "broken_boundary.csv"
        with broken.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        with self.assertRaises(UnblindedError) as ctx:
            self._join(broken)
        self.assertTrue(
            any("MISSING_IN_UNBLIND_SOURCE" in item for item in ctx.exception.errors),
            ctx.exception.errors,
        )
        self.assertTrue(
            any("FUZZY_MATCH_REJECTED" in item for item in ctx.exception.errors),
            ctx.exception.errors,
        )

    def test_fuzzy_episode_match_is_rejected(self) -> None:
        broken = write_unblind_source(
            self.root / "broken_fuzzy.csv", fuzzy_episode_index=5
        )
        with self.assertRaises(UnblindedError) as ctx:
            self._join(broken)
        joined = " ".join(ctx.exception.errors)
        self.assertIn("FUZZY_MATCH_REJECTED", joined)

    def test_missing_column_fails_fast(self) -> None:
        broken = write_unblind_source(
            self.root / "broken_column.csv", omit_column="C12_percentile"
        )
        with self.assertRaises(UnblindedError) as ctx:
            self._join(broken)
        self.assertTrue(
            any("missing columns" in item for item in ctx.exception.errors),
            ctx.exception.errors,
        )

    def test_arm_quartile_inconsistency_fails_fast(self) -> None:
        broken = write_unblind_source(
            self.root / "broken_quartile.csv", c12_percentile_override={0: "0.95"}
        )
        with self.assertRaises(UnblindedError) as ctx:
            self._join(broken)
        self.assertTrue(
            any("must sit in" in item for item in ctx.exception.errors),
            ctx.exception.errors,
        )

    def test_missing_source_file_fails_fast(self) -> None:
        with self.assertRaises(UnblindedError):
            self._join(self.root / "does_not_exist.csv")

    def test_non_diagnostic_run_is_not_applicable(self) -> None:
        exploratory = load_run(
            write_synthetic_run(self.root / "runs2", n_episodes=2)
        )
        with self.assertRaises(UnblindedNotApplicable):
            build_unblinded_join(loaded=exploratory, source_path=self.source)

    def test_percentile_quartile_rule(self) -> None:
        self.assertEqual(c12_group_from_percentile(0.0), C12_GROUP_LOW)
        self.assertEqual(c12_group_from_percentile(0.25), C12_GROUP_LOW)
        self.assertEqual(c12_group_from_percentile(0.75), C12_GROUP_HIGH)
        self.assertEqual(c12_group_from_percentile(1.0), C12_GROUP_HIGH)
        with self.assertRaises(UnblindedError):
            c12_group_from_percentile(0.5)

    def test_provenance_is_derived_from_reviewer_identity(self) -> None:
        self.assertEqual(review_provenance(UNBLINDED_REVIEWER), REVIEW_PROVENANCE_OWNER_UNBLINDED)
        self.assertEqual(review_provenance("DESIGN_OWNER"), REVIEW_PROVENANCE_FIRST_BLIND)
        self.assertEqual(review_provenance(""), REVIEW_PROVENANCE_FIRST_BLIND)


# ---------------------------------------------------------------------------
# 2. Web surface
# ---------------------------------------------------------------------------


class TestUnblindedWeb(unittest.TestCase):
    RUN_ID = "g1_design_diagnostic_unblinded_web"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self._tmp.name)
        self.registry = default_registry_path(self.root)
        self.owner_db = default_owner_db_path(self.root)
        self.run_root = write_synthetic_run(
            self.root / "outputs" / "g1_audit_runs",
            run_id=self.RUN_ID,
            n_episodes=EPISODES,
            run_stage=DESIGN_DIAGNOSTIC_RUN_STAGE,
            set_role=DESIGN_DIAGNOSTIC_RUN_STAGE,
        )
        auto_register(self.registry, self.run_root, owner_db_path=self.owner_db)
        self.source = write_unblind_source(
            self.root / "0-doc" / "unblind" / "02_selection_internal.csv"
        )
        self.service = G1AuditWebInput(
            project_root=self.root,
            registry_path=self.registry,
            owner_db_path=self.owner_db,
        )
        self.client = self._client()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _client(self, **kwargs) -> TestClient:
        kwargs.setdefault("unblind_source_path", self.source)
        proxy = Mock()
        proxy.register_video.side_effect = lambda source, run_id, episode_id: _FakeIdent("d" * 64)
        proxy.ensure_proxy_file.side_effect = lambda sha, profile: Path(
            self.run_root / "media/demo_0/video.mp4"
        )
        app = create_app(
            project_root=self.root,
            web_input=self.service,
            video_proxy=proxy,
            **kwargs,
        )
        return TestClient(app)

    # -- blinded page must stay blind ------------------------------------

    def test_blind_page_still_renders(self) -> None:
        page = self.client.get(
            f"/audit/{self.RUN_ID}/episode/data--demo_0", follow_redirects=True
        )
        self.assertEqual(page.status_code, 200)
        self.assertIn("design-diagnostic-banner", page.text)

    def test_blind_page_leaks_no_diagnostic_token(self) -> None:
        for index in (0, 7, 19):
            with self.subTest(index=index):
                page = self.client.get(
                    f"/audit/{self.RUN_ID}/episode/data--demo_{index}", follow_redirects=True
                )
                for probe in FORBIDDEN_PROBES:
                    self.assertNotIn(probe.lower(), page.text.lower(), probe)

    def test_blind_page_offers_the_owner_entry_point(self) -> None:
        page = self.client.get(
            f"/audit/{self.RUN_ID}/episode/data--demo_0", follow_redirects=True
        )
        self.assertIn("btn-owner-unblinded-review", page.text)
        self.assertIn(f"/audit/{self.RUN_ID}/unblinded", page.text)

    def test_index_leaks_no_diagnostic_token(self) -> None:
        page = self.client.get("/")
        for probe in FORBIDDEN_PROBES:
            self.assertNotIn(probe.lower(), page.text.lower(), probe)

    # -- unblinded page --------------------------------------------------

    def test_unblinded_entry_redirects_to_first_event(self) -> None:
        response = self.client.get(f"/audit/{self.RUN_ID}/unblinded", follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertIn("/unblinded/episode/", response.headers["location"])

    def test_unblinded_page_shows_every_required_field(self) -> None:
        page = self.client.get(
            f"/audit/{self.RUN_ID}/unblinded/episode/data--demo_0"
        )
        self.assertEqual(page.status_code, 200, page.text[:400])
        for marker in (
            "UNBLINDED OWNER REVIEW",
            "FIRST BLINDED RESULT IS PRESERVED",
            'id="ub-arm"',
            'id="ub-c12-group"',
            'id="ub-c12"',
            'id="ub-p12"',
            'id="ub-pair-id"',
            'id="ub-direction-evidence"',
            'id="ub-run-length"',
            'id="ub-first-blind-decision"',
            'id="ub-c12-explanation"',
            'id="ub-p12-explanation"',
            'id="btn-open-matched-pair"',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, page.text)

    def test_unblinded_page_shows_four_decimal_c12_and_p12(self) -> None:
        page = self.client.get(
            f"/audit/{self.RUN_ID}/unblinded/episode/data--demo_0"
        )
        # C12 and P12 are rounded to about 4 decimal places, and are distinct.
        self.assertIn('id="ub-c12">0.1134<', page.text)
        self.assertIn('id="ub-p12">0.1061<', page.text)

    def test_unblinded_page_shows_chinese_explanations(self) -> None:
        page = self.client.get(
            f"/audit/{self.RUN_ID}/unblinded/episode/data--demo_0"
        )
        self.assertIn("轨迹一致性", page.text)
        self.assertIn("持续后段运动上下文", page.text)
        self.assertIn("只验证 trajectory mechanism", page.text)

    def test_unblinded_page_offers_no_recommended_answer(self) -> None:
        page = self.client.get(
            f"/audit/{self.RUN_ID}/unblinded/episode/data--demo_0"
        )
        self.assertIn("NO AUTO LABELLING", page.text)
        # The neutral placeholder is preselected while nothing is reviewed.
        self.assertIn('value="" selected', page.text)
        for label in ("VALID", "REDUNDANT", "MISALIGNED"):
            self.assertNotIn(f'value="{label}" selected', page.text)

    def test_matched_pair_page_renders_both_arms(self) -> None:
        page = self.client.get(f"/audit/{self.RUN_ID}/unblinded/pair/P01")
        self.assertEqual(page.status_code, 200, page.text[:400])
        self.assertIn("ub-pair-table", page.text)
        self.assertIn("data/demo_0", page.text)
        self.assertIn("data/demo_1", page.text)

    def test_unknown_pair_is_404(self) -> None:
        page = self.client.get(f"/audit/{self.RUN_ID}/unblinded/pair/P99")
        self.assertEqual(page.status_code, 404)
        self.assertIn("UNKNOWN_MATCHED_PAIR", page.text)

    def test_unknown_event_is_404(self) -> None:
        page = self.client.get(
            f"/audit/{self.RUN_ID}/unblinded/episode/data--demo_999"
        )
        self.assertEqual(page.status_code, 404)
        self.assertIn("UNKNOWN_UNBLINDED_EVENT", page.text)

    def test_disabled_flag_blocks_the_route(self) -> None:
        client = self._client(unblinded_owner_review=False)
        page = client.get(f"/audit/{self.RUN_ID}/unblinded", follow_redirects=True)
        self.assertEqual(page.status_code, 403)
        self.assertIn("UNBLINDED_DISABLED", page.text)

    def test_join_failure_is_visible_not_partial(self) -> None:
        broken = write_unblind_source(self.root / "broken.csv", drop_episode_index=1)
        client = self._client(unblind_source_path=broken)
        page = client.get(f"/audit/{self.RUN_ID}/unblinded", follow_redirects=True)
        self.assertEqual(page.status_code, 400)
        self.assertIn("UNBLINDED_JOIN_FAILED", page.text)
        self.assertIn("MISSING_IN_UNBLIND_SOURCE", page.text)

    def test_non_diagnostic_run_is_rejected_over_http(self) -> None:
        exploratory = write_synthetic_run(
            self.root / "outputs" / "g1_audit_runs", n_episodes=2
        )
        auto_register(self.registry, exploratory, owner_db_path=self.owner_db)
        page = self.client.get(f"/audit/{exploratory.name}/unblinded", follow_redirects=True)
        self.assertEqual(page.status_code, 400)
        self.assertIn("UNBLINDED_NOT_APPLICABLE", page.text)

    # -- re-review semantics --------------------------------------------

    def _seed_blind_review(self, episode_id: str, decision: str, **extra: str) -> None:
        store = ReviewStore(self.owner_db, reviewer="DESIGN_OWNER")
        store.save_boundary_review(
            run_id=self.RUN_ID,
            episode_id=episode_id,
            predicted={f"{episode_id.split('/')[-1]}-B0001": 4},
            boundary_id=f"{episode_id.split('/')[-1]}-B0001",
            decision=decision,
            episode_length=10,
            **extra,
        )

    def _rows(self, episode_id: str) -> list[sqlite3.Row]:
        connection = sqlite3.connect(str(self.owner_db))
        connection.row_factory = sqlite3.Row
        try:
            return connection.execute(
                f"SELECT * FROM {BOUNDARY_TABLE} WHERE run_id = ? AND episode_id = ? "
                "ORDER BY review_id",
                (self.RUN_ID, episode_id),
            ).fetchall()
        finally:
            connection.close()

    def test_owner_review_is_appended_and_first_blind_is_preserved(self) -> None:
        self._seed_blind_review("data/demo_0", "VALID")
        before = self._rows("data/demo_0")
        self.assertEqual(len(before), 1)

        response = self.client.post(
            f"/audit/{self.RUN_ID}/unblinded/episode/data--demo_0/review",
            data={
                "ub_decision": "REDUNDANT",
                "ub_reason_code": "REDUNDANT_DIRECTION_JITTER",
                "ub_comment": "owner re-review",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200, response.text[:400])

        after = self._rows("data/demo_0")
        self.assertEqual(len(after), 2)
        # The first blinded revision is byte-for-byte preserved.
        self.assertEqual(after[0]["decision"], before[0]["decision"])
        self.assertEqual(after[0]["review_id"], before[0]["review_id"])
        self.assertEqual(after[0]["reviewer"], "DESIGN_OWNER")
        self.assertEqual(after[0]["reviewed_at"], before[0]["reviewed_at"])
        # The new revision is attributed to the owner unblinded identity.
        self.assertEqual(after[1]["decision"], "REDUNDANT")
        self.assertEqual(after[1]["reason_code"], "REDUNDANT_DIRECTION_JITTER")
        self.assertEqual(after[1]["comment"], "owner re-review")
        self.assertEqual(after[1]["reviewer"], UNBLINDED_REVIEWER)

    def test_page_distinguishes_first_blind_from_owner_review(self) -> None:
        self._seed_blind_review("data/demo_2", "VALID")
        self.client.post(
            f"/audit/{self.RUN_ID}/unblinded/episode/data--demo_2/review",
            data={"ub_decision": "MISALIGNED", "ub_reason_code": "MISALIGNED_GRIPPER",
                  "ub_corrected_frame": "6"},
            follow_redirects=True,
        )
        page = self.client.get(f"/audit/{self.RUN_ID}/unblinded/episode/data--demo_2")
        self.assertIn("FIRST_BLINDED_REVIEW", page.text)
        self.assertIn("OWNER_UNBLINDED_REVIEW", page.text)
        self.assertIn('id="ub-revision-count">2<', page.text)

    def test_review_is_append_only_across_labels(self) -> None:
        for decision, extra in (
            ("VALID", {}),
            ("REDUNDANT", {"ub_reason_code": "REDUNDANT_ROTATION"}),
            ("MISALIGNED", {"ub_reason_code": "MISALIGNED_GRIPPER", "ub_corrected_frame": "5"}),
        ):
            self.client.post(
                f"/audit/{self.RUN_ID}/unblinded/episode/data--demo_4/review",
                data={"ub_decision": decision, **extra},
                follow_redirects=True,
            )
        rows = self._rows("data/demo_4")
        self.assertEqual([row["decision"] for row in rows], ["VALID", "REDUNDANT", "MISALIGNED"])
        self.assertTrue(all(row["reviewer"] == UNBLINDED_REVIEWER for row in rows))

    def test_repeat_submission_of_the_same_owner_revision_is_a_no_op(self) -> None:
        payload = {"ub_decision": "VALID"}
        self.client.post(
            f"/audit/{self.RUN_ID}/unblinded/episode/data--demo_6/review",
            data=payload, follow_redirects=True,
        )
        self.client.post(
            f"/audit/{self.RUN_ID}/unblinded/episode/data--demo_6/review",
            data=payload, follow_redirects=True,
        )
        self.assertEqual(len(self._rows("data/demo_6")), 1)

    def test_not_reviewed_is_rejected(self) -> None:
        page = self.client.post(
            f"/audit/{self.RUN_ID}/unblinded/episode/data--demo_8/review",
            data={"ub_decision": ""},
            follow_redirects=True,
        )
        self.assertEqual(page.status_code, 400)
        self.assertIn("VALIDATION_FAILED", page.text)
        self.assertEqual(len(self._rows("data/demo_8")), 0)

    def test_redundant_without_reason_code_is_rejected(self) -> None:
        page = self.client.post(
            f"/audit/{self.RUN_ID}/unblinded/episode/data--demo_9/review",
            data={"ub_decision": "REDUNDANT", "ub_reason_code": "MISALIGNED_GRIPPER"},
            follow_redirects=True,
        )
        self.assertEqual(page.status_code, 400)
        self.assertIn("VALIDATION_FAILED", page.text)
        self.assertEqual(len(self._rows("data/demo_9")), 0)

    def test_misaligned_requires_corrected_frame(self) -> None:
        page = self.client.post(
            f"/audit/{self.RUN_ID}/unblinded/episode/data--demo_10/review",
            data={"ub_decision": "MISALIGNED", "ub_reason_code": "MISALIGNED_GRIPPER"},
            follow_redirects=True,
        )
        self.assertEqual(page.status_code, 400)
        self.assertIn("corrected_frame", page.text)

    def test_boundary_only_write_leaves_other_tables_untouched(self) -> None:
        self.client.post(
            f"/audit/{self.RUN_ID}/unblinded/episode/data--demo_12/review",
            data={"ub_decision": "VALID"},
            follow_redirects=True,
        )
        connection = sqlite3.connect(str(self.owner_db))
        try:
            counts = {
                table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in (SIGNAL_TABLE, ADDED_TABLE, NOTE_TABLE)
            }
            boundary_rows = connection.execute(
                f"SELECT COUNT(*) FROM {BOUNDARY_TABLE} WHERE run_id = ?",
                (self.RUN_ID,),
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(counts, {SIGNAL_TABLE: 0, ADDED_TABLE: 0, NOTE_TABLE: 0})
        self.assertEqual(int(boundary_rows), 1)

    def test_save_boundary_review_rejects_unknown_boundary(self) -> None:
        store = ReviewStore(self.owner_db, reviewer=UNBLINDED_REVIEWER)
        with self.assertRaises(ValidationFailed):
            store.save_boundary_review(
                run_id=self.RUN_ID,
                episode_id="data/demo_0",
                predicted={"demo_0-B0001": 4},
                boundary_id="demo_0-B9999",
                decision="VALID",
                episode_length=10,
            )

    def test_join_reflects_the_owner_revision_after_reload(self) -> None:
        self._seed_blind_review("data/demo_14", "VALID")
        self.client.post(
            f"/audit/{self.RUN_ID}/unblinded/episode/data--demo_14/review",
            data={"ub_decision": "REDUNDANT", "ub_reason_code": "REDUNDANT_SHORT_PAUSE"},
            follow_redirects=True,
        )
        store = ReviewStore(self.owner_db, reviewer=UNBLINDED_REVIEWER)
        join = build_unblinded_join(
            loaded=load_run(self.run_root),
            source_path=self.source,
            boundary_history=store.boundary_history_for_run(run_id=self.RUN_ID),
        )
        event = join.event("data/demo_14")
        self.assertEqual(event.first_blind_decision, "VALID")
        self.assertEqual(event.first_blind_review_id, 1)
        self.assertEqual(event.current_decision, "REDUNDANT")
        self.assertEqual(event.current_provenance, REVIEW_PROVENANCE_OWNER_UNBLINDED)
        self.assertEqual(event.revision_count, 2)
        self.assertTrue(event.has_owner_revision)


# ---------------------------------------------------------------------------
# 3. Real materialized run + real internal selection table
# ---------------------------------------------------------------------------


class TestRealUnblindedJoin(unittest.TestCase):
    def _locate_run(self) -> Path | None:
        registry = default_registry_path(ROOT)
        if not registry.is_file():
            return None
        for run_id, raw in load_registry(registry).get("runs", {}).items():
            if str(raw.get("run_stage") or "") != DESIGN_DIAGNOSTIC_RUN_STAGE:
                continue
            folder = Path(str(raw.get("audit_folder_path") or ""))
            if folder.is_dir():
                return folder
        return None

    def setUp(self) -> None:
        self.run_root = self._locate_run()
        if self.run_root is None:
            self.skipTest("DESIGN_DIAGNOSTIC run not materialized yet")
        from project2_g1_audit_web.unblinded import UNBLIND_SOURCE_RELPATH

        self.source = ROOT / UNBLIND_SOURCE_RELPATH
        if not self.source.is_file():
            self.skipTest("internal selection table not present")
        self.loaded = load_run(self.run_root)
        self.store = ReviewStore(default_owner_db_path(ROOT), reviewer=UNBLINDED_REVIEWER)
        self.join = build_unblinded_join(
            loaded=self.loaded,
            source_path=self.source,
            boundary_history=self.store.boundary_history_for_run(
                run_id=str(self.loaded["run_id"])
            ),
        )

    def test_real_join_is_twenty_of_twenty(self) -> None:
        self.assertEqual(self.join.event_count, EXPECTED_UNBLIND_EVENT_COUNT)
        self.assertEqual(self.join.pair_count, EXPECTED_PAIR_COUNT)
        self.assertEqual(self.join.low_count, 10)
        self.assertEqual(self.join.high_count, 10)

    # The four events the Design Owner adjudicated after unblinding, with the
    # frozen first-blind decision and the resulting current decision. This
    # mirrors ``05_owner_adjudication_result.md``; the first-blinded revision of
    # each must survive as the earliest revision of the append-only history.
    ADJUDICATED = {
        "data/demo_211": ("VALID", "REDUNDANT"),
        "data/demo_217": ("VALID", "REDUNDANT"),
        "data/demo_220": ("VALID", "REDUNDANT"),
        "data/demo_296": ("REDUNDANT", "VALID"),
    }

    def test_real_first_blinded_reviews_are_preserved(self) -> None:
        # The Design Owner's blinded pass must remain the *earliest* revision of
        # every event, whatever the owner later adjudicated. The adjudication
        # appends revisions; it must never overwrite the blinded one.
        self.assertTrue(self.join.first_blind_review_preserved)
        for event in self.join.events:
            with self.subTest(episode=event.episode_id):
                self.assertIsNotNone(event.first_blind_review_id)
                expected = self.ADJUDICATED.get(event.episode_id)
                if expected is None:
                    # Not adjudicated: the blinded revision is still the current
                    # one, and no owner revision exists.
                    self.assertEqual(event.revision_count, 1)
                    self.assertEqual(event.first_blind_review_id, event.current_review_id)
                    self.assertEqual(event.first_blind_decision, event.current_decision)
                    self.assertEqual(
                        event.current_provenance, REVIEW_PROVENANCE_FIRST_BLIND
                    )
                    self.assertFalse(event.has_owner_revision)
                else:
                    first_decision, current_decision = expected
                    self.assertGreater(event.revision_count, 1)
                    self.assertNotEqual(
                        event.first_blind_review_id, event.current_review_id
                    )
                    self.assertEqual(event.first_blind_decision, first_decision)
                    self.assertEqual(event.current_decision, current_decision)
                    self.assertEqual(
                        event.current_provenance,
                        REVIEW_PROVENANCE_OWNER_UNBLINDED,
                    )
                    self.assertTrue(event.has_owner_revision)

    def test_real_owner_adjudicated_set_matches_the_frozen_record(self) -> None:
        # Exactly the four recorded events carry an owner revision. If the owner
        # adjudicates more, this freeze must be re-issued rather than silently
        # drifting.
        adjudicated = {
            event.episode_id for event in self.join.events if event.has_owner_revision
        }
        self.assertEqual(adjudicated, set(self.ADJUDICATED))

    def test_real_events_are_all_in_the_frozen_quartile_arms(self) -> None:
        for event in self.join.events:
            with self.subTest(episode=event.episode_id):
                self.assertIn(event.c12_group, (C12_GROUP_LOW, C12_GROUP_HIGH))
                self.assertEqual(event.event_frame, event.run_boundary_frame)


# ---------------------------------------------------------------------------
# 3. Episode media on the unblinded surface
# ---------------------------------------------------------------------------


def _folder_fingerprint(root: Path) -> dict[str, tuple[int, int]]:
    """Size + mtime for every file under ``root``, keyed by relative posix path."""

    out: dict[str, tuple[int, int]] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            stat = path.stat()
            out[path.relative_to(root).as_posix()] = (stat.st_size, stat.st_mtime_ns)
    return out


class TestUnblindedMedia(unittest.TestCase):
    """The unblinded page must carry the episode video and the frame axis.

    Re-review is only meaningful if the Design Owner can actually watch the
    episode. The page must therefore render the episode video, the frame
    alignment axis, the frame navigation and the diagnostic plots -- all served
    read-only out of the run folder, and only on the unblinded surface.
    """

    RUN_ID = "g1_design_diagnostic_unblinded_media"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self._tmp.name)
        self.registry = default_registry_path(self.root)
        self.owner_db = default_owner_db_path(self.root)
        self.run_root = write_synthetic_run(
            self.root / "outputs" / "g1_audit_runs",
            run_id=self.RUN_ID,
            n_episodes=EPISODES,
            run_stage=DESIGN_DIAGNOSTIC_RUN_STAGE,
            set_role=DESIGN_DIAGNOSTIC_RUN_STAGE,
        )
        auto_register(self.registry, self.run_root, owner_db_path=self.owner_db)
        self.source = write_unblind_source(
            self.root / "0-doc" / "unblind" / "02_selection_internal.csv"
        )
        self.service = G1AuditWebInput(
            project_root=self.root,
            registry_path=self.registry,
            owner_db_path=self.owner_db,
        )
        self.client = self._client()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _client(self, **kwargs) -> TestClient:
        kwargs.setdefault("unblind_source_path", self.source)
        proxy = Mock()
        proxy.register_video.side_effect = lambda source, run_id, episode_id: _FakeIdent("e" * 64)
        proxy.ensure_proxy_file.side_effect = lambda sha, profile: Path(
            self.run_root / "media/demo_0/video.mp4"
        )
        return TestClient(
            create_app(
                project_root=self.root,
                web_input=self.service,
                video_proxy=proxy,
                **kwargs,
            )
        )

    def _episode_page(self, index: int = 0):
        return self.client.get(
            f"/audit/{self.RUN_ID}/unblinded/episode/data--demo_{index}"
        )

    def test_unblinded_ui_script_anchors_exist_on_the_page(self) -> None:
        # Every DOM hook unblinded_ui.js + audit_sync.js query must exist, or the
        # page silently renders without working media (the reported defect).
        page = self._episode_page(0)
        for marker in (
            # unblinded_ui.js
            'id="unblinded-media"',
            "data-focus-frame=",
            'id="btn-focus-frame"',
            'id="unblinded-review-form"',
            "data-bound-decision",
            "cond-reason",
            "cond-frame",
            "data-reason-for",
            "data-for=",
            # audit_sync.js
            'id="frame-strip"',
            'id="strip-status"',
            'id="strip-playhead"',
            'id="strip-track"',
            'id="cur-frame"',
            'id="cur-time"',
            'id="jump-frame"',
            'id="btn-jump-frame"',
            "data-frame-delta=",
            "strip-mark",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, page.text)

        pair_page = self.client.get(f"/audit/{self.RUN_ID}/unblinded/pair/P01")
        for marker in (
            'id="unblinded-pair-media"',
            "data-pair-arm=",
            'id="ub-pair-cur-frame-a"',
            'id="ub-pair-cur-time-a"',
            'id="ub-pair-cur-frame-b"',
            'id="ub-pair-cur-time-b"',
            'id="btn-pair-focus-a"',
            'id="btn-pair-focus-b"',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, pair_page.text)

    def test_unblinded_page_renders_the_episode_video(self) -> None:
        page = self._episode_page(0)
        self.assertEqual(page.status_code, 200, page.text[:400])
        self.assertIn("<video", page.text)
        self.assertIn('data-media-key="video"', page.text)
        self.assertIn(f"/media/{self.RUN_ID}/data--demo_0/video", page.text)

    def test_unblinded_page_renders_the_frame_alignment_axis(self) -> None:
        page = self._episode_page(0)
        for marker in (
            'id="frame-strip"',
            'data-fps="20.0"',
            'data-length="10"',
            'id="strip-status"',
            'id="strip-playhead"',
            'class="strip-col',
            'data-frame="4"',
            'data-boundary-id="demo_0-B0001"',
            'class="strip-mark final"',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, page.text)

    def test_unblinded_page_renders_the_frame_navigation(self) -> None:
        page = self._episode_page(0)
        for marker in (
            'id="cur-frame"',
            'id="cur-time"',
            'id="jump-frame"',
            'id="btn-jump-frame"',
            'data-frame-delta="-1"',
            'data-frame-delta="1"',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, page.text)

    def test_unblinded_page_renders_the_diagnostic_plots(self) -> None:
        page = self._episode_page(0)
        self.assertIn(f"/media/{self.RUN_ID}/data--demo_0/signal_boundary_plot", page.text)
        self.assertIn(f"/media/{self.RUN_ID}/data--demo_0/signal_plot", page.text)

    def test_unblinded_page_focuses_the_diagnostic_frame(self) -> None:
        page = self._episode_page(0)
        self.assertIn('data-focus-frame="4"', page.text)
        self.assertIn('id="ub-focus-frame">4<', page.text)
        self.assertIn("ub-focus-col", page.text)

    def test_unblinded_page_loads_the_frame_sync_script(self) -> None:
        page = self._episode_page(0)
        self.assertIn("/static/audit_sync.js", page.text)
        self.assertIn("/static/unblinded_ui.js", page.text)

    def test_unblinded_media_route_serves_the_episode_video(self) -> None:
        response = self.client.get(f"/media/{self.RUN_ID}/data--demo_0/video")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"fake-mp4-bytes", response.content)

    def test_unblinded_media_route_serves_the_diagnostic_plot(self) -> None:
        response = self.client.get(f"/media/{self.RUN_ID}/data--demo_0/signal_boundary_plot")
        self.assertEqual(response.status_code, 200)

    def test_unblinded_pair_page_renders_both_arm_videos(self) -> None:
        page = self.client.get(f"/audit/{self.RUN_ID}/unblinded/pair/P01")
        self.assertEqual(page.status_code, 200, page.text[:400])
        self.assertEqual(page.text.count("<video"), 2)
        for marker in (
            'data-pair-arm="A"',
            'data-pair-arm="B"',
            'id="btn-pair-focus-a"',
            'id="btn-pair-focus-b"',
            f"/media/{self.RUN_ID}/data--demo_0/video",
            f"/media/{self.RUN_ID}/data--demo_1/video",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, page.text)

    def test_unblinded_media_rendering_leaves_the_run_folder_untouched(self) -> None:
        before = _folder_fingerprint(self.run_root)
        for index in (0, 7, 19):
            self._episode_page(index)
        self.client.get(f"/audit/{self.RUN_ID}/unblinded/pair/P01")
        self.client.get(f"/media/{self.RUN_ID}/data--demo_0/video")
        self.assertEqual(before, _folder_fingerprint(self.run_root))

    def test_blind_page_still_has_its_own_media(self) -> None:
        page = self.client.get(
            f"/audit/{self.RUN_ID}/episode/data--demo_0", follow_redirects=True
        )
        self.assertEqual(page.status_code, 200)
        self.assertIn("<video", page.text)
        self.assertIn('id="frame-strip"', page.text)
        self.assertIn('id="strip-playhead"', page.text)

    def test_unblinded_media_does_not_leak_into_the_blind_page(self) -> None:
        blind = self.client.get(
            f"/audit/{self.RUN_ID}/episode/data--demo_0", follow_redirects=True
        )
        for marker in (
            "unblinded-media",
            "unblinded-pair-media",
            "unblinded_ui.js",
            "ub-focus-frame",
            "ub-arm",
            "ub-c12",
        ):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, blind.text)


if __name__ == "__main__":
    unittest.main()