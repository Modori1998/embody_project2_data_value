"""P2-G3 Taxonomy v0.2 paired baseline runner (v0.1 vs v0.2, same inputs).

Two cohorts, one fixed local Qwen3-VL-4B Q4 configuration:

* **known_cases** -- the three historical diagnostic segments
  (``demo_33-S0001``, ``demo_75-S0001``, ``demo_47-S0003``).  Appearing here
  does NOT make them new evidence; they can never contribute to any
  unseen-sample generalisation or accuracy claim.
* **microset** -- 12 fresh Development segments, episode-disjoint from the whole
  Phase-1 probe set (which contains every previously used and diagnostic
  episode).  Frozen before any v0.2 call.

Both versions run on **identical** RGB frames, model revision, sampling
parameters and output-token budget.  The only differences are the v0.2 prompt
instructions and the v0.2 schema/validator.  v0.1 has no ``event_assessment``
field, so that metric is reported ``NOT_APPLICABLE`` for v0.1 rather than
treated as an identical comparable.

No semantic accuracy is computed: there is no independent human reference.
Without one the report carries ``NOT_ESTIMABLE``.

Usage (renderer environment)::

    PY=C:/Users/95611/miniconda3/envs/project1_robomimic_audit/python.exe
    $PY scripts/run_g3_taxonomy_v02_paired.py --run-id <ID> --cohort all
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
from project2_g3 import semantic_reporting as R  # noqa: E402
from project2_g3 import semantic_schema as S  # noqa: E402
from project2_g3 import semantic_validation as V  # noqa: E402
from project2_g3.dev_segments import (  # noqa: E402
    SamplingError,
    V02SelectionError,
    frozen_segments_for_episode,
    left_boundary_types,
    resolve_v02_microset,
    target_keyframes,
)

#: Pre-registered engineering gates (v0.2 plan §4).  Never adjusted post hoc.
GATES: dict[str, Any] = {
    "illegal_model_inputs_max": 0,
    "truncated_outputs_max": 0,
    "illegal_frame_references_max": 0,
    "cross_boundary_references_max": 0,
    "forbidden_field_leaks_max": 0,
    "json_parse_rate_min": 0.90,
    "schema_valid_rate_min": 0.90,
    "frame_reference_valid_rate_min": 0.90,
}

#: Historical diagnostic segments (already seen in prior rounds).
KNOWN_CASES: tuple[dict[str, Any], ...] = (
    {"episode_id": "data/demo_33", "segment_id": "demo_33-S0001",
     "start_frame": 0, "end_frame": 3, "label": "short_first_segment"},
    {"episode_id": "data/demo_75", "segment_id": "demo_75-S0001",
     "start_frame": 0, "end_frame": 3, "label": "short_first_segment"},
    {"episode_id": "data/demo_47", "segment_id": "demo_47-S0003",
     "start_frame": 50, "end_frame": 90, "label": "close_vs_grasp_and_event_evidence"},
)

DEFAULT_MODEL_REVISION = (
    "Qwen/Qwen3-VL-4B-Instruct-GGUF@1cd86afb9a95c410a6038ab3b40d8b578c892266::"
    "Qwen3VL-4B-Instruct-Q4_K_M.gguf+mmproj-Qwen3VL-4B-Instruct-F16.gguf"
)
DEFAULT_MAX_TOKENS = 512
DEFAULT_SEED = 1234
DEFAULT_TEMPERATURE = 0.0

VERSIONS = ("v0_1", "v0_2")


def _load_probe():
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


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _sanitize(text: Any, roots: list[str]) -> Any:
    if not isinstance(text, str):
        return text
    out = text
    for root in roots:
        if root:
            out = out.replace(root, "<LOCAL_ROOT>")
            out = out.replace(root.replace("\\", "/"), "<LOCAL_ROOT>")
    return out


def _deep_sanitize(obj: Any, roots: list[str]) -> Any:
    if isinstance(obj, dict):
        return {k: _deep_sanitize(v, roots) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_sanitize(v, roots) for v in obj]
    return _sanitize(obj, roots)


# --------------------------------------------------------------------------- #
def build_cohort(
    *,
    name: str,
    adapter: Any,
    entries: list[dict[str, Any]],
    verify_frozen: bool,
) -> list[dict[str, Any]]:
    """Attach frozen intervals and target keyframes to a cohort's entries."""

    cache: dict[str, dict[str, Any]] = {}
    out: list[dict[str, Any]] = []
    for entry in entries:
        episode_id = entry["episode_id"]
        if episode_id not in cache:
            segs = frozen_segments_for_episode(adapter, episode_id)
            cache[episode_id] = {
                "by_id": {s.segment_id: s for s in segs},
                "boundaries": left_boundary_types(adapter, episode_id),
            }
        segment = cache[episode_id]["by_id"].get(entry["segment_id"])
        if segment is None:
            raise SamplingError(f"STOP_SEGMENT_NOT_FOUND: {entry['segment_id']}")
        if (segment.start_frame, segment.end_frame) != (entry["start_frame"], entry["end_frame"]):
            if verify_frozen:
                raise SamplingError(
                    "STOP_SEGMENT_INTERVAL_CHANGED: "
                    f"{entry['segment_id']} pinned=[{entry['start_frame']},{entry['end_frame']}] "
                    f"recomputed=[{segment.start_frame},{segment.end_frame}]"
                )
        keyframes = target_keyframes(
            adapter, episode_id, segment, cache[episode_id]["boundaries"].get(segment.segment_id)
        )
        out.append({
            **entry,
            "cohort": name,
            "source_episode_id": episode_id,
            "start_frame": segment.start_frame,
            "end_frame": segment.end_frame,
            "segment_length": segment.length,
            "target_keyframes": keyframes,
            "segment_identity_verified": True,
        })
    return out


def run_one(
    *,
    probe: Any,
    renderer_frames: dict[int, Any],
    identity: V.TargetSegmentIdentity,
    manifest: list[V.FrameEntry],
    prompt: str,
    args: Any,
) -> dict[str, Any]:
    payload = {
        "model": args.model,
        "messages": [{"role": "user", "content":
                      [{"type": "text", "text": prompt}] +
                      [{"type": "image_url",
                        "image_url": {"url": probe.image_data_uri(p)}} for p in
                       [Path(f) for f in sorted(renderer_frames)]]}],
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
        "seed": args.seed,
        "stream": False,
        "response_format": {"type": "json_object"},
    }
    t0 = time.perf_counter()
    status, body, raw = probe._http_json(
        f"{args.base_url.rstrip('/')}/v1/chat/completions", payload, args.timeout)
    elapsed = time.perf_counter() - t0
    gpu = probe.gpu_snapshot()
    parsed_resp = probe.parse_response(body) if status == 200 else {}
    text = parsed_resp.get("text")
    return {
        "http_status": status,
        "finish_reason": parsed_resp.get("finish_reason"),
        "raw_response_text": text,
        "prompt_tokens": parsed_resp.get("prompt_tokens"),
        "completion_tokens": parsed_resp.get("completion_tokens"),
        "predicted_ms": parsed_resp.get("predicted_ms"),
        "wall_seconds": round(elapsed, 3),
        "vram_used_after_mib": (gpu or {}).get("vram_used_mib"),
        "processing_error": None if status != 0 else f"SERVER_UNREACHABLE: {body.get('_error')}",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-root", default="outputs/p2_g3_taxonomy_v02")
    parser.add_argument("--run-id")
    parser.add_argument("--cohort", choices=("known_cases", "microset", "all"),
                        default="all")
    parser.add_argument("--base-url", default=os.environ.get("G3_VLM_BASE_URL",
                                                             "http://127.0.0.1:8080"))
    parser.add_argument("--model", default="qwen3-vl-4b-q4_k_m")
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--timeout", type=float, default=900.0)
    parser.add_argument("--task-text", default=P.DEFAULT_TASK_TEXT)
    parser.add_argument("--rgb-cache",
                        default=str(Path.home() / "embody" / "_local_vlm_deploy" / "rgb_g3_v02"))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--v02-prompt", choices=("v0_2", "v0_2_1"), default="v0_2_1",
                        help="which v0.2 prompt implementation to use; v0_2 is the "
                             "first implementation whose outputs omitted required keys, "
                             "kept selectable only to reproduce that finding")
    parser.add_argument("--shareable-out")
    args = parser.parse_args(argv)

    os.environ.setdefault("MUJOCO_GL", "wgl")
    probe = _load_probe()

    run_id = args.run_id or "g3_taxonomy_v02_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.output_root) / run_id
    if out_dir.exists():
        print(f"STOP_RUN_EXISTS: {out_dir}", file=sys.stderr)
        return 2
    out_dir.mkdir(parents=True)

    from project2_g1.config import load_g1_p1_config
    from project2_g1.source import build_can_mh_adapter
    from project2_mvp.m2_materializer import assert_frozen_g1_identity
    from project2_mvp.rgb_input import render_clean_rgb_frames, write_clean_rgb_png

    identity_probe = assert_frozen_g1_identity()
    adapter = build_can_mh_adapter(load_g1_p1_config())
    rgb_dir = Path(args.rgb_cache) / run_id
    rgb_dir.mkdir(parents=True, exist_ok=True)

    # -- cohorts (resolved and frozen before any model call) --------------
    cohorts: dict[str, list[dict[str, Any]]] = {}
    if args.cohort in ("known_cases", "all"):
        cohorts["known_cases"] = build_cohort(
            name="known_cases", adapter=adapter, entries=list(KNOWN_CASES),
            verify_frozen=True)
    if args.cohort in ("microset", "all"):
        resolved = resolve_v02_microset()
        cohorts["microset"] = build_cohort(
            name="microset", adapter=adapter,
            entries=[{k: v for k, v in s.items() if k in
                      ("episode_id", "segment_id", "start_frame", "end_frame")}
                     for s in resolved["samples"]],
            verify_frozen=True)
        for target, source in zip(cohorts["microset"], resolved["samples"]):
            target["selection_proxies"] = source["selection_proxies"]
            target["episode_duration_stratum"] = source["episode_duration_stratum"]
        (out_dir / "microset_selection.json").write_text(
            json.dumps(resolved, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    run_manifest = {
        "run_id": run_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "V0_2_TINY_PAIRED_DEVELOPMENT_ONLY_NOT_FORMAL",
        "owner_freeze": {
            "output_architecture": "FROZEN_JSON_ENUM_NOTE_FRAME_EVIDENCE_QC_V1",
            "taxonomy_v0_2": "OWNER_APPROVED_FROZEN_FOR_IMPLEMENTATION",
            "evidence_rubric_v0_2": "OWNER_APPROVED_FROZEN_FOR_IMPLEMENTATION",
            "formal_g3_taxonomy_v1": "NOT_FROZEN",
        },
        "versions": {
            "v0_1": {"schema": S.SEMANTIC_SCHEMA_VERSION,
                     "prompt": P.SEMANTIC_PROMPT_VERSION,
                     "prompt_template_sha256": P.template_sha256()},
            "v0_2": {"schema": S.SEMANTIC_SCHEMA_VERSION_V0_2,
                     "prompt": (P.SEMANTIC_PROMPT_VERSION_V0_2_1
                                if args.v02_prompt == "v0_2_1"
                                else P.SEMANTIC_PROMPT_VERSION_V0_2),
                     "prompt_variant": args.v02_prompt,
                     "prompt_template_sha256": (
                         P.template_sha256_v0_2_1() if args.v02_prompt == "v0_2_1"
                         else P.template_sha256_v0_2())},
        },
        "schema_sha256": {
            "v0_1": _sha256_bytes(json.dumps(S.json_schema(), sort_keys=True,
                                             ensure_ascii=False).encode("utf-8")),
            "v0_2": _sha256_bytes(json.dumps(S.json_schema_v0_2(), sort_keys=True,
                                             ensure_ascii=False).encode("utf-8")),
        },
        "model_revision": args.model_revision,
        "base_url": args.base_url,
        "task_text": args.task_text,
        "sampling_parameters": {
            "temperature": args.temperature, "seed": args.seed,
            "max_tokens": args.max_tokens, "stream": False,
            "response_format": {"type": "json_object"},
            "input_policy": "TARGET_KEYFRAMES_ONLY",
        },
        "frozen_g1_identity": identity_probe,
        "pre_registered_gates": GATES,
        "cohorts": {name: {"count": len(rows),
                           "segments": [r["segment_id"] for r in rows]}
                    for name, rows in cohorts.items()},
        "no_accuracy_claim": (
            "No independent human semantic reference exists; semantic accuracy is "
            "NOT_ESTIMABLE. Diagnostic cases cannot support any generalisation claim."
        ),
    }
    (out_dir / "run_manifest.json").write_text(
        json.dumps(run_manifest, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    (out_dir / "candidate_schema_v0_2.json").write_text(
        json.dumps(S.json_schema_v0_2(), indent=2, ensure_ascii=False), encoding="utf-8")

    # -- run ---------------------------------------------------------------
    records: dict[str, list[dict[str, Any]]] = {v: [] for v in VERSIONS}
    raw_rows: list[dict[str, Any]] = []
    finding_rows: list[dict[str, Any]] = []
    sample_rows: list[dict[str, Any]] = []

    for cohort_name, rows in cohorts.items():
        if args.limit:
            rows = rows[: args.limit]
        for row in rows:
            episode_id = row["episode_id"]
            segment_id = row["segment_id"]
            keyframes = row["target_keyframes"]
            rendered = render_clean_rgb_frames(adapter, episode_id, keyframes)
            by_index = {f.frame_index: f for f in rendered}

            identity = V.TargetSegmentIdentity(
                source_episode_id=episode_id, segment_id=segment_id,
                start_frame=row["start_frame"], end_frame=row["end_frame"])

            manifest: list[V.FrameEntry] = []
            frame_paths: list[Path] = []
            for position, index in enumerate(keyframes):
                frame = by_index[index]
                role = ("START" if position == 0 else
                        "END" if position == len(keyframes) - 1 else "MIDDLE")
                png = write_clean_rgb_png(frame, rgb_dir / f"{segment_id}_f{index:05d}.png")
                frame_paths.append(png)
                manifest.append(V.FrameEntry(
                    frame_index=index, role=role, source_episode_id=episode_id,
                    origin_segment_id=segment_id, target_segment_id=segment_id,
                    is_target_segment_frame=True,
                    pixel_sha256=str(frame.provenance["pixel_sha256"]).lower()))

            sample_rows.append({
                "cohort": cohort_name,
                "episode_id": episode_id,
                "segment_id": segment_id,
                "start_frame": row["start_frame"],
                "end_frame": row["end_frame"],
                "segment_length": row["segment_length"],
                "target_keyframes": ";".join(map(str, keyframes)),
                "frame_pixel_sha256s": ";".join(e.pixel_sha256 for e in manifest),
                "frame_png_sha256s": ";".join(_sha256_bytes(p.read_bytes()) for p in frame_paths),
                "episode_duration_stratum": row.get("episode_duration_stratum", ""),
                "gripper_travel": (row.get("selection_proxies") or {}).get("gripper_travel"),
                "eef_path_length_m": (row.get("selection_proxies") or {}).get("eef_path_length_m"),
            })

            for version in VERSIONS:
                if version == "v0_1":
                    prompt = P.render_prompt(
                        source_episode_id=episode_id, segment_id=segment_id,
                        start_frame=row["start_frame"], end_frame=row["end_frame"],
                        frames=manifest, task_text=args.task_text)
                    prompt_sha = P.prompt_sha256(prompt)
                else:
                    render_v02 = (P.render_prompt_v0_2_1 if args.v02_prompt == "v0_2_1"
                                  else P.render_prompt_v0_2)
                    prompt = render_v02(
                        source_episode_id=episode_id, segment_id=segment_id,
                        start_frame=row["start_frame"], end_frame=row["end_frame"],
                        frames=manifest, task_text=args.task_text)
                    prompt_sha = P.prompt_sha256(prompt)

                request_sha = _sha256_bytes(json.dumps({
                    "segment_id": segment_id, "prompt_sha256": prompt_sha,
                    "frames": [e.to_dict() for e in manifest],
                    "version": version,
                }, sort_keys=True, ensure_ascii=False).encode("utf-8"))

                call = run_one(probe=probe, renderer_frames=frame_paths,
                               identity=identity, manifest=manifest, prompt=prompt, args=args)

                raw_rows.append({
                    "cohort": cohort_name, "segment_id": segment_id, "version": version,
                    "request_sha256": request_sha, "prompt_sha256": prompt_sha,
                    "http_status": call["http_status"],
                    "finish_reason": call["finish_reason"],
                    "raw_response_text": call["raw_response_text"],
                    "raw_response_sha256": _sha256_bytes(
                        (call["raw_response_text"] or "").encode("utf-8")),
                    "processing_error": call["processing_error"],
                    "wall_seconds": call["wall_seconds"],
                    "prompt_tokens": call["prompt_tokens"],
                    "completion_tokens": call["completion_tokens"],
                    "predicted_ms": call["predicted_ms"],
                    "vram_used_after_mib": call["vram_used_after_mib"],
                })

                if version == "v0_1":
                    result = V.validate_model_output(
                        call["raw_response_text"], manifest=manifest, identity=identity,
                        finish_reason=call["finish_reason"],
                        processing_error=call["processing_error"])
                else:
                    result = V.validate_model_output_v0_2(
                        call["raw_response_text"], manifest=manifest, identity=identity,
                        finish_reason=call["finish_reason"],
                        processing_error=call["processing_error"])

                for finding in result.findings:
                    finding_rows.append({
                        "cohort": cohort_name, "segment_id": segment_id,
                        "version": version, "status": result.status, **finding.to_dict(),
                    })

                records[version].append({
                    "cohort": cohort_name, "segment_id": segment_id,
                    "status": result.status, "parse_ok": result.parse_ok,
                    "schema_ok": result.schema_ok,
                    "frame_evidence_ok": result.frame_evidence_ok,
                    "finish_reason": call["finish_reason"],
                    "model_payload": result.parsed,
                    "wall_seconds": call["wall_seconds"],
                    "vram_used_after_mib": call["vram_used_after_mib"],
                    "validation": result.to_dict(),
                })
                print(f"  [{cohort_name}] {segment_id:<18} {version} "
                      f"status={result.status:<20} json={result.parse_ok} "
                      f"schema={result.schema_ok} frames={result.frame_evidence_ok} "
                      f"{call['wall_seconds']}s", flush=True)

    # -- artifacts ---------------------------------------------------------
    _write_jsonl(out_dir / "raw_model_responses.jsonl", raw_rows)
    _write_jsonl(out_dir / "label_qc_findings.jsonl", finding_rows)
    _write_csv(out_dir / "sample_manifest.csv", sample_rows,
               list(sample_rows[0].keys()))

    rates: dict[str, Any] = {}
    gates: dict[str, Any] = {}
    # Reporting needs the real schema version string, because v0.1 has no
    # event_assessment field and that metric must be NOT_APPLICABLE, not zero.
    schema_version_of = {
        "v0_1": S.SEMANTIC_SCHEMA_VERSION,
        "v0_2": S.SEMANTIC_SCHEMA_VERSION_V0_2,
    }
    for version in VERSIONS:
        version_records = records[version]
        model_version = schema_version_of[version]
        cohort_records = {
            name: [r for r in version_records if r["cohort"] == name]
            for name in cohorts
        }
        rates[version] = {
            "all": R.compute_rates(version_records, version=model_version),
            **{name: R.compute_rates(rows, version=model_version)
               for name, rows in cohort_records.items()},
        }
        gates[version] = {
            name: R.evaluate_gates(R.compute_rates(rows, version=model_version), GATES)
            for name, rows in cohort_records.items()
        }
        gates[version]["all"] = R.evaluate_gates(rates[version]["all"], GATES)
        _write_jsonl(out_dir / f"labels_{version}.jsonl",
                     [{"cohort": r["cohort"], "segment_id": r["segment_id"],
                       "status": r["status"], "model_payload": r["model_payload"],
                       "validation": r["validation"]} for r in version_records])

    paired_rows = R.paired_comparison(rates["v0_1"]["all"], rates["v0_2"]["all"])
    summary = {
        "run_id": run_id,
        "scope": "V0_2_TINY_PAIRED_DEVELOPMENT_ONLY_NOT_FORMAL",
        "cohorts": {name: len(rows) for name, rows in cohorts.items()},
        "rates_by_version": rates,
        "gates_by_version": gates,
        "paired_comparison": paired_rows,
        "paired_markdown": R.render_paired_markdown(paired_rows),
        "semantic_accuracy": R.NOT_ESTIMABLE,
        "gate_note": (
            "Engineering-contract gates pre-registered before the run and not "
            "adjusted afterwards. They are not semantic accuracy thresholds."
        ),
    }
    (out_dir / "paired_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    (out_dir / "paired_comparison.md").write_text(
        "# v0.1 vs v0.2 paired comparison\n\n" + summary["paired_markdown"] + "\n",
        encoding="utf-8")

    if args.shareable_out:
        _emit_shareable(Path(args.shareable_out), run_manifest, summary, sample_rows,
                        raw_rows, finding_rows, out_dir, args.rgb_cache)

    print()
    print(summary["paired_markdown"])
    for version in VERSIONS:
        print(f"{version} gates (all): {json.dumps(gates[version]['all'], ensure_ascii=False)}")
    print(f"artifacts: {out_dir}")
    return 0


def _emit_shareable(dest: Path, run_manifest, summary, sample_rows, raw_rows,
                    finding_rows, out_dir: Path, rgb_cache: str) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    roots = [str(Path(rgb_cache).parent), str(Path.home()), str(ROOT)]

    (dest / "run_manifest.json").write_text(json.dumps(
        _deep_sanitize(run_manifest, roots), indent=2, ensure_ascii=False, default=str),
        encoding="utf-8")
    (dest / "paired_summary.json").write_text(json.dumps(
        _deep_sanitize(summary, roots), indent=2, ensure_ascii=False, default=str),
        encoding="utf-8")
    (dest / "paired_comparison.md").write_text(summary["paired_markdown"] + "\n",
                                               encoding="utf-8")
    (dest / "sample_manifest.csv").write_text(
        _csv_text(sample_rows, list(sample_rows[0].keys())), encoding="utf-8")
    for name in ("microset_selection.json", "candidate_schema_v0_2.json",
                 "labels_v0_1.jsonl", "labels_v0_2.jsonl",
                 "raw_model_responses.jsonl", "label_qc_findings.jsonl"):
        source = out_dir / name
        if not source.is_file():
            continue
        if name.endswith(".jsonl"):
            rows = [json.loads(line) for line in source.read_text(
                encoding="utf-8").splitlines() if line.strip()]
            _write_jsonl(dest / name, _deep_sanitize(rows, roots))
        elif name.endswith(".json"):
            payload = json.loads(source.read_text(encoding="utf-8"))
            (dest / name).write_text(json.dumps(
                _deep_sanitize(payload, roots), indent=2, ensure_ascii=False, default=str),
                encoding="utf-8")
        else:
            (dest / name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def _csv_text(rows: list[dict[str, Any]], fieldnames: list[str]) -> str:
    import io

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


if __name__ == "__main__":
    raise SystemExit(main())
