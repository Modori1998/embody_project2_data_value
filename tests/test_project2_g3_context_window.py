"""Tests for the P2-G3 Phase-1B Context Window contract (no VLM, no renderer).

Coverage targets required by the Phase-1B brief:

1. Frozen G1 segment identity is never changed;
2. neighbour boundaries and directions are correct;
3. frames are never read across an episode boundary;
4. a missing previous/next segment is handled as ``MISSING_NEIGHBOR``;
5. a wrong frame index or a duplicated evidence role cannot pollute the output;
6. a context frame can never be mislabelled as a target-segment frame;
7. the evidence budget is enforced;
8. no privileged field is introduced;
9. every frame still satisfies the Clean RGB Source Contract.

Synthetic fixtures keep these tests independent of the renderer stack.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from project2_g1.boundary_engine import UnlabeledSegment  # noqa: E402
from project2_g1.source import FormalEpisodeArrays  # noqa: E402
from project2_mvp.rgb_input import MODEL_RGB_CONTRACT_VERSION, CleanRGBFrame  # noqa: E402
from project2_g3.context_window import (  # noqa: E402
    ALLOWED_CONTEXT_FIELDS,
    CONTEXT_WINDOW_VERSION,
    MAX_CONTEXT_FRAMES_TOTAL,
    MAX_NEXT_CONTEXT_FRAMES,
    MAX_PREV_CONTEXT_FRAMES,
    NEIGHBOR_MISSING,
    NEIGHBOR_PRESENT,
    ROLE_NEXT_MIDDLE,
    ROLE_NEXT_START,
    ROLE_PREV_END,
    ROLE_TARGET_KEYFRAME,
    ContextFrame,
    ContextWindow,
    ContextWindowError,
    audit_context_surfaces,
    build_context_window,
    plan_context_frames,
    validate_context_window,
)


def _episode(n: int = 200, episode_id: str = "data/demo_x") -> FormalEpisodeArrays:
    return FormalEpisodeArrays(
        source_episode_id=episode_id,
        native_episode_key=episode_id.split("/")[-1],
        frame_index=np.arange(n, dtype=np.int64),
        eef_pos=np.linspace(0.0, 1.0, n * 3, dtype=np.float64).reshape(n, 3),
        eef_quat=np.tile(np.array([0.0, 0.0, 0.0, 1.0]), (n, 1)),
        gripper_qpos=np.linspace(0.04, 0.0, n * 2, dtype=np.float64).reshape(n, 2),
        joint_pos=np.zeros((n, 7), dtype=np.float64),
        actions=np.ones((n, 7), dtype=np.float64) * 0.1,
        provenance={"task": "PickPlaceCan", "dataset_id": "robomimic_v15_can_mh"},
    )


def _segment(start: int, end: int, sid: str, episode_id: str = "data/demo_x") -> UnlabeledSegment:
    return UnlabeledSegment(
        segment_id=sid,
        source_episode_id=episode_id,
        start_frame=start,
        end_frame=end,
        duration_frames=end - start + 1,
        duration_sec=(end - start + 1) * 0.05,
        left_boundary_id=f"b_{sid}",
        right_boundary_id=f"b_{sid}_r",
        left_boundary_reason="TEST",
        right_boundary_reason="TEST",
        segmentation_version="G1-TEST",
        config_version="cfg-test",
        short_segment_flag=False,
        long_segment_flag=False,
        review_required=False,
    )


def _frame(index: int, episode_id: str = "data/demo_x", **overrides) -> CleanRGBFrame:
    provenance = {
        "contract_version": MODEL_RGB_CONTRACT_VERSION,
        "source": "TEST",
        "overlay_applied": False,
        "audit_mp4_used": False,
        "lossy_video_roundtrip": False,
        "pixel_sha256": f"hash-{index}",
    }
    provenance.update(overrides)
    return CleanRGBFrame(
        source_episode_id=episode_id,
        frame_index=index,
        rgb=np.full((2, 2, 3), index % 256, dtype=np.uint8),
        provenance=provenance,
    )


def _three_segments() -> list[UnlabeledSegment]:
    # contiguous, non-overlapping, exactly like the frozen G1 output
    return [_segment(0, 9, "s1"), _segment(10, 39, "s2"), _segment(40, 69, "s3")]


def _cache_for(segments, episode_id: str = "data/demo_x") -> dict[int, CleanRGBFrame]:
    indices: set[int] = set()
    for index, seg in enumerate(segments):
        indices.update({seg.start_frame, (seg.start_frame + seg.end_frame) // 2, seg.end_frame})
        if index > 0:
            indices.add(segments[index - 1].end_frame)
        if index + 1 < len(segments):
            indices.add(segments[index + 1].start_frame)
            indices.add((segments[index + 1].start_frame + segments[index + 1].end_frame) // 2)
    return {i: _frame(i, episode_id) for i in sorted(indices)}


class ContextPlanningTest(unittest.TestCase):
    def test_prev_is_previous_end_and_next_is_next_start(self) -> None:
        segments = _three_segments()
        plans, status = plan_context_frames(segments[1], segments[0], segments[2])
        roles = {p.evidence_role: p for p in plans}
        self.assertEqual(roles[ROLE_PREV_END].frame_index, 9)          # s1 end
        self.assertEqual(roles[ROLE_PREV_END].origin_segment_id, "s1")
        self.assertEqual(roles[ROLE_NEXT_START].frame_index, 40)       # s3 start
        self.assertEqual(roles[ROLE_NEXT_START].origin_segment_id, "s3")
        self.assertEqual(status, {"PREV": NEIGHBOR_PRESENT, "NEXT": NEIGHBOR_PRESENT})
        self.assertTrue(all(not p.is_target_segment_frame for p in plans))

    def test_missing_prev_and_next_are_explicit(self) -> None:
        segments = _three_segments()
        first_plans, first_status = plan_context_frames(segments[0], None, segments[1])
        self.assertEqual(first_status["PREV"], NEIGHBOR_MISSING)
        self.assertNotIn(ROLE_PREV_END, {p.evidence_role for p in first_plans})

        last_plans, last_status = plan_context_frames(segments[2], segments[1], None)
        self.assertEqual(last_status["NEXT"], NEIGHBOR_MISSING)
        self.assertNotIn(ROLE_NEXT_START, {p.evidence_role for p in last_plans})

    def test_next_middle_only_for_long_enough_segment(self) -> None:
        short_next = _segment(10, 12, "s_short")     # 3 frames -> no MIDDLE
        long_next = _segment(10, 40, "s_long")       # 31 frames -> MIDDLE
        short_plans, _ = plan_context_frames(_segment(0, 9, "s"), None, short_next)
        long_plans, _ = plan_context_frames(_segment(0, 9, "s"), None, long_next)
        self.assertNotIn(ROLE_NEXT_MIDDLE, {p.evidence_role for p in short_plans})
        self.assertIn(ROLE_NEXT_MIDDLE, {p.evidence_role for p in long_plans})

    def test_budget_is_bounded(self) -> None:
        segments = _three_segments()
        plans, _ = plan_context_frames(segments[1], segments[0], segments[2])
        self.assertLessEqual(
            sum(p.evidence_role == ROLE_PREV_END for p in plans), MAX_PREV_CONTEXT_FRAMES
        )
        self.assertLessEqual(
            sum(p.evidence_role in (ROLE_NEXT_START, ROLE_NEXT_MIDDLE) for p in plans),
            MAX_NEXT_CONTEXT_FRAMES,
        )
        self.assertLessEqual(len(plans), MAX_CONTEXT_FRAMES_TOTAL)


class ContextWindowBuildTest(unittest.TestCase):
    def test_target_segment_identity_is_unchanged(self) -> None:
        segments = _three_segments()
        window = build_context_window(
            segments, 1, _episode(), adapter=None, left_boundary_type=None,
            render=False, frame_cache=_cache_for(segments),
        )
        self.assertEqual(window.target_segment_id, "s2")
        self.assertEqual((window.target_start_frame, window.target_end_frame), (10, 39))
        # the original in-segment assertion still holds
        for index in window.target_keyframe_indices:
            self.assertTrue(10 <= index <= 39)
        self.assertEqual(
            list(window.target_keyframe_indices), [10, 24, 39]  # START / MIDDLE / END
        )

    def test_target_keyframes_are_flagged_and_neighbors_are_not(self) -> None:
        segments = _three_segments()
        window = build_context_window(
            segments, 1, _episode(), adapter=None, left_boundary_type=None,
            render=False, frame_cache=_cache_for(segments),
        )
        for frame in window.context_frames:
            inside = 10 <= frame.frame_index <= 39
            self.assertEqual(frame.is_target_segment_frame, inside)
        self.assertEqual(
            {f.evidence_role for f in window.context_frames},
            {ROLE_PREV_END, ROLE_NEXT_START, ROLE_NEXT_MIDDLE},
        )

    def test_neighbor_frames_are_adjacent_and_correctly_directed(self) -> None:
        segments = _three_segments()
        window = build_context_window(
            segments, 1, _episode(), adapter=None, left_boundary_type=None,
            render=False, frame_cache=_cache_for(segments),
        )
        by_role = {f.evidence_role: f for f in window.context_frames}
        self.assertLess(by_role[ROLE_PREV_END].frame_index, 10)
        self.assertEqual(by_role[ROLE_PREV_END].origin_segment_id, "s1")
        self.assertGreater(by_role[ROLE_NEXT_START].frame_index, 39)
        self.assertEqual(by_role[ROLE_NEXT_START].origin_segment_id, "s3")

    def test_first_segment_has_no_prev_and_last_has_no_next(self) -> None:
        segments = _three_segments()
        cache = _cache_for(segments)
        first = build_context_window(
            segments, 0, _episode(), adapter=None, left_boundary_type=None,
            render=False, frame_cache=cache,
        )
        last = build_context_window(
            segments, 2, _episode(), adapter=None, left_boundary_type=None,
            render=False, frame_cache=cache,
        )
        self.assertEqual(first.neighbor_status["PREV"], NEIGHBOR_MISSING)
        self.assertEqual(last.neighbor_status["NEXT"], NEIGHBOR_MISSING)
        self.assertNotIn(ROLE_PREV_END, {f.evidence_role for f in first.context_frames})
        self.assertNotIn(ROLE_NEXT_START, {f.evidence_role for f in last.context_frames})

    def test_evidence_indices_are_unique(self) -> None:
        segments = _three_segments()
        window = build_context_window(
            segments, 1, _episode(), adapter=None, left_boundary_type=None,
            render=False, frame_cache=_cache_for(segments),
        )
        indices = window.evidence_indices
        self.assertEqual(len(indices), len(set(indices)))

    def test_render_false_emits_no_render_provenance_claim(self) -> None:
        segments = _three_segments()
        window = build_context_window(
            segments, 1, _episode(), adapter=None, left_boundary_type=None, render=False,
        )
        for frame in window.context_frames:
            self.assertIsNone(frame.pixel_sha256)
            self.assertFalse(frame.renderer_provenance["overlay_applied"])


class ContextWindowValidationTest(unittest.TestCase):
    """Each guard is exercised by constructing the exact violation."""

    def _valid_window(self) -> ContextWindow:
        segments = _three_segments()
        return build_context_window(
            segments, 1, _episode(), adapter=None, left_boundary_type=None,
            render=False, frame_cache=_cache_for(segments),
        )

    def _rebuild(self, window: ContextWindow, frames) -> ContextWindow:
        return ContextWindow(
            context_window_version=window.context_window_version,
            episode_id=window.episode_id,
            target_segment_id=window.target_segment_id,
            target_start_frame=window.target_start_frame,
            target_end_frame=window.target_end_frame,
            target_keyframe_indices=window.target_keyframe_indices,
            context_frames=tuple(frames),
            neighbor_status=window.neighbor_status,
            budget_audit=window.budget_audit,
            provenance=window.provenance,
        )

    def test_cross_episode_frame_is_rejected(self) -> None:
        window = self._valid_window()
        bad = list(window.context_frames)
        original = bad[0]
        bad[0] = ContextFrame(
            source_episode_id="data/demo_other",
            frame_index=original.frame_index,
            pixel_sha256=original.pixel_sha256,
            target_segment_id=original.target_segment_id,
            origin_segment_id=original.origin_segment_id,
            evidence_role=original.evidence_role,
            is_target_segment_frame=False,
            renderer_provenance=original.renderer_provenance,
        )
        with self.assertRaises(ContextWindowError):
            validate_context_window(self._rebuild(window, bad), _episode())

    def test_neighbor_flagged_as_target_frame_is_rejected(self) -> None:
        window = self._valid_window()
        bad = list(window.context_frames)
        original = bad[0]
        bad[0] = ContextFrame(
            source_episode_id=original.source_episode_id,
            frame_index=original.frame_index,
            pixel_sha256=original.pixel_sha256,
            target_segment_id=original.target_segment_id,
            origin_segment_id=original.origin_segment_id,
            evidence_role=original.evidence_role,
            is_target_segment_frame=True,       # lie: this frame is outside the target
            renderer_provenance=original.renderer_provenance,
        )
        with self.assertRaises(ContextWindowError):
            validate_context_window(self._rebuild(window, bad), _episode())

    def test_neighbor_placed_inside_target_segment_is_rejected(self) -> None:
        window = self._valid_window()
        bad = list(window.context_frames)
        original = bad[0]
        bad[0] = ContextFrame(
            source_episode_id=original.source_episode_id,
            frame_index=20,                      # inside [10, 39]
            pixel_sha256=original.pixel_sha256,
            target_segment_id=original.target_segment_id,
            origin_segment_id=original.origin_segment_id,
            evidence_role=ROLE_PREV_END,
            is_target_segment_frame=False,
            renderer_provenance=original.renderer_provenance,
        )
        with self.assertRaises(ContextWindowError):
            validate_context_window(self._rebuild(window, bad), _episode())

    def test_prev_after_target_is_rejected(self) -> None:
        window = self._valid_window()
        bad = list(window.context_frames)
        original = bad[0]
        bad[0] = ContextFrame(
            source_episode_id=original.source_episode_id,
            frame_index=50,                      # after the target -> wrong direction
            pixel_sha256=original.pixel_sha256,
            target_segment_id=original.target_segment_id,
            origin_segment_id="s1",
            evidence_role=ROLE_PREV_END,
            is_target_segment_frame=False,
            renderer_provenance=original.renderer_provenance,
        )
        with self.assertRaises(ContextWindowError):
            validate_context_window(self._rebuild(window, bad), _episode())

    def test_duplicate_role_pair_is_rejected(self) -> None:
        window = self._valid_window()
        bad = list(window.context_frames) + [window.context_frames[0]]
        with self.assertRaises(ContextWindowError):
            validate_context_window(self._rebuild(window, bad), _episode())

    def test_origin_equal_to_target_is_rejected(self) -> None:
        window = self._valid_window()
        bad = list(window.context_frames)
        original = bad[0]
        bad[0] = ContextFrame(
            source_episode_id=original.source_episode_id,
            frame_index=original.frame_index,
            pixel_sha256=original.pixel_sha256,
            target_segment_id=original.target_segment_id,
            origin_segment_id=original.target_segment_id,   # not a neighbour
            evidence_role=original.evidence_role,
            is_target_segment_frame=False,
            renderer_provenance=original.renderer_provenance,
        )
        with self.assertRaises(ContextWindowError):
            validate_context_window(self._rebuild(window, bad), _episode())

    def test_target_role_inside_context_frames_is_rejected(self) -> None:
        window = self._valid_window()
        bad = list(window.context_frames) + [
            ContextFrame(
                source_episode_id=window.episode_id,
                frame_index=25,
                pixel_sha256="hash-25",
                target_segment_id=window.target_segment_id,
                origin_segment_id=window.target_segment_id,
                evidence_role=ROLE_TARGET_KEYFRAME,
                is_target_segment_frame=True,
                renderer_provenance=dict(window.context_frames[0].renderer_provenance),
            )
        ]
        with self.assertRaises(ContextWindowError):
            validate_context_window(self._rebuild(window, bad), _episode())

    def test_unknown_role_is_rejected(self) -> None:
        window = self._valid_window()
        bad = list(window.context_frames)
        original = bad[0]
        bad[0] = ContextFrame(
            source_episode_id=original.source_episode_id,
            frame_index=original.frame_index,
            pixel_sha256=original.pixel_sha256,
            target_segment_id=original.target_segment_id,
            origin_segment_id=original.origin_segment_id,
            evidence_role="SOMETHING_ELSE",
            is_target_segment_frame=False,
            renderer_provenance=original.renderer_provenance,
        )
        with self.assertRaises(ContextWindowError):
            validate_context_window(self._rebuild(window, bad), _episode())

    def test_frame_beyond_episode_is_rejected(self) -> None:
        window = self._valid_window()
        bad = list(window.context_frames)
        original = bad[0]
        bad[0] = ContextFrame(
            source_episode_id=original.source_episode_id,
            frame_index=999,                     # episode has 200 frames
            pixel_sha256=original.pixel_sha256,
            target_segment_id=original.target_segment_id,
            origin_segment_id=original.origin_segment_id,
            evidence_role=original.evidence_role,
            is_target_segment_frame=False,
            renderer_provenance=original.renderer_provenance,
        )
        with self.assertRaises(ContextWindowError):
            validate_context_window(self._rebuild(window, bad), _episode())

    def test_budget_exceeded_is_rejected(self) -> None:
        window = self._valid_window()
        extra = [
            ContextFrame(
                source_episode_id=window.episode_id,
                frame_index=index,
                pixel_sha256=f"hash-{index}",
                target_segment_id=window.target_segment_id,
                origin_segment_id="s3",
                evidence_role=ROLE_NEXT_MIDDLE,
                is_target_segment_frame=False,
                renderer_provenance=dict(window.context_frames[0].renderer_provenance),
            )
            for index in (45, 46, 47)
        ]
        with self.assertRaises(ContextWindowError):
            validate_context_window(
                self._rebuild(window, list(window.context_frames) + extra), _episode()
            )

    def test_neighbor_status_mismatch_is_rejected(self) -> None:
        window = self._valid_window()
        broken = ContextWindow(
            context_window_version=window.context_window_version,
            episode_id=window.episode_id,
            target_segment_id=window.target_segment_id,
            target_start_frame=window.target_start_frame,
            target_end_frame=window.target_end_frame,
            target_keyframe_indices=window.target_keyframe_indices,
            context_frames=window.context_frames,
            neighbor_status={"PREV": NEIGHBOR_MISSING, "NEXT": NEIGHBOR_PRESENT},
            budget_audit=window.budget_audit,
            provenance=window.provenance,
        )
        with self.assertRaises(ContextWindowError):
            validate_context_window(broken, _episode())

    def test_keyframe_outside_segment_is_rejected(self) -> None:
        window = self._valid_window()
        broken = ContextWindow(
            context_window_version=window.context_window_version,
            episode_id=window.episode_id,
            target_segment_id=window.target_segment_id,
            target_start_frame=window.target_start_frame,
            target_end_frame=window.target_end_frame,
            target_keyframe_indices=(10, 24, 99),     # 99 outside [10, 39]
            context_frames=window.context_frames,
            neighbor_status=window.neighbor_status,
            budget_audit=window.budget_audit,
            provenance=window.provenance,
        )
        with self.assertRaises(ContextWindowError):
            validate_context_window(broken, _episode())


class ContextCleanRGBTest(unittest.TestCase):
    """Every frame must still satisfy the Clean RGB Source Contract."""

    def _window_with(self, **overrides) -> ContextWindow:
        segments = _three_segments()
        cache = _cache_for(segments)
        bad_index = segments[0].end_frame
        cache[bad_index] = _frame(bad_index, **overrides)
        return build_context_window(
            segments, 1, _episode(), adapter=None, left_boundary_type=None,
            render=False, frame_cache=cache,
        )

    def test_overlay_is_rejected(self) -> None:
        with self.assertRaises(ContextWindowError):
            self._window_with(overlay_applied=True)

    def test_audit_mp4_source_is_rejected(self) -> None:
        with self.assertRaises(ContextWindowError):
            self._window_with(audit_mp4_used=True)

    def test_lossy_roundtrip_is_rejected(self) -> None:
        with self.assertRaises(ContextWindowError):
            self._window_with(lossy_video_roundtrip=True)

    def test_contract_version_mismatch_is_rejected(self) -> None:
        with self.assertRaises(ContextWindowError):
            self._window_with(contract_version="SOMETHING_ELSE")


class ContextPrivilegedFieldTest(unittest.TestCase):
    def test_allowlist_passes(self) -> None:
        from project2_g3.context_window import audit_context_field_names

        self.assertTrue(audit_context_field_names(ALLOWED_CONTEXT_FIELDS)["passed"])

    def test_forbidden_name_is_detected(self) -> None:
        from project2_g3.context_window import audit_context_field_names

        audit = audit_context_field_names({"context_frames", "reward", "can_pos"})
        self.assertFalse(audit["passed"])
        self.assertIn("reward", audit["forbidden_hits"])
        self.assertIn("can_pos", audit["forbidden_hits"])

    def test_unapproved_name_is_detected(self) -> None:
        from project2_g3.context_window import audit_context_field_names

        audit = audit_context_field_names({"context_frames", "simulator_pose"})
        self.assertFalse(audit["passed"])
        self.assertIn("simulator_pose", audit["unapproved_fields"])

    def test_emitted_surfaces_have_no_forbidden_token(self) -> None:
        segments = _three_segments()
        window = build_context_window(
            segments, 1, _episode(), adapter=None, left_boundary_type=None,
            render=False, frame_cache=_cache_for(segments),
        )
        audit = audit_context_surfaces(window)
        self.assertTrue(audit["passed"], audit["forbidden_hits"])

    def test_forbidden_renderer_provenance_key_is_detected(self) -> None:
        segments = _three_segments()
        cache = _cache_for(segments)
        index = segments[0].end_frame
        cache[index] = _frame(index, reward=1.0)      # privileged field injected
        # the builder must fail closed rather than emit the forbidden surface
        with self.assertRaises(ContextWindowError) as ctx:
            build_context_window(
                segments, 1, _episode(), adapter=None, left_boundary_type=None,
                render=False, frame_cache=cache,
            )
        self.assertIn("FORBIDDEN", str(ctx.exception))


class ContextProvenanceTest(unittest.TestCase):
    def test_window_records_no_vlm_and_no_boundary_change(self) -> None:
        segments = _three_segments()
        window = build_context_window(
            segments, 1, _episode(), adapter=None, left_boundary_type=None,
            render=False, frame_cache=_cache_for(segments),
        )
        self.assertFalse(window.provenance["vlm_invoked"])
        self.assertFalse(window.provenance["frozen_g1_boundaries_modified"])
        self.assertTrue(window.provenance["target_keyframes_reused_not_recomputed"])
        self.assertEqual(window.context_window_version, CONTEXT_WINDOW_VERSION)

    def test_to_dict_round_trips_required_fields(self) -> None:
        segments = _three_segments()
        window = build_context_window(
            segments, 1, _episode(), adapter=None, left_boundary_type=None,
            render=False, frame_cache=_cache_for(segments),
        )
        payload = window.to_dict()
        required = {
            "source_episode_id", "frame_index", "pixel_sha256", "target_segment_id",
            "origin_segment_id", "evidence_role", "is_target_segment_frame",
            "renderer_provenance",
        }
        for frame in payload["context_frames"]:
            self.assertTrue(required.issubset(frame.keys()), required - set(frame.keys()))


class ABPanelTest(unittest.TestCase):
    """Panel A must be exactly the target keyframes; panel B adds neighbours.

    Regression guard: an earlier revision built panel A from ``context_frames``,
    which by construction holds only neighbour frames, so panel A came out empty
    while panel B silently showed neighbour frames as if they were the segment.
    """

    def _cells(self):
        from project2_g3.observability_ab import build_panel_cells

        segments = _three_segments()
        cache = _cache_for(segments)
        window = build_context_window(
            segments, 1, _episode(), adapter=None, left_boundary_type=None,
            render=False, frame_cache=cache,
        )
        return build_panel_cells(window, segments[1], None, cache), window

    def test_panel_a_is_exactly_the_target_keyframes(self) -> None:
        (cells_a, _), window = self._cells()
        self.assertEqual(len(cells_a), len(window.target_keyframe_indices))
        self.assertTrue(all(c["is_target_segment_frame"] for c in cells_a))
        self.assertFalse(any("<PREV" in c["label"] or "NEXT" in c["label"] for c in cells_a))

    def test_panel_b_contains_every_target_frame_and_the_neighbours(self) -> None:
        (cells_a, ordered_b), window = self._cells()
        self.assertEqual(len(ordered_b), len(cells_a) + len(window.context_frames))
        self.assertEqual(
            sum(c["is_target_segment_frame"] for c in ordered_b), len(cells_a)
        )
        self.assertEqual(
            sum(not c["is_target_segment_frame"] for c in ordered_b),
            len(window.context_frames),
        )

    def test_panel_b_orders_prev_target_next(self) -> None:
        (_cells_a, ordered_b), _window = self._cells()
        labels = [c["label"] for c in ordered_b]
        kinds = [
            "PREV" if label.startswith("<PREV")
            else "NEXT" if label.startswith("NEXT")
            else "TARGET"
            for label in labels
        ]
        self.assertEqual(kinds, sorted(kinds, key=["PREV", "TARGET", "NEXT"].index))

    def test_every_cell_has_a_non_empty_label(self) -> None:
        (cells_a, ordered_b), _window = self._cells()
        for cell in list(cells_a) + list(ordered_b):
            self.assertTrue(str(cell["label"]).strip())

    def test_role_label_band_is_drawn_inside_the_canvas(self) -> None:
        """Regression: the label used to be drawn below a too-short canvas.

        An earlier revision placed the per-cell role/frame-index text at
        ``_HEADER + _PAD + _CELL + 4`` while sizing the canvas to
        ``_HEADER + _CELL + 2 * _PAD``, so the text fell outside the image and
        the analyst sheet showed unlabelled frames - the analyst could not tell
        target evidence from neighbour evidence by anything but border colour.
        """

        from project2_g3 import observability_ab as ab

        cells = [
            {"rgb": np.zeros((128, 128, 3), dtype=np.uint8),
             "is_target_segment_frame": True, "label": "START f0"},
            {"rgb": np.zeros((128, 128, 3), dtype=np.uint8),
             "is_target_segment_frame": False, "label": "<PREV END f9"},
        ]
        strip = ab._render_strip(cells, title="t", annotate=True)
        self.assertEqual(
            strip.height, ab._HEADER + ab._CELL + 2 * ab._PAD + ab._FOOTER
        )
        footer = np.asarray(strip)[strip.height - ab._FOOTER:, :, :]
        background = np.array(ab._BG, dtype=np.uint8)
        self.assertTrue(
            bool((footer != background).any()),
            "role label band is blank: the per-cell label text was clipped",
        )


class BlindingTest(unittest.TestCase):
    def test_blinded_order_is_deterministic_and_balanced(self) -> None:
        from project2_g3.observability_ab import blinded_order

        orders = {f"seg_{i}": blinded_order(f"seg_{i}") for i in range(60)}
        for segment_id, order in orders.items():
            self.assertEqual(order, blinded_order(segment_id))
            self.assertEqual(set(order), {"A", "B"})
        first_positions = [o[0] for o in orders.values()]
        self.assertIn("A", first_positions)
        self.assertIn("B", first_positions)

    def test_review_sheet_dimensions_are_unscored_by_contract(self) -> None:
        from project2_g3.observability_ab import REVIEW_DIMENSIONS, UNSCORED

        self.assertTrue(REVIEW_DIMENSIONS)
        self.assertEqual(UNSCORED, "UNSCORED")


if __name__ == "__main__":
    unittest.main()
