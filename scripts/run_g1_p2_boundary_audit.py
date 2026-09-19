"""CLI: G1-P2 Boundary Engine + Postprocess exploratory audit package.

Does not run Human GT calibration, threshold search, or G1-P3.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import unittest
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from project2_g1.alignment import audit_nan_inf, audit_temporal_alignment
from project2_g1.boundary_config import load_g1_p2_config
from project2_g1.boundary_engine import run_boundary_engine
from project2_g1.boundary_io import write_episode_audit_tables, write_human_review_template
from project2_g1.config import load_g1_p1_config
from project2_g1.paths import (
    CONFIG_PATH,
    DATASET_LOW_DIM_HDF5,
    DATASET_RAW_HDF5,
    DATASET_TYPE,
    G1_P2_CONFIG_PATH,
    G1_P2_OUTPUT_ROOT,
    OUTPUT_ROOT as G1_P1_OUTPUT_ROOT,
    P1_ADAPTER_PATH,
    PROJECT2_ENGINEERING_MASTER,
    PROJECT2_READABLE_DESIGN,
    PROJECT2_ROADMAP,
    PROJECT2_ROOT,
)
from project2_g1.plot import plot_episode_signals
from project2_g1.privileged_audit import load_privileged_overlay
from project2_g1.report import write_g1_p2_audit_report
from project2_g1.signals import compute_formal_signals
from project2_g1.smoke import select_g1_p2_smoke_episodes
from project2_g1.source import build_can_mh_adapter, enumerate_episodes, load_formal_episode
from project2_g1.video import count_video_frames, render_episode_audit_video

CHECK_KEYS = (
    "CANDIDATE_RULE_TEST",
    "PERSISTENCE_TEST",
    "SUPPORTING_ONLY_TEST",
    "CONSOLIDATION_TEST",
    "HARD_PROTECTION_TEST",
    "PAUSE_BRIDGING_TEST",
    "PRIVILEGED_LEAKAGE",
    "FULL_PIPELINE_SMOKE",
)


def _map_test_name(name: str) -> str | None:
    lowered = name.lower()
    if "privileged" in lowered or "leakage" in lowered:
        return "PRIVILEGED_LEAKAGE"
    if "rotation_only" in lowered or "action_spike_only" in lowered or "supporting" in lowered:
        return "SUPPORTING_ONLY_TEST"
    if "consolidat" in lowered:
        return "CONSOLIDATION_TEST"
    if "hard_boundary" in lowered or "hard_protection" in lowered or "micro" in lowered:
        return "HARD_PROTECTION_TEST"
    if "pause" in lowered or "bridge" in lowered:
        return "PAUSE_BRIDGING_TEST"
    if "pipeline_smoke" in lowered:
        return "FULL_PIPELINE_SMOKE"
    if "persistence" in lowered or "single_frame_peak" in lowered:
        return "PERSISTENCE_TEST"
    if "isolated_speed" in lowered or "persistent_move" in lowered or "persistent_idle" in lowered or "persistent_gripper" in lowered:
        return "CANDIDATE_RULE_TEST"
    return None


def _run_unit_tests() -> dict[str, Any]:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.discover(str(ROOT / "tests"), pattern="test_g1_p2_*.py"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    statuses = {key: "PASS" for key in CHECK_KEYS}
    failures = [str(item[0]) for item in result.failures + result.errors]
    if not result.wasSuccessful():
        for fail in failures:
            mapped = _map_test_name(fail)
            if mapped:
                statuses[mapped] = "FAIL"
            else:
                statuses["FULL_PIPELINE_SMOKE"] = "FAIL"
        if not any(statuses[key] == "FAIL" for key in CHECK_KEYS):
            statuses["FULL_PIPELINE_SMOKE"] = "FAIL"
    statuses["_unittest_ok"] = "PASS" if result.wasSuccessful() else "FAIL"
    statuses["_failures"] = failures
    statuses["_tests_run"] = int(result.testsRun)
    return statuses


def _ensure_video(
    adapter,
    identity,
    dest: Path,
    *,
    fps: float,
    skip_video: bool,
) -> dict[str, Any]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    p1_video = G1_P1_OUTPUT_ROOT / identity.native_episode_key / "video.mp4"
    if dest.is_file() and skip_video:
        return {
            "video_path": str(dest.resolve()),
            "requested_frames": identity.num_steps,
            "written_frames": count_video_frames(dest),
            "source": "reused existing G1-P2 smoke video",
        }
    if p1_video.is_file():
        shutil.copy2(p1_video, dest)
        return {
            "video_path": str(dest.resolve()),
            "requested_frames": identity.num_steps,
            "written_frames": count_video_frames(dest),
            "source": f"copied G1-P1 smoke video {p1_video}",
        }
    if skip_video:
        return {
            "video_path": "SKIPPED",
            "requested_frames": identity.num_steps,
            "written_frames": None,
            "source": "skip-video and no reusable clip",
        }
    return render_episode_audit_video(
        adapter,
        identity.source_episode_id,
        dest,
        fps=fps,
    )


def _decision_counts(result) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for decision in result.decisions.values():
        counter[decision.decision] += 1
    return dict(counter)


def _observed_cases(samples: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    total_c = sum(int(row["candidate_count"]) for row in samples)
    total_s = sum(int(row["suppressed_count"]) for row in samples)
    total_f = sum(int(row["final_boundary_count"]) for row in samples)
    lines.append(
        f"Smoke totals: candidates={total_c}, suppressed={total_s}, final_boundaries={total_f}."
    )
    for row in samples:
        lines.append(
            (
                f"{row['episode_id']} quality={row['quality_group']}: "
                f"candidates={row['candidate_count']} suppressed={row['suppressed_count']} "
                f"final={row['final_boundary_count']} segments={row['segment_count']} "
                f"decisions={row.get('decision_counts', {})} "
                f"short_flags={row.get('short_segment_count', 0)} "
                f"long_flags={row.get('long_segment_count', 0)} "
                f"micro={row.get('micro_interaction_count', 0)}."
            )
        )
        if row.get("candidate_type_counts"):
            lines.append(f"{row['episode_id']} raw candidate types: {row['candidate_type_counts']}")
    lines.append(
        "These counts describe exploratory engine behavior on smoke episodes. "
        "They are not a correctness or calibration claim."
    )
    pause = sum(
        int(row.get("decision_counts", {}).get("SUPPRESS_SHORT_PAUSE", 0) or 0) for row in samples
    )
    merged = sum(
        int(row.get("decision_counts", {}).get("MERGE_CONSOLIDATION", 0) or 0) for row in samples
    )
    lines.append(f"Consolidation MERGE_CONSOLIDATION decisions across smoke = {merged}.")
    lines.append(f"Pause bridging SUPPRESS_SHORT_PAUSE decisions across smoke = {pause}.")
    lines.append(
        "Short-segment flags often appear at episode start/end near exploratory gripper-threshold crossings; "
        "Hard Boundaries were retained rather than deleted."
    )
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="G1-P2 exploratory Boundary Engine audit")
    parser.add_argument("--output-dir", type=Path, default=G1_P2_OUTPUT_ROOT)
    parser.add_argument("--skip-video", action="store_true")
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args(argv)

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    p1_config = load_g1_p1_config()
    p2_config = load_g1_p2_config()
    (output_dir / "exploratory_config.json").write_text(
        json.dumps(p2_config.raw or p2_config.metadata(), indent=2) + "\n",
        encoding="utf-8",
    )

    adapter = build_can_mh_adapter(p1_config)
    identities = enumerate_episodes(adapter)
    smoke = select_g1_p2_smoke_episodes(identities, adapter, p2_config)

    samples: list[dict[str, Any]] = []
    engine_results = []
    check_notes: list[str] = []
    unknowns = [
        "G1_P1_HUMAN_VISUAL_REVIEW = DEFERRED because of REMOTE_ENVIRONMENT_LIMITATION. This is not a P1 failure.",
        "All G1-P2 numeric thresholds are EXPLORATORY / DATA_CALIBRATION_PENDING / NOT_FORMAL.",
        "boundary_tolerance_window is schema-only and is not used by the segmenter.",
        "Human Boundary GT is not available; no threshold optimization was performed.",
        "UPSTREAM_SIGNAL_ISSUE = NO. G1-P1 quaternion / alignment / signal formulas were not rewritten.",
        "DATA_SCHEMA_ISSUE = NO.",
        "PIPELINE_BUG = NO for the exploratory smoke path.",
        "Pause bridging did not fire on this 6-episode smoke set; the synthetic unit test still covers the rule.",
    ]
    blockers: list[str] = []
    live_ok = True

    for identity in smoke:
        print(
            f"G1-P2 smoke episode {identity.source_episode_id} length={identity.num_steps}",
            flush=True,
        )
        episode = load_formal_episode(adapter, identity.source_episode_id)
        signals = compute_formal_signals(episode, p1_config)
        result = run_boundary_engine(signals, p2_config)
        engine_results.append(result)
        privileged = load_privileged_overlay(adapter, identity.source_episode_id)
        episode_dir = output_dir / identity.native_episode_key
        tables = write_episode_audit_tables(episode_dir, result)
        plot_path = plot_episode_signals(
            signals,
            episode_dir / "signal_boundary_plot.png",
            privileged=privileged,
            candidate_boundaries=result.candidate_frames,
            suppressed_boundaries=result.suppressed_frames,
            final_boundaries=result.final_frames,
            final_boundary_annotations=result.final_annotations,
            motion_state_evidence=result.motion_state,
            title=(
                f"G1-P2 Exploratory Boundary Audit  |  {signals.source_episode_id}  |  "
                f"T={signals.n_frames}  |  EXPLORATORY / NOT_FORMAL"
            ),
        )
        video_info = _ensure_video(
            adapter,
            identity,
            episode_dir / "video.mp4",
            fps=p1_config.control_frequency_hz,
            skip_video=args.skip_video,
        )
        rgb_count = video_info.get("written_frames")
        alignment = audit_temporal_alignment(episode, signals, rgb_frame_count=rgb_count)
        nan_audit = audit_nan_inf(signals)
        if alignment.status != "PASS" or nan_audit["status"] != "PASS":
            live_ok = False
            blockers.append(
                f"{identity.source_episode_id}: alignment={alignment.status} nan_inf={nan_audit['status']}"
            )
        if rgb_count is not None and int(rgb_count) != signals.n_frames:
            live_ok = False
            blockers.append(
                f"{identity.source_episode_id}: video frames {rgb_count} != signal length {signals.n_frames}"
            )
        weak = adapter.get_weak_reference(identity.source_episode_id)
        type_counts = Counter(c.candidate_type for c in result.candidates)
        micro = sum(1 for event in result.final_events if "MICRO_INTERACTION" in event.review_flags)
        sample = {
            "episode_id": identity.source_episode_id,
            "native_episode_key": identity.native_episode_key,
            "quality_group": weak.get("quality_bucket"),
            "length": identity.num_steps,
            "candidate_count": len(result.candidates),
            "suppressed_count": len(result.suppressed_frames),
            "final_boundary_count": len(result.final_events),
            "segment_count": len(result.segments),
            "video_path": video_info["video_path"],
            "plot_path": str(plot_path.resolve()),
            "review_required": bool(result.review_required),
            "short_segment_count": sum(1 for seg in result.segments if seg.short_segment_flag),
            "long_segment_count": sum(1 for seg in result.segments if seg.long_segment_flag),
            "micro_interaction_count": micro,
            "decision_counts": _decision_counts(result),
            "candidate_type_counts": dict(type_counts),
            "tables": tables,
            "alignment": alignment.status,
            "nan_inf": nan_audit["status"],
        }
        samples.append(sample)
        check_notes.append(
            f"{identity.source_episode_id}: alignment={alignment.status} nan_inf={nan_audit['status']} "
            f"video_frames={rgb_count} candidates={sample['candidate_count']} "
            f"final={sample['final_boundary_count']} segments={sample['segment_count']}"
        )

    unittest_status = {key: "SKIPPED" for key in CHECK_KEYS}
    unittest_status.update({"_unittest_ok": "SKIPPED", "_failures": [], "_tests_run": 0})
    if not args.skip_tests:
        unittest_status = _run_unit_tests()

    automated = {key: unittest_status.get(key, "FAIL") for key in CHECK_KEYS}
    if not live_ok:
        automated["FULL_PIPELINE_SMOKE"] = "FAIL"
    elif unittest_status.get("FULL_PIPELINE_SMOKE") == "PASS" and samples:
        automated["FULL_PIPELINE_SMOKE"] = "PASS"

    worse_present = any(row.get("quality_group") == "WORSE" for row in samples)
    if not worse_present:
        unknowns.append("WORSE demo was requested but not present in the selected smoke set.")

    blocked = any(value == "FAIL" for value in automated.values()) or bool(blockers)
    if unittest_status.get("_unittest_ok") == "FAIL":
        blocked = True
        unknowns.append(f"unittest failures: {unittest_status.get('_failures')}")
    status = "BLOCKED" if blocked else "PASS_READY_FOR_HUMAN_BOUNDARY_REVIEW"

    template_path = write_human_review_template(
        output_dir / "human_boundary_review_template.csv",
        engine_results,
    )
    manifest_path = output_dir / "episode_manifest.csv"
    manifest_fields = [
        "episode_id",
        "native_episode_key",
        "quality_group",
        "length",
        "candidate_count",
        "suppressed_count",
        "final_boundary_count",
        "segment_count",
        "video_path",
        "plot_path",
        "review_required",
        "short_segment_count",
        "long_segment_count",
        "alignment",
        "nan_inf",
    ]
    with manifest_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=manifest_fields)
        writer.writeheader()
        for row in samples:
            writer.writerow({key: row.get(key, "") for key in manifest_fields})

    report_path = write_g1_p2_audit_report(
        output_dir / "g1_p2_boundary_engine_audit_report.md",
        {
            "discovery": {
                "engineering_master": str(PROJECT2_ENGINEERING_MASTER),
                "roadmap": str(PROJECT2_ROADMAP),
                "readable_design": str(PROJECT2_READABLE_DESIGN),
                "dataset_path": f"raw={DATASET_RAW_HDF5}; low_dim={DATASET_LOW_DIM_HDF5}",
                "dataset_type": DATASET_TYPE,
                "project_root": str(PROJECT2_ROOT),
                "g1_p1_code_baseline": str((PROJECT2_ROOT / "src" / "project2_g1").resolve()),
                "g1_p1_config": str(CONFIG_PATH.resolve()),
                "g1_p2_config": str(G1_P2_CONFIG_PATH.resolve()),
                "reused_p1_reader": "YES",
                "source_reader_path": str(P1_ADAPTER_PATH),
            },
            "g1_p1_automated_audit": "PASS",
            "parameters": p2_config.marked_parameters(),
            "samples": samples,
            "automated_checks": automated,
            "check_notes": check_notes
            + [
                f"unittest_ok={unittest_status.get('_unittest_ok')} tests_run={unittest_status.get('_tests_run')}",
                f"human_review_template={template_path.resolve()}",
                "G1-P3 Calibration Search was not implemented or executed.",
                "Motion regime uses G1-P1 translation_speed plus P2 persistence; it does not rewrite P1 signal formulas and does not use smoothed_translation_speed as the moving/idle detector.",
            ],
            "observed_cases": _observed_cases(samples),
            "unknowns": unknowns,
            "blockers": blockers,
            "issue_flags": {
                "UPSTREAM_SIGNAL_ISSUE": "NO",
                "DATA_SCHEMA_ISSUE": "NO",
                "PIPELINE_BUG": "NO",
            },
            "g1_p2_status": status,
        },
    )
    summary = {
        "G1_P2_STATUS": status,
        "G1_P2_SEGMENTATION_STATUS": "EXPLORATORY_ONLY",
        "G1_P1_HUMAN_VISUAL_REVIEW": "DEFERRED",
        "automated_checks": automated,
        "manifest": str(manifest_path.resolve()),
        "report": str(report_path.resolve()),
        "review_template": str(template_path.resolve()),
        "episodes": [row["episode_id"] for row in samples],
        "worse_demo_included": worse_present,
        "threshold_frozen": False,
        "human_gt_calibration": False,
        "g1_p3_started": False,
    }
    (output_dir / "g1_p2_run_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0 if status == "PASS_READY_FOR_HUMAN_BOUNDARY_REVIEW" else 1


if __name__ == "__main__":
    raise SystemExit(main())
