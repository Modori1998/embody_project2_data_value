"""CLI: G1-P1 Signal Contract + Audit Harness smoke run.

Does not implement Boundary Engine / segmentation.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from project2_g1.alignment import audit_nan_inf, audit_temporal_alignment
from project2_g1.config import load_g1_p1_config
from project2_g1.paths import (
    DATASET_LOW_DIM_HDF5,
    DATASET_RAW_HDF5,
    DATASET_TYPE,
    OUTPUT_ROOT,
    P1_ADAPTER_PATH,
    PROJECT1_ROOT,
    PROJECT2_ENGINEERING_MASTER,
    PROJECT2_READABLE_DESIGN,
    PROJECT2_ROADMAP,
    PROJECT2_ROOT,
)
from project2_g1.plot import plot_episode_signals
from project2_g1.privileged_audit import load_privileged_overlay
from project2_g1.report import write_audit_report
from project2_g1.signals import compute_formal_signals
from project2_g1.smoke import select_smoke_episodes
from project2_g1.source import (
    build_can_mh_adapter,
    enumerate_episodes,
    inspect_source_schema,
    load_formal_episode,
)
from project2_g1.video import render_episode_audit_video


def _run_unit_tests() -> dict[str, str]:
    loader = unittest.TestLoader()
    suite = loader.discover(str(ROOT / "tests"), pattern="test_g1_p1_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    ok = result.wasSuccessful()
    mapping = {
        "test_quaternion_sign_invariance": "QUATERNION_SIGN_INVARIANCE",
        "test_temporal_alignment": "TEMPORAL_ALIGNMENT",
        "test_privileged_leakage": "PRIVILEGED_LEAKAGE",
        "test_numerical_quality": "NAN_INF_CHECK",
    }
    statuses = {name: "PASS" if ok else "FAIL" for name in mapping.values()}
    failures = [str(item[0]) for item in result.failures + result.errors]
    for fail in failures:
        for needle, key in mapping.items():
            if needle in fail:
                statuses[key] = "FAIL"
    statuses["_unittest_ok"] = "PASS" if ok else "FAIL"
    statuses["_failures"] = failures
    return statuses


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="G1-P1 Signal Contract + Audit Harness")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--skip-video", action="store_true")
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args(argv)

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    config = load_g1_p1_config()
    adapter = build_can_mh_adapter(config)
    identities = enumerate_episodes(adapter)
    smoke = select_smoke_episodes(identities, config)
    schema = inspect_source_schema(adapter, smoke[0].native_episode_key)

    samples = []
    catalog = None
    alignment_pass = True
    nan_pass = True
    video_align_pass = True
    check_notes = []
    unknowns = [
        "Can/MH raw/low_dim have no stored RGB; smoke video is freshly rendered from STATE_t via P1 renderer, not an upstream pre-encoded episode mp4.",
        "Recorded action remains NORMALIZED_CONTROLLER_INPUT. Adapter documents OSC_POSE output scales (0.05 m / 0.5 rad) as controller maps; this phase does not claim the HDF5 action stream is already physical velocity.",
        "OPEN/CLOSED gripper threshold and moving/stationary threshold are DATA_CALIBRATION_PENDING. motion_state_candidate is exploratory only.",
        "Packed obs/object layout [7:10]=Can_pos follows P1 M07 reconstruction; named Can_* keys are absent from HDF5.",
        "demo_64 length=1050 exists and was excluded from smoke by max_smoke_length_frames=400 to avoid large materialize.",
    ]

    for identity in smoke:
        print(
            f"G1-P1 smoke episode {identity.source_episode_id} length={identity.num_steps}",
            flush=True,
        )
        episode = load_formal_episode(adapter, identity.source_episode_id)
        signals = compute_formal_signals(episode, config)
        if catalog is None:
            catalog = signals.catalog
        privileged = load_privileged_overlay(adapter, identity.source_episode_id)
        episode_dir = output_dir / identity.native_episode_key
        episode_dir.mkdir(parents=True, exist_ok=True)
        plot_path = plot_episode_signals(
            signals,
            episode_dir / "signal_plot.png",
            privileged=privileged,
            candidate_boundaries=None,
            suppressed_boundaries=None,
            final_boundaries=None,
        )
        video_info = {
            "video_path": "SKIPPED",
            "requested_frames": signals.n_frames,
            "written_frames": None,
        }
        existing_video = episode_dir / "video.mp4"
        if args.skip_video and existing_video.is_file():
            from project2_g1.video import count_video_frames

            video_info = {
                "video_path": str(existing_video.resolve()),
                "requested_frames": signals.n_frames,
                "written_frames": count_video_frames(existing_video),
                "source": "reused existing smoke video",
            }
        elif not args.skip_video:
            video_info = render_episode_audit_video(
                adapter,
                identity.source_episode_id,
                episode_dir / "video.mp4",
                fps=config.control_frequency_hz,
            )
        rgb_count = video_info.get("written_frames")
        alignment = audit_temporal_alignment(episode, signals, rgb_frame_count=rgb_count)
        nan_audit = audit_nan_inf(signals)
        if alignment.status != "PASS":
            alignment_pass = False
        if nan_audit["status"] != "PASS":
            nan_pass = False
        if rgb_count is not None and int(rgb_count) != signals.n_frames:
            video_align_pass = False
        issues = []
        if alignment.status != "PASS":
            issues.append({"alignment": alignment.checks})
        if nan_audit["issues"]:
            issues.extend(nan_audit["issues"])
        if rgb_count is not None and int(rgb_count) != signals.n_frames:
            issues.append(
                f"video frames {rgb_count} != signal length {signals.n_frames}"
            )
        weak = adapter.get_weak_reference(identity.source_episode_id)
        split = adapter.get_split_membership(identity.source_episode_id)
        samples.append(
            {
                "episode_id": identity.source_episode_id,
                "native_episode_key": identity.native_episode_key,
                "length": identity.num_steps,
                "video_path": video_info["video_path"],
                "signal_plot_path": str(plot_path.resolve()),
                "weak_reference": weak.get("quality_bucket"),
                "split": split.get("split_role"),
                "issues": issues or ["none"],
                "alignment": alignment.status,
                "nan_inf": nan_audit["status"],
            }
        )
        check_notes.append(
            f"{identity.source_episode_id}: alignment={alignment.status} nan_inf={nan_audit['status']} "
            f"video_frames={rgb_count}"
        )

    unittest_status = {
        "QUATERNION_SIGN_INVARIANCE": "SKIPPED",
        "PRIVILEGED_LEAKAGE": "SKIPPED",
        "_unittest_ok": "SKIPPED",
        "_failures": [],
    }
    if not args.skip_tests:
        unittest_status = _run_unit_tests()

    automated = {
        "QUATERNION_SIGN_INVARIANCE": unittest_status.get("QUATERNION_SIGN_INVARIANCE", "FAIL"),
        "TEMPORAL_ALIGNMENT": "PASS" if alignment_pass and unittest_status.get("TEMPORAL_ALIGNMENT") != "FAIL" else "FAIL",
        "PRIVILEGED_LEAKAGE": unittest_status.get("PRIVILEGED_LEAKAGE", "FAIL"),
        "NAN_INF_CHECK": "PASS" if nan_pass and unittest_status.get("NAN_INF_CHECK") != "FAIL" else "FAIL",
        "VIDEO_SIGNAL_FRAME_ALIGNMENT": (
            "PASS"
            if video_align_pass and any(row.get("video_path") not in ("SKIPPED", None) for row in samples)
            else ("SKIPPED" if args.skip_video else "FAIL")
        ),
    }
    blocked = any(value == "FAIL" for value in automated.values())
    if unittest_status.get("_unittest_ok") == "FAIL":
        blocked = True
        unknowns.append(f"unittest failures: {unittest_status.get('_failures')}")
    status = "BLOCKED" if blocked else "PASS_READY_FOR_USER_REVIEW"

    manifest_path = output_dir / "episode_manifest.csv"
    with manifest_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "episode_id",
                "native_episode_key",
                "length",
                "video_path",
                "signal_plot_path",
                "weak_reference",
                "split",
                "alignment",
                "nan_inf",
                "issues",
            ],
        )
        writer.writeheader()
        for row in samples:
            writer.writerow({key: row[key] if key != "issues" else json.dumps(row["issues"]) for key in writer.fieldnames})

    report_path = write_audit_report(
        output_dir / "g1_p1_signal_contract_audit_report.md",
        {
            "discovery": {
                "engineering_master": str(PROJECT2_ENGINEERING_MASTER),
                "roadmap": str(PROJECT2_ROADMAP),
                "readable_design": str(PROJECT2_READABLE_DESIGN),
                "dataset_path": f"raw={DATASET_RAW_HDF5}; low_dim={DATASET_LOW_DIM_HDF5}",
                "dataset_type": DATASET_TYPE,
                "project_root": str(PROJECT2_ROOT),
                "reused_p1_reader": "YES",
                "source_reader_path": str(P1_ADAPTER_PATH),
                "episode_count": len(identities),
            },
            "schema": schema,
            "signal_catalog": catalog or [],
            "samples": samples,
            "automated_checks": automated,
            "check_notes": check_notes
            + [
                f"P1 root reused: {PROJECT1_ROOT}",
                f"unittest_ok={unittest_status.get('_unittest_ok')}",
            ],
            "unknowns": unknowns,
            "g1_p1_status": status,
        },
    )
    summary = {
        "G1_P1_STATUS": status,
        "automated_checks": automated,
        "manifest": str(manifest_path.resolve()),
        "report": str(report_path.resolve()),
        "episodes": [row["episode_id"] for row in samples],
        "boundary_engine_implemented": False,
    }
    (output_dir / "g1_p1_run_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0 if status == "PASS_READY_FOR_USER_REVIEW" else 1


if __name__ == "__main__":
    raise SystemExit(main())
