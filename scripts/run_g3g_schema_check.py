"""G3G-P1: two frozen Task B frames per model with schema-constrained decoding.

Run one already-started llama-server arm at a time. Raw requests remain in outputs/.
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
sys.path.insert(0, str(ROOT / "src"))
from project2_g3 import semantic_prompt as P, semantic_schema as S, semantic_validation as V
from project2_g3.g3d_paired import sha256, verified_frames
from run_g3g_pilot import EXPECTED, FROZEN, RGB, PROMPT_B_SHA, SCHEMA_SHA, api, append, sample_resources

SEGMENTS = ("demo_2-S0003", "demo_159-S0003")


def constrained_format(schema: dict) -> dict:
    return {"type": "json_object", "schema": schema}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=EXPECTED, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8093")
    parser.add_argument("--backend", type=Path, required=True)
    parser.add_argument("--gpu-layers", type=int, required=True)
    args = parser.parse_args()
    out = args.run_dir
    out.mkdir(parents=True, exist_ok=True)
    if any((out / f"{args.arm}_{suffix}").exists() for suffix in ("inputs.jsonl", "responses.jsonl", "manifest.json")):
        raise FileExistsError("STOP_ARM_OUTPUT_EXISTS")
    schema = S.json_schema_v0_2()
    if P.template_sha256_v0_2_3() != PROMPT_B_SHA:
        raise ValueError("STOP_PROMPT_DRIFT")
    if hashlib.sha256(json.dumps(schema, sort_keys=True, ensure_ascii=False).encode()).hexdigest() != SCHEMA_SHA:
        raise ValueError("STOP_SCHEMA_DRIFT")
    model_path, model_sha, mmproj_path, mmproj_sha = EXPECTED[args.arm]
    if sha256(model_path) != model_sha or sha256(mmproj_path) != mmproj_sha:
        raise ValueError("STOP_MODEL_SHA_MISMATCH")
    backend_version = subprocess.run([str(args.backend), "--version"], capture_output=True, text=True, check=True)
    status, models, _ = api(args.base_url + "/v1/models", timeout=10)
    if status != 200 or len(models.get("data", [])) != 1 or not models["data"][0]["id"].endswith(model_path.name):
        raise ValueError("STOP_MODEL_SERVICE_IDENTITY")
    model_id = models["data"][0]["id"]
    frozen = json.loads((FROZEN / "run_manifest.json").read_text(encoding="utf-8"))
    rows = {r["segment_id"]: r for r in csv.DictReader((FROZEN / "sample_manifest.csv").open(encoding="utf-8-sig"))}
    manifest = {"arm": args.arm, "backend_version": (backend_version.stdout + backend_version.stderr).strip(),
                "model_sha256": model_sha, "mmproj_sha256": mmproj_sha, "gpu_layers": args.gpu_layers,
                "ctx_size": 4096, "schema_sha256": SCHEMA_SHA, "prompt_template_sha256": PROMPT_B_SHA,
                "response_format": constrained_format(schema), "temperature": 0, "seed": 1234,
                "max_tokens": 512, "max_attempts": 2, "segments": SEGMENTS}
    (out / f"{args.arm}_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    old_inputs_path = ROOT / "outputs/g3g/pilot_20261014_r1" / f"{args.arm}_inputs.jsonl"
    old_inputs = {(r["segment_id"], r["task"]): r for r in
                  (json.loads(line) for line in old_inputs_path.open(encoding="utf-8"))}
    results = []
    for sid in SEGMENTS:
        row = rows[sid]
        paths = verified_frames(row, RGB)
        indices = [int(i) for i in row["target_keyframes"].split(";")]
        frames = [V.FrameEntry(index, role, row["episode_id"], sid, sid, True, pixel)
                  for index, role, pixel in zip(indices, ("START", "MIDDLE", "END"), row["frame_pixel_sha256s"].split(";"))]
        prompt = P.render_prompt_v0_2_3(source_episode_id=row["episode_id"], segment_id=sid,
                    start_frame=int(row["start_frame"]), end_frame=int(row["end_frame"]),
                    frames=frames, task_text=frozen["task_text"])
        content = [{"type": "text", "text": prompt}]
        for path in paths:
            with Image.open(path) as image:
                if image.size != (128, 128):
                    raise ValueError("STOP_IMAGE_DIMENSION_DRIFT")
            content.append({"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()}})
        content_sha = hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        if content_sha != old_inputs[(sid, "B")]["content_sha256"]:
            raise ValueError("STOP_CONTENT_DRIFT")
        payload = {"model": model_id, "messages": [{"role": "user", "content": content}],
                   "max_tokens": 512, "temperature": 0.0, "seed": 1234, "stream": False,
                   "response_format": constrained_format(schema)}
        append(out / f"{args.arm}_inputs.jsonl", {"segment_id": sid, "content_sha256": content_sha,
               "png_sha256": row["frame_png_sha256s"].split(";"), "frame_indices": indices, "request": payload})
        for attempt in (1, 2):
            stop = threading.Event()
            samples = []
            thread = threading.Thread(target=sample_resources, args=(stop, samples), daemon=True)
            thread.start()
            start = time.perf_counter()
            status, body, raw = api(args.base_url + "/v1/chat/completions", payload, timeout=300)
            elapsed = time.perf_counter() - start
            stop.set()
            thread.join(timeout=5)
            choice = (body.get("choices") or [{}])[0] if isinstance(body, dict) else {}
            answer = (choice.get("message") or {}).get("content")
            finish = choice.get("finish_reason")
            qc = V.validate_model_output_v0_2(answer, manifest=frames,
                   identity=V.TargetSegmentIdentity(row["episode_id"], sid, int(row["start_frame"]),
                                                     int(row["end_frame"])), finish_reason=finish,
                   processing_error=None if status == 200 else str(body.get("_error", status)))
            valid = status == 200 and finish == "stop" and qc.parse_ok and qc.schema_ok and qc.frame_evidence_ok and not qc.truncated
            record = {"arm": args.arm, "segment_id": sid, "attempt": attempt, "http_status": status,
                      "raw_http": raw, "raw_response": body, "parsed": qc.parsed, "qc": qc.to_dict(),
                      "finish_reason": finish, "valid": bool(valid), "wall_seconds": elapsed,
                      "usage": body.get("usage") if isinstance(body, dict) else None,
                      "peak_used_vram_mib": max((s["used_vram_mib"] for s in samples if s["used_vram_mib"] is not None), default=None),
                      "min_free_ram_mib": min((s["free_ram_mib"] for s in samples), default=None),
                      "resource_samples": samples}
            append(out / f"{args.arm}_responses.jsonl", record)
            print(args.arm, sid, attempt, "VALID" if valid else "INVALID", f"{elapsed:.2f}s", flush=True)
            if record["min_free_ram_mib"] is not None and record["min_free_ram_mib"] < 1024:
                raise RuntimeError("STOP_SYSTEM_RAM_PRESSURE")
            if status != 200 and any(word in raw.lower() for word in ("out of memory", "cuda error")):
                raise RuntimeError("STOP_GPU_RESOURCE_ERROR")
            if valid:
                break
        results.append({"segment_id": sid, "attempts": attempt, "valid": bool(valid)})
        if not valid:
            break
    (out / f"{args.arm}_summary.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    return 0 if len(results) == 2 and all(r["valid"] for r in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
