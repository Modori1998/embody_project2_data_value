"""Run G3D2 frozen five-arm pilot/full experiment in a new local directory."""
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
from project2_g3.g3d_paired import score_pairs, verified_frames, sha256
from project2_g3.g3d2_temporal import GROUPS, VERSION, TEMPORAL_INSTRUCTION, build_content, request_sha

FROZEN = ROOT / "0-doc/10-design-review/evidence/P2_G3_Taxonomy_v0_2_20261013"
PILOT = {"demo_2-S0003", "demo_169-S0002", "demo_172-S0004", "demo_180-S0001"}


def gpu_preflight():
    result = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,process_name",
        "--format=csv,noheader"], capture_output=True, text=True, check=True)
    busy = [line for line in result.stdout.splitlines() if any(word in line.lower() for word in ("python", "m11", "act"))]
    if busy:
        raise ValueError("STOP_COMPETING_GPU_PROCESS: " + ";".join(busy))


def append(path, row):
    with path.open("a", encoding="utf-8") as out:
        out.write(json.dumps(row, ensure_ascii=False) + "\n")


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def score_five(rows):
    scores = {}
    for group in GROUPS:
        pairs = [{"segment_id": r["segment_id"], "human": r["human"],
                  "A": r[group], "B": r[group]} for r in rows]
        scores[group] = score_pairs(pairs)["A"]
    return scores


def main():
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
        if pilot.get("calls") != 20 or not pilot.get("gate_pass"):
            raise ValueError("STOP_PILOT_GATE_FAILED")
    gpu_preflight()
    frozen = json.loads((FROZEN / "run_manifest.json").read_text(encoding="utf-8"))
    if P.template_sha256_v0_2_1() != frozen["versions"]["v0_2"]["prompt_template_sha256"] or digest(S.json_schema_v0_2()) != frozen["schema_sha256"]["v0_2"]:
        raise ValueError("STOP_FROZEN_PROMPT_SCHEMA_DRIFT")
    rows = [r for r in csv.DictReader((FROZEN / "sample_manifest.csv").open(encoding="utf-8-sig")) if r["cohort"] == "microset"]
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
    cache, prepared = {}, {}
    selected = [r for r in rows if args.stage == "full" or r["segment_id"] in PILOT]
    try:
        for row in selected:
            episode_id, segment_id = row["episode_id"], row["segment_id"]
            if episode_id not in cache:
                episode = load_formal_episode(adapter, episode_id)
                results, _ = run_window({episode_id: compute_formal_signals(episode, config)}, BOUNDARY_CONSOLIDATION_WINDOW)
                cache[episode_id] = episode, results[0]
            episode, result = cache[episode_id]
            segment = result.segments[int(segment_id.rsplit("S", 1)[1])-1]
            if (segment.segment_id, segment.start_frame, segment.end_frame) != (segment_id, int(row["start_frame"]), int(row["end_frame"])):
                raise ValueError("STOP_SEGMENT_IDENTITY")
            events = {e.boundary_id: e for e in result.final_events}
            left = events.get(segment.left_boundary_id)
            paths = verified_frames(row, args.rgb_cache)
            frames = [V.FrameEntry(idx, role, episode_id, segment_id, segment_id, True, pixel)
                      for idx, role, pixel in zip(map(int, row["target_keyframes"].split(";")),
                          ("START", "MIDDLE", "END"), row["frame_pixel_sha256s"].split(";"))]
            identity = V.TargetSegmentIdentity(episode_id, segment_id, segment.start_frame, segment.end_frame)
            options = {}
            for group in GROUPS:
                content, state = build_content(group=group, identity=identity, frames=frames, paths=paths,
                    task_text=frozen["task_text"], segment=segment, episode=episode,
                    gripper_state=result.gripper_state, left_boundary_type=left.candidate_type if left else None,
                    dt_s=config.nominal_dt_s, image_data_uri=probe.image_data_uri)
                options[group] = (content, state)
            # Fail before calls if matrix changes any frozen image bytes or old-state text.
            old_images = [x for x in options["G0"][0] if x["type"] == "image_url"]
            for group in GROUPS:
                if [x for x in options[group][0] if x["type"] == "image_url"] != old_images:
                    raise ValueError("STOP_RGB_REQUEST_DRIFT")
            if options["G1"][1] != options["T1"][1] or options["G0"][1] or options["T0"][1]:
                raise ValueError("STOP_STATE_MATRIX_DRIFT")
            prepared[segment_id] = paths, frames, identity, options
    finally:
        close = getattr(adapter, "close", None)
        if close:
            close()
    args.output.mkdir(parents=True)
    run = {"version": VERSION, "stage": args.stage, "frozen_manifest_sha256": sha256(FROZEN / "run_manifest.json"),
           "prompt_v021_sha256": P.template_sha256_v0_2_1(),
           "temporal_instruction_sha256": hashlib.sha256(TEMPORAL_INSTRUCTION.encode()).hexdigest(),
           "schema_sha256": frozen["schema_sha256"]["v0_2"], "model_revision": frozen["model_revision"],
           "model_gguf_sha256": sha256(Path(models[0]["id"])), "mmproj_sha256": sha256(args.mmproj),
           "model_service_id": models[0]["id"], "context_length": 4096,
           "sampling": frozen["sampling_parameters"], "groups": GROUPS,
           "sample_order": [r["segment_id"] for r in selected], "expected_calls": len(selected)*5,
           "rgb_sha256": {r["segment_id"]: r["frame_png_sha256s"] for r in selected}}
    (args.output / "run_manifest.json").write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
    records, failures = {}, []
    for i, row in enumerate(selected):
        segment_id = row["segment_id"]
        paths, frames, identity, options = prepared[segment_id]
        order = GROUPS[i%5:] + GROUPS[:i%5]
        for group in order:
            gpu_preflight()
            content, state = options[group]
            payload = {"model": models[0]["id"], "messages": [{"role": "user", "content": content}],
                       "max_tokens": 512, "temperature": 0.0, "seed": 1234, "stream": False,
                       "response_format": {"type": "json_object"}}
            meta = {"segment_id": segment_id, "group": group, "request_sha256": request_sha(payload),
                    "state_sha256": hashlib.sha256(state.encode()).hexdigest() if state else None,
                    "prompt_sha256": hashlib.sha256(content[0]["text"].encode()).hexdigest(),
                    "rgb_sha256": [sha256(path) for path in paths]}
            append(args.output / "inputs.jsonl", {**meta, "state_text": state, "request": payload})
            started = time.perf_counter()
            try:
                status, body, raw = probe._http_json(args.base_url + "/v1/chat/completions", payload, 120)
            except Exception as exc:
                status, body, raw = 0, {"_error": f"{type(exc).__name__}: {exc}"}, ""
            response = probe.parse_response(body) if status == 200 else {}
            qc = V.validate_model_output_v0_2(response.get("text"), manifest=frames, identity=identity,
                finish_reason=response.get("finish_reason"),
                processing_error=None if status == 200 else str(body.get("_error", status)))
            record = {**meta, "http_status": status, "raw_response": body, "raw_http": raw,
                      "parsed": qc.parsed, "qc": qc.to_dict(), "wall_seconds": time.perf_counter()-started,
                      "prompt_tokens": response.get("prompt_tokens"),
                      "completion_tokens": response.get("completion_tokens"), "gpu": probe.gpu_snapshot()}
            append(args.output / "responses.jsonl", record)
            records[segment_id, group] = record
            print(segment_id, group, qc.status, f'{record["wall_seconds"]:.2f}s', flush=True)
            if status != 200 or not (qc.parse_ok and qc.schema_ok and qc.frame_evidence_ok) or qc.truncated:
                failures.append(f"{segment_id}:{group}:{qc.status}")
                break
        if failures:
            break
    summary = {"stage": args.stage, "calls": len(records), "expected_calls": len(selected)*5,
               "failures": failures, "gate_pass": not failures and len(records)==len(selected)*5}
    if args.stage == "full" and summary["gate_pass"]:
        human = {r["segment_id"]: r for r in csv.DictReader(args.human_reference.open(encoding="utf-8-sig")) if r["cohort"] == "microset"}
        if set(human) != {r["segment_id"] for r in rows}:
            raise ValueError("STOP_HUMAN_COHORT_DRIFT")
        comparisons = []
        for row in selected:
            sid = row["segment_id"]
            ref = human[sid]
            for field in ("episode_id", "start_frame", "end_frame", "target_keyframes", "frame_png_sha256s"):
                if row[field] != ref[field]:
                    raise ValueError("STOP_HUMAN_IDENTITY_DRIFT")
            item = {"segment_id": sid, "human": {"motion_phase": ref["phase_ref"],
                "events": [x for x in ref["event_types_ref"].split(";") if x]}}
            item.update({group: records[sid, group]["parsed"] for group in GROUPS})
            comparisons.append(item)
            append(args.output / "per_segment.jsonl", item)
        scores = score_five(comparisons)
        (args.output / "scores.json").write_text(json.dumps(scores, ensure_ascii=False, indent=2), encoding="utf-8")
        summary["scores"] = scores
    (args.output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if summary["gate_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
