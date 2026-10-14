"""Post-hoc reliability and semantic analysis for completed G3D2-R runs.

Pure, offline logic only: no model calls, no filesystem mutation. A cell is a
planned ``(segment_id, group)`` experiment unit. For each cell the attempts are
ordered 1..N; the first valid attempt is the final prediction and a cell whose
attempts are exhausted without a valid response is a permanent failure that is
reported, never repaired or dropped.
"""
from __future__ import annotations

from project2_g3.g3d_paired import score_pairs

ALLOWED_EVENTS = ("grasp_attempt", "object_motion", "release_attempt")


def is_valid(record: dict) -> bool:
    qc = record.get("qc") or {}
    return (record.get("http_status") == 200 and bool(qc.get("parse_ok"))
            and bool(qc.get("schema_ok")) and bool(qc.get("frame_evidence_ok"))
            and not qc.get("truncated"))


def load_cells(responses: list[dict], expected: list[tuple[str, str]]) -> dict:
    """Group attempt records per ``(segment_id, group)`` and enforce a clean chain."""
    cells: dict[tuple[str, str], list[dict]] = {}
    for record in responses:
        cells.setdefault((record["segment_id"], record["group"]), []).append(record)
    if set(cells) != set(expected):
        missing = sorted(set(expected) - set(cells))
        extra = sorted(set(cells) - set(expected))
        raise ValueError(f"STOP_CELL_MATRIX_DRIFT missing={missing} extra={extra}")
    for key, attempts in cells.items():
        attempts.sort(key=lambda r: r["attempt"])
        if [a["attempt"] for a in attempts] != list(range(1, len(attempts) + 1)):
            raise ValueError(f"STOP_ATTEMPT_SEQUENCE {key}")
        if any(is_valid(a) for a in attempts[:-1]):
            raise ValueError(f"STOP_RETRY_AFTER_VALID {key}")
    return cells


def truth(ref: dict) -> dict:
    return {"motion_phase": ref["phase_ref"],
            "events": [e for e in ref["event_types_ref"].split(";") if e]}


def _zero_stat() -> dict:
    return {"planned_cells": 0, "total_attempts": 0, "first_attempt_total": 0,
            "first_attempt_valid": 0, "retry_attempts": 0, "retry_recovered": 0,
            "final_valid": 0, "final_failed": 0, "prompt_tokens": 0, "completion_tokens": 0,
            "wall_seconds": 0.0, "error_types": {}}


def _finalize(stat: dict) -> None:
    stat["first_attempt_valid_rate"] = stat["first_attempt_valid"] / stat["first_attempt_total"]
    stat["final_valid_rate"] = stat["final_valid"] / stat["planned_cells"]
    stat["average_attempts_per_cell"] = stat["total_attempts"] / stat["planned_cells"]


def reliability(cells: dict, groups: list[str]) -> dict:
    overall = _zero_stat()
    per_group = {}
    for group in groups:
        stat = _zero_stat()
        for (_sid, grp), attempts in sorted(cells.items()):
            if grp != group:
                continue
            stat["planned_cells"] += 1
            first, final = attempts[0], attempts[-1]
            stat["first_attempt_total"] += 1
            stat["first_attempt_valid"] += is_valid(first)
            stat["retry_attempts"] += len(attempts) - 1
            stat["final_valid"] += is_valid(final)
            stat["final_failed"] += not is_valid(final)
            stat["retry_recovered"] += is_valid(final) and len(attempts) > 1
            for record in attempts:
                stat["total_attempts"] += 1
                stat["prompt_tokens"] += record["prompt_tokens"] or 0
                stat["completion_tokens"] += record["completion_tokens"] or 0
                stat["wall_seconds"] += record["wall_seconds"]
                if not is_valid(record):
                    name = record["qc"]["status"]
                    stat["error_types"][name] = stat["error_types"].get(name, 0) + 1
        _finalize(stat)
        per_group[group] = stat
        for key in ("planned_cells", "total_attempts", "first_attempt_total", "first_attempt_valid",
                    "retry_attempts", "retry_recovered", "final_valid", "final_failed",
                    "prompt_tokens", "completion_tokens"):
            overall[key] += stat[key]
        overall["wall_seconds"] += stat["wall_seconds"]
        for name, count in stat["error_types"].items():
            overall["error_types"][name] = overall["error_types"].get(name, 0) + count
    _finalize(overall)
    return {"overall": overall, "per_group": per_group}


def own_scores(cells: dict, human: dict, groups: list[str]) -> tuple[dict, dict]:
    scores, valid_ids = {}, {}
    for group in groups:
        valid = [sid for sid in human if (sid, group) in cells and is_valid(cells[sid, group][-1])]
        rows = [{"segment_id": sid, "human": truth(human[sid]),
                 "A": cells[sid, group][-1]["parsed"], "B": cells[sid, group][-1]["parsed"]}
                for sid in valid]
        scores[group] = score_pairs(rows)["A"] if rows else None
        valid_ids[group] = valid
    return scores, valid_ids


def common_valid_scores(cells: dict, human: dict, groups: list[str]) -> tuple[dict, list[str]]:
    valid_ids = {g: [sid for sid in human if is_valid(cells[sid, g][-1])] for g in groups}
    common = sorted(set.intersection(*(set(v) for v in valid_ids.values()))) if groups else []
    if not common:
        return None, []
    scores = {}
    for group in groups:
        rows = [{"segment_id": sid, "human": truth(human[sid]),
                 "A": cells[sid, group][-1]["parsed"], "B": cells[sid, group][-1]["parsed"]}
                for sid in common]
        scores[group] = score_pairs(rows)["A"]
    return scores, common


def end_to_end(cells: dict, human: dict, groups: list[str]) -> dict:
    """Over all planned segments: valid AND event-set exact match (and phase)."""
    out = {}
    for group in groups:
        valid = exact = phase = 0
        for sid in human:
            record = cells[sid, group][-1]
            if not is_valid(record):
                continue
            valid += 1
            pred = {e["event_type"] for e in record["parsed"]["events"]}
            exact += pred == set(truth(human[sid])["events"])
            phase += record["parsed"]["motion_phase"] == human[sid]["phase_ref"]
        out[group] = {"planned": len(human), "valid": valid,
                      "end_to_end_event_exact_match": exact, "end_to_end_phase_correct": phase,
                      "end_to_end_event_exact_match_rate": exact / len(human)}
    return out


def per_segment(cells: dict, human: dict, groups: list[str]) -> list[dict]:
    items = []
    for sid in human:
        item = {"segment_id": sid, "human": truth(human[sid])}
        for group in groups:
            record = cells[sid, group][-1]
            item[group] = {"valid": is_valid(record), "attempts": len(cells[sid, group]),
                           "parsed": record["parsed"] if is_valid(record) else None}
            if is_valid(record):
                pred = {e["event_type"] for e in record["parsed"]["events"]}
                item[group]["event_set"] = sorted(pred)
                item[group]["event_exact_match"] = pred == set(item["human"]["events"])
                item[group]["phase_correct"] = record["parsed"]["motion_phase"] == item["human"]["motion_phase"]
        items.append(item)
    return items


def contrasts(scores: dict, scope: str) -> list[dict]:
    order = [("T0", "G0"), ("G1", "G0"), ("T1", "T0"), ("T2", "T1"), ("T2", "T0")]

    def micro(group):
        return (scores.get(group) or {}).get("event_type_micro_f1")

    out = []
    for treatment, baseline in order:
        t, b = micro(treatment), micro(baseline)
        out.append({"contrast": f"{treatment} vs {baseline} ({scope})",
                    "metric": "event_type_micro_f1", "baseline": b, "treatment": t,
                    "delta": (t or 0) - (b or 0)})
    return out


def evaluate(cells: dict, human: dict, groups: list[str]) -> dict:
    own, own_ids = own_scores(cells, human, groups)
    common, common_ids = common_valid_scores(cells, human, groups)
    return {"reliability": reliability(cells, groups),
            "semantics_own_valid": own, "own_valid_segments": own_ids,
            "semantics_common_valid": common, "common_valid_segments": common_ids,
            "end_to_end": end_to_end(cells, human, groups),
            "contrasts_own": contrasts(own, "own-valid"),
            "contrasts_common": contrasts(common, "common-valid") if common else []}
