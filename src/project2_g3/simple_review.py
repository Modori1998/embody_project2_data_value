"""Small, development-only A then B human comprehension review."""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path

SEED = "P2_G3_PHASE1C_SIMPLE10_20261013_V1"
ANSWERS = ("UNSCORED", "CANNOT", "UNCERTAIN", "CAN")
LIMITS = ("UNSCORED", "MISSING_ACTION_CONTEXT", "LOW_RESOLUTION", "OCCLUDED_OR_OUT_OF_FRAME", "OTHER", "NONE")
RANK = {"CANNOT": 0, "UNCERTAIN": 1, "CAN": 2}


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def strata(row):
    length = int(row["end_frame"]) - int(row["start_frame"]) + 1
    edge = "FIRST" if row["prev_status"] == "MISSING_NEIGHBOR" else "LAST" if row["next_status"] == "MISSING_NEIGHBOR" else "INTERIOR"
    context = "COMPLETE" if row["prev_status"] == row["next_status"] == "PRESENT" else "INCOMPLETE"
    return ("SHORT" if length <= 10 else "NORMAL", edge, context)


def select(rows, count=10):
    """Greedily cover structural strata and episodes; hash breaks all ties."""
    if len({r["segment_id"] for r in rows}) != len(rows) or count > len(rows):
        raise ValueError("invalid source sample")
    if count < 3:
        raise ValueError("sample too small to cover strata")
    chosen = {}
    wanted = {"SHORT", "NORMAL", "FIRST", "LAST", "INTERIOR", "COMPLETE", "INCOMPLETE"}
    targets = {"SHORT": 4, "NORMAL": 6, "FIRST": 2, "LAST": 2,
               "INTERIOR": 6, "COMPLETE": 5, "INCOMPLETE": 5}
    def rank(r):
        return hashlib.sha256(f'{SEED}|{r["segment_id"]}'.encode()).hexdigest()
    while len(chosen) < count:
        counts = {s: sum(s in strata(r) for r in chosen.values()) for s in wanted}
        episodes = {r["episode_id"] for r in chosen.values()}
        pool = [r for r in rows if r["segment_id"] not in chosen]
        r = min(pool, key=lambda x: (-sum(counts[s] < targets[s] for s in strata(x)),
                                      -(x["episode_id"] not in episodes), rank(x)))
        chosen[r["segment_id"]] = r
    result = [dict(r, length=int(r["end_frame"])-int(r["start_frame"])+1,
                   selection_strata="|".join(strata(r)), selection_seed=SEED)
              for r in sorted(chosen.values(), key=lambda x: (x["episode_id"], int(x["start_frame"])))]
    if not wanted <= {s for r in result for s in r["selection_strata"].split("|")}:
        raise ValueError("selection failed to cover strata")
    return result


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
            if (p["is_target_segment_frame"] == "True") != inside or inside != (p["origin_segment_id"] == sid):
                raise ValueError(f"frame origin: {sid}")


def blank(row):
    return {"episode_id": row["episode_id"], "segment_id": row["segment_id"],
            "a_answer": "UNSCORED", "b_answer": "UNSCORED", "primary_limitation": "UNSCORED",
            "status": "UNSCORED", "review_notes": "", "review_timestamp": ""}


def a_panel_field(key):
    if {key["panel1_is"], key["panel2_is"]} != {"A", "B"}:
        raise ValueError("invalid A/B mapping")
    return "blinded_panel1" if key["panel1_is"] == "A" else "blinded_panel2"


def can_view_b(record):
    return record.get("a_answer", "UNSCORED") in RANK


def validate_review(d, expected):
    if d.get("segment_id") != expected["segment_id"] or d.get("episode_id") != expected["episode_id"]:
        raise ValueError("review identity mismatch")
    if d.get("a_answer") not in ANSWERS or d.get("b_answer") not in ANSWERS or d.get("primary_limitation") not in LIMITS:
        raise ValueError("invalid answer")
    if d.get("status") not in ("UNSCORED", "A_SCORED", "B_SCORED", "COMPLETE", "SKIPPED"):
        raise ValueError("invalid status")
    if d["b_answer"] != "UNSCORED" and d["a_answer"] == "UNSCORED":
        raise ValueError("B requires saved A")
    if d["status"] in ("A_SCORED", "B_SCORED", "COMPLETE") and d["a_answer"] == "UNSCORED":
        raise ValueError("A answer required")
    if d["status"] in ("B_SCORED", "COMPLETE") and d["b_answer"] == "UNSCORED":
        raise ValueError("B answer required")
    if d["status"] == "COMPLETE" and d["primary_limitation"] == "UNSCORED":
        raise ValueError("limitation required")
    if len(d.get("review_notes", "")) > 2000:
        raise ValueError("notes too long")


def save_review(directory, d, selected):
    sid = d.get("segment_id")
    if sid not in selected:
        raise ValueError("segment not selected")
    validate_review(d, selected[sid])
    target = Path(directory) / "simple_review.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    current = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
    current[sid] = d
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, target)


def summarize(rows, reviews):
    selected = {r["segment_id"]: r for r in rows}
    result = {"context_decision": "PENDING_HUMAN_REVIEW", "selected": len(rows),
              "complete": 0, "skipped": 0, "unfinished": 0}
    if len({d.get("segment_id") for d in reviews}) != len(reviews):
        raise ValueError("duplicate review segment")
    for d in reviews:
        if d.get("segment_id") not in selected:
            raise ValueError("unknown segment in results")
        validate_review(d, selected[d["segment_id"]])
    complete = [d for d in reviews if d["status"] == "COMPLETE"]
    result["complete"] = len(complete)
    result["skipped"] = sum(d["status"] == "SKIPPED" for d in reviews)
    result["unfinished"] = len(rows) - len(complete) - result["skipped"]
    if not complete:
        return result
    result["cannot_or_uncertain_to_can"] = sum(d["a_answer"] in ("CANNOT", "UNCERTAIN") and d["b_answer"] == "CAN" for d in complete)
    result["improved"] = sum(RANK[d["b_answer"]] > RANK[d["a_answer"]] for d in complete)
    result["unchanged"] = sum(RANK[d["b_answer"]] == RANK[d["a_answer"]] for d in complete)
    result["worse"] = sum(RANK[d["b_answer"]] < RANK[d["a_answer"]] for d in complete)
    result["primary_limitation"] = {level: sum(d["primary_limitation"] == level for d in complete) for level in LIMITS if level != "UNSCORED"}
    by_kind = {kind: [] for kind in ("improved", "unchanged", "worse")}
    for d in complete:
        delta = RANK[d["b_answer"]] - RANK[d["a_answer"]]
        by_kind["improved" if delta > 0 else "worse" if delta < 0 else "unchanged"].append(d)
    examples = [sorted(items, key=lambda d:d["segment_id"])[0] for items in by_kind.values() if items]
    result["typical_cases"] = [{"segment_id": d["segment_id"], "a_answer": d["a_answer"], "b_answer": d["b_answer"], "primary_limitation": d["primary_limitation"], "review_notes": d["review_notes"]} for d in examples[:3]]
    if result["complete"] == len(rows):
        if result["improved"] >= 7 and result["worse"] == 0:
            result["suggested_context_decision"] = "ADOPT_CONTEXT_AS_DEFAULT"
        elif result["improved"] > result["worse"]:
            result["suggested_context_decision"] = "KEEP_CONTEXT_OPTIONAL"
        elif result["worse"] > 0:
            result["suggested_context_decision"] = "REVISE_CONTEXT_POLICY"
        else:
            result["suggested_context_decision"] = "REJECT_CONTEXT"
    return result
