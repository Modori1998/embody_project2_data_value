import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from project2_g3.g3d2r_reliability import (  # noqa: E402
    common_valid_scores, end_to_end, load_cells, own_scores, reliability,
)


def record(segment, group, attempt, *, valid=True, phase="grasp", events=("grasp_attempt",)):
    qc = {"status": "VALID" if valid else "INVALID_MODEL_OUTPUT", "parse_ok": valid,
          "schema_ok": valid, "frame_evidence_ok": valid, "truncated": False}
    return {"segment_id": segment, "group": group, "attempt": attempt, "http_status": 200,
            "qc": qc, "prompt_tokens": 10, "completion_tokens": 5, "wall_seconds": 1.0,
            "parsed": {"motion_phase": phase, "events": [{"event_type": e} for e in events]}}


def ref(phase, events):
    return {"phase_ref": phase, "event_types_ref": ";".join(events)}


def test_reliability_is_per_group_and_counts_retry_recovery():
    cells = {
        ("s1", "G0"): [record("s1", "G0", 1)],
        ("s1", "T0"): [record("s1", "T0", 1, valid=False), record("s1", "T0", 2)],
        ("s2", "G0"): [record("s2", "G0", 1, valid=False)],
        ("s2", "T0"): [record("s2", "T0", 1)],
    }
    report = reliability(cells, ["G0", "T0"])
    g0, t0 = report["per_group"]["G0"], report["per_group"]["T0"]
    assert (g0["planned_cells"], g0["first_attempt_valid"], g0["retry_attempts"]) == (2, 1, 0)
    assert (g0["final_valid"], g0["final_failed"]) == (1, 1)
    assert (t0["planned_cells"], t0["first_attempt_valid"], t0["retry_recovered"]) == (2, 1, 1)
    assert (t0["final_valid"], t0["final_failed"], t0["total_attempts"]) == (2, 0, 3)
    assert t0["average_attempts_per_cell"] == 1.5
    assert g0["error_types"] == {"INVALID_MODEL_OUTPUT": 1}
    overall = report["overall"]
    assert (overall["planned_cells"], overall["total_attempts"]) == (4, 5)
    assert overall["prompt_tokens"] == 50


def test_load_cells_rejects_matrix_drift_and_retry_after_valid():
    with pytest.raises(ValueError, match="STOP_CELL_MATRIX_DRIFT"):
        load_cells([record("s1", "G0", 1)], [("s1", "G0"), ("s1", "T0")])
    with pytest.raises(ValueError, match="STOP_RETRY_AFTER_VALID"):
        load_cells([record("s1", "G0", 1), record("s1", "G0", 2)], [("s1", "G0")])


def test_own_common_and_end_to_end_handle_invalid_cells():
    cells = {
        ("s1", "G0"): [record("s1", "G0", 1, phase="grasp")],
        ("s1", "T0"): [record("s1", "T0", 1, valid=False), record("s1", "T0", 2, valid=False)],
        ("s2", "G0"): [record("s2", "G0", 1, phase="idle", events=())],
        ("s2", "T0"): [record("s2", "T0", 1, phase="idle", events=())],
    }
    human = {"s1": ref("transport", ["grasp_attempt"]), "s2": ref("idle", [])}
    own, valid_ids = own_scores(cells, human, ["G0", "T0"])
    assert valid_ids == {"G0": ["s1", "s2"], "T0": ["s2"]}
    assert (own["G0"]["phase_correct"], own["G0"]["exact_match"]) == (1, 2)
    assert own["T0"]["phase_correct"] == 1
    common, ids = common_valid_scores(cells, human, ["G0", "T0"])
    assert ids == ["s2"]  # only s2 is valid for both arms
    assert common["G0"]["exact_match"] == 1
    e2e = end_to_end(cells, human, ["G0", "T0"])
    assert e2e["T0"] == {"planned": 2, "valid": 1, "end_to_end_event_exact_match": 1,
                         "end_to_end_phase_correct": 1, "end_to_end_event_exact_match_rate": 0.5}
