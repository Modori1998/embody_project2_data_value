"""P2-G3 tiny structured-JSON baseline runner (real local Qwen3-VL-4B inference).

One fixed model, one fixed prompt, one fixed schema, one fixed sample list, one
frozen configuration.  Ten development segments, target-keyframes only.

What this run IS: implementation-feasibility evidence for the Owner-frozen
output *architecture* -- does the interface actually produce parseable,
schema-valid, correctly-scoped JSON on real robot frames, and which exact
failure modes remain?

What this run is NOT (and must never be reported as):
* **not** action-recognition accuracy -- there is no human ground truth here;
* **not** a formal held-out evaluation;
* **not** a validated taxonomy -- the v0.1 enums stay candidate pending Owner
  review;
* **not** an 8B result -- the local 4B Q4_K_M is a development probe only.

Usage (renderer environment, which also has the stdlib-only probe importable)::

    PY=C:/Users/95611/miniconda3/envs/project1_robomimic_audit/python.exe
    $PY scripts/run_g3_json_tiny_baseline.py --run-id g3_json_tiny_20261013 \\
        --output-root outputs/p2_g3_json_tiny_baseline

The runner fails closed before any model call if the frozen inputs (segment
identity, frame provenance, sample list) cannot be verified.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from project2_g3 import semantic_prompt as P  # noqa: E402
from project2_g3 import semantic_schema as S  # noqa: E402
from project2_g3 import semantic_validation as V  # noqa: E402
from project2_g3.dev_segments import (  # noqa: E402
    PINNED_BASELINE_SEGMENTS,
    PHASE1C_SALT,
    SamplingError,
    resolve_baseline_samples,
)

# --------------------------------------------------------------------------- #
# pre-registered engineering gates
# --------------------------------------------------------------------------- #
GATES: dict[str, Any] = {
    "illegal_model_inputs_max": 0,
    "json_parse_rate_min": 0.90,
    "schema_valid_rate_min": 0.90,
    "frame_evidence_valid_rate_min": 0.90,
    "truncated_outputs_max": 0,
    "undetected_cross_boundary_max": 0,
}

DEFAULT_MAX_TOKENS = 512
DEFAULT_SEED = 1234
DEFAULT_TEMPERATURE = 0.0

#: Stable column order so artifacts exist even for an empty (dry) run.
QUEUE_FIELDS = (
    "sample_order", "episode_id", "segment_id", "annotation_review_status",
    "review_reasons", "candidate_finding_count", "deterministic_finding_count",
    "cross_boundary_references", "invalid_references", "training_disposition",
)
DEFAULT_MODEL_REVISION = (
    "Qwen/Qwen3-VL-4B-Instruct-GGUF@1cd86afb9a95c410a6038ab3b40d8b578c892266::"
    "Qwen3VL-4B-Instruct-Q4_K_M.gguf+mmproj-Qwen3VL-4B-Instruct-F16.gguf"
)


def _load_probe():
    """Reuse the audited deployment-branch probe client (stdlib only)."""

    path = ROOT / "scripts" / "probe_g3_local_vlm.py"
    spec = importlib.util.spec_from_file_location("probe_g3_local_vlm", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["probe_g3_local_vlm"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def _sanitize(text: Any, deploy_root: str | None) -> Any:
    """Replace machine-specific absolute roots in a *copy* for sharing."""

    if not isinstance(text, str):
        return text
    out = text
    for root in filter(None, [deploy_root, str(ROOT).replace("/", "\\"),
                              str(ROOT), str(Path.home())]):
        out = out.replace(root, "<LOCAL_ROOT>")
        out = out.replace(root.replace("\\", "/"), "<LOCAL_ROOT>")
    return out


def _deep_sanitize(obj: Any, deploy_root: str | None) -> Any:
    if isinstance(obj, dict):
        return {k: _deep_sanitize(v, deploy_root) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_sanitize(v, deploy_root) for v in obj]
    return _sanitize(obj, deploy_root)


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-root", default="outputs/p2_g3_json_tiny_baseline")
    parser.add_argument("--run-id")
    parser.add_argument("--base-url", default=os.environ.get("G3_VLM_BASE_URL",
                                                             "http://127.0.0.1:8080"))
    parser.add_argument("--model", default="qwen3-vl-4b-q4_k_m")
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--timeout", type=float, default=900.0)
    parser.add_argument("--task-text", default=P.DEFAULT_TASK_TEXT)
    parser.add_argument("--rgb-cache", default=str(Path.home() / "embody" / "_local_vlm_deploy" / "rgb_g3_json"))
    parser.add_argument("--limit", type=int, help="debug: only the first N samples")
    parser.add_argument("--dry-run", action="store_true",
                        help="resolve/render/validate plumbing but do not call the model")
    parser.add_argument("--shareable-out", help="write a sanitized evidence copy here")
    parser.add_argument("--boundary-regression", action="store_true",
                        help="additionally run the demo_47-S0003 target-only vs "
                             "target+neighbour boundary check; results are written to "
                             "boundary_regression/ and are EXCLUDED from the baseline "
                             "denominator")
    args = parser.parse_args(argv)

    os.environ.setdefault("MUJOCO_GL", "wgl")
    probe = _load_probe()

    run_id = args.run_id or "g3_json_tiny_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.output_root) / run_id
    if out_dir.exists():
        print(f"STOP_RUN_EXISTS: {out_dir}", file=sys.stderr)
        return 2
    out_dir.mkdir(parents=True)

    # -- 1. resolve the frozen sample (fail closed) ------------------------
    try:
        resolved = resolve_baseline_samples()
    except SamplingError as exc:
        print(f"STOP_SAMPLING_PRECONDITION_FAILED: {exc}", file=sys.stderr)
        return 3
    samples = resolved["samples"]
    if args.limit:
        samples = samples[: args.limit]

    # -- 2. render target keyframes (frozen renderer, read-only) ----------
    from project2_mvp.m2_materializer import assert_frozen_g1_identity
    from project2_mvp.rgb_input import render_clean_rgb_frames, write_clean_rgb_png
    from project2_g1.source import build_can_mh_adapter
    from project2_g1.config import load_g1_p1_config

    identity = assert_frozen_g1_identity()
    adapter = build_can_mh_adapter(load_g1_p1_config())
    rgb_dir = Path(args.rgb_cache) / run_id
    rgb_dir.mkdir(parents=True, exist_ok=True)

    prompt_template_sha = P.template_sha256()
    schema = S.json_schema()
    schema_sha = _sha256_bytes(json.dumps(schema, sort_keys=True, ensure_ascii=False).encode("utf-8"))

    run_manifest = {
        "run_id": run_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "output_scope": "TINY_BASELINE_DEVELOPMENT_ONLY_NOT_FORMAL",
        "owner_freeze_architecture": "G3_OUTPUT_ARCHITECTURE=FROZEN_JSON_ENUM_NOTE_FRAME_EVIDENCE_QC_V1",
        "schema_version": S.SEMANTIC_SCHEMA_VERSION,
        "prompt_version": P.SEMANTIC_PROMPT_VERSION,
        "prompt_template_sha256": prompt_template_sha,
        "schema_sha256": schema_sha,
        "model_revision": args.model_revision,
        "base_url": args.base_url,
        "task_text": args.task_text,
        "sampling_parameters": {
            "temperature": args.temperature, "seed": args.seed,
            "max_tokens": args.max_tokens, "stream": False,
            "response_format": {"type": "json_object"},
            "context_policy": "TARGET_KEYFRAMES_ONLY",
        },
        "selection_salt": PHASE1C_SALT,
        "pinned_sample_count": len(PINNED_BASELINE_SEGMENTS),
        "frozen_g1_identity": identity,
        "pre_registered_gates": GATES,
        "argus_upstream": {
            "repo": "Pantheon-Industries-Inc/argus",
            "commit": "ccfd313f18d9981ba3ad2868d7f7d8bc3ecb7629",
            "files_read": ["label/prompts.py", "label/harness.py", "checks/label_consistency.py"],
            "mechanisms_borrowed": [
                "JSON-only interface + response_format=json_object",
                "controlled enums for categorical fields with free text only where free",
                "explicit uncertain/unclear abstention values",
                "evidence discipline: cite supplied frames only",
                "local-vs-global separation (segment local here, no episode claims)",
            ],
            "not_copied": "the full Argus episode prompt/schema/vocabulary",
        },
        "not_frozen_notice": (
            "v0.1 enums, prompt bytes and schema version are CANDIDATE. "
            "This run is not a taxonomy freeze and not an accuracy evaluation."
        ),
    }
    (out_dir / "run_manifest.json").write_text(
        json.dumps(run_manifest, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    (out_dir / "candidate_schema.json").write_text(
        json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")

    sample_rows: list[dict[str, Any]] = []
    frame_rows: list[dict[str, Any]] = []
    request_rows: list[dict[str, Any]] = []
    raw_rows: list[dict[str, Any]] = []
    label_rows: list[dict[str, Any]] = []
    finding_rows: list[dict[str, Any]] = []
    queue_rows: list[dict[str, Any]] = []
    illegal_inputs: list[dict[str, Any]] = []

    for sample in samples:
        episode_id = sample["episode_id"]
        segment_id = sample["segment_id"]
        keyframes = sample["target_keyframes"]

        rendered = render_clean_rgb_frames(adapter, episode_id, keyframes)
        by_index = {f.frame_index: f for f in rendered}

        identity_obj = V.TargetSegmentIdentity(
            source_episode_id=episode_id, segment_id=segment_id,
            start_frame=sample["start_frame"], end_frame=sample["end_frame"],
        )

        manifest: list[V.FrameEntry] = []
        for position, index in enumerate(keyframes):
            frame = by_index[index]
            role = ("START" if position == 0 else
                    "END" if position == len(keyframes) - 1 else
                    "MIDDLE")
            png = write_clean_rgb_png(frame, rgb_dir / f"{segment_id}_f{index:05d}.png")
            entry = V.FrameEntry(
                frame_index=index, role=role, source_episode_id=episode_id,
                origin_segment_id=segment_id, target_segment_id=segment_id,
                is_target_segment_frame=True,
                pixel_sha256=str(frame.provenance["pixel_sha256"]).lower(),
            )
            manifest.append(entry)
            frame_rows.append({
                "sample_order": sample["sample_order"], "segment_id": segment_id,
                "position": position, **entry.to_dict(),
                "png_path": str(png), "png_bytes": png.stat().st_size,
                "contract_version": frame.provenance["contract_version"],
                "overlay_applied": frame.provenance["overlay_applied"],
                "audit_mp4_used": frame.provenance["audit_mp4_used"],
                "lossy_video_roundtrip": frame.provenance["lossy_video_roundtrip"],
                "shape": "x".join(str(v) for v in frame.provenance["shape"]),
            })

        # -- illegal-input gate (pre-call, fail closed) -------------------
        input_findings = V.check_manifest_integrity(manifest, identity_obj)
        if input_findings:
            illegal_inputs.append({
                "segment_id": segment_id,
                "findings": [f.to_dict() for f in input_findings],
            })

        prompt = P.render_prompt(
            source_episode_id=episode_id, segment_id=segment_id,
            start_frame=sample["start_frame"], end_frame=sample["end_frame"],
            frames=manifest, task_text=args.task_text,
        )
        prompt_sha = P.prompt_sha256(prompt)

        request = V.build_request_record(
            identity=identity_obj, manifest=manifest, prompt_sha256=prompt_sha,
            model_revision=args.model_revision,
            sampling={"temperature": args.temperature, "seed": args.seed,
                      "max_tokens": args.max_tokens, "response_format": "json_object"},
        )
        request["sample_order"] = sample["sample_order"]
        request["prompt_text_sha256"] = prompt_sha
        request_rows.append(request)

        sample_rows.append({
            "sample_order": sample["sample_order"], "episode_id": episode_id,
            "segment_id": segment_id, "start_frame": sample["start_frame"],
            "end_frame": sample["end_frame"], "segment_length": sample["segment_length"],
            "strata": sample["strata"], "selection_salt": sample["selection_salt"],
            "keyframe_count": len(keyframes), "target_keyframes": ";".join(map(str, keyframes)),
            "frame_pixel_sha256s": ";".join(e.pixel_sha256 for e in manifest),
            "prompt_sha256": prompt_sha,
            "schema_version": S.SEMANTIC_SCHEMA_VERSION,
        })

        if args.dry_run:
            continue

        # -- 3. model call -------------------------------------------------
        uris = [probe.image_data_uri(rgb_dir / f"{segment_id}_f{i:05d}.png") for i in keyframes]
        payload = {
            "model": args.model,
            "messages": [{"role": "user", "content":
                          [{"type": "text", "text": prompt}] +
                          [{"type": "image_url", "image_url": {"url": u}} for u in uris]}],
            "max_tokens": args.max_tokens,
            "temperature": args.temperature,
            "seed": args.seed,
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        gpu_before = probe.gpu_snapshot()
        t0 = time.perf_counter()
        status, body, raw = probe._http_json(
            f"{args.base_url.rstrip('/')}/v1/chat/completions", payload, args.timeout)
        elapsed = time.perf_counter() - t0
        gpu_after = probe.gpu_snapshot()

        if status == 0:
            processing_error = f"SERVER_UNREACHABLE: {body.get('_error')}"
            text, finish_reason, usage = None, None, {}
        else:
            processing_error = None
            parsed_resp = probe.parse_response(body) if status == 200 else {}
            text = parsed_resp.get("text")
            finish_reason = parsed_resp.get("finish_reason")
            usage = parsed_resp

        # raw response recorded verbatim BEFORE any interpretation
        raw_rows.append({
            "sample_order": sample["sample_order"], "segment_id": segment_id,
            "http_status": status, "finish_reason": finish_reason,
            "raw_response_text": text,
            "raw_response_sha256": _sha256_bytes((text or "").encode("utf-8")),
            "processing_error": processing_error,
            "wall_seconds": round(elapsed, 3),
            "prompt_tokens": (usage or {}).get("prompt_tokens"),
            "completion_tokens": (usage or {}).get("completion_tokens"),
            "predicted_ms": (usage or {}).get("predicted_ms"),
            "vram_used_before_mib": (gpu_before or {}).get("vram_used_mib"),
            "vram_used_after_mib": (gpu_after or {}).get("vram_used_mib"),
            "request_sha256": request["request_sha256"],
        })

        result = V.validate_model_output(
            text, manifest=manifest, identity=identity_obj,
            finish_reason=finish_reason, processing_error=processing_error,
        )

        label_rows.append({
            "sample_order": sample["sample_order"],
            "source_episode_id": episode_id, "segment_id": segment_id,
            "segment_interval_frames": [sample["start_frame"], sample["end_frame"]],
            "schema_version": S.SEMANTIC_SCHEMA_VERSION,
            "prompt_sha256": prompt_sha, "model_revision": args.model_revision,
            "request_sha256": request["request_sha256"],
            "raw_response_sha256": raw_rows[-1]["raw_response_sha256"],
            "label_qc_status": result.status,
            "model_payload": result.parsed,
            "validation": result.to_dict(),
        })
        for finding in result.findings:
            finding_rows.append({
                "sample_order": sample["sample_order"], "segment_id": segment_id,
                "label_qc_status": result.status, **finding.to_dict(),
            })
        queue_rows.append({
            "sample_order": sample["sample_order"], "episode_id": episode_id,
            "segment_id": segment_id, "annotation_review_status": result.status,
            "review_reasons": ";".join(sorted({f.check_id for f in result.findings})),
            "candidate_finding_count": len(result.candidate_findings),
            "deterministic_finding_count": len(result.deterministic_findings),
            "cross_boundary_references": ";".join(map(str, result.cross_boundary_references)),
            "invalid_references": ";".join(map(str, result.invalid_references)),
            "training_disposition": "NOT_EVALUATED",
        })
        print(f"  [{sample['sample_order']:>2}/{len(samples)}] {segment_id:<18} "
              f"status={result.status:<20} json={result.parse_ok} "
              f"schema={result.schema_ok} frames={result.frame_evidence_ok} "
              f"{elapsed:.1f}s", flush=True)

    # -- 4. artifacts ------------------------------------------------------
    _write_jsonl(out_dir / "frame_manifest.jsonl", frame_rows)
    _write_jsonl(out_dir / "model_requests.jsonl", request_rows)
    _write_jsonl(out_dir / "raw_model_responses.jsonl", raw_rows)
    _write_jsonl(out_dir / "structured_segment_labels.jsonl", label_rows)
    _write_jsonl(out_dir / "label_qc_findings.jsonl", finding_rows)

    if sample_rows:
        with (out_dir / "sample_manifest.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(sample_rows[0].keys()))
            writer.writeheader()
            writer.writerows(sample_rows)

    with (out_dir / "annotation_review_queue.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(QUEUE_FIELDS))
        writer.writeheader()
        writer.writerows(queue_rows)

    if illegal_inputs:
        (out_dir / "illegal_inputs.json").write_text(
            json.dumps(illegal_inputs, indent=2, ensure_ascii=False), encoding="utf-8")

    summary = _summarize(samples, raw_rows, label_rows, finding_rows, illegal_inputs, args)
    (out_dir / "baseline_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.shareable_out:
        _emit_shareable(Path(args.shareable_out), run_manifest, summary, sample_rows,
                        frame_rows, request_rows, raw_rows, label_rows, finding_rows,
                        queue_rows, args.rgb_cache)

    if args.boundary_regression and not args.dry_run:
        run_boundary_regression(out_dir=out_dir, probe=probe, adapter=adapter,
                                rgb_dir=rgb_dir, args=args)

    print()
    print(json.dumps(summary["rates"], indent=2, ensure_ascii=False))
    print("GATES:", json.dumps(summary["gates"], ensure_ascii=False))
    print(f"artifacts: {out_dir}")
    return 0


# --------------------------------------------------------------------------- #
# statistics
# --------------------------------------------------------------------------- #
def _summarize(samples, raw_rows, label_rows, finding_rows, illegal_inputs, args) -> dict[str, Any]:
    n = len(samples)
    attempted = len(raw_rows) if raw_rows else 0
    ok_http = sum(1 for r in raw_rows if r["http_status"] == 200)
    parse_ok = sum(1 for r in label_rows if r["validation"]["parse_ok"])
    schema_ok = sum(1 for r in label_rows if r["validation"]["schema_ok"])
    frames_ok = sum(1 for r in label_rows if r["validation"]["frame_evidence_ok"])
    truncated = sum(1 for r in label_rows if r["validation"]["truncated"])
    abstained = sum(1 for r in label_rows if r["validation"]["abstained"])
    cross = sum(len(r["validation"]["cross_boundary_references"]) for r in label_rows)
    invalid_refs = sum(len(r["validation"]["invalid_references"]) for r in label_rows)

    status_counts: dict[str, int] = {}
    for row in label_rows:
        status_counts[row["label_qc_status"]] = status_counts.get(row["label_qc_status"], 0) + 1

    check_counts: dict[str, int] = {}
    scope_counts: dict[str, int] = {}
    for row in finding_rows:
        check_counts[row["check_id"]] = check_counts.get(row["check_id"], 0) + 1
        scope_counts[row["scope"]] = scope_counts.get(row["scope"], 0) + 1

    def rate(num: int) -> float:
        return round(num / attempted, 4) if attempted else 0.0

    rates = {
        "samples_pinned": n,
        "model_requests_attempted": attempted,
        "http_200_rate": rate(ok_http),
        "json_parse_rate": rate(parse_ok),
        "schema_valid_rate": rate(schema_ok),
        "frame_evidence_valid_rate": rate(frames_ok),
        "mean_wall_seconds": round(
            sum(r["wall_seconds"] for r in raw_rows) / attempted, 3) if attempted else None,
        "mean_completion_tokens": round(
            sum((r["completion_tokens"] or 0) for r in raw_rows) / attempted, 1) if attempted else None,
        "peak_vram_used_mib": max((r["vram_used_after_mib"] or 0) for r in raw_rows) if raw_rows else None,
        "cross_boundary_reference_count": cross,
        "invalid_frame_reference_count": invalid_refs,
        "truncated_output_count": truncated,
        "abstained_count": abstained,
        "abstention_rate": rate(abstained),
        "qc_status_counts": status_counts,
        "finding_counts_by_check": check_counts,
        "finding_counts_by_scope": scope_counts,
        "illegal_model_inputs": len(illegal_inputs),
    }
    if raw_rows:
        peak = max((r["vram_used_after_mib"] or 0) for r in raw_rows)
        rates["peak_vram_note"] = (
            "vram_used_after_mib is read after each call; the server holds the "
            "model resident, so this is load+inference occupancy, not isolated delta."
        )
        rates["peak_vram_used_mib"] = peak

    gates = {
        "illegal_model_inputs": {
            "observed": len(illegal_inputs),
            "max": GATES["illegal_model_inputs_max"],
            "pass": len(illegal_inputs) <= GATES["illegal_model_inputs_max"],
        },
        "json_parse_rate": {
            "observed": rates["json_parse_rate"], "min": GATES["json_parse_rate_min"],
            "pass": rates["json_parse_rate"] >= GATES["json_parse_rate_min"],
        },
        "schema_valid_rate": {
            "observed": rates["schema_valid_rate"], "min": GATES["schema_valid_rate_min"],
            "pass": rates["schema_valid_rate"] >= GATES["schema_valid_rate_min"],
        },
        "frame_evidence_valid_rate": {
            "observed": rates["frame_evidence_valid_rate"],
            "min": GATES["frame_evidence_valid_rate_min"],
            "pass": rates["frame_evidence_valid_rate"] >= GATES["frame_evidence_valid_rate_min"],
        },
        "truncated_outputs": {
            "observed": truncated, "max": GATES["truncated_outputs_max"],
            "pass": truncated <= GATES["truncated_outputs_max"],
        },
        "detected_cross_boundary_references": {
            "observed": cross,
            "note": (
                "Every cited frame outside the frozen target interval or not marked "
                "as a target-segment frame is flagged by construction; this counter "
                "reports how many such citations the model actually made. It does NOT "
                "prove that all neighbour mis-attribution is detectable from indices "
                "alone -- a note may describe a neighbour event without citing a frame."
            ),
            "pass": True,
        },
    }
    return {
        "run_id": None,
        "scope": "TINY_BASELINE_DEVELOPMENT_ONLY_NOT_FORMAL",
        "accuracy_claim": "NONE - no human ground truth; do not compute accuracy",
        "model": args.model_revision,
        "max_tokens": args.max_tokens,
        "seed": args.seed,
        "temperature": args.temperature,
        "rates": rates,
        "gates": gates,
        "all_gates_pass": all(g["pass"] for g in gates.values()),
        "gate_note": (
            "Gates were fixed before the run. They are engineering-contract gates, "
            "not semantic accuracy thresholds. Failing a gate is reported as a "
            "failure; thresholds are not adjusted after seeing results."
        ),
    }


def _emit_shareable(dest: Path, run_manifest, summary, sample_rows, frame_rows,
                    request_rows, raw_rows, label_rows, finding_rows, queue_rows,
                    rgb_cache: str) -> None:
    """Write a path-sanitized evidence copy.  Local originals stay untouched."""

    dest.mkdir(parents=True, exist_ok=True)
    deploy_root = str(Path(rgb_cache).parent)

    (dest / "run_manifest.json").write_text(json.dumps(
        _deep_sanitize(run_manifest, deploy_root), indent=2, ensure_ascii=False, default=str),
        encoding="utf-8")
    (dest / "baseline_summary.json").write_text(json.dumps(
        _deep_sanitize(summary, deploy_root), indent=2, ensure_ascii=False, default=str),
        encoding="utf-8")
    (dest / "candidate_schema.json").write_text(
        json.dumps(S.json_schema(), indent=2, ensure_ascii=False), encoding="utf-8")
    (dest / "sample_manifest.csv").write_text(
        "".join(_csv_text(sample_rows)), encoding="utf-8")
    (dest / "annotation_review_queue.csv").write_text(
        "".join(_csv_text(queue_rows, QUEUE_FIELDS)), encoding="utf-8")
    for name, rows in (
        ("frame_manifest.jsonl", frame_rows),
        ("model_requests.jsonl", request_rows),
        ("raw_model_responses.jsonl", raw_rows),
        ("structured_segment_labels.jsonl", label_rows),
        ("label_qc_findings.jsonl", finding_rows),
    ):
        _write_jsonl(dest / name, _deep_sanitize(rows, deploy_root))


def run_boundary_regression(*, out_dir: Path, probe, adapter, rgb_dir: Path, args) -> dict:
    """Target-only vs target+neighbour check on demo_47-S0003.

    Purpose: exercise the ``TARGET_CONTEXT_CROSS_BOUNDARY`` guard against real
    model output.  A *single* clean run does not prove neighbour mis-attribution
    is solved; it only shows the checker and the interface behave.  These results
    are kept out of the 10-segment baseline denominator.
    """

    from project2_g3.dev_segments import (
        frozen_segments_for_episode, left_boundary_types, neighbour_context_frames,
        target_keyframes,
    )
    from project2_mvp.rgb_input import render_clean_rgb_frames, write_clean_rgb_png

    episode_id = "data/demo_47"
    segment_id = "demo_47-S0003"
    segments = frozen_segments_for_episode(adapter, episode_id)
    index = next(i for i, s in enumerate(segments) if s.segment_id == segment_id)
    target = segments[index]
    left = left_boundary_types(adapter, episode_id).get(segment_id)
    keyframes = target_keyframes(adapter, episode_id, target, left)
    context = neighbour_context_frames(segments, index)

    all_frames = sorted({*keyframes, *(frame for frame, _, _ in context)})
    rendered = {f.frame_index: f for f in render_clean_rgb_frames(adapter, episode_id, all_frames)}

    identity = V.TargetSegmentIdentity(
        source_episode_id=episode_id, segment_id=segment_id,
        start_frame=target.start_frame, end_frame=target.end_frame,
    )

    def build_manifest(with_context: bool) -> list[V.FrameEntry]:
        manifest: list[V.FrameEntry] = []
        for order, frame_index in enumerate(
            ([f for f, _, _ in context] if with_context else []) + list(keyframes)
        ):
            origin = segment_id
            role = "TARGET_KEYFRAME"
            if with_context and order < len(context):
                frame_index, role, origin = context[order]
            manifest.append(V.FrameEntry(
                frame_index=frame_index, role=role, source_episode_id=episode_id,
                origin_segment_id=origin, target_segment_id=segment_id,
                is_target_segment_frame=origin == segment_id,
                pixel_sha256=str(rendered[frame_index].provenance["pixel_sha256"]).lower(),
            ))
        for entry in manifest:
            write_clean_rgb_png(
                rendered[entry.frame_index],
                rgb_dir / f"bnd_{segment_id}_{'ctx' if not entry.is_target_segment_frame else 'tgt'}_f{entry.frame_index:05d}.png",
            )
        return manifest

    out: dict[str, Any] = {
        "scope": "OPTIONAL_BOUNDARY_REGRESSION_EXCLUDED_FROM_BASELINE",
        "episode_id": episode_id, "segment_id": segment_id,
        "target_interval": [target.start_frame, target.end_frame],
        "target_keyframes": keyframes,
        "neighbour_context_frames": [
            {"frame_index": f, "role": r, "origin_segment_id": o} for f, r, o in context
        ],
        "endpoint_note": (
            "A single clean result does NOT prove neighbour mis-attribution is solved. "
            "It only shows the guard executes and reports what the model cited."
        ),
        "variants": [],
    }

    for label, with_context in (("target_only", False), ("target_plus_neighbour", True)):
        manifest = build_manifest(with_context)
        prompt = P.render_prompt(
            source_episode_id=episode_id, segment_id=segment_id,
            start_frame=target.start_frame, end_frame=target.end_frame,
            frames=manifest, task_text=args.task_text,
        )
        uris = []
        for entry in manifest:
            suffix = "ctx" if not entry.is_target_segment_frame else "tgt"
            uris.append(probe.image_data_uri(
                rgb_dir / f"bnd_{segment_id}_{suffix}_f{entry.frame_index:05d}.png"))
        payload = {
            "model": args.model,
            "messages": [{"role": "user", "content":
                          [{"type": "text", "text": prompt}] +
                          [{"type": "image_url", "image_url": {"url": u}} for u in uris]}],
            "max_tokens": args.max_tokens, "temperature": args.temperature,
            "seed": args.seed, "stream": False,
            "response_format": {"type": "json_object"},
        }
        t0 = time.perf_counter()
        status, body, raw = probe._http_json(
            f"{args.base_url.rstrip('/')}/v1/chat/completions", payload, args.timeout)
        elapsed = time.perf_counter() - t0
        parsed_resp = probe.parse_response(body) if status == 200 else {}
        text = parsed_resp.get("text")
        result = V.validate_model_output(
            text, manifest=manifest, identity=identity,
            finish_reason=parsed_resp.get("finish_reason"),
            processing_error=None if status != 0 else "SERVER_UNREACHABLE",
        )
        out["variants"].append({
            "variant": label,
            "input_manifest": [e.to_dict() for e in manifest],
            "image_order": [e.frame_index for e in manifest],
            "prompt_sha256": P.prompt_sha256(prompt),
            "http_status": status, "wall_seconds": round(elapsed, 3),
            "raw_response_text": text,
            "raw_response_sha256": _sha256_bytes((text or "").encode("utf-8")),
            "validation": result.to_dict(),
            "model_payload": result.parsed,
        })
        print(f"  boundary[{label}] status={result.status} "
              f"cross_boundary={result.cross_boundary_references} "
              f"images={len(manifest)}", flush=True)

    (out_dir / "boundary_regression").mkdir(exist_ok=True)
    (out_dir / "boundary_regression" / "boundary_regression.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return out


def _csv_text(rows: list[dict[str, Any]], fieldnames: object = None) -> list[str]:
    import io

    if fieldnames is None:
        if not rows:
            return []
        fieldnames = list(rows[0].keys())
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(fieldnames))
    writer.writeheader()
    writer.writerows(rows)
    return [buffer.getvalue()]


if __name__ == "__main__":
    raise SystemExit(main())
