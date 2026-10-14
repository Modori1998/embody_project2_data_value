"""Run the G3F minimal A/B paired experiment (A = v0.2.1, B = v0.2.2).

Both arms receive the identical frozen 3 RGB frames, model, mmproj, schema,
seed 1234, temperature 0, max_tokens 512 and the frozen
``FALLBACK_JSON_OBJECT_RETRY_V1`` retry protocol.  The ONLY difference is the
prompt template: A uses the frozen v0.2.1 prompt, B the Phase–Event candidate
v0.2.2.  No robot state, no extra frames, no Can Position.

New run directory only (never reuses a G3D2-R run or the old 44-cell prefix).
Pilot = 4 segments x 2 arms = 8 cells.  Full = 12 segments x 2 arms = 24 cells
and requires a passing pilot summary for the same prompt SHAs.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from project2_g3 import semantic_prompt as P, semantic_schema as S, semantic_validation as V
from project2_g3 import phase_event_qc as Q
from project2_g3.g3d_paired import score_pairs, verified_frames, sha256
from project2_g3.g3d2r_reliability import is_valid

FROZEN = ROOT / "0-doc/10-design-review/evidence/P2_G3_Taxonomy_v0_2_20261013"
PILOT = ("demo_2-S0003", "demo_4-S0003", "demo_169-S0002", "demo_180-S0001")
ARMS = ("A", "B")
ARM_PROMPT = {"A": "v0_2_1", "B": "v0_2_2"}
PROTOCOL = "fallback_json_object_retry_v1"
MAX_STRUCTURE_ATTEMPTS = 2
MAX_SERVICE_ATTEMPTS = 3

#: Pre-registered success criteria (frozen in G3F_Phase_Event_Plan.md before
#: any full-run inference).  Evaluated only after all 24 cells exist.
SUCCESS_CRITERIA = {
    "micro_f1_delta_min": 0.10,
    "object_motion_positives_min": 2,
    "object_motion_fp_increase_max": 1,
    "phase_correct_drop_max": 1,
    "event_exact_match_not_lower": True,
}


def gpu_preflight():
    result = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,process_name",
        "--format=csv,noheader"], capture_output=True, text=True, check=True)
    busy = [line for line in result.stdout.splitlines()
            if any(word in line.lower() for word in ("python", "m11", "act"))]
    if busy:
        raise ValueError("STOP_COMPETING_GPU_PROCESS: " + ";".join(busy))


def append(path: Path, row: dict):
    with path.open("a", encoding="utf-8") as out:
        out.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("pilot", "full"), required=True)
    parser.add_argument("--rgb-cache", type=Path, required=True)
    parser.add_argument("--human-reference", type=Path, required=True)
    parser.add_argument("--mmproj", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pilot-summary", type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("STOP_OUTPUT_EXISTS")
    if args.stage == "full":
        if not args.pilot_summary or not args.pilot_summary.is_file():
            raise ValueError("STOP_PILOT_REQUIRED")
        pilot = json.loads(args.pilot_summary.read_text(encoding="utf-8"))
        if pilot.get("calls") != 8 or not pilot.get("gate_pass") or pilot.get("protocol") != PROTOCOL:
            raise ValueError("STOP_PILOT_GATE_FAILED")
        for arm, version in ARM_PROMPT.items():
            if pilot.get("prompt_template_sha256", {}).get(arm) != P.prompt_version_info(version)["prompt_template_sha256"]:
                raise ValueError("STOP_PILOT_PROMPT_DRIFT")
    gpu_preflight()
    frozen = json.loads((FROZEN / "run_manifest.json").read_text(encoding="utf-8"))
    if P.template_sha256_v0_2_1() != frozen["versions"]["v0_2"]["prompt_template_sha256"] \
            or hashlib.sha256(json.dumps(S.json_schema_v0_2(), sort_keys=True, ensure_ascii=False).encode()).hexdigest() != frozen["schema_sha256"]["v0_2"]:
        raise ValueError("STOP_FROZEN_PROMPT_SCHEMA_DRIFT")
    rows = [r for r in csv.DictReader((FROZEN / "sample_manifest.csv").open(encoding="utf-8-sig"))
            if r["cohort"] == "microset"]
    if len(rows) != 12 or len({r["segment_id"] for r in rows}) != 12:
        raise ValueError("STOP_COHORT_DRIFT")
    for row in rows:
        verified_frames(row, args.rgb_cache)
    if not args.mmproj.is_file() or args.mmproj.name != "mmproj-Qwen3VL-4B-Instruct-F16.gguf":
        raise ValueError("STOP_MMPROJ_IDENTITY")
    with urllib.request.urlopen(args.base_url + "/v1/models", timeout=10) as reply:
        models = json.load(reply)["data"]
    if len(models) != 1 or not models[0]["id"].endswith("Qwen3VL-4B-Instruct-Q4_K_M.gguf"):
        raise ValueError("STOP_MODEL_IDENTITY")

    from project2_g1.config import load_g1_p1_config
    from project2_g1.source import build_can_mh_adapter, load_formal_episode
    from project2_g1.signals import compute_formal_signals
    from project2_g1.stage_b_calibration import run_window
    from project2_g1.stage_c_regression import BOUNDARY_CONSOLIDATION_WINDOW
    from project2_mvp.m2_materializer import assert_frozen_g1_identity
    spec = importlib.util.spec_from_file_location("g3probe", ROOT / "scripts/probe_g3_local_vlm.py")
    probe = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = probe
    spec.loader.exec_module(probe)
    assert_frozen_g1_identity()
    config = load_g1_p1_config()
    adapter = build_can_mh_adapter(config)

    selected = [r for r in rows if args.stage == "full" or r["segment_id"] in PILOT]
    prepared = {}
    try:
        for row in selected:
            episode_id, segment_id = row["episode_id"], row["segment_id"]
            episode = load_formal_episode(adapter, episode_id)
            results, _ = run_window({episode_id: compute_formal_signals(episode, config)}, BOUNDARY_CONSOLIDATION_WINDOW)
            segment = results[0].segments[int(segment_id.rsplit("S", 1)[1]) - 1]
            if (segment.segment_id, segment.start_frame, segment.end_frame) != (
                    segment_id, int(row["start_frame"]), int(row["end_frame"])):
                raise ValueError("STOP_SEGMENT_IDENTITY")
            paths = verified_frames(row, args.rgb_cache)
            frames = [V.FrameEntry(idx, role, episode_id, segment_id, segment_id, True, pixel)
                      for idx, role, pixel in zip(map(int, row["target_keyframes"].split(";")),
                          ("START", "MIDDLE", "END"), row["frame_pixel_sha256s"].split(";"))]
            prepared[segment_id] = paths, frames, episode_id
    finally:
        close = getattr(adapter, "close", None)
        if close:
            close()

    args.output.mkdir(parents=True)
    prompt_info = {arm: P.prompt_version_info(version) for arm, version in ARM_PROMPT.items()}
    run = {
        "version": "G3F_PHASE_EVENT_PAIRED_V0_2_2_CANDIDATE",
        "stage": args.stage,
        "frozen_manifest_sha256": sha256(FROZEN / "run_manifest.json"),
        "arms": {arm: {"prompt_version": prompt_info[arm]["prompt_version"],
                       "prompt_template_sha256": prompt_info[arm]["prompt_template_sha256"],
                       "robot_state": False} for arm in ARMS},
        "schema_sha256": frozen["schema_sha256"]["v0_2"],
        "phase_event_qc_version": Q.PHASE_EVENT_QC_VERSION,
        "model_revision": frozen["model_revision"],
        "model_gguf_sha256": sha256(Path(models[0]["id"])),
        "mmproj_sha256": sha256(args.mmproj),
        "model_service_id": models[0]["id"],
        "context_length": 4096,
        "sampling": frozen["sampling_parameters"],
        "protocol": PROTOCOL,
        "max_structure_attempts": MAX_STRUCTURE_ATTEMPTS,
        "max_service_attempts": MAX_SERVICE_ATTEMPTS,
        "sample_order": [r["segment_id"] for r in selected],
        "expected_calls": len(selected) * len(ARMS),
        "prompt_template_sha256": {arm: prompt_info[arm]["prompt_template_sha256"] for arm in ARMS},
        "rgb_sha256": {r["segment_id"]: r["frame_png_sha256s"] for r in selected},
        "success_criteria": SUCCESS_CRITERIA,
    }
    (args.output / "run_manifest.json").write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")

    records, failures = {}, []
    for i, row in enumerate(selected):
        segment_id = row["segment_id"]
        paths, frames, episode_id = prepared[segment_id]
        order = ARMS[i % 2:] + ARMS[:i % 2]
        for arm in order:
            gpu_preflight()
            prompt = P.render_prompt_for_version(
                ARM_PROMPT[arm], source_episode_id=episode_id, segment_id=segment_id,
                start_frame=int(row["start_frame"]), end_frame=int(row["end_frame"]),
                frames=frames, task_text=frozen["task_text"])
            content = [{"type": "text", "text": prompt}]
            content.extend({"type": "image_url", "image_url": {"url": probe.image_data_uri(p)}} for p in paths)
            payload = {"model": models[0]["id"], "messages": [{"role": "user", "content": content}],
                       "max_tokens": 512, "temperature": 0.0, "seed": 1234, "stream": False,
                       "response_format": {"type": "json_object"}}
            meta = {"segment_id": segment_id, "arm": arm, "prompt_version": ARM_PROMPT[arm],
                    "request_sha256": hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
                    "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                    "rgb_sha256": [sha256(p) for p in paths]}
            append(args.output / "inputs.jsonl", {**meta, "request": payload})
            service_errors = structure_errors = 0
            attempt = 0
            final = None
            while True:
                attempt += 1
                started = time.perf_counter()
                try:
                    status, body, raw = probe._http_json(args.base_url + "/v1/chat/completions", payload, 120)
                except Exception as exc:
                    status, body, raw = 0, {"_error": f"{type(exc).__name__}: {exc}"}, ""
                response = probe.parse_response(body) if status == 200 else {}
                qc = V.validate_model_output_v0_2(response.get("text"), manifest=frames,
                    identity=V.TargetSegmentIdentity(episode_id, segment_id,
                        int(row["start_frame"]), int(row["end_frame"])),
                    finish_reason=response.get("finish_reason"),
                    processing_error=None if status == 200 else str(body.get("_error", status)))
                review = Q.review_annotation(qc.parsed) if qc.parsed else {
                    "phase_event_qc_version": Q.PHASE_EVENT_QC_VERSION,
                    "review_status": "NOT_APPLICABLE", "findings": []}
                record = {**meta, "attempt": attempt, "http_status": status, "raw_response": body,
                          "raw_http": raw, "parsed": qc.parsed, "qc": qc.to_dict(),
                          "phase_event_qc": review, "wall_seconds": time.perf_counter() - started,
                          "prompt_tokens": response.get("prompt_tokens"),
                          "completion_tokens": response.get("completion_tokens"),
                          "gpu": probe.gpu_snapshot()}
                append(args.output / "responses.jsonl", record)
                print(segment_id, arm, attempt, qc.status, f'{record["wall_seconds"]:.2f}s', flush=True)
                if status == 200 and qc.parse_ok and qc.schema_ok and qc.frame_evidence_ok and not qc.truncated:
                    final = record
                    break
                if status in (0, 429, 500, 502, 503, 504):
                    service_errors += 1
                    if any(t in json.dumps(body, ensure_ascii=False).lower()
                           for t in ("out of memory", "cuda out of memory", "cuda error")):
                        raise RuntimeError("STOP_GPU_RESOURCE_ERROR")
                    if service_errors >= MAX_SERVICE_ATTEMPTS:
                        break
                elif status == 200:
                    structure_errors += 1
                    if structure_errors >= MAX_STRUCTURE_ATTEMPTS:
                        break
                else:
                    break
            records[segment_id, arm] = final
            if final is None:
                failures.append(f"{segment_id}:{arm}:FAILED_AFTER_{attempt}_ATTEMPTS")

    attempts = [json.loads(line) for line in (args.output / "responses.jsonl").open(encoding="utf-8")]
    first = [r for r in attempts if r["attempt"] == 1]
    summary = {
        "stage": args.stage, "protocol": PROTOCOL, "calls": len(records),
        "expected_calls": len(selected) * len(ARMS), "failures": failures,
        "gate_pass": not failures and len(records) == len(selected) * len(ARMS),
        "prompt_template_sha256": run["prompt_template_sha256"],
        "reliability": {
            "first_attempt_valid": sum(is_valid(r) for r in first),
            "first_attempt_total": len(first),
            "retry_attempts": len(attempts) - len(first),
            "retry_recovered": sum(is_valid(r) and r["attempt"] > 1 for r in records.values() if r),
            "final_valid": sum(is_valid(r) for r in records.values() if r),
            "final_failed": sum(r is None for r in records.values()),
            "total_attempts": len(attempts),
            "prompt_tokens": sum(r["prompt_tokens"] or 0 for r in attempts),
            "completion_tokens": sum(r["completion_tokens"] or 0 for r in attempts),
            "wall_seconds": sum(r["wall_seconds"] for r in attempts),
        },
    }

    if args.stage == "full" and summary["gate_pass"]:
        human = {r["segment_id"]: r for r in csv.DictReader(args.human_reference.open(encoding="utf-8-sig"))
                 if r["cohort"] == "microset"}
        if set(human) != {r["segment_id"] for r in rows}:
            raise ValueError("STOP_HUMAN_COHORT_DRIFT")
        comparisons = []
        for row in selected:
            sid = row["segment_id"]
            ref = human[sid]
            for field in ("episode_id", "start_frame", "end_frame", "target_keyframes", "frame_png_sha256s"):
                if row[field] != ref[field]:
                    raise ValueError("STOP_HUMAN_IDENTITY_DRIFT")
            item = {"segment_id": sid,
                    "human": {"motion_phase": ref["phase_ref"],
                              "events": [x for x in ref["event_types_ref"].split(";") if x]}}
            for arm in ARMS:
                item[arm] = records[sid, arm]["parsed"]
            comparisons.append(item)
            append(args.output / "per_segment.jsonl", item)
        scores = score_pairs(comparisons)
        (args.output / "scores.json").write_text(json.dumps(
            {"A": scores["A"], "B": scores["B"], "segments": scores["segments"]},
            ensure_ascii=False, indent=2), encoding="utf-8")
        summary["scores"] = {"A": scores["A"], "B": scores["B"]}
        summary["success_criteria_result"] = evaluate_criteria(comparisons, scores)

    (args.output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if summary["gate_pass"] else 2


def evaluate_criteria(comparisons: list[dict], scores: dict) -> dict:
    """Apply the frozen pre-registered thresholds to A (v0.2.1) vs B (v0.2.2)."""
    a, b = scores["A"], scores["B"]
    positives = ("demo_2-S0003", "demo_4-S0003", "demo_159-S0003")

    def om_recovered(arm: str) -> int:
        n = 0
        for item in comparisons:
            if item["segment_id"] in positives:
                pred = {e["event_type"] for e in item[arm]["events"]}
                if "object_motion" in pred and "object_motion" in item["human"]["events"]:
                    n += 1
        return n

    checks = {
        "micro_f1_delta": b["event_type_micro_f1"] - a["event_type_micro_f1"],
        "object_motion_positive_a": om_recovered("A"),
        "object_motion_positive_b": om_recovered("B"),
        "object_motion_fp_delta": b["by_type"]["object_motion"]["fp"] - a["by_type"]["object_motion"]["fp"],
        "phase_correct_delta": b["phase_correct"] - a["phase_correct"],
        "exact_match_delta": b["exact_match"] - a["exact_match"],
    }
    checks["micro_f1_pass"] = checks["micro_f1_delta"] >= SUCCESS_CRITERIA["micro_f1_delta_min"]
    checks["object_motion_positive_pass"] = checks["object_motion_positive_b"] >= SUCCESS_CRITERIA["object_motion_positives_min"]
    checks["object_motion_fp_pass"] = checks["object_motion_fp_delta"] <= SUCCESS_CRITERIA["object_motion_fp_increase_max"]
    checks["phase_correct_pass"] = checks["phase_correct_delta"] >= -SUCCESS_CRITERIA["phase_correct_drop_max"]
    checks["exact_match_pass"] = checks["exact_match_delta"] >= 0
    passed = all(checks[k] for k in ("micro_f1_pass", "object_motion_positive_pass",
                                     "object_motion_fp_pass", "phase_correct_pass", "exact_match_pass"))
    checks["decision"] = "CANDIDATE_GO" if passed else "NO_GAIN"
    return checks


if __name__ == "__main__":
    raise SystemExit(main())
