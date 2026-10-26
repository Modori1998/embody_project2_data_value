"""Approved 6-cell engineering Pilot then 34 fresh cells, serial local 4B only."""
from __future__ import annotations
import argparse
import base64
import csv
import hashlib
import io
import json
import re
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
import psutil
from PIL import Image
from run_g3g_pilot import api, append, EXPECTED, PROMPT_B_SHA, SCHEMA_SHA

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from project2_g3 import semantic_prompt as P, semantic_schema as S, semantic_validation as V, phase_event_qc as Q
from project2_g3.g3d_paired import sha256

DEPLOY = Path("C:/Users/95611/embody/_local_vlm_deploy")
BACKEND = DEPLOY / "llama_cpp/bin/llama-server.exe"
FROZEN = ROOT / "0-doc/10-design-review/evidence/P2_G3_Taxonomy_v0_2_20261013"
HUMAN_SHA = "ecc716860eaf7617e00c1b23812fb1394a2719851346580a24e057a7e1ac938c"
HIDDEN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def gpu_preflight(owned_pid=None):
    result = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,process_name", "--format=csv,noheader"],
                            capture_output=True, text=True, check=True, creationflags=HIDDEN)
    rows = []
    for line in result.stdout.splitlines():
        pid = int(line.split(",", 1)[0])
        try:
            name = psutil.Process(pid).name().lower()
        except psutil.Error:
            name = "UNKNOWN"
        rows.append({"pid": pid, "name": name})
        if pid != owned_pid and name not in ("dwm.exe", "listary.exe", "omencommandcenterbackground.exe", "chatgpt.exe"):
            raise RuntimeError("STOP_COMPETING_OR_UNKNOWN_GPU_PROCESS:" + line)
    return rows


def visual_tokens(log):
    return list(map(int, re.findall(r"decoding image batch \d+/\d+, n_tokens_batch = (\d+)", log)))


def observe_visual_tokens(log, usage, image_count, previous):
    encoded = visual_tokens(log)
    if len(encoded) == image_count:
        return encoded, encoded, False
    cached = usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
    total = usage.get("prompt_tokens", 0)
    # A retry of the identical immutable payload may use the whole prompt KV.
    # Reuse only its own prior measured image counts, never an N*constant guess.
    if not encoded and len(previous) == image_count and total > 0 and cached >= total - 1:
        return previous, [], True
    return [], encoded, False


def sample_gpu(stop, samples, output):
    while not stop.is_set():
        start = time.time()
        result = subprocess.run(["nvidia-smi", "--query-gpu=index,name,memory.used,memory.total", "--format=csv,noheader,nounits"],
                                capture_output=True, text=True, creationflags=HIDDEN)
        fields = result.stdout.strip().split(",")
        item = {"unix_s": start, "query_seconds": time.time() - start, "raw": result.stdout.strip(),
                "used_vram_mib": int(fields[2]) if result.returncode == 0 and len(fields) == 4 else None}
        samples.append(item)
        append(output, item)
        stop.wait(max(0, 0.1 - (time.time() - start)))


def prepare_request(cell, manifest, row, task, model_id):
    anchors = list(map(int, row["target_keyframes"].split(";")))
    ids = cell["frame_ids"]
    if len(ids) != cell["requested_image_count"] or ids != sorted(set(ids)) or not set(anchors) <= set(ids):
        raise ValueError("STOP_INPUT_CARDINALITY")
    frames, images, hashes = [], [], []
    for index in ids:
        item = manifest["frames"][f'{cell["segment_id"]}:{index}']
        raw = Path(item["path"]).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        image = Image.open(io.BytesIO(raw)).convert("RGB")
        pixel = hashlib.sha256(image.tobytes()).hexdigest()
        if image.size != (128, 128) or digest != item["png_sha256"] or pixel != item["provenance"]["pixel_sha256"]:
            raise ValueError("STOP_RGB_IDENTITY")
        if not int(row["start_frame"]) <= index <= int(row["end_frame"]):
            raise ValueError("STOP_FRAME_RANGE")
        role = "START" if index == anchors[0] else "END" if index == anchors[-1] else "MIDDLE"
        frames.append(V.FrameEntry(index, role, row["episode_id"], row["segment_id"], row["segment_id"], True, pixel))
        images.append({"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(raw).decode()}})
        hashes.append(digest)
    prompt = P.render_prompt_for_version("v0_2_3", source_episode_id=row["episode_id"], segment_id=row["segment_id"],
                start_frame=int(row["start_frame"]), end_frame=int(row["end_frame"]), frames=frames, task_text=task)
    payload = {"model": model_id, "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}] + images}],
               "temperature": 0.0, "seed": 1234, "max_tokens": 512, "stream": False, "response_format": {"type": "json_object"}}
    return payload, frames, hashes


def run_stage(stage, cells, output, manifest, frozen, task, model_id, logpath, pid, samples):
    output.mkdir()
    terminal = []
    for cell in cells:
        gpu_state = gpu_preflight(pid)
        payload, frames, hashes = prepare_request(cell, manifest, frozen[cell["segment_id"]], task, model_id)
        meta = {"stage": stage, "segment_id": cell["segment_id"], "arm": len(frames), "frame_ids": cell["frame_ids"],
                "rgb_sha256": hashes, "gpu_processes": gpu_state,
                "request_sha256": hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()}
        append(output / "inputs.jsonl", {**meta, "request": payload})
        structure_errors = service_errors = attempt = 0
        previous_measurement = []
        while True:
            attempt += 1
            offset = logpath.stat().st_size
            started_wall, started = time.time(), time.perf_counter()
            status, body, raw = api("http://127.0.0.1:8097/v1/chat/completions", payload, timeout=120)
            elapsed, ended_wall = time.perf_counter() - started, time.time()
            with logpath.open("rb") as stream:
                stream.seek(offset)
                log = stream.read().decode("utf-8", errors="replace")
            choice = (body.get("choices") or [{}])[0]
            qc = V.validate_model_output_v0_2(choice.get("message", {}).get("content"), manifest=frames,
                identity=V.TargetSegmentIdentity(cell["episode_id"], cell["segment_id"], cell["start_frame"], cell["end_frame"]),
                finish_reason=choice.get("finish_reason"), processing_error=None if status == 200 else str(body))
            tokens, encoded_now, cache_reuse = observe_visual_tokens(log, body.get("usage", {}), len(frames), previous_measurement)
            if len(tokens) == len(frames):
                previous_measurement = tokens
            values = [s["used_vram_mib"] for s in samples if started_wall <= s["unix_s"] <= ended_wall and s["used_vram_mib"] is not None]
            valid = status == 200 and qc.parse_ok and qc.schema_ok and qc.frame_evidence_ok and not qc.truncated
            record = {**meta, "attempt": attempt, "http_status": status, "raw_http": raw, "raw_response": body,
                "parsed": qc.parsed, "qc": qc.to_dict(), "phase_event_qc": Q.review_annotation(qc.parsed) if qc.parsed else None,
                "valid": valid, "wall_seconds": elapsed, "started_unix_s": started_wall, "ended_unix_s": ended_wall,
                "usage": body.get("usage", {}), "timings": body.get("timings"), "log_offset": offset,
                "visual_embedding_tokens_per_image": tokens, "visual_embedding_tokens": sum(tokens) if len(tokens) == len(frames) else None,
                "newly_encoded_visual_tokens": sum(encoded_now), "visual_measurement_reused_from_identical_payload": cache_reuse,
                "visual_token_gate": len(tokens) == len(frames), "sampled_peak_vram_mib": max(values) if values else None,
                "resource_sample_count": len(values)}
            append(output / "responses.jsonl", record)
            (output / f'{cell["segment_id"]}_{len(frames)}_attempt{attempt}_backend.log').write_text(log, encoding="utf-8")
            print(stage, cell["segment_id"], len(frames), attempt, qc.status, f"{elapsed:.2f}s", "vision", tokens, flush=True)
            if status == 200 and (len(tokens) != len(frames) or not values):
                terminal.append(record)
                dump(output / "terminal.json", terminal)
                raise RuntimeError("STOP_VISUAL_TOKENS_OR_RESOURCE_OBSERVABILITY")
            if valid:
                break
            if any(s in str(body).lower() for s in ("out of memory", "cuda error")):
                raise RuntimeError("STOP_GPU_RESOURCE_ERROR")
            if status in (0, 429, 500, 502, 503, 504):
                service_errors += 1
                if service_errors >= 3:
                    break
            elif status == 200:
                structure_errors += 1
                if structure_errors >= 2:
                    break
            else:
                break
        terminal.append(record)
        dump(output / "terminal.json", terminal)
    gate = len(terminal) == len(cells) and all(r["valid"] and r["visual_token_gate"] for r in terminal)
    dump(output / "summary.json", {"stage": stage, "planned_cells": len(cells), "terminal_cells": len(terminal), "gate_pass": gate})
    return gate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--human-reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pilot-only", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("STOP_OUTPUT_EXISTS")
    gpu_preflight()
    with socket.socket() as check:
        check.bind(("127.0.0.1", 8097))
    model, model_sha, mmproj, mmproj_sha = EXPECTED["4B"]
    if sha256(model) != model_sha or sha256(mmproj) != mmproj_sha or sha256(args.human_reference) != HUMAN_SHA:
        raise ValueError("STOP_MODEL_OR_HUMAN_IDENTITY")
    if P.template_sha256_v0_2_3() != PROMPT_B_SHA or hashlib.sha256(json.dumps(S.json_schema_v0_2(), sort_keys=True, ensure_ascii=False).encode()).hexdigest() != SCHEMA_SHA:
        raise ValueError("STOP_PROMPT_SCHEMA_DRIFT")
    manifest = json.loads(args.input_manifest.read_text(encoding="utf-8"))
    approved_path = ROOT / "0-doc/10-design-review/evidence/Argus_Frame_Ablation_20261026/frame_schedule_approved.json"
    approved = json.loads(approved_path.read_text(encoding="utf-8"))
    if manifest["schedule_sha256"] != sha256(approved_path) or manifest["cells"] != approved["cells"]:
        raise ValueError("STOP_APPROVED_SCHEDULE_DRIFT")
    rows = list(csv.DictReader((FROZEN / "sample_manifest.csv").open(encoding="utf-8-sig")))
    frozen = {r["segment_id"]: r for r in rows if r["cohort"] == "microset"}
    refs = list(csv.DictReader(args.human_reference.open(encoding="utf-8-sig")))
    human = {r["segment_id"]: r for r in refs}
    if set(human) != set(frozen) or len(refs) != 12 or len(manifest["cells"]) != 34:
        raise ValueError("STOP_COHORT_DRIFT")
    task = json.loads((FROZEN / "run_manifest.json").read_text(encoding="utf-8"))["task_text"]
    cells = []
    for i, (sid, row) in enumerate(frozen.items()):
        for field in ("episode_id", "start_frame", "end_frame", "target_keyframes", "frame_png_sha256s"):
            if human[sid][field] != row[field]:
                raise ValueError("STOP_HUMAN_IDENTITY_DRIFT")
        current = [c for c in manifest["cells"] if c["segment_id"] == sid]
        expected = [3, 4] if int(row["segment_length"]) < 12 else [3, 6, 12]
        if [c["requested_image_count"] for c in current] != expected:
            raise ValueError("STOP_MATRIX_DRIFT")
        for cell in current:
            prepare_request(cell, manifest, row, task, str(model).replace("\\", "/"))
        rotate = i % len(current)
        cells.extend(current[rotate:] + current[:rotate])
    pilot = [c for sid in ("demo_2-S0003", "demo_169-S0002") for c in manifest["cells"] if c["segment_id"] == sid]
    version = subprocess.run([str(BACKEND), "--version"], capture_output=True, text=True, check=True, creationflags=HIDDEN)
    if "build 11577" not in version.stdout + version.stderr:
        raise ValueError("STOP_BACKEND_VERSION")
    args.output.mkdir(parents=True)
    argv = [str(BACKEND), "-m", str(model), "--mmproj", str(mmproj), "-ngl", "99", "-c", "4096", "-np", "1",
            "--host", "127.0.0.1", "--port", "8097", "--no-webui", "--jinja", "--temp", "0", "--seed", "1234", "-lv", "5"]
    identity = {"argv": argv, "backend_version": version.stdout + version.stderr, "backend_sha256": sha256(BACKEND),
                "backend_impl_sha256": sha256(BACKEND.with_name("llama-server-impl.dll")),
                "model_sha256": model_sha, "mmproj_sha256": mmproj_sha, "prompt_sha256": PROMPT_B_SHA, "schema_sha256": SCHEMA_SHA,
                "input_manifest_sha256": sha256(args.input_manifest), "human_reference_sha256": HUMAN_SHA,
                "runner_sha256": sha256(Path(__file__)), "planned_pilot": 6, "planned_full": 34, "warmup_calls": 0,
                "token_definition": "actual decoded image embedding tokens; image delimiters excluded",
                "telemetry_target_interval_s": 0.1, "started_unix_s": time.time()}
    dump(args.output / "run_identity.json", identity)
    logpath = args.output / "backend.log"
    stop, samples = threading.Event(), []
    thread = threading.Thread(target=sample_gpu, args=(stop, samples, args.output / "gpu_samples.jsonl"), daemon=True)
    thread.start()
    server = None
    start = time.perf_counter()
    try:
        with logpath.open("wb", buffering=0) as log:
            server = subprocess.Popen(argv, stdout=log, stderr=log, creationflags=HIDDEN)
            dump(args.output / "owned_backend.json", {"pid": server.pid, "argv": argv})
            for _ in range(120):
                if server.poll() is not None:
                    raise RuntimeError("STOP_BACKEND_EXIT")
                if api("http://127.0.0.1:8097/health", timeout=2)[0] == 200:
                    break
                time.sleep(0.5)
            else:
                raise RuntimeError("STOP_BACKEND_TIMEOUT")
            identity["model_load_seconds"] = time.perf_counter() - start
            dump(args.output / "run_identity.json", identity)
            status, models, _ = api("http://127.0.0.1:8097/v1/models", timeout=5)
            if status != 200 or len(models.get("data", [])) != 1 or not models["data"][0]["id"].endswith(model.name):
                raise RuntimeError("STOP_SERVICE_MODEL_IDENTITY")
            model_id = models["data"][0]["id"]
            if not run_stage("pilot", pilot, args.output / "pilot", manifest, frozen, task, model_id, logpath, server.pid, samples):
                raise RuntimeError("STOP_PILOT_GATE_FAILED")
            if not args.pilot_only:
                run_stage("full", cells, args.output / "full", manifest, frozen, task, model_id, logpath, server.pid, samples)
    except Exception as error:
        dump(args.output / "incident.json", {"error": repr(error), "unix_s": time.time()})
        raise
    finally:
        if server is not None and server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=15)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
        stop.set()
        thread.join(timeout=10)
        identity["total_session_seconds"] = time.perf_counter() - start
        dump(args.output / "run_identity.json", identity)


if __name__ == "__main__":
    main()
