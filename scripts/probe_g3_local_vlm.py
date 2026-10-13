"""P2-G3 local VLM deployment probe (single-image / multi-image feasibility).

This script talks to a locally running OpenAI-compatible VLM server
(llama.cpp ``llama-server`` for the Qwen3-VL GGUF deployment check) and records
everything needed to decide whether a local GPU can serve real RGB frames.

It is deliberately self-contained: **standard library only**.  It does not
import the Project-2 runtime, does not modify any Project-1/2 environment and
never uploads robot imagery anywhere except to the explicitly supplied
``--base-url`` (default: local loopback).

Safety properties
-----------------
* Defaults to ``127.0.0.1``; nothing is sent to a remote host unless the caller
  passes a different ``--base-url`` on purpose.
* Records image SHA-256 and byte size, so the exact bytes sent are auditable.
* Records the model id actually served (``/v1/models``) and every sampling
  parameter, so a run cannot be silently reinterpreted later.
* Reports GPU VRAM from ``nvidia-smi`` before/after/peak; a missing
  ``nvidia-smi`` degrades gracefully instead of failing the run.
* Never claims semantic correctness.  It only records whether the request
  completed, whether the answer parsed as JSON, and whether the answer text
  contains an obvious evidence-limit disclaimer.

Usage
-----
    python scripts/probe_g3_local_vlm.py \
        --base-url http://127.0.0.1:8080 \
        --images frame_start.png frame_mid.png frame_end.png \
        --prompt "..." \
        --label three_image \
        --json-out outputs/.../three_image.json \
        --csv-out outputs/.../resource_latency.csv

    python scripts/probe_g3_local_vlm.py --list-models

Exit codes: 0 on a completed request, 2 on transport/HTTP failure,
3 on OOM detected, 4 on connection refused / server not reachable.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import mimetypes
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PROBE_VERSION = "P2_G3_LOCAL_VLM_PROBE_V1"
DEFAULT_BASE_URL = "http://127.0.0.1:8080"

# Phrases that indicate the model honoured an "say you cannot tell" instruction.
# Recording this is *not* a quality score; it only detects blatant
# evidence-limit violations.
_UNCERTAINTY_MARKERS = (
    "无法判断", "无法确定", "不能确定", "难以判断", "看不清", "无法确认",
    "cannot determine", "unable to determine", "cannot tell", "not visible",
    "insufficient", "unclear",
)
# Phrases that suggest the model asserted cross-segment events as target events.
_CROSS_SEGMENT_MARKERS = (
    "邻段", "相邻段", "前一段", "后一段", "previous segment", "next segment",
    "neighbour segment", "neighbor segment",
)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def image_data_uri(path: Path) -> str:
    mime, _ = mimetypes.guess_type(path.name)
    if mime is None:
        mime = "image/png"
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{payload}"


def _http_json(url: str, payload: dict | None, timeout: float) -> tuple[int, dict, str]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return response.status, json.loads(raw), raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"_raw": raw[:2000]}
        return exc.code, parsed, raw
    except urllib.error.URLError as exc:
        return 0, {"_error": f"{type(exc).__name__}: {exc.reason}"}, str(exc.reason)


def gpu_snapshot() -> dict | None:
    """Best-effort NVIDIA snapshot; returns None when unavailable."""
    try:
        out = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    line = (out.stdout or "").strip().splitlines()
    if out.returncode != 0 or not line:
        return None
    parts = [p.strip() for p in line[0].split(",")]
    if len(parts) < 5:
        return None
    try:
        return {
            "gpu_name": parts[0],
            "vram_total_mib": int(parts[1]),
            "vram_used_mib": int(parts[2]),
            "vram_free_mib": int(parts[3]),
            "gpu_util_pct": int(parts[4]),
        }
    except ValueError:
        return None


def gpu_processes() -> list[str]:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory",
             "--format=csv,noheader"],
            capture_output=True, text=True, timeout=20, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return [ln.strip() for ln in (out.stdout or "").splitlines() if ln.strip()]


# --------------------------------------------------------------------------- #
# request construction
# --------------------------------------------------------------------------- #
def build_payload(
    *,
    model: str,
    prompt: str,
    image_uris: list[str],
    max_tokens: int,
    temperature: float,
    seed: int | None,
    json_object: bool,
    system_prompt: str | None,
) -> dict:
    content: list[dict] = [{"type": "text", "text": prompt}]
    for uri in image_uris:
        content.append({"type": "image_url", "image_url": {"url": uri}})
    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": content})
    payload: dict = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }
    if seed is not None:
        payload["seed"] = seed
    if json_object:
        payload["response_format"] = {"type": "json_object"}
    return payload


def parse_response(body: dict) -> dict:
    """Normalise the answer across OpenAI-compatible server variants."""
    choices = body.get("choices") or []
    message = (choices[0].get("message") or {}) if choices else {}
    text = message.get("content")
    if isinstance(text, list):  # some servers emit content parts
        text = "".join(part.get("text", "") for part in text if isinstance(part, dict))
    timings = body.get("timings") or {}
    usage = body.get("usage") or {}
    return {
        "text": text,
        "finish_reason": choices[0].get("finish_reason") if choices else None,
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "predicted_ms": timings.get("predicted_ms"),
        "predicted_n": timings.get("predicted_n"),
        "prompt_ms": timings.get("prompt_ms"),
        "prompt_n": timings.get("prompt_n"),
    }


def try_json(text: str | None) -> tuple[bool, object]:
    if not text:
        return False, None
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = [ln for ln in stripped.splitlines() if not ln.strip().startswith("```")]
        stripped = "\n".join(lines).strip()
    try:
        return True, json.loads(stripped)
    except json.JSONDecodeError:
        start, end = stripped.find("{"), stripped.rfind("}")
        if 0 <= start < end:
            try:
                return True, json.loads(stripped[start:end + 1])
            except json.JSONDecodeError:
                return False, None
    return False, None


def evidence_flags(text: str | None) -> dict:
    lowered = (text or "").lower()
    return {
        "states_uncertainty": any(m.lower() in lowered for m in _UNCERTAINTY_MARKERS),
        "mentions_neighbour_segment": any(m.lower() in lowered for m in _CROSS_SEGMENT_MARKERS),
    }


_OOM_MARKERS = (
    "out of memory",
    "cuda_error_out_of_memory",
    "failed to allocate",
    "insufficient memory",
    "cannot allocate memory",
)


def is_oom(status: int, body: dict, raw: str) -> bool:
    """Only a server-side 5xx with an explicit allocation failure counts as OOM.

    A bare substring test on ``oom`` is deliberately avoided: it would match
    unrelated words such as "room" or "zoom" and silently mislabel a run.
    """
    if status < 500:
        return False
    blob = ((raw or "") + json.dumps(body or {})).lower()
    return any(marker in blob for marker in _OOM_MARKERS)


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def list_models(base_url: str, timeout: float) -> int:
    status, body, raw = _http_json(f"{base_url.rstrip('/')}/v1/models", None, timeout)
    print(json.dumps({"status": status, "body": body if status else raw}, indent=2,
                     ensure_ascii=False))
    return 0 if status == 200 else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default=os.environ.get("G3_VLM_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--model", default="local-vlm",
                        help="model id echoed in the request; server maps it internally")
    parser.add_argument("--images", nargs="*", default=[],
                        help="one or more image paths, supplied in temporal order")
    parser.add_argument("--prompt", default=None)
    parser.add_argument("--system-prompt", default=None)
    parser.add_argument("--label", default="run")
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--timeout", type=float, default=900.0)
    parser.add_argument("--json-object", action="store_true",
                        help="ask the server for a JSON object response")
    parser.add_argument("--list-models", action="store_true")
    parser.add_argument("--json-out")
    parser.add_argument("--csv-out")
    parser.add_argument("--notes", default="")
    args = parser.parse_args(argv)

    if args.list_models:
        return list_models(args.base_url, args.timeout)

    if not args.prompt:
        parser.error("--prompt is required unless --list-models is used")
    if not args.images:
        parser.error("at least one --images entry is required")

    image_paths = [Path(p) for p in args.images]
    for path in image_paths:
        if not path.exists():
            print(f"IMAGE_NOT_FOUND: {path}", file=sys.stderr)
            return 2

    # --- provenance of the exact bytes we are about to send ---
    image_meta = []
    for index, path in enumerate(image_paths):
        size = path.stat().st_size
        image_meta.append({
            "order": index,
            "name": path.name,
            "path": str(path),
            "bytes": size,
            "sha256": sha256_file(path),
        })

    before = gpu_snapshot()
    started = datetime.now(timezone.utc)
    t0 = time.perf_counter()

    payload = build_payload(
        model=args.model,
        prompt=args.prompt,
        image_uris=[image_data_uri(p) for p in image_paths],
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        seed=args.seed,
        json_object=args.json_object,
        system_prompt=args.system_prompt,
    )

    status, body, raw = _http_json(
        f"{args.base_url.rstrip('/')}/v1/chat/completions", payload, args.timeout
    )
    elapsed = time.perf_counter() - t0
    finished = datetime.now(timezone.utc)
    after = gpu_snapshot()

    if status == 0:
        print(f"SERVER_UNREACHABLE {args.base_url}: {body.get('_error')}", file=sys.stderr)
        return 4

    parsed = parse_response(body) if status == 200 else {}
    text = parsed.get("text")
    json_ok, json_value = try_json(text)
    flags = evidence_flags(text)
    oom = is_oom(status, body, raw)

    record = {
        "probe_version": PROBE_VERSION,
        "label": args.label,
        "started_utc": started.isoformat(),
        "finished_utc": finished.isoformat(),
        "base_url": args.base_url,
        "requested_model": args.model,
        "http_status": status,
        "image_count": len(image_paths),
        "images": image_meta,
        "total_image_bytes": sum(m["bytes"] for m in image_meta),
        "prompt": args.prompt,
        "system_prompt": args.system_prompt,
        "sampling": {
            "max_tokens": args.max_tokens,
            "temperature": args.temperature,
            "seed": args.seed,
            "json_object": args.json_object,
            "stream": False,
        },
        "wall_seconds": round(elapsed, 3),
        "prompt_tokens": parsed.get("prompt_tokens"),
        "completion_tokens": parsed.get("completion_tokens"),
        "predicted_ms": parsed.get("predicted_ms"),
        "predicted_n": parsed.get("predicted_n"),
        "prompt_ms": parsed.get("prompt_ms"),
        "prompt_n": parsed.get("prompt_n"),
        "finish_reason": parsed.get("finish_reason"),
        "response_text": text,
        "json_parsed_ok": json_ok,
        "json_value": json_value,
        "evidence_flags": flags,
        "completed_inference": status == 200 and bool(text),
        "oom_detected": bool(oom),
        "gpu_before": before,
        "gpu_after": after,
        "gpu_compute_processes_after": gpu_processes(),
        "notes": args.notes,
    }
    if status != 200:
        record["error_body"] = body

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.csv_out:
        out = Path(args.csv_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        exists = out.exists()
        with out.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=[
                "timestamp_utc", "label", "http_status", "image_count",
                "total_image_bytes", "image_hashes", "max_tokens", "temperature",
                "seed", "wall_seconds", "prompt_tokens", "completion_tokens",
                "predicted_ms", "vram_total_mib", "vram_used_before_mib",
                "vram_used_after_mib", "vram_free_after_mib", "oom_detected",
                "completed_inference", "json_parsed_ok", "states_uncertainty",
                "response_chars",
            ])
            if not exists:
                writer.writeheader()
            writer.writerow({
                "timestamp_utc": started.isoformat(),
                "label": args.label,
                "http_status": status,
                "image_count": len(image_paths),
                "total_image_bytes": record["total_image_bytes"],
                "image_hashes": ";".join(m["sha256"][:16] for m in image_meta),
                "max_tokens": args.max_tokens,
                "temperature": args.temperature,
                "seed": args.seed,
                "wall_seconds": record["wall_seconds"],
                "prompt_tokens": record["prompt_tokens"],
                "completion_tokens": record["completion_tokens"],
                "predicted_ms": record["predicted_ms"],
                "vram_total_mib": (before or {}).get("vram_total_mib"),
                "vram_used_before_mib": (before or {}).get("vram_used_mib"),
                "vram_used_after_mib": (after or {}).get("vram_used_mib"),
                "vram_free_after_mib": (after or {}).get("vram_free_mib"),
                "oom_detected": record["oom_detected"],
                "completed_inference": record["completed_inference"],
                "json_parsed_ok": json_ok,
                "states_uncertainty": flags["states_uncertainty"],
                "response_chars": len(text or ""),
            })

    # --- human-readable console summary ---
    print("=" * 72)
    print(f"label            : {args.label}")
    print(f"http_status      : {status}")
    print(f"images           : {len(image_paths)}")
    print(f"image bytes      : {record['total_image_bytes']}")
    print(f"wall seconds     : {record['wall_seconds']}")
    print(f"prompt tokens    : {record['prompt_tokens']}  completion: {record['completion_tokens']}")
    print(f"predicted ms     : {record['predicted_ms']}")
    print(f"json parsed      : {json_ok}")
    print(f"completed        : {record['completed_inference']}   oom: {record['oom_detected']}")
    if before or after:
        print(f"vram used        : {before and before['vram_used_mib']} -> "
              f"{after and after['vram_used_mib']} MiB "
              f"(total {(after or before or {}).get('vram_total_mib')} MiB)")
    print("-" * 72)
    print("response:")
    print(text if text else f"<no text>  error={record.get('error_body')}")
    print("=" * 72)

    if record["oom_detected"]:
        return 3
    return 0 if status == 200 else 2


if __name__ == "__main__":
    raise SystemExit(main())
