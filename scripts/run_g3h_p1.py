"""Run the preregistered G3H-P1 mechanism Pilot, one phase at a time.

Stages: stage1 (7 VLM calls), baseline (7 fresh VLM calls after a signed-off
fact_gate.json), map (CPU only). Raw image payloads remain under outputs/.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from project2_g3 import g3h_two_stage as H, semantic_prompt as P, semantic_schema as S, semantic_validation as V
from project2_g3.g3d_paired import sha256, verified_frames
from run_g3g_pilot import EXPECTED, FROZEN, RGB, PROMPT_B_SHA, SCHEMA_SHA, api, append, sample_resources

SEGMENTS = ("demo_2-S0003", "demo_4-S0003", "demo_159-S0003", "demo_169-S0002",
            "demo_180-S0001", "demo_232-S0002", "demo_172-S0004")
MODEL_SHA = EXPECTED["8B"][1]
MMPROJ_SHA = EXPECTED["8B"][3]


def canonical_sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def protocol_identity() -> dict:
    return {"fact_prompt_sha256": hashlib.sha256(H.FACT_PROMPT.encode()).hexdigest(),
            "fact_schema_sha256": canonical_sha(H.fact_schema()),
            "mapper_code_sha256": sha256(Path(H.__file__)),
            "runner_code_sha256": sha256(Path(__file__)),
            "baseline_prompt_sha256": PROMPT_B_SHA, "baseline_schema_sha256": SCHEMA_SHA}


def frozen_preflight() -> tuple[dict, dict]:
    frozen = json.loads((FROZEN / "run_manifest.json").read_text(encoding="utf-8"))
    if P.template_sha256_v0_2_3() != PROMPT_B_SHA or canonical_sha(S.json_schema_v0_2()) != SCHEMA_SHA:
        raise ValueError("STOP_FROZEN_BASELINE_DRIFT")
    available = tuple(frozen["cohorts"]["microset"]["segments"])
    if not all(sid in available for sid in SEGMENTS):
        raise ValueError("STOP_SEGMENT_COHORT_DRIFT")
    rows = {r["segment_id"]: r for r in csv.DictReader((FROZEN / "sample_manifest.csv").open(encoding="utf-8-sig"))}
    return frozen, rows


def prepared(frozen: dict, rows: dict) -> list[dict]:
    out = []
    for sid in SEGMENTS:
        row = rows[sid]
        paths = verified_frames(row, RGB)
        indices = [int(i) for i in row["target_keyframes"].split(";")]
        frames = [V.FrameEntry(index, role, row["episode_id"], sid, sid, True, pixel)
                  for index, role, pixel in zip(indices, ("START", "MIDDLE", "END"), row["frame_pixel_sha256s"].split(";"))]
        images = []
        for path in paths:
            with Image.open(path) as img:
                if img.size != (128, 128):
                    raise ValueError("STOP_IMAGE_DIMENSION_DRIFT")
            images.append("data:image/png;base64," + base64.b64encode(path.read_bytes()).decode())
        out.append({"sid": sid, "row": row, "indices": indices, "frames": frames,
                    "images": images, "png_sha256": row["frame_png_sha256s"].split(";")})
    return out


def manifest_for(backend: Path, gpu_layers: int, frozen: dict, prepared_rows: list[dict]) -> dict:
    version = subprocess.run([str(backend), "--version"], capture_output=True, text=True, check=True)
    return {"run_scope": "G3H_P1_SEVEN_SEGMENT_MECHANISM_PILOT", "git_head": subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip(),
            "backend_version": (version.stdout + version.stderr).strip(), "backend_path": str(backend),
            "model_sha256": MODEL_SHA, "mmproj_sha256": MMPROJ_SHA, "gpu_layers": gpu_layers,
            "ctx_size": 4096, "temperature": 0, "seed": 1234, "max_tokens": 512,
            "max_attempts_per_cell": 2, "segments": list(SEGMENTS), "protocol": protocol_identity(),
            "frozen_manifest_sha256": sha256(FROZEN / "run_manifest.json"),
            "frames": {x["sid"]: {"indices": x["indices"], "png_sha256": x["png_sha256"]}
                       for x in prepared_rows}}


def require_gate(run_dir: Path, identity: dict) -> dict:
    gate_path = run_dir / "fact_gate.json"
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    if gate.get("passed") is not True or gate.get("protocol") != identity or gate.get("segments") != list(SEGMENTS):
        raise ValueError("STOP_FACT_GATE_NOT_PASSED")
    if gate.get("stage1_responses_sha256") != sha256(run_dir / "stage1_responses.jsonl"):
        raise ValueError("STOP_FACT_GATE_RESPONSE_DRIFT")
    return gate


def run_vlm(args, frozen: dict, rows: list[dict], identity: dict) -> int:
    out = args.run_dir
    out.mkdir(parents=True, exist_ok=True)
    mode = args.mode
    if any((out / f"{mode}_{suffix}").exists() for suffix in ("inputs.jsonl", "responses.jsonl", "summary.json")):
        raise FileExistsError("STOP_PHASE_OUTPUT_EXISTS")
    model_path, model_sha, mmproj_path, mmproj_sha = EXPECTED["8B"]
    if sha256(model_path) != model_sha or sha256(mmproj_path) != mmproj_sha:
        raise ValueError("STOP_MODEL_SHA_MISMATCH")
    manifest = manifest_for(args.backend, args.gpu_layers, frozen, rows)
    manifest_path = out / "run_manifest.json"
    if manifest_path.exists():
        if json.loads(manifest_path.read_text(encoding="utf-8")) != manifest:
            raise ValueError("STOP_RUN_MANIFEST_DRIFT")
    else:
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    if mode == "baseline":
        require_gate(out, identity)
        if not (out / "stage1_summary.json").is_file():
            raise ValueError("STOP_STAGE1_MISSING")
    status, models, _ = api(args.base_url + "/v1/models", timeout=10)
    if status != 200 or len(models.get("data", [])) != 1 or not models["data"][0]["id"].endswith(model_path.name):
        raise ValueError("STOP_MODEL_SERVICE_IDENTITY")
    model_id = models["data"][0]["id"]
    results = []
    for x in rows:
        sid, row, indices, frames = x["sid"], x["row"], x["indices"], x["frames"]
        prompt = (H.render_fact_prompt(sid, indices) if mode == "stage1" else P.render_prompt_v0_2_3(
            source_episode_id=row["episode_id"], segment_id=sid, start_frame=int(row["start_frame"]),
            end_frame=int(row["end_frame"]), frames=frames, task_text=frozen["task_text"]))
        content = [{"type": "text", "text": prompt}] + [
            {"type": "image_url", "image_url": {"url": img}} for img in x["images"]]
        payload = {"model": model_id, "messages": [{"role": "user", "content": content}],
                   "max_tokens": 512, "temperature": 0.0, "seed": 1234, "stream": False,
                   "response_format": {"type": "json_object", "schema": H.fact_schema() if mode == "stage1" else S.json_schema_v0_2()}}
        append(out / f"{mode}_inputs.jsonl", {"segment_id": sid, "mode": mode, "indices": indices,
               "png_sha256": x["png_sha256"], "content_sha256": canonical_sha(content), "request": payload})
        valid = False
        for attempt in (1, 2):
            stop = threading.Event()
            samples = []
            thread = threading.Thread(target=sample_resources, args=(stop, samples), daemon=True)
            thread.start()
            start = time.perf_counter()
            status, body, raw = api(args.base_url + "/v1/chat/completions", payload, timeout=300)
            wall = time.perf_counter() - start
            stop.set(); thread.join(timeout=5)
            choice = (body.get("choices") or [{}])[0] if isinstance(body, dict) else {}
            answer = (choice.get("message") or {}).get("content")
            finish = choice.get("finish_reason")
            parsed = None
            if mode == "stage1":
                try:
                    parsed = H.parse_fact_json(answer) if isinstance(answer, str) else None
                    findings = H.validate_facts(parsed, sid, indices) if parsed else ["FACT_PARSE_ERROR"]
                except (ValueError, TypeError, KeyError) as exc:
                    findings = [f"FACT_PARSE_ERROR:{exc}"]
                qc = {"findings": findings, "parse_ok": parsed is not None,
                      "schema_ok": not findings, "frame_evidence_ok": not findings}
                valid = status == 200 and finish == "stop" and not findings
            else:
                result = V.validate_model_output_v0_2(answer, manifest=frames,
                    identity=V.TargetSegmentIdentity(row["episode_id"], sid, int(row["start_frame"]),
                                                     int(row["end_frame"])), finish_reason=finish,
                    processing_error=None if status == 200 else str(body.get("_error", status)))
                parsed, qc = result.parsed, result.to_dict()
                valid = status == 200 and finish == "stop" and result.parse_ok and result.schema_ok \
                    and result.frame_evidence_ok and not result.truncated
            record = {"mode": mode, "segment_id": sid, "attempt": attempt, "model_id": model_id,
                      "http_status": status, "raw_http": raw, "raw_response": body, "parsed": parsed,
                      "qc": qc, "finish_reason": finish, "valid": bool(valid), "usage": body.get("usage"),
                      "wall_seconds": wall,
                      "peak_used_vram_mib": max((s["used_vram_mib"] for s in samples if s["used_vram_mib"] is not None), default=None),
                      "min_free_ram_mib": min((s["free_ram_mib"] for s in samples), default=None),
                      "resource_samples": samples}
            append(out / f"{mode}_responses.jsonl", record)
            print(mode, sid, attempt, "VALID" if valid else "INVALID", f"{wall:.2f}s", flush=True)
            if record["min_free_ram_mib"] is not None and record["min_free_ram_mib"] < 1536:
                raise RuntimeError("STOP_SYSTEM_RAM_PRESSURE")
            if status != 200 and any(word in raw.lower() for word in ("out of memory", "cuda error")):
                raise RuntimeError("STOP_GPU_RESOURCE_ERROR")
            if valid:
                break
        results.append({"segment_id": sid, "attempts": attempt, "valid": bool(valid)})
        if not valid:
            break
    (out / f"{mode}_summary.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if len(results) == 7 and all(r["valid"] for r in results) else 2


def run_map(args, rows: list[dict], identity: dict) -> int:
    out = args.run_dir
    require_gate(out, identity)
    if (out / "mapped_results.jsonl").exists():
        raise FileExistsError("STOP_MAPPED_OUTPUT_EXISTS")
    baseline = json.loads((out / "baseline_summary.json").read_text(encoding="utf-8"))
    if len(baseline) != 7 or not all(x["valid"] for x in baseline):
        raise ValueError("STOP_BASELINE_INCOMPLETE")
    stage1 = {}
    for r in (json.loads(line) for line in (out / "stage1_responses.jsonl").open(encoding="utf-8")):
        if r["valid"]:
            stage1[r["segment_id"]] = r
    if set(stage1) != set(SEGMENTS):
        raise ValueError("STOP_STAGE1_INCOMPLETE")
    complete = []
    for x in rows:
        sid, row, frames, indices = x["sid"], x["row"], x["frames"], x["indices"]
        facts = stage1[sid]["parsed"]
        try:
            mapped = H.map_facts(facts, sid, indices)
            qc = V.validate_model_output_v0_2(json.dumps(mapped, ensure_ascii=False), manifest=frames,
                identity=V.TargetSegmentIdentity(row["episode_id"], sid, int(row["start_frame"]),
                                                 int(row["end_frame"])), finish_reason="stop")
            valid = qc.parse_ok and qc.schema_ok and qc.frame_evidence_ok and not qc.truncated
            finding = None if valid else qc.to_dict()
        except Exception as exc:
            mapped, valid, finding = None, False, f"{type(exc).__name__}: {exc}"
        append(out / "mapped_results.jsonl", {"segment_id": sid, "stage1_attempt": stage1[sid]["attempt"],
               "stage1_fact_sha256": canonical_sha(facts), "mapped": mapped, "valid": bool(valid),
               "finding": finding, "qc": qc.to_dict() if mapped is not None else None})
        complete.append(bool(valid))
        print("map", sid, "VALID" if valid else "INVALID", flush=True)
    return 0 if all(complete) else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("stage1", "baseline", "map"), required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--backend", type=Path)
    parser.add_argument("--gpu-layers", type=int, default=32)
    parser.add_argument("--base-url", default="http://127.0.0.1:8093")
    args = parser.parse_args()
    if args.mode != "map" and args.backend is None:
        parser.error("--backend is required for VLM calls")
    frozen, catalog = frozen_preflight()
    rows = prepared(frozen, catalog)
    identity = protocol_identity()
    return run_map(args, rows, identity) if args.mode == "map" else run_vlm(args, frozen, rows, identity)


if __name__ == "__main__":
    raise SystemExit(main())
