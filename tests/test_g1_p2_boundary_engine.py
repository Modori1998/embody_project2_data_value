"""G1-P2 Boundary Engine unit / integration tests.

Synthetic episodes only. These tests do not search thresholds and do not
claim Human-GT calibration.
"""

from __future__ import annotations

import ast
import math
import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import numpy as np

from project2_g1.boundary_config import G1P2Config, load_g1_p2_config
from project2_g1.boundary_engine import (
    CANDIDATE_DIRECTION,
    CANDIDATE_GRIPPER,
    CANDIDATE_IDLE_TO_MOVE,
    CANDIDATE_MOVE_TO_IDLE,
    DECISION_MERGE_CONSOLIDATION,
    DECISION_RETAIN_HARD,
    DECISION_SUPPRESS_SHORT_PAUSE,
    FLAG_MICRO_INTERACTION,
    BoundaryCandidate,
    consolidate_candidates,
    debounce_candidates,
    persistent_binary_transitions,
    persistent_high_runs,
    run_boundary_engine,
)
from project2_g1.config import G1P1Config
from project2_g1.signals import compute_formal_signals
from project2_g1.source import FormalEpisodeArrays

ENGINE_PATH = SRC / "project2_g1" / "boundary_engine.py"
FORBIDDEN_TOKENS = (
    "can_pos",
    "Can_pos",
    "Can_quat",
    "Can_to_robot0_eef",
    "object_packed",
    "reward",
    "rewards",
    "success",
    "dones",
    "next_obs",
    "privileged_audit",
    "get_privileged_reference",
)


def _open_gripper(n: int) -> np.ndarray:
    return np.stack([np.full(n, 0.04), np.full(n, -0.04)], axis=1)


def _closed_gripper(n: int) -> np.ndarray:
    return np.stack([np.full(n, 0.01), np.full(n, -0.01)], axis=1)


def _identity_quat(n: int) -> np.ndarray:
    return np.tile(np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64), (n, 1))


def _episode(
    pos: np.ndarray,
    *,
    gripper: np.ndarray | None = None,
    quat: np.ndarray | None = None,
    actions: np.ndarray | None = None,
    episode_id: str = "data/demo_synth",
) -> FormalEpisodeArrays:
    n = len(pos)
    if gripper is None:
        gripper = _open_gripper(n)
    if quat is None:
        quat = _identity_quat(n)
    if actions is None:
        actions = np.zeros((n, 7), dtype=np.float64)
    return FormalEpisodeArrays(
        source_episode_id=episode_id,
        native_episode_key=episode_id.split("/")[-1],
        frame_index=np.arange(n, dtype=np.int64),
        eef_pos=np.asarray(pos, dtype=np.float64),
        eef_quat=np.asarray(quat, dtype=np.float64),
        gripper_qpos=np.asarray(gripper, dtype=np.float64),
        joint_pos=np.zeros((n, 7), dtype=np.float64),
        actions=np.asarray(actions, dtype=np.float64),
        provenance={},
    )


def _cfg(**overrides: object) -> G1P2Config:
    values = dict(
        motion_speed_threshold=0.02,
        motion_persistence_frames=4,
        direction_change_threshold=1.2,
        direction_persistence_frames=3,
        gripper_state_threshold=0.06,
        gripper_persistence_frames=4,
        debounce_frames=4,
        boundary_consolidation_window=8,
        pause_bridge_duration=10,
        min_segment_length=8,
        max_segment_length=80,
        rotation_support_threshold=0.015,
        action_support_threshold=0.5,
        support_window_frames=8,
        direction_compatibility_threshold=0.8,
        direction_window_frames=8,
        direction_min_window_displacement_m=0.005,
    )
    values.update(overrides)
    return G1P2Config(**values)  # type: ignore[arg-type]


def _run(episode: FormalEpisodeArrays, config: G1P2Config | None = None):
    signals = compute_formal_signals(episode, G1P1Config())
    return signals, run_boundary_engine(signals, config or _cfg())


class CandidateRuleTests(unittest.TestCase):
    def test_isolated_speed_spike_is_not_a_candidate(self) -> None:
        n = 40
        pos = np.zeros((n, 3), dtype=np.float64)
        pos[:, 2] = 0.9
        pos[20:, 0] = 0.05
        _, result = _run(_episode(pos, episode_id="data/demo_spike"))
        motion = [
            c
            for c in result.candidates
            if c.candidate_type in {CANDIDATE_MOVE_TO_IDLE, CANDIDATE_IDLE_TO_MOVE}
        ]
        self.assertEqual(motion, [], [c.to_row() for c in result.candidates])

    def test_persistent_move_to_idle(self) -> None:
        n = 50
        pos = np.zeros((n, 3), dtype=np.float64)
        for t in range(n):
            pos[t, 0] = 0.01 * min(t, 30)
            pos[t, 2] = 0.9
        _, result = _run(_episode(pos, episode_id="data/demo_stop"))
        types = [c.candidate_type for c in result.candidates]
        self.assertIn(CANDIDATE_MOVE_TO_IDLE, types)
        move_idle = [c for c in result.candidates if c.candidate_type == CANDIDATE_MOVE_TO_IDLE]
        self.assertTrue(any(29 <= c.frame <= 33 for c in move_idle), [c.frame for c in move_idle])

    def test_persistent_idle_to_move(self) -> None:
        n = 50
        pos = np.zeros((n, 3), dtype=np.float64)
        pos[:, 2] = 0.9
        for t in range(20, n):
            pos[t, 0] = 0.01 * (t - 19)
        _, result = _run(_episode(pos, episode_id="data/demo_go"))
        types = [c.candidate_type for c in result.candidates]
        self.assertIn(CANDIDATE_IDLE_TO_MOVE, types)
        idle_move = [c for c in result.candidates if c.candidate_type == CANDIDATE_IDLE_TO_MOVE]
        self.assertTrue(any(18 <= c.frame <= 22 for c in idle_move), [c.frame for c in idle_move])

    def test_persistent_gripper_transition_is_hard(self) -> None:
        n = 50
        pos = np.zeros((n, 3), dtype=np.float64)
        pos[:, 2] = 0.9
        gripper = _open_gripper(n)
        gripper[25:] = _closed_gripper(n - 25)
        _, result = _run(_episode(pos, gripper=gripper, episode_id="data/demo_grip"))
        hard = [c for c in result.candidates if c.candidate_type == CANDIDATE_GRIPPER]
        self.assertTrue(hard)
        self.assertTrue(all(c.primary_reason.startswith("PERSISTENT_GRIPPER_") for c in hard))
        self.assertTrue(any(c.polarity == "OPEN_TO_CLOSE" and 23 <= c.frame <= 27 for c in hard))


class PersistenceTests(unittest.TestCase):
    def test_persistence_rejects_short_binary_spike(self) -> None:
        state = np.array([0, 0, 0, 0, 1, 0, 0, 0, 0], dtype=np.int8)
        self.assertEqual(persistent_binary_transitions(state, 4), [])

    def test_persistence_accepts_sustained_regime_change(self) -> None:
        state = np.array([0, 0, 0, 0, 1, 1, 1, 1, 1], dtype=np.int8)
        found = persistent_binary_transitions(state, 4)
        self.assertEqual(found, [(4, 0, 1)])

    def test_direction_persistence_rejects_single_frame_peak(self) -> None:
        values = np.zeros(20, dtype=np.float64)
        values[10] = 2.0
        self.assertEqual(persistent_high_runs(values, 1.2, 3), [])


class SupportingOnlyTests(unittest.TestCase):
    def test_rotation_only_is_not_a_boundary(self) -> None:
        n = 40
        pos = np.zeros((n, 3), dtype=np.float64)
        pos[:, 2] = 0.9
        quat = np.zeros((n, 4), dtype=np.float64)
        for t in range(n):
            theta = 0.08 * t
            quat[t] = [0.0, 0.0, math.sin(theta / 2.0), math.cos(theta / 2.0)]
        signals, result = _run(_episode(pos, quat=quat, episode_id="data/demo_rot"))
        self.assertGreater(float(np.max(signals.eef_rotation_delta_rad)), 0.05)
        self.assertEqual(result.candidates, [])
        self.assertEqual(len(result.final_events), 0)
        self.assertEqual(len(result.segments), 1)
        self.assertEqual(result.segments[0].segment_label, "NONE")

    def test_action_spike_only_is_not_a_boundary(self) -> None:
        n = 40
        pos = np.zeros((n, 3), dtype=np.float64)
        pos[:, 2] = 0.9
        actions = np.zeros((n, 7), dtype=np.float64)
        actions[18:22, 0] = 1.0
        signals, result = _run(_episode(pos, actions=actions, episode_id="data/demo_act"))
        self.assertGreater(float(np.max(signals.action_change_magnitude)), 0.5)
        self.assertEqual(result.candidates, [])
        self.assertEqual(len(result.final_events), 0)


class ConsolidationTests(unittest.TestCase):
    def test_hard_and_nearby_soft_consolidate_to_hard_frame(self) -> None:
        hard = BoundaryCandidate(
            episode_id="data/demo_c",
            candidate_id="demo_c-C0001",
            frame=60,
            candidate_type=CANDIDATE_GRIPPER,
            primary_reason="PERSISTENT_GRIPPER_OPEN_TO_CLOSE",
            supporting_reasons=[],
            evidence_value=0.04,
            persistence_status="PERSISTENT",
            source_signal="gripper_aperture",
            config_version="test",
            polarity="OPEN_TO_CLOSE",
        )
        soft = BoundaryCandidate(
            episode_id="data/demo_c",
            candidate_id="demo_c-C0002",
            frame=64,
            candidate_type=CANDIDATE_DIRECTION,
            primary_reason="PERSISTENT_DIRECTION_CHANGE",
            supporting_reasons=["ROTATION_SUPPORT"],
            evidence_value=1.8,
            persistence_status="PERSISTENT",
            source_signal="direction_change_evidence",
            config_version="test",
            polarity="DIRECTION_CHANGE",
        )
        decisions = debounce_candidates([hard, soft], _cfg(debounce_frames=1, boundary_consolidation_window=8))
        events = consolidate_candidates([hard, soft], decisions, _cfg(boundary_consolidation_window=8))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].frame, 60)
        self.assertEqual(events[0].candidate_type, CANDIDATE_GRIPPER)
        self.assertEqual(decisions[soft.candidate_id].decision, DECISION_MERGE_CONSOLIDATION)
        self.assertIn("ROTATION_SUPPORT", events[0].supporting_reasons)

    def test_opposite_hard_boundaries_are_not_merged(self) -> None:
        a = BoundaryCandidate(
            episode_id="data/demo_h",
            candidate_id="demo_h-C0001",
            frame=20,
            candidate_type=CANDIDATE_GRIPPER,
            primary_reason="PERSISTENT_GRIPPER_OPEN_TO_CLOSE",
            supporting_reasons=[],
            evidence_value=0.04,
            persistence_status="PERSISTENT",
            source_signal="gripper_aperture",
            config_version="test",
            polarity="OPEN_TO_CLOSE",
        )
        b = BoundaryCandidate(
            episode_id="data/demo_h",
            candidate_id="demo_h-C0002",
            frame=24,
            candidate_type=CANDIDATE_GRIPPER,
            primary_reason="PERSISTENT_GRIPPER_CLOSE_TO_OPEN",
            supporting_reasons=[],
            evidence_value=0.04,
            persistence_status="PERSISTENT",
            source_signal="gripper_aperture",
            config_version="test",
            polarity="CLOSE_TO_OPEN",
        )
        decisions = debounce_candidates([a, b], _cfg(debounce_frames=1))
        events = consolidate_candidates([a, b], decisions, _cfg(boundary_consolidation_window=8))
        self.assertEqual(len(events), 2)


class HardProtectionTests(unittest.TestCase):
    def test_hard_boundary_near_short_segment_is_not_removed(self) -> None:
        n = 50
        pos = np.zeros((n, 3), dtype=np.float64)
        pos[:, 2] = 0.9
        gripper = _open_gripper(n)
        gripper[20:25] = _closed_gripper(5)
        config = _cfg(gripper_persistence_frames=3, min_segment_length=10, debounce_frames=1)
        _, result = _run(_episode(pos, gripper=gripper, episode_id="data/demo_micro"), config)
        hard_final = [e for e in result.final_events if e.candidate_type == CANDIDATE_GRIPPER]
        self.assertGreaterEqual(len(hard_final), 2, [e.to_row() for e in result.final_events])
        self.assertTrue(any(FLAG_MICRO_INTERACTION in e.review_flags for e in hard_final))
        retain = [d for d in result.decisions.values() if d.decision == DECISION_RETAIN_HARD]
        self.assertTrue(retain)


class PauseBridgingTests(unittest.TestCase):
    def test_short_same_direction_pause_can_bridge(self) -> None:
        n = 70
        pos = np.zeros((n, 3), dtype=np.float64)
        pos[:, 2] = 0.9
        x = 0.0
        for t in range(n):
            if t < 25 or t >= 31:
                x += 0.01
            pos[t, 0] = x
        config = _cfg(
            motion_persistence_frames=4,
            pause_bridge_duration=10,
            min_segment_length=4,
            direction_compatibility_threshold=0.8,
        )
        _, result = _run(_episode(pos, episode_id="data/demo_pause"), config)
        self.assertTrue(
            any(d.decision == DECISION_SUPPRESS_SHORT_PAUSE for d in result.decisions.values()),
            [d.to_row() for d in result.decisions.values()],
        )
        self.assertFalse(
            any(e.candidate_type == CANDIDATE_MOVE_TO_IDLE and e.active for e in result.events)
            and any(e.candidate_type == CANDIDATE_IDLE_TO_MOVE and e.active for e in result.events)
        )


class PrivilegedLeakageTests(unittest.TestCase):
    def test_privileged_leakage(self) -> None:
        source = ENGINE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        strings = [
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        ]
        leaked_strings = sorted(set(FORBIDDEN_TOKENS).intersection(strings))
        self.assertEqual(leaked_strings, [], leaked_strings)
        self.assertNotIn("from .privileged_audit", source)
        self.assertNotIn("load_privileged_overlay", source)
        self.assertNotIn("get_privileged_reference", source)


class PipelineSmokeTests(unittest.TestCase):
    def test_full_pipeline_smoke_covers_episode_without_semantic_labels(self) -> None:
        n = 80
        pos = np.zeros((n, 3), dtype=np.float64)
        for t in range(n):
            pos[t, 0] = 0.01 * min(t, 40)
            pos[t, 2] = 0.9
        gripper = _open_gripper(n)
        gripper[50:] = _closed_gripper(n - 50)
        _, result = _run(_episode(pos, gripper=gripper, episode_id="data/demo_pipe"))
        self.assertGreaterEqual(len(result.segments), 1)
        self.assertEqual(result.segments[0].start_frame, 0)
        self.assertEqual(result.segments[-1].end_frame, n - 1)
        for left, right in zip(result.segments, result.segments[1:]):
            self.assertEqual(right.start_frame, left.end_frame + 1)
        for seg in result.segments:
            self.assertEqual(seg.segment_label, "NONE")
            self.assertEqual(seg.semantic_phase, "NONE")
            self.assertFalse(any(token in seg.segment_id.lower() for token in ("approach", "grasp", "place")))
        load_g1_p2_config()
        self.assertFalse(load_g1_p2_config().formal)


if __name__ == "__main__":
    unittest.main()
