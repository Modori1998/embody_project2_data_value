"""Independent tests for MAX_CARDINALITY_MIN_TOTAL_DISTANCE_ONE_TO_ONE_V1."""

from __future__ import annotations

import itertools
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from project2_g1.boundary_matching import (
    MATCHING_RULE_ID,
    TOLERANCE_FRAMES,
    MatchPoint,
    match_by_episode,
    match_one_episode,
)


def _gt(episode: str, frame: int, gt_id: str | None = None) -> MatchPoint:
    return MatchPoint(episode_id=episode, frame=frame, point_id=gt_id or f"{episode}-G{frame}")


def _pred(episode: str, frame: int, pred_id: str | None = None) -> MatchPoint:
    return MatchPoint(episode_id=episode, frame=frame, point_id=pred_id or f"{episode}-P{frame}")


def brute_force(gts: list[MatchPoint], preds: list[MatchPoint], tolerance: int = 3):
    best = None
    pred_ids = [item.point_id for item in preds]
    choices = list(range(len(preds))) + [None]
    for assignment in itertools.product(choices, repeat=len(gts)):
        used = set()
        pairs = []
        legal = True
        for gt, choice in zip(gts, assignment):
            if choice is None:
                continue
            pred = preds[choice]
            if pred.point_id in used or abs(pred.frame - gt.frame) > tolerance:
                legal = False
                break
            used.add(pred.point_id)
            pairs.append((gt.frame, pred.frame, gt.point_id, pred.point_id))
        if not legal:
            continue
        key = (-len(pairs), sum(abs(gf - pf) for gf, pf, _g, _p in pairs), tuple(sorted((gf, pf) for gf, pf, _g, _p in pairs)))
        if best is None or key < best[0]:
            best = (key, pairs)
    return best[1] if best else []


def greedy_nearest_pair(gts: list[MatchPoint], preds: list[MatchPoint], tolerance: int = 3):
    candidates = []
    for gt in gts:
        for pred in preds:
            dist = abs(pred.frame - gt.frame)
            if dist <= tolerance:
                candidates.append((dist, gt.frame, pred.frame, gt.point_id, pred.point_id))
    candidates.sort()
    used_g: set[str] = set()
    used_p: set[str] = set()
    pairs = []
    for _dist, _gf, _pf, gid, pid in candidates:
        if gid in used_g or pid in used_p:
            continue
        used_g.add(gid)
        used_p.add(pid)
        pairs.append((gid, pid))
    return pairs


class MatchingContractTests(unittest.TestCase):
    def test_rule_id_and_tolerance_are_frozen(self) -> None:
        self.assertEqual(MATCHING_RULE_ID, "MAX_CARDINALITY_MIN_TOTAL_DISTANCE_ONE_TO_ONE_V1")
        self.assertEqual(TOLERANCE_FRAMES, 3)
        with self.assertRaises(ValueError):
            match_one_episode([_gt("e", 0)], [_pred("e", 0)], tolerance_frames=5)

    def test_a_single_exact_match(self) -> None:
        result = match_one_episode([_gt("e", 10)], [_pred("e", 10)])
        self.assertEqual(result.tp, 1)
        self.assertEqual(result.pairs[0].match_class, "EXACT")
        self.assertEqual(result.fp, 0)
        self.assertEqual(result.fn, 0)

    def test_b_single_near_match_within_3(self) -> None:
        result = match_one_episode([_gt("e", 10)], [_pred("e", 13)])
        self.assertEqual(result.tp, 1)
        self.assertEqual(result.pairs[0].match_class, "NEAR")
        self.assertEqual(result.pairs[0].abs_error_frames, 3)

    def test_c_outside_3_is_no_match(self) -> None:
        result = match_one_episode([_gt("e", 10)], [_pred("e", 14)])
        self.assertEqual(result.tp, 0)
        self.assertEqual(result.fp, 1)
        self.assertEqual(result.fn, 1)

    def test_d_one_gt_multiple_predictions(self) -> None:
        result = match_one_episode(
            [_gt("e", 10)],
            [_pred("e", 10, "P10"), _pred("e", 11, "P11")],
        )
        self.assertEqual(result.tp, 1)
        self.assertEqual(result.fp, 1)
        self.assertEqual(result.pairs[0].pred_id, "P10")
        self.assertEqual(result.unmatched_pred_ids, ("P11",))

    def test_e_greedy_nearest_loses_cardinality(self) -> None:
        gts = [_gt("e", 0, "G0"), _gt("e", 4, "G4")]
        preds = [_pred("e", 3, "P3"), _pred("e", 7, "P7")]
        greedy = greedy_nearest_pair(gts, preds)
        self.assertEqual(len(greedy), 1)
        result = match_one_episode(gts, preds)
        self.assertEqual(result.tp, 2)
        self.assertEqual(
            {(pair.gt_id, pair.pred_id) for pair in result.pairs},
            {("G0", "P3"), ("G4", "P7")},
        )

    def test_f_min_total_distance_wins_at_same_cardinality(self) -> None:
        gts = [_gt("e", 0, "G0"), _gt("e", 10, "G10")]
        preds = [_pred("e", 0, "P0"), _pred("e", 2, "P2")]
        result = match_one_episode(gts, preds)
        self.assertEqual(result.tp, 1)
        self.assertEqual(result.pairs[0].gt_id, "G0")
        self.assertEqual(result.pairs[0].pred_id, "P0")
        self.assertEqual(result.pairs[0].abs_error_frames, 0)

    def test_g_lexicographic_tie_break(self) -> None:
        gts = [_gt("e", 0, "G0"), _gt("e", 6, "G6")]
        preds = [_pred("e", 3, "P3")]
        result = match_one_episode(gts, preds)
        self.assertEqual(result.tp, 1)
        self.assertEqual(result.pairs[0].gt_id, "G0")
        self.assertEqual(result.pairs[0].pred_id, "P3")
        oracle = brute_force(gts, preds)
        self.assertEqual(oracle[0][:2], (0, 3))

    def test_h_never_cross_episode(self) -> None:
        matching = match_by_episode(
            [_gt("A", 10)],
            [_pred("B", 10)],
        )
        self.assertEqual(matching["A"].tp, 0)
        self.assertEqual(matching["A"].fn, 1)
        self.assertEqual(matching["B"].tp, 0)
        self.assertEqual(matching["B"].fp, 1)
        with self.assertRaises(ValueError):
            match_one_episode([_gt("A", 10)], [_pred("B", 10)])

    def test_i_empty_gt(self) -> None:
        result = match_one_episode([], [_pred("e", 4), _pred("e", 8)])
        self.assertEqual(result.tp, 0)
        self.assertEqual(result.fp, 2)
        self.assertEqual(result.fn, 0)

    def test_j_empty_predictions(self) -> None:
        result = match_one_episode([_gt("e", 4), _gt("e", 8)], [])
        self.assertEqual(result.tp, 0)
        self.assertEqual(result.fp, 0)
        self.assertEqual(result.fn, 2)

    def test_dp_matches_brute_force_oracle(self) -> None:
        gts = [_gt("e", frame, f"G{frame}") for frame in (0, 3, 8)]
        preds = [_pred("e", frame, f"P{frame}") for frame in (1, 4, 10, 12)]
        result = match_one_episode(gts, preds)
        oracle = brute_force(gts, preds)
        self.assertEqual(
            [(pair.gt_frame, pair.pred_frame) for pair in result.pairs],
            sorted((gf, pf) for gf, pf, _gid, _pid in oracle),
        )


if __name__ == "__main__":
    unittest.main()
