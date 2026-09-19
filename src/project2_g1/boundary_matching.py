"""Frozen one-to-one boundary matching.

MATCHING_RULE_ID = MAX_CARDINALITY_MIN_TOTAL_DISTANCE_ONE_TO_ONE_V1

Within one episode:
1. legal pairs satisfy |pred_frame - gt_frame| <= T
2. maximize matched pair count
3. then minimize sum |pred_frame - gt_frame|
4. then lexicographically minimal pair list sorted by (gt_frame ASC, pred_frame ASC)

The search is a non-crossing DP on frame-sorted sequences. On a line, any
crossing matching can be uncrossed while preserving legality, weakly decreasing
L1 cost, and producing a lexicographically smaller (gt_frame, pred_frame) list.
Therefore the three-level optimum is attained by a non-crossing matching.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, Mapping, Sequence

MATCHING_RULE_ID = "MAX_CARDINALITY_MIN_TOTAL_DISTANCE_ONE_TO_ONE_V1"
TOLERANCE_FRAMES = 3
TOLERANCE_SECONDS = 0.15
SAMPLE_HZ = 20.0


class MatchingError(ValueError):
    pass


@dataclass(frozen=True)
class MatchPoint:
    episode_id: str
    frame: int
    point_id: str


@dataclass(frozen=True)
class MatchedPair:
    episode_id: str
    gt_id: str
    gt_frame: int
    pred_id: str
    pred_frame: int

    @property
    def delta_frame(self) -> int:
        return self.pred_frame - self.gt_frame

    @property
    def abs_error_frames(self) -> int:
        return abs(self.delta_frame)

    @property
    def abs_error_seconds(self) -> float:
        return self.abs_error_frames / SAMPLE_HZ

    @property
    def match_class(self) -> str:
        return "EXACT" if self.abs_error_frames == 0 else "NEAR"

    def lex_key(self) -> tuple[int, int]:
        return (self.gt_frame, self.pred_frame)


@dataclass(frozen=True)
class EpisodeMatching:
    episode_id: str
    pairs: tuple[MatchedPair, ...]
    unmatched_gt_ids: tuple[str, ...]
    unmatched_pred_ids: tuple[str, ...]

    @property
    def tp(self) -> int:
        return len(self.pairs)

    @property
    def fp(self) -> int:
        return len(self.unmatched_pred_ids)

    @property
    def fn(self) -> int:
        return len(self.unmatched_gt_ids)


def _as_point(item: Mapping[str, object] | MatchPoint, *, kind: str) -> MatchPoint:
    if isinstance(item, MatchPoint):
        return item
    episode_id = str(item.get("episode_id") or "")
    if kind == "gt":
        point_id = str(item.get("gt_id") or item.get("point_id") or "")
        frame = int(item["gt_frame"] if "gt_frame" in item else item["frame"])
    else:
        point_id = str(item.get("pred_id") or item.get("pred_boundary_id") or item.get("point_id") or "")
        frame = int(item["pred_frame"] if "pred_frame" in item else item["frame"])
    if not episode_id:
        raise MatchingError(f"{kind} episode_id is required")
    if not point_id:
        raise MatchingError(f"{kind} id is required")
    return MatchPoint(episode_id=episode_id, frame=frame, point_id=point_id)


def match_one_episode(
    gts: Sequence[Mapping[str, object] | MatchPoint],
    preds: Sequence[Mapping[str, object] | MatchPoint],
    *,
    tolerance_frames: int = TOLERANCE_FRAMES,
) -> EpisodeMatching:
    if tolerance_frames != TOLERANCE_FRAMES:
        raise MatchingError("TOLERANCE_MODIFIED is forbidden; T must remain 3")
    gt_points = [_as_point(item, kind="gt") for item in gts]
    pred_points = [_as_point(item, kind="pred") for item in preds]
    episodes = {item.episode_id for item in gt_points + pred_points}
    if len(episodes) > 1:
        raise MatchingError("match_one_episode forbids cross-episode inputs")
    episode_id = next(iter(episodes)) if episodes else ""
    if len({item.point_id for item in gt_points}) != len(gt_points):
        raise MatchingError("duplicate gt_id in episode")
    if len({item.point_id for item in pred_points}) != len(pred_points):
        raise MatchingError("duplicate pred_id in episode")

    gt_order = sorted(range(len(gt_points)), key=lambda idx: (gt_points[idx].frame, gt_points[idx].point_id))
    pred_order = sorted(range(len(pred_points)), key=lambda idx: (pred_points[idx].frame, pred_points[idx].point_id))
    n = len(gt_order)
    m = len(pred_order)

    @lru_cache(maxsize=None)
    def dp(i: int, j: int) -> tuple[int, int, tuple[tuple[int, int], ...]]:
        if i == n or j == m:
            return (0, 0, ())
        skip_gt = dp(i + 1, j)
        skip_pred = dp(i, j + 1)
        options = [skip_gt, skip_pred]
        gt = gt_points[gt_order[i]]
        pred = pred_points[pred_order[j]]
        if abs(pred.frame - gt.frame) <= tolerance_frames:
            card, cost, pairs = dp(i + 1, j + 1)
            options.append((
                card + 1,
                cost + abs(pred.frame - gt.frame),
                pairs + ((gt_order[i], pred_order[j]),),
            ))
        return min(
            options,
            key=lambda item: (
                -item[0],
                item[1],
                tuple(sorted(
                    (gt_points[gi].frame, pred_points[pj].frame) for gi, pj in item[2]
                )),
            ),
        )

    _card, _cost, raw_pairs = dp(0, 0)
    matched_gt = {gi for gi, _pj in raw_pairs}
    matched_pred = {pj for _gi, pj in raw_pairs}
    pairs = tuple(sorted(
        (
            MatchedPair(
                episode_id=gt_points[gi].episode_id,
                gt_id=gt_points[gi].point_id,
                gt_frame=gt_points[gi].frame,
                pred_id=pred_points[pj].point_id,
                pred_frame=pred_points[pj].frame,
            )
            for gi, pj in raw_pairs
        ),
        key=lambda pair: pair.lex_key(),
    ))
    unmatched_gt = tuple(
        gt_points[idx].point_id
        for idx in sorted(range(len(gt_points)), key=lambda i: (gt_points[i].frame, gt_points[i].point_id))
        if idx not in matched_gt
    )
    unmatched_pred = tuple(
        pred_points[idx].point_id
        for idx in sorted(range(len(pred_points)), key=lambda i: (pred_points[i].frame, pred_points[i].point_id))
        if idx not in matched_pred
    )
    return EpisodeMatching(
        episode_id=episode_id,
        pairs=pairs,
        unmatched_gt_ids=unmatched_gt,
        unmatched_pred_ids=unmatched_pred,
    )


def match_by_episode(
    gts: Iterable[Mapping[str, object] | MatchPoint],
    preds: Iterable[Mapping[str, object] | MatchPoint],
    *,
    tolerance_frames: int = TOLERANCE_FRAMES,
) -> dict[str, EpisodeMatching]:
    if tolerance_frames != TOLERANCE_FRAMES:
        raise MatchingError("TOLERANCE_MODIFIED is forbidden; T must remain 3")
    gt_points = [_as_point(item, kind="gt") for item in gts]
    pred_points = [_as_point(item, kind="pred") for item in preds]
    episodes = sorted({item.episode_id for item in gt_points + pred_points})
    out: dict[str, EpisodeMatching] = {}
    for episode_id in episodes:
        out[episode_id] = match_one_episode(
            [item for item in gt_points if item.episode_id == episode_id],
            [item for item in pred_points if item.episode_id == episode_id],
            tolerance_frames=tolerance_frames,
        )
    return out
