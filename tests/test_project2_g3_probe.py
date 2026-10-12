"""Tests for the P2-G3 Phase-1 audit scaffold (no VLM, no renderer required).

Coverage targets required by the Phase-1 brief:
- off-by-one frame handling;
- segments with no gripper event;
- missing / out-of-range frames;
- source reference provenance;
- forbidden-field leakage into a model input.

These tests use synthetic in-memory fixtures so they run without the heavy
robosuite/mujoco renderer stack.
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

from project2_g1.boundary_engine import CANDIDATE_GRIPPER, UnlabeledSegment  # noqa: E402
from project2_g1.source import FormalEpisodeArrays  # noqa: E402
from project2_mvp.m2 import select_keyframes  # noqa: E402
from project2_mvp.rgb_input import MODEL_RGB_CONTRACT_VERSION, CleanRGBFrame  # noqa: E402
from project2_g3.evidence_pack import (  # noqa: E402
    ALLOWED_EVIDENCE_FIELDS,
    EvidencePackError,
    assert_evidence_alignment,
    audit_forbidden_field_names,
    build_evidence_pack,
    task_text_evidence,
)


def _episode(n: int = 40) -> FormalEpisodeArrays:
    return FormalEpisodeArrays(
        source_episode_id="data/demo_x",
        native_episode_key="demo_x",
        frame_index=np.arange(n, dtype=np.int64),
        eef_pos=np.linspace(0.0, 1.0, n * 3, dtype=np.float64).reshape(n, 3),
        eef_quat=np.tile(np.array([0.0, 0.0, 0.0, 1.0]), (n, 1)),
        gripper_qpos=np.linspace(0.04, 0.0, n * 2, dtype=np.float64).reshape(n, 2),
        joint_pos=np.zeros((n, 7), dtype=np.float64),
        actions=np.ones((n, 7), dtype=np.float64) * 0.1,
        provenance={"task": "PickPlaceCan", "dataset_id": "robomimic_v15_can_mh"},
    )


def _segment(start: int, end: int, *, sid: str = "s1") -> UnlabeledSegment:
    return UnlabeledSegment(
        segment_id=sid,
        source_episode_id="data/demo_x",
        start_frame=start,
        end_frame=end,
        duration_frames=end - start + 1,
        duration_sec=(end - start + 1) * 0.05,
        left_boundary_id="b_left",
        right_boundary_id="b_right",
        left_boundary_reason="TEST",
        right_boundary_reason="TEST",
        segmentation_version="G1-TEST",
        config_version="cfg-test",
        short_segment_flag=False,
        long_segment_flag=False,
        review_required=False,
    )


def _fake_frame(index: int) -> CleanRGBFrame:
    return CleanRGBFrame(
        source_episode_id="data/demo_x",
        frame_index=index,
        rgb=np.zeros((2, 2, 3), dtype=np.uint8),
        provenance={
            "contract_version": MODEL_RGB_CONTRACT_VERSION,
            "source": "TEST",
            "overlay_applied": False,
            "audit_mp4_used": False,
            "lossy_video_roundtrip": False,
            "pixel_sha256": f"hash-{index}",
        },
    )


class KeyframeSelectionTest(unittest.TestCase):
    def test_inclusive_range_and_middle(self) -> None:
        kf = select_keyframes(_segment(0, 10), left_boundary_type=None)
        frames = {k.frame_index: set(k.roles) for k in kf}
        self.assertEqual(set(frames), {0, 5, 10})
        self.assertEqual(frames[5], {"MIDDLE"})

    def test_off_by_one_single_frame_segment(self) -> None:
        # start == end must still yield exactly one frame carrying START+MIDDLE+END.
        kf = select_keyframes(_segment(7, 7), left_boundary_type=None)
        self.assertEqual(len(kf), 1)
        self.assertEqual(kf[0].frame_index, 7)
        self.assertEqual(set(kf[0].roles), {"START", "MIDDLE", "END"})

    def test_middle_uses_floor_division(self) -> None:
        kf = select_keyframes(_segment(3, 8), left_boundary_type=None)
        frames = {k.frame_index for k in kf}
        self.assertIn(5, frames)  # (3+8)//2 == 5


class GripperEventTest(unittest.TestCase):
    def test_no_gripper_event_when_left_boundary_not_gripper(self) -> None:
        kf = select_keyframes(_segment(0, 20), left_boundary_type="DIRECTION_CHANGE")
        roles = [r for k in kf for r in k.roles]
        self.assertNotIn("GRIPPER_EVENT", roles)

    def test_gripper_event_attached_to_start_frame(self) -> None:
        kf = select_keyframes(_segment(4, 30), left_boundary_type=CANDIDATE_GRIPPER)
        start = [k for k in kf if k.frame_index == 4][0]
        self.assertIn("GRIPPER_EVENT", start.roles)
        self.assertIn("START", start.roles)


class EvidencePackTest(unittest.TestCase):
    def test_build_pack_without_render_uses_cache(self) -> None:
        seg = _segment(0, 20)
        indices = sorted({k.frame_index for k in select_keyframes(seg, left_boundary_type=None)})
        cache = {i: _fake_frame(i) for i in indices}
        pack = build_evidence_pack(
            seg,
            _episode(),
            adapter=None,
            left_boundary_type=None,
            gripper_state=None,
            render=False,
            frame_cache=cache,
        )
        self.assertEqual(pack.rgb_indices, pack.keyframe_indices)
        self.assertTrue(pack.alignment_audit["index_preserving"])
        self.assertFalse(pack.task_text.recorded_instruction)
        self.assertTrue(pack.forbidden_field_audit["passed"])

    def test_out_of_segment_frame_fails(self) -> None:
        seg = _segment(0, 20)
        # cache provides a frame outside the segment range
        cache = {i: _fake_frame(i) for i in (0, 10, 25)}
        with self.assertRaises(EvidencePackError):
            build_evidence_pack(
                seg, _episode(40), adapter=None, left_boundary_type=None,
                gripper_state=None, render=False, frame_cache=cache,
            )

    def test_frame_index_beyond_episode_fails(self) -> None:
        seg = _segment(0, 100)  # episode only has 40 frames
        with self.assertRaises(EvidencePackError):
            build_evidence_pack(
                seg, _episode(40), adapter=None, left_boundary_type=None,
                gripper_state=None, render=False,
            )

    def test_alignment_detects_index_mismatch(self) -> None:
        seg = _segment(0, 20)
        cache = {i: _fake_frame(i) for i in (0, 10, 20)}
        pack = build_evidence_pack(
            seg, _episode(), adapter=None, left_boundary_type=None,
            gripper_state=None, render=False, frame_cache=cache,
        )
        broken = type(pack)(
            episode_id=pack.episode_id, segment_id=pack.segment_id,
            start_frame=pack.start_frame, end_frame=pack.end_frame,
            duration_frames=pack.duration_frames, duration_sec=pack.duration_sec,
            keyframes=pack.keyframes,
            rgb_frames=(pack.rgb_frames[0],),  # drop two frames
            motion_summary=pack.motion_summary, task_text=pack.task_text,
            forbidden_field_audit=pack.forbidden_field_audit,
            alignment_audit=pack.alignment_audit, provenance=pack.provenance,
        )
        with self.assertRaises(EvidencePackError):
            assert_evidence_alignment(broken)

    def test_provenance_reference_preserved(self) -> None:
        seg = _segment(0, 20)
        cache = {i: _fake_frame(i) for i in (0, 10, 20)}
        pack = build_evidence_pack(
            seg, _episode(), adapter=None, left_boundary_type=CANDIDATE_GRIPPER,
            gripper_state=None, render=False, frame_cache=cache,
        )
        prov = pack.provenance
        self.assertEqual(prov["rgb_contract_version"], MODEL_RGB_CONTRACT_VERSION)
        self.assertEqual(prov["left_boundary_type"], CANDIDATE_GRIPPER)
        self.assertFalse(prov["vlm_invoked"])
        self.assertEqual(prov["source_episode_provenance"]["dataset_id"], "robomimic_v15_can_mh")


class ForbiddenFieldTest(unittest.TestCase):
    def test_allowlist_passes(self) -> None:
        self.assertTrue(audit_forbidden_field_names(ALLOWED_EVIDENCE_FIELDS)["passed"])

    def test_forbidden_tokens_detected(self) -> None:
        audit = audit_forbidden_field_names({"keyframe_rgb", "reward", "object_gt", "next_obs"})
        self.assertFalse(audit["passed"])
        self.assertIn("reward", audit["forbidden_hits"])
        self.assertIn("object_gt", audit["forbidden_hits"])
        self.assertIn("next_obs", audit["forbidden_hits"])

    def test_unapproved_field_detected(self) -> None:
        audit = audit_forbidden_field_names({"keyframe_rgb", "simulator_pose"})
        self.assertFalse(audit["passed"])
        self.assertIn("simulator_pose", audit["unapproved_fields"])

    def test_task_text_not_upgraded_to_instruction(self) -> None:
        evidence = task_text_evidence({"task": "PickPlaceCan"})
        self.assertTrue(evidence.available)
        self.assertEqual(evidence.value, "PickPlaceCan")
        self.assertFalse(evidence.recorded_instruction)

    def test_missing_task_field(self) -> None:
        evidence = task_text_evidence({})
        self.assertFalse(evidence.available)
        self.assertIsNone(evidence.value)
        self.assertFalse(evidence.recorded_instruction)


class DevelopmentPoolRuleTest(unittest.TestCase):
    def test_probe_digest_is_deterministic(self) -> None:
        from project2_g3.development_pool import probe_digest

        self.assertEqual(probe_digest("data/demo_7"), probe_digest("data/demo_7"))
        self.assertNotEqual(probe_digest("data/demo_7"), probe_digest("data/demo_8"))

    def test_selection_is_stratified_and_unique(self) -> None:
        from project2_g3.development_pool import assign_probe_strata, select_probe_episodes

        members = [
            {"episode_id": f"data/demo_{i}", "frame_count": 10 + i, "duration_seconds": 0.5}
            for i in range(60)
        ]
        stratified = assign_probe_strata(members)
        selected = select_probe_episodes(stratified, per_stratum=4)
        self.assertEqual(len(selected), 12)
        self.assertEqual(len({r["episode_id"] for r in selected}), 12)
        self.assertEqual(
            sorted({r["duration_stratum"] for r in selected}), ["LONG", "MEDIUM", "SHORT"]
        )

    def test_selection_is_order_independent(self) -> None:
        from project2_g3.development_pool import assign_probe_strata, select_probe_episodes

        members = [
            {"episode_id": f"data/demo_{i}", "frame_count": 10 + (i % 17), "duration_seconds": 0.5}
            for i in range(60)
        ]
        a = select_probe_episodes(assign_probe_strata(members), per_stratum=4)
        b = select_probe_episodes(assign_probe_strata(list(reversed(members))), per_stratum=4)
        self.assertEqual([r["episode_id"] for r in a], [r["episode_id"] for r in b])


if __name__ == "__main__":
    unittest.main()
