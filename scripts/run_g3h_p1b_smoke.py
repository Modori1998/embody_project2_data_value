"""One-cell G3H-P1B Stage 1 smoke test; never resumes or expands to other cells."""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from project2_g3 import g3h_two_stage as H
from project2_g3.g3d_paired import sha256
from run_g3g_pilot import EXPECTED, api, sample_resources
from run_g3h_p1 import canonical_sha, frozen_preflight, prepared, protocol_identity, manifest_for

SEGMENT = "demo_2-S0003"
MAX_TOKENS = 1024
CONTEXT_SIZE = 4096
RAM_STOP_MIB = 1536


def make_payload(model_id: str, row: dict) -> dict:
    content = [{"type": "text", "text": H.render_fact_prompt(SEGMENT, row["indices"])}]
    content += [{"type": "image_url", "image_url": {"url": img}} for img in row["images"]]
    return {"model": model_id, "messages": [{"role": "user", "content": content}],
            "max_tokens": MAX_TOKENS, "temperature": 0.0, "seed": 1234,
            "stream": False, "response_format": {"type": "json_object", "schema": H.fact_schema()}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--backend", required=True, type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:8093")
    args = parser.parse_args()
    out = args.run_dir
    if out.exists():
        raise FileExistsError("STOP_NEW_RUN_ID_REQUIRED")
    frozen, catalog = frozen_preflight()
    row = next(x for x in prepared(frozen, catalog) if x["sid"] == SEGMENT)
    model_path, model_sha, mmproj_path, mmproj_sha = EXPECTED["8B"]
    if sha256(model_path) != model_sha or sha256(mmproj_path) != mmproj_sha:
        raise ValueError("STOP_MODEL_SHA_MISMATCH")
    status, models, _ = api(args.base_url + "/v1/models", timeout=10)
    if status != 200 or len(models.get("data", [])) != 1 or not models["data"][0]["id"].endswith(model_path.name):
        raise ValueError("STOP_MODEL_SERVICE_IDENTITY")
    model_id = models["data"][0]["id"]
    payload = make_payload(model_id, row)
    out.mkdir(parents=True)
    manifest = manifest_for(args.backend, 32, frozen, [row])
    manifest.update({"run_scope": "G3H_P1B_SINGLE_STAGE1_SMOKE", "max_tokens": MAX_TOKENS,
                     "max_attempts_per_cell": 1, "segments": [SEGMENT], "parent_protocol": protocol_identity(),
                     "request_content_sha256": canonical_sha(payload["messages"][0]["content"])})
    (out / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "request.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    stop = threading.Event()
    samples: list[dict] = []
    thread = threading.Thread(target=sample_resources, args=(stop, samples), daemon=True)
    thread.start()
    start = time.perf_counter()
    try:
        status, body, raw = api(args.base_url + "/v1/chat/completions", payload, timeout=300)
    finally:
        stop.set()
        thread.join(timeout=5)
    elapsed = time.perf_counter() - start
    (out / "raw_http.txt").write_text(raw, encoding="utf-8")
    (out / "response.json").write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    choice = (body.get("choices") or [{}])[0]
    answer = (choice.get("message") or {}).get("content")
    finish = choice.get("finish_reason")
    try:
        parsed = H.parse_fact_json(answer)
        findings = H.validate_facts(parsed, SEGMENT, row["indices"])
    except (ValueError, TypeError, KeyError) as exc:
        parsed, findings = None, [f"FACT_INVALID:{exc}"]
    if parsed is not None:
        (out / "facts.json").write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
    minimum_ram = min((s["free_ram_mib"] for s in samples), default=None)
    summary = {"http_status": status, "finish_reason": finish, "usage": body.get("usage"),
               "wall_seconds": elapsed, "peak_used_vram_mib": max((s["used_vram_mib"] for s in samples
                                                                        if s["used_vram_mib"] is not None), default=None),
               "min_free_ram_mib": minimum_ram, "findings": findings,
               "valid": status == 200 and finish == "stop" and not findings,
               "resource_stop": minimum_ram is not None and minimum_ram < RAM_STOP_MIB}
    (out / "resource_samples.json").write_text(json.dumps(samples, indent=2), encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 0 if summary["valid"] and not summary["resource_stop"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
