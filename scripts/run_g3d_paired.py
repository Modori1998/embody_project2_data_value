"""Frozen G3D paired model runner; human labels are read after inference."""
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
from project2_g3.g3d_paired import motion_block, score_pairs, verified_frames, sha256

FROZEN = ROOT / "0-doc/10-design-review/evidence/P2_G3_Taxonomy_v0_2_20261013"
SMALL = ("demo_2-S0003", "demo_169-S0002", "demo_172-S0004", "demo_180-S0001")


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def append(path, row):
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rgb-cache", type=Path, required=True)
    parser.add_argument("--human-reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stage", choices=("small", "full"), required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--small-summary", type=Path,
                        help="Required for full stage; must show 8/8 successful small calls")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("STOP_OUTPUT_EXISTS")
    if args.stage == "full":
        if not args.small_summary or not args.small_summary.is_file():
            raise ValueError("STOP_SMALL_GATE_REQUIRED")
        small = json.loads(args.small_summary.read_text(encoding="utf-8"))
        if small.get("stage") != "small" or small.get("calls") != 8 or not small.get("gate_pass"):
            raise ValueError("STOP_SMALL_GATE_FAILED")
    gpu_check = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,process_name",
                                "--format=csv,noheader"], capture_output=True, text=True,
                               check=True)
    competing = [line for line in gpu_check.stdout.splitlines()
                 if "python" in line.lower() or "act" in line.lower() or "m11" in line.lower()]
    if competing:
        raise ValueError("STOP_COMPETING_GPU_PROCESS: " + ";".join(competing))
    frozen = json.loads((FROZEN / "run_manifest.json").read_text(encoding="utf-8"))
    if frozen["versions"]["v0_2"]["prompt_template_sha256"] != P.template_sha256_v0_2_1() or frozen["schema_sha256"]["v0_2"] != digest(S.json_schema_v0_2()):
        raise ValueError("STOP_PROMPT_OR_SCHEMA_DRIFT")
    rows = [r for r in csv.DictReader((FROZEN / "sample_manifest.csv").open(encoding="utf-8-sig")) if r["cohort"] == "microset"]
    if len(rows) != 12 or len({r["segment_id"] for r in rows}) != 12:
        raise ValueError("STOP_COHORT_DRIFT")
    for row in rows:
        verified_frames(row, args.rgb_cache)
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
    try:
        for row in rows:
            episode_id, segment_id = row["episode_id"], row["segment_id"]
            if episode_id not in cache:
                episode = load_formal_episode(adapter, episode_id)
                results, _ = run_window({episode_id: compute_formal_signals(episode, config)}, BOUNDARY_CONSOLIDATION_WINDOW)
                cache[episode_id] = episode, results[0]
            episode, result = cache[episode_id]
            segment = result.segments[int(segment_id.rsplit("S", 1)[1]) - 1]
            if (segment.segment_id, segment.start_frame, segment.end_frame) != (segment_id, int(row["start_frame"]), int(row["end_frame"])):
                raise ValueError("STOP_SEGMENT_IDENTITY")
            events = {event.boundary_id: event for event in result.final_events}
            left = events.get(segment.left_boundary_id)
            paths = verified_frames(row, args.rgb_cache)
            frames = [V.FrameEntry(index, role, episode_id, segment_id, segment_id, True, pixel)
                      for index, role, pixel in zip(map(int, row["target_keyframes"].split(";")), ("START", "MIDDLE", "END"), row["frame_pixel_sha256s"].split(";"))]
            identity = V.TargetSegmentIdentity(episode_id, segment_id, segment.start_frame, segment.end_frame)
            base = P.render_prompt_v0_2_1(source_episode_id=episode_id, segment_id=segment_id,
                    start_frame=segment.start_frame, end_frame=segment.end_frame, frames=frames, task_text=frozen["task_text"])
            block = motion_block(segment, episode, gripper_state=result.gripper_state,
                                 left_boundary_type=left.candidate_type if left else None)
            prepared[segment_id] = paths, frames, identity, base, block
    finally:
        close = getattr(adapter, "close", None)
        if close:
            close()
    selected = [r for r in rows if args.stage == "full" or r["segment_id"] in SMALL]
    args.output.mkdir(parents=True)
    (args.output / "run_manifest.json").write_text(json.dumps({"stage": args.stage, "frozen": frozen,
        "model_service_id": models[0]["id"], "sample_order": [r["segment_id"] for r in selected],
        "expected_calls": 2 * len(selected), "model_gguf_sha256": sha256(Path(models[0]["id"])),
        "rgb_png_sha256": {r["segment_id"]: r["frame_png_sha256s"] for r in selected}},
        ensure_ascii=False, indent=2), encoding="utf-8")
    failures, parsed = [], {}
    for i, row in enumerate(selected):
        segment_id = row["segment_id"]
        paths, frames, identity, base, block = prepared[segment_id]
        for arm in (("A", "B") if i % 2 == 0 else ("B", "A")):
            prompt = base + (block if arm == "B" else "")
            payload = {"model": models[0]["id"], "messages": [{"role": "user", "content":
                [{"type": "text", "text": prompt}] + [{"type": "image_url", "image_url": {"url": probe.image_data_uri(p)}} for p in paths]}],
                "max_tokens": 512, "temperature": 0.0, "seed": 1234, "stream": False, "response_format": {"type": "json_object"}}
            meta = {"segment_id": segment_id, "arm": arm, "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                    "request_sha256": digest(payload), "rgb_sha256": [sha256(p) for p in paths]}
            append(args.output / "inputs.jsonl", {**meta, "prompt": prompt, "request": payload})
            started = time.perf_counter()
            try:
                status, body, raw = probe._http_json(args.base_url + "/v1/chat/completions", payload, 120)
            except Exception as exc:
                status, body, raw = 0, {"_error": f"{type(exc).__name__}: {exc}"}, ""
            elapsed = time.perf_counter() - started
            response = probe.parse_response(body) if status == 200 else {}
            qc = V.validate_model_output_v0_2(response.get("text"), manifest=frames, identity=identity,
                    finish_reason=response.get("finish_reason"), processing_error=None if status == 200 else str(body.get("_error", status)))
            record = {**meta, "http_status": status, "raw_response": body, "raw_http": raw,
                      "wall_seconds": elapsed, "prompt_tokens": response.get("prompt_tokens"),
                      "completion_tokens": response.get("completion_tokens"), "gpu": probe.gpu_snapshot(),
                      "qc": qc.to_dict(), "parsed": qc.parsed}
            append(args.output / "responses.jsonl", record)
            parsed[segment_id, arm] = record
            if status != 200 or not (qc.parse_ok and qc.schema_ok and qc.frame_evidence_ok) or qc.truncated:
                failures.append(f"{segment_id}:{arm}:{qc.status}")
            print(f"{segment_id} {arm} {qc.status} {elapsed:.1f}s", flush=True)
            if status == 0:
                break
        if failures and parsed[segment_id, arm]["http_status"] == 0:
            break
    summary = {"stage": args.stage, "calls": len(parsed), "failures": failures, "gate_pass": not failures}
    if args.stage == "full" and not failures:
        human = {r["segment_id"]: r for r in csv.DictReader(args.human_reference.open(encoding="utf-8-sig")) if r["cohort"] == "microset"}
        if set(human) != {r["segment_id"] for r in rows}:
            raise ValueError("STOP_HUMAN_COHORT_DRIFT")
        comparisons = []
        for row in selected:
            key, ref = row["segment_id"], human[row["segment_id"]]
            for field in ("episode_id", "start_frame", "end_frame", "target_keyframes", "frame_png_sha256s"):
                if row[field] != ref[field]:
                    raise ValueError("STOP_HUMAN_IDENTITY_DRIFT")
            comparisons.append({"segment_id": key, "human": {"motion_phase": ref["phase_ref"],
                "events": [x for x in ref["event_types_ref"].split(";") if x]},
                "A": parsed[key, "A"]["parsed"], "B": parsed[key, "B"]["parsed"]})
        scores = score_pairs(comparisons)
        (args.output / "paired_scores.json").write_text(json.dumps(scores, ensure_ascii=False, indent=2), encoding="utf-8")
        summary["scores"] = {arm: scores[arm] for arm in ("A", "B")}
    (args.output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
