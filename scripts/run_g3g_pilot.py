"""Run one model arm of the frozen G3G 16-cell engineering Pilot.

Start exactly one llama-server separately, run --arm 4B, stop it, then repeat
with --arm 8B. Raw RGB-derived requests and responses stay in outputs/.
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
import urllib.error
import urllib.request
from pathlib import Path

import psutil
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from project2_g3 import phase_event_qc as Q, semantic_prompt as P, semantic_schema as S
from project2_g3 import semantic_validation as V
from project2_g3.g3d_paired import sha256, verified_frames

FROZEN = ROOT / "0-doc/10-design-review/evidence/P2_G3_Taxonomy_v0_2_20261013"
SEGMENTS = ("demo_2-S0003", "demo_159-S0003", "demo_169-S0002", "demo_180-S0001")
TASKS = ("A", "B")
EXPECTED = {
    "4B": (Path("C:/Users/95611/embody/_local_vlm_deploy/models/Qwen3VL-4B-Instruct-Q4_K_M.gguf"),
           "66358cb18bb6b3b1b6675aa412c7a88ef01d228f481184d13668e5201c730a0a",
           Path("C:/Users/95611/embody/_local_vlm_deploy/models/mmproj-Qwen3VL-4B-Instruct-F16.gguf"),
           "256f3a43bd4205ffef48d6b92715e1e70b5b0e9aef06522584967513a9985331"),
    "8B": (ROOT / "outputs/g3g/models/Qwen3VL-8B-Instruct-Q4_K_M.gguf",
           "67d1659bfe71b89d50b45a4ad1a9e5b997e5bb16ce5da66a6a6167abd569e9e2",
           ROOT / "outputs/g3g/models/mmproj-Qwen3VL-8B-Instruct-F16.gguf",
           "ca524100ebf825c9a870db1c580d03879e0da0ab2541697e2458e64891cf9d38"),
}
RGB = Path("C:/Users/95611/embody/_local_vlm_deploy/rgb_g3_v02/g3_taxonomy_v02_20261013")
PROMPT_B_SHA = "cb9fa472a27332bb39ba37d373edfd7c3b361217137972a0553f9171ba7373c1"
SCHEMA_SHA = "4cbec780693511c6e029a1fc005a7c523e5af7ea6a4ba127c7b9fc44253d0ad7"
SMOKE_A_SHA = "3755760ae0d47fd094c08ee1ea4f2145f352ad75ef41f97e2ebef47174daf9aa"


def append(path: Path, item: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, ensure_ascii=False) + "\n")
        handle.flush()


def api(url: str, payload: dict | None = None, timeout: int = 300):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode()
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with opener.open(request, timeout=timeout) as reply:
            raw = reply.read().decode("utf-8", errors="replace")
            return reply.status, json.loads(raw), raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw), raw
        except json.JSONDecodeError:
            return exc.code, {"_raw": raw}, raw
    except Exception as exc:
        return 0, {"_error": f"{type(exc).__name__}: {exc}"}, ""


def task_a_prompt(segment_id: str, indices: list[int]) -> str:
    design = (ROOT / "0-doc/10-design-review/G3G_Design.md").read_text(encoding="utf-8")
    line = next(x[2:] for x in design.splitlines()
                if x.startswith("> You are inspecting three clean RGB frames"))
    return line + f"\nsegment_id: {segment_id}\nframe_indices: {', '.join(map(str, indices))} (START, MIDDLE, END)"


def valid_a(value: object, segment_id: str, indices: list[int]) -> bool:
    if not isinstance(value, dict) or set(value) != {"segment_id", "can_visible", "can_position_change",
                                                   "can_moves_with_gripper", "gripper_open_close_change"}:
        return False
    if value["segment_id"] != segment_id:
        return False
    for key in ("can_visible", "can_position_change", "can_moves_with_gripper", "gripper_open_close_change"):
        item = value[key]
        if not isinstance(item, dict) or set(item) != {"answer", "evidence_frame_indices", "observation"}:
            return False
        if item["answer"] not in ("yes", "no", "uncertain") or not isinstance(item["observation"], str):
            return False
        cited = item["evidence_frame_indices"]
        if not isinstance(cited, list) or any(type(i) is not int or i not in indices for i in cited):
            return False
    return True


def sample_resources(stop: threading.Event, samples: list) -> None:
    while not stop.is_set():
        ram = psutil.virtual_memory()
        gpu = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total",
                              "--format=csv,noheader,nounits"], capture_output=True, text=True)
        vram = None
        if gpu.returncode == 0:
            try:
                vram = int(gpu.stdout.splitlines()[0].split(",")[0].strip())
            except (ValueError, IndexError):
                pass
        samples.append({"time": time.time(), "free_ram_mib": ram.available / (1 << 20),
                        "used_vram_mib": vram})
        stop.wait(0.5)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=EXPECTED, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8089")
    parser.add_argument("--backend", type=Path, required=True)
    parser.add_argument("--gpu-layers", type=int, required=True)
    parser.add_argument("--resume", action="store_true", help="Continue from recorded terminal cells without extra attempts")
    args = parser.parse_args()
    arm = args.arm
    out = args.run_dir
    out.mkdir(parents=True, exist_ok=True)
    if not args.resume and ((out / f"{arm}_inputs.jsonl").exists() or (out / f"{arm}_responses.jsonl").exists()):
        raise FileExistsError("STOP_ARM_OUTPUT_EXISTS")
    if args.resume and not (out / f"{arm}_responses.jsonl").is_file():
        raise FileNotFoundError("STOP_RESUME_RECORDS_MISSING")
    frozen = json.loads((FROZEN / "run_manifest.json").read_text(encoding="utf-8"))
    if P.template_sha256_v0_2_3() != PROMPT_B_SHA:
        raise ValueError("STOP_PROMPT_DRIFT")
    schema_hash = hashlib.sha256(json.dumps(S.json_schema_v0_2(), sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    if schema_hash != SCHEMA_SHA:
        raise ValueError("STOP_SCHEMA_DRIFT")
    model_path, model_sha, mmproj_path, mmproj_sha = EXPECTED[arm]
    if sha256(model_path) != model_sha or sha256(mmproj_path) != mmproj_sha:
        raise ValueError("STOP_MODEL_SHA_MISMATCH")
    version_result = subprocess.run([str(args.backend), "--version"], capture_output=True, text=True)
    backend_version = (version_result.stdout + version_result.stderr).strip()
    if not backend_version:
        raise ValueError("STOP_BACKEND_IDENTITY")
    status, models, _ = api(args.base_url + "/v1/models", timeout=10)
    if status != 200 or len(models.get("data", [])) != 1 or \
            not models["data"][0]["id"].endswith(model_path.name):
        raise ValueError("STOP_MODEL_SERVICE_IDENTITY")
    model_id = models["data"][0]["id"]
    rows = {r["segment_id"]: r for r in csv.DictReader((FROZEN / "sample_manifest.csv").open(encoding="utf-8-sig"))}
    prepared = []
    for sid in SEGMENTS:
        row = rows[sid]
        paths = verified_frames(row, RGB)
        indices = [int(i) for i in row["target_keyframes"].split(";")]
        frames = [V.FrameEntry(index, role, row["episode_id"], sid, sid, True, pixel)
                  for index, role, pixel in zip(indices, ("START", "MIDDLE", "END"), row["frame_pixel_sha256s"].split(";"))]
        images = []
        dims = []
        for path in paths:
            with Image.open(path) as image:
                dims.append(list(image.size))
            images.append("data:image/png;base64," + base64.b64encode(path.read_bytes()).decode())
        prepared.append((row, indices, frames, images, dims))
    plan = []
    for row, indices, frames, images, dims in prepared:
        sid = row["segment_id"]
        for task in TASKS:
            prompt = (task_a_prompt(sid, indices) if task == "A" else P.render_prompt_v0_2_3(
                source_episode_id=row["episode_id"], segment_id=sid,
                start_frame=int(row["start_frame"]), end_frame=int(row["end_frame"]),
                frames=frames, task_text=frozen["task_text"]))
            if task == "A" and sid == "demo_2-S0003" and hashlib.sha256(prompt.encode()).hexdigest() != SMOKE_A_SHA:
                raise ValueError("STOP_TASK_A_PROMPT_DRIFT")
            content = [{"type": "text", "text": prompt}]
            content.extend({"type": "image_url", "image_url": {"url": image}} for image in images)
            content_sha = hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            plan.append((row, indices, frames, task, content, content_sha, dims))
    if arm == "8B":
        other = [json.loads(line) for line in (out / "4B_inputs.jsonl").open(encoding="utf-8")]
        if [(r["segment_id"], r["task"], r["content_sha256"]) for r in other] != [
            (r["segment_id"], t, digest) for r, _, _, t, _, digest, _ in plan]:
            raise ValueError("STOP_PAIRED_CONTENT_MISMATCH")
    manifest = {"arm": arm, "git_head": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                                                          text=True, check=True).stdout.strip(),
                "backend_version": backend_version, "backend_path": str(args.backend),
                "gpu_layers": args.gpu_layers, "ctx_size": 4096,
                "model": str(model_path), "model_sha256": model_sha,
                "mmproj": str(mmproj_path), "mmproj_sha256": mmproj_sha,
                "service_id": model_id, "frozen_manifest_sha256": sha256(FROZEN / "run_manifest.json"),
                "task_a_prompt_source": "G3G_Design.md", "task_b_prompt_sha256": PROMPT_B_SHA,
                "schema_sha256": SCHEMA_SHA, "response_format": "json_object", "max_tokens": 512,
                "temperature": 0, "seed": 1234, "max_attempts_per_cell": 2,
                "order": [[r["segment_id"], t] for r, _, _, t, _, _, _ in plan],
                "frames": {r["segment_id"]: {"indices": idx, "png_sha256": r["frame_png_sha256s"].split(";"),
                                              "dimensions": dims} for r, idx, _, _, _, _, dims in plan}}
    manifest_path = out / f"{arm}_run_manifest.json"
    if args.resume:
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        if previous != manifest:
            changed = [key for key in manifest if previous.get(key) != manifest[key]]
            raise ValueError("STOP_RESUME_MANIFEST_DRIFT:" + ",".join(changed))
    else:
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    previous_inputs = {}
    previous_responses = {}
    if args.resume:
        previous_inputs = {(r["segment_id"], r["task"]): r for r in
                           (json.loads(line) for line in (out / f"{arm}_inputs.jsonl").open(encoding="utf-8"))}
        for item in (json.loads(line) for line in (out / f"{arm}_responses.jsonl").open(encoding="utf-8")):
            previous_responses.setdefault((item["segment_id"], item["task"]), []).append(item)
    finished = []
    for row, indices, frames, task, content, content_sha, dims in plan:
        sid = row["segment_id"]
        payload = {"model": model_id, "messages": [{"role": "user", "content": content}],
                   "max_tokens": 512, "temperature": 0.0, "seed": 1234, "stream": False,
                   "response_format": {"type": "json_object"}}
        input_record = {"segment_id": sid, "task": task,
            "content_sha256": content_sha, "prompt_sha256": hashlib.sha256(content[0]["text"].encode()).hexdigest(),
            "png_sha256": row["frame_png_sha256s"].split(";"), "frame_indices": indices,
            "request": payload}
        old_input = previous_inputs.get((sid, task))
        if old_input is not None:
            if old_input != input_record:
                raise ValueError("STOP_RESUME_INPUT_DRIFT")
        else:
            append(out / f"{arm}_inputs.jsonl", input_record)
        prior = previous_responses.get((sid, task), [])
        if any(r["valid"] for r in prior) or len(prior) >= 2:
            final_old = next((r for r in prior if r["valid"]), None)
            finished.append({"arm": arm, "task": task, "segment_id": sid,
                             "first_valid": bool(prior[0]["valid"]), "attempts": len(prior),
                             "final_valid": final_old is not None,
                             "final": final_old["parsed"] if final_old else None})
            if task == "B" and sum(r["task"] == "B" and not r["final_valid"] for r in finished) >= 2:
                raise RuntimeError("STOP_GENERAL_TASK_B_SCHEMA_FAILURE")
            continue
        final = None
        for attempt in range(len(prior) + 1, 3):
            stop = threading.Event()
            samples = []
            thread = threading.Thread(target=sample_resources, args=(stop, samples), daemon=True)
            thread.start()
            start = time.perf_counter()
            status, body, raw = api(args.base_url + "/v1/chat/completions", payload)
            wall = time.perf_counter() - start
            stop.set(); thread.join(timeout=5)
            choice = (body.get("choices") or [{}])[0] if isinstance(body, dict) else {}
            answer = (choice.get("message") or {}).get("content")
            if isinstance(answer, list):
                answer = "".join(x.get("text", "") for x in answer if isinstance(x, dict))
            finish = choice.get("finish_reason")
            parsed = None
            qc = None
            review = None
            if task == "A":
                try:
                    parsed = json.loads(answer) if isinstance(answer, str) else None
                except json.JSONDecodeError:
                    pass
                valid = status == 200 and finish == "stop" and valid_a(parsed, sid, indices)
                qc = {"parse_ok": isinstance(parsed, dict), "schema_ok": valid_a(parsed, sid, indices),
                      "frame_evidence_ok": valid_a(parsed, sid, indices), "truncated": finish == "length"}
            else:
                result = V.validate_model_output_v0_2(answer, manifest=frames,
                    identity=V.TargetSegmentIdentity(row["episode_id"], sid, int(row["start_frame"]),
                                                     int(row["end_frame"])), finish_reason=finish,
                    processing_error=None if status == 200 else str(body.get("_error", status)))
                parsed = result.parsed
                qc = result.to_dict()
                review = Q.review_annotation(parsed) if parsed else None
                valid = status == 200 and finish == "stop" and result.parse_ok and result.schema_ok \
                    and result.frame_evidence_ok and not result.truncated
            record = {"arm": arm, "task": task, "segment_id": sid, "attempt": attempt,
                      "content_sha256": content_sha, "http_status": status, "raw_http": raw,
                      "raw_response": body, "parsed": parsed, "qc": qc, "phase_event_qc": review,
                      "finish_reason": finish, "valid": bool(valid), "wall_seconds": wall,
                      "usage": body.get("usage") if isinstance(body, dict) else None,
                      "peak_used_vram_mib": max((x["used_vram_mib"] for x in samples if x["used_vram_mib"] is not None), default=None),
                      "min_free_ram_mib": min((x["free_ram_mib"] for x in samples), default=None),
                      "resource_samples": samples}
            append(out / f"{arm}_responses.jsonl", record)
            print(arm, sid, task, attempt, "VALID" if valid else "INVALID", f"{wall:.2f}s", flush=True)
            if record["min_free_ram_mib"] is not None and record["min_free_ram_mib"] < 1024:
                raise RuntimeError("STOP_SYSTEM_RAM_PRESSURE")
            if status != 200 and any(t in json.dumps(body, ensure_ascii=False).lower()
                                         for t in ("out of memory", "cuda out of memory", "cuda error")):
                raise RuntimeError("STOP_GPU_RESOURCE_ERROR")
            if valid:
                final = record
                break
        finished.append({"arm": arm, "task": task, "segment_id": sid,
                         "first_valid": attempt == 1 and final is not None,
                         "attempts": attempt, "final_valid": final is not None,
                         "final": final["parsed"] if final else None})
        (out / f"{arm}_summary.json").write_text(json.dumps(finished, ensure_ascii=False, indent=2), encoding="utf-8")
        if task == "B" and sum(r["task"] == "B" and not r["final_valid"] for r in finished) >= 2:
            raise RuntimeError("STOP_GENERAL_TASK_B_SCHEMA_FAILURE")
    (out / f"{arm}_summary.json").write_text(json.dumps(finished, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
