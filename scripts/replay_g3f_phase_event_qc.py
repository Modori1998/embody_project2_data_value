"""Offline replay of the G3F Phase–Event QC over a finished G3D2-R run.

Read-only: loads the stored per-cell responses and the frozen human reference,
applies ``phase_event_qc.review_annotation`` to every finally-valid prediction
and reports, per arm:

* how many cells each rule fired on;
* whether the three known ``object_motion`` misses are detected at all;
* how many *semantically correct* predictions were flagged (false alerts);
* what the rules structurally cannot see (blind spots).

Nothing here changes a stored result.  Outputs land under the gitignored
``outputs/`` tree.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from project2_g3.g3d2_temporal import GROUPS  # noqa: E402
from project2_g3.g3d2r_reliability import is_valid, truth  # noqa: E402
from project2_g3.phase_event_qc import PHASE_EVENT_QC_VERSION, review_annotation  # noqa: E402

#: Segments the pre-registration flags as the object_motion true positives.
OBJECT_MOTION_POSITIVES = ("demo_2-S0003", "demo_4-S0003", "demo_159-S0003")


def arm_field(record: dict) -> str:
    """G3D2-R stores ``group`` (G0/G1/T0/T1/T2); G3F stores ``arm`` (A/B)."""

    return record.get("arm") or record.get("group")


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def load_human(path: Path) -> dict:
    return {r["segment_id"]: r for r in csv.DictReader(path.open(encoding="utf-8-sig"))
            if r["cohort"] == "microset"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--human-reference", type=Path, required=True)
    args = parser.parse_args()

    human = load_human(args.human_reference)
    records: dict[tuple[str, str], dict] = {}
    for record in load_jsonl(args.run_dir / "responses.jsonl"):
        key = (record["segment_id"], arm_field(record))
        if is_valid(record) or key not in records:
            records[key] = record
    arms = [a for a in ("A", "B") if any(k[1] == a for k in records)] or list(GROUPS)
    # keep only finally-valid predictions; a failed cell has no prediction to review
    final = {k: r for k, r in records.items() if is_valid(r)}

    rows, per_group = [], {g: {} for g in arms}
    miss_detected = {sid: {} for sid in OBJECT_MOTION_POSITIVES}
    for (sid, arm), record in sorted(final.items()):
        payload = record["parsed"]
        review = review_annotation(payload)
        want = set(truth(human[sid])["events"])
        pred = {e["event_type"] for e in payload["events"]}
        exact = pred == want
        row = {"segment_id": sid, "arm": arm, "review": review,
               "phase": payload.get("motion_phase"),
               "predicted_events": sorted(pred), "human_events": sorted(want),
               "event_exact_match": exact, "attempts": record["attempt"],
               "note": payload.get("observation_note"),
               "object_relation": payload.get("object_relation")}
        rows.append(row)
        for finding in review["findings"]:
            per_group[arm][finding["check_id"]] = per_group[arm].get(finding["check_id"], 0) + 1
        if sid in miss_detected:
            fired = [f["check_id"] for f in review["findings"]]
            miss_detected[sid][arm] = {"phase": payload.get("motion_phase"),
                                         "events": sorted(pred), "qc_fired": fired}

    def is_false_alert(row: dict) -> bool:
        return row["event_exact_match"] and bool(row["review"]["findings"])

    false_alerts = [r for r in rows if is_false_alert(r)]
    report = {
        "phase_event_qc_version": PHASE_EVENT_QC_VERSION,
        "run_dir": args.run_dir.name,
        "valid_cells": len(rows),
        "per_arm_findings": per_group,
        "known_object_motion_positives": miss_detected,
        "object_motion_miss_detected_count": sum(
            1 for sid in OBJECT_MOTION_POSITIVES
            if any(v["qc_fired"] for v in miss_detected[sid].values())),
        "false_alert_cells": [
            {"segment_id": r["segment_id"], "arm": r["arm"],
             "check_ids": [f["check_id"] for f in r["review"]["findings"]]}
            for r in false_alerts],
        "false_alert_count": len(false_alerts),
    }
    (args.run_dir / "phase_event_qc_replay.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.run_dir / "phase_event_qc_replay.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in (
        "phase_event_qc_version", "valid_cells", "per_arm_findings",
        "object_motion_miss_detected_count", "false_alert_count")},
        ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
