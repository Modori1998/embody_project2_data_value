"""Phase 1C development-only human observability review."""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path

METRICS = ("object_visible", "motion_phase_decidable", "gripper_transition_visible", "object_following_decidable", "release_decidable")
LEVELS = ("UNSCORED", "SUFFICIENT", "PARTIAL", "INSUFFICIENT", "NOT_APPLICABLE")
LIMITS = ("UNSCORED", "NONE", "LOW_RESOLUTION", "OCCLUSION", "OUT_OF_FRAME", "TEMPORAL_GAP", "OTHER")
SEED = "P2_G3_PHASE1C_SELECTION_20261013_V1"


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def select(rows, count=24):
    """Cover every episode and structural stratum, then fill by seeded hash."""
    if len({r["segment_id"] for r in rows}) != len(rows):
        raise ValueError("duplicate segment_id")
    groups = {}
    for r in rows:
        groups.setdefault(r["episode_id"], []).append(r)
    if count < len(groups):
        raise ValueError("sample smaller than episode count")
    def rank(r):
        return hashlib.sha256(f'{SEED}|{r["segment_id"]}'.encode()).hexdigest()
    def strata(r):
        return ["SHORT" if int(r["end_frame"])-int(r["start_frame"])+1 <= 10 else "NONSHORT",
                "FIRST" if r["prev_status"] == "MISSING_NEIGHBOR" else "LAST" if r["next_status"] == "MISSING_NEIGHBOR" else "INTERIOR",
                "COMPLETE" if r["prev_status"] == r["next_status"] == "PRESENT" else "INCOMPLETE"]
    chosen = {}
    for episode in sorted(groups):
        r = min(groups[episode], key=rank)
        chosen[r["segment_id"]] = r
    wanted = {"SHORT", "NONSHORT", "FIRST", "LAST", "INTERIOR", "COMPLETE", "INCOMPLETE"}
    while len(chosen) < count:
        covered = {s for r in chosen.values() for s in strata(r)}
        pool = [r for r in rows if r["segment_id"] not in chosen]
        if not pool:
            break
        r = min(pool, key=lambda x: (-len(set(strata(x)) & (wanted-covered)), rank(x)))
        chosen[r["segment_id"]] = r
    return [dict(r, length=int(r["end_frame"])-int(r["start_frame"])+1,
                 selection_strata="|".join(strata(r)), selection_seed=SEED) for r in sorted(chosen.values(), key=lambda x: (x["episode_id"], int(x["start_frame"])))]


def validate_assets(rows, key_rows, provenance, root):
    keys = {r["segment_id"]: r for r in key_rows}
    if len(keys) != len(key_rows):
        raise ValueError("duplicate blinding key")
    by_segment = {}
    for p in provenance:
        by_segment.setdefault(p["target_segment_id"], []).append(p)
    for r in rows:
        sid, eid = r["segment_id"], r["episode_id"]
        k = keys[sid]
        if k["episode_id"] != eid or {k["panel1_is"], k["panel2_is"]} != {"A", "B"}:
            raise ValueError(f"bad blinding key: {sid}")
        for field in ("analyst_sheet", "blinded_panel1", "blinded_panel2"):
            p = Path(root) / r[field]
            if not p.is_file() or p.stat().st_size == 0 or not p.stem.startswith(sid + "_"):
                raise ValueError(f"missing/mismatched panel: {sid} {field}")
        ps = by_segment[sid]
        if len(ps) != len({(p["frame_index"], p["evidence_role"]) for p in ps}):
            raise ValueError(f"duplicate evidence frame: {sid}")
        if len(ps) != (r["prev_status"] == "PRESENT") + 2*(r["next_status"] == "PRESENT"):
            raise ValueError(f"unexpected frame count: {sid}")
        if any(p["episode_id"] != eid or p["source_episode_id"] != eid for p in ps):
            raise ValueError(f"cross episode: {sid}")
        lo, hi = int(r["start_frame"]), int(r["end_frame"])
        for p in ps:
            inside = lo <= int(p["frame_index"]) <= hi
            if (p["is_target_segment_frame"] == "True") != inside:
                raise ValueError(f"frame origin: {sid}")
            if inside != (p["origin_segment_id"] == sid):
                raise ValueError(f"segment origin: {sid}")


def blank(row, reviewer):
    d = {"episode_id": row["episode_id"], "segment_id": row["segment_id"], "reviewer_id": reviewer,
         "status": "UNSCORED", "skip_reason": "", "neighbor_context_helpful": "UNSCORED",
         "event_outside_target": "UNSCORED", "primary_limitation": "UNSCORED", "review_notes": "", "review_timestamp": ""}
    d.update({f"{arm}_{metric}": "UNSCORED" for arm in "AB" for metric in METRICS})
    return d


def validate_review(d, expected_segment, expected_reviewer):
    if d.get("segment_id") != expected_segment or d.get("reviewer_id") != expected_reviewer:
        raise ValueError("review identity mismatch")
    if d.get("status") not in ("UNSCORED", "COMPLETE", "SKIPPED"):
        raise ValueError("invalid status")
    if d.get("primary_limitation") not in LIMITS:
        raise ValueError("invalid limitation")
    if d.get("neighbor_context_helpful") not in ("UNSCORED", "YES", "NO", "UNCLEAR"):
        raise ValueError("invalid context value")
    if d.get("event_outside_target") not in ("UNSCORED", "YES", "NO", "UNCLEAR"):
        raise ValueError("invalid outside event")
    for arm in "AB":
        for metric in METRICS:
            if d.get(f"{arm}_{metric}") not in LEVELS:
                raise ValueError("invalid metric")
    if d["status"] == "COMPLETE" and any(d[f"{arm}_{m}"] == "UNSCORED" for arm in "AB" for m in METRICS):
        raise ValueError("incomplete review")
    if d["status"] == "SKIPPED" and not d.get("skip_reason", "").strip():
        raise ValueError("skip reason required")


def save_review(directory, d, selected):
    reviewer = d.get("reviewer_id", "")
    if not reviewer or not reviewer.replace("_", "").replace("-", "").isalnum():
        raise ValueError("invalid reviewer_id")
    sid = d.get("segment_id")
    if sid not in selected:
        raise ValueError("segment not selected")
    validate_review(d, sid, reviewer)
    target = Path(directory) / f"{reviewer}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    current = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
    current[sid] = d
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, target)


def summarize(rows, reviews):
    result = {"decision": "PENDING_HUMAN_REVIEW", "selected": len(rows), "complete": 0, "skipped": 0, "missing": 0}
    selected = {r["segment_id"]: r for r in rows}
    valid = []
    for d in reviews:
        sid = d.get("segment_id")
        if sid not in selected:
            raise ValueError("unknown segment in results")
        validate_review(d, sid, d["reviewer_id"])
        if d["status"] == "COMPLETE":
            valid.append(d)
        elif d["status"] == "SKIPPED":
            result["skipped"] += 1
    result["complete"] = len(valid)
    result["missing"] = len(rows) - len({d["segment_id"] for d in reviews})
    if not valid:
        return result
    result["metrics"] = {}
    result["event_outside_target"] = sum(d["event_outside_target"] == "YES" for d in valid)
    result["primary_limitation"] = {x: sum(d["primary_limitation"] == x for d in valid) for x in LIMITS if x != "UNSCORED"}
    scale = {"INSUFFICIENT": 0, "PARTIAL": 1, "SUFFICIENT": 2}
    result["groups"] = {}
    result["cases"] = {"improved": [], "degraded": [], "tied": []}
    for group in ("SHORT", "NONSHORT", "FIRST", "LAST", "INTERIOR", "COMPLETE", "INCOMPLETE"):
        subset = [d for d in valid if group in selected[d["segment_id"]]["selection_strata"].split("|")]
        result["groups"][group] = {"complete": len(subset), "paired_improved": 0, "paired_degraded": 0, "paired_tied": 0}
        for d in subset:
            a = [scale[d[f"A_{m}"]] for m in METRICS if d[f"A_{m}"] in scale and d[f"B_{m}"] in scale]
            b = [scale[d[f"B_{m}"]] for m in METRICS if d[f"A_{m}"] in scale and d[f"B_{m}"] in scale]
            if a:
                delta = sum(b)-sum(a)
                result["groups"][group]["paired_improved" if delta>0 else "paired_degraded" if delta<0 else "paired_tied"] += 1
    for d in valid:
        a = [scale[d[f"A_{m}"]] for m in METRICS if d[f"A_{m}"] in scale and d[f"B_{m}"] in scale]
        b = [scale[d[f"B_{m}"]] for m in METRICS if d[f"A_{m}"] in scale and d[f"B_{m}"] in scale]
        if a:
            delta = sum(b)-sum(a)
            result["cases"]["improved" if delta>0 else "degraded" if delta<0 else "tied"].append({"segment_id":d["segment_id"],"score_delta":delta})
    for metric in METRICS:
        counts = {arm: {level: sum(d[f"{arm}_{metric}"] == level for d in valid) for level in LEVELS if level != "UNSCORED"} for arm in "AB"}
        pairs = {"improved": 0, "degraded": 0, "tied": 0}
        for d in valid:
            a, b = d[f"A_{metric}"], d[f"B_{metric}"]
            if a in scale and b in scale:
                pairs["improved" if scale[b] > scale[a] else "degraded" if scale[b] < scale[a] else "tied"] += 1
        denominators = {arm: sum(counts[arm][level] for level in scale) for arm in "AB"}
        proportions = {arm: {level: (counts[arm][level]/denominators[arm] if denominators[arm] else None) for level in scale} for arm in "AB"}
        result["metrics"][metric] = {"counts": counts, "valid_counts": denominators, "proportions": proportions, "pairs": pairs}
    return result
