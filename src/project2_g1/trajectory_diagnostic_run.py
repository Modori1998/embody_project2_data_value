"""Materialize the blinded G1-P3 Trajectory Mechanism Diagnostic Set as an
immutable ``DESIGN_DIAGNOSTIC`` G1 Human Audit Web run.

Additive only. This module:

* consumes the frozen Detector / Formal Signal semantics without modifying them;
* never re-selects, re-ranks or re-matches the Diagnostic Set — the single
  source of truth for the 20 events is ``03_selection_blinded.csv``;
* treats blinding as a hard gate: no reviewer-facing artifact may carry
  Arm A/B, P12, C12, coherence, target/control, pair_id, match_distance or
  selection_reason;
* writes nothing except the new immutable Audit Run folder.

Each selected event becomes exactly one reviewable Final Boundary. The frozen
Detector's candidate / decision / segment tables are copied verbatim as context;
only ``final_boundaries.csv`` is restricted to the single diagnostic event.
"""

from __future__ import annotations

import csv
import json
import re
import shutil
import tempfile
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from project2_g1_audit_web.contract import (
    CONTRACT_VERSION,
    DESIGN_DIAGNOSTIC_RUN_STAGE,
    DESIGN_DIAGNOSTIC_SET_ROLE,
    blocked_downstreams,
    validate_g1_audit_folder,
)
from project2_g1_audit_web.hashes import (
    SIGNAL_CONTRACT_VERSION,
    allocate_run_id,
    config_hash_from_path,
    now_iso,
    signal_contract_hash_from_path,
)
from project2_g1_audit_web.registry import auto_register

from .alignment import audit_nan_inf, audit_temporal_alignment
from .boundary_config import load_g1_p2_config
from .boundary_engine import BoundaryEvent, EngineResult, run_boundary_engine
from .boundary_io import write_episode_audit_tables
from .config import load_g1_p1_config
from .paths import CONFIG_PATH, DATASET_RAW_HDF5, G1_P2_CONFIG_PATH
from .plot import plot_episode_signals
from .signals import compute_formal_signals
from .source import build_can_mh_adapter, enumerate_episodes, load_formal_episode
from .video import count_video_frames, render_episode_audit_video

EXPECTED_CONFIG_HASH = "dde590e759a31cb8c865369e18256ebecbbd01bc94a58e1d3ca695bb50f2a630"
EXPECTED_SIGNAL_HASH = "24c62aef1f7bdbd14f0c1a075e8ecaafa762d4bcce454ad25842d54a2f34232d"
SOURCE_DATASET_ID = "robomimic_v15_can_mh"

BLINDED_MANIFEST_RELPATH = (
    "0-doc/80-audit-local/g1_p3_trajectory_mechanism_validation/03_selection_blinded.csv"
)
EXPECTED_EVENT_COUNT = 20
EXPECTED_DISTINCT_EPISODES = 20

# Rendered episode videos are expensive and fully deterministic per episode, so
# they live in a validated cache outside the immutable run folder. A build that
# is interrupted can therefore resume without re-rendering finished episodes.
MEDIA_CACHE_RELPATH = "outputs/g1_audit_web/diagnostic_media_cache"
MEDIA_RENDER_WORKERS = 3

BLINDED_COLUMNS = (
    "diagnostic_event_id",
    "episode_id",
    "boundary_id",
    "event_frame",
    "event_type",
    "representative_candidate_id",
    "member_candidate_ids",
    "diagnostic_set_id",
)

# Reviewer-facing payload must never contain these. ``VALID`` / ``REDUNDANT`` /
# ``MISALIGNED`` are legitimate review labels and are deliberately absent.
BLINDING_FORBIDDEN_TOKENS = frozenset(
    {
        "arm",
        "p12",
        "c12",
        "coherence",
        "target",
        "control",
        "pair_id",
        "match_distance",
        "selection_reason",
        "expected",
    }
)
# Existing frozen Detector vocabulary that legitimately contains a token above.
BLINDING_ALLOWED_IDENTIFIERS = frozenset({"target_boundary_id"})

MANIFEST_FIELDS = (
    "run_id", "episode_id", "native_episode_key", "demo_key", "source_hdf5",
    "source_dataset_id", "set_role", "config_hash", "signal_contract_version",
    "signal_contract_hash", "video_relpath", "plot_relpath", "signal_plot_relpath",
    "candidates_relpath", "boundaries_relpath", "segments_relpath", "smoke_relpath",
    "quality_group", "review_required", "length", "candidate_count",
    "suppressed_count", "final_boundary_count", "segment_count",
    "short_segment_count", "long_segment_count", "cluster_count",
    "deactivated_candidate_count", "keep_count", "merge_count",
    "retain_hard_count", "alignment", "nan_inf",
)

# Reviewer-facing text artifacts inside the run folder.
AUDITED_RUN_FILES = ("run_meta.json", "episode_manifest.csv", "human_boundary_review_codebook.json")


class TrajectoryDiagnosticRunError(ValueError):
    """Fail-fast: the Diagnostic Set could not be materialized faithfully."""


def _fail(message: str) -> None:
    raise TrajectoryDiagnosticRunError(message)


# --------------------------------------------------------------------------
# Blinding audit
# --------------------------------------------------------------------------


def blinding_violations(text: Any) -> list[str]:
    """Forbidden design tokens found in a reviewer-facing payload fragment."""

    lowered = str(text or "").lower()
    found: set[str] = set()
    for word in set(re.findall(r"[a-z0-9_]+", lowered)):
        if word in BLINDING_ALLOWED_IDENTIFIERS:
            continue
        if word in BLINDING_FORBIDDEN_TOKENS:
            found.add(word)
            continue
        for segment in word.split("_"):
            if segment in BLINDING_FORBIDDEN_TOKENS:
                found.add(f"{word}::{segment}")
    return sorted(found)


def audit_blinding_rows(rows: Iterable[Mapping[str, Any]], *, source: str = "") -> list[str]:
    """Blinding violations across both column names and cell values."""

    violations: list[str] = []
    for row in rows:
        for key, value in row.items():
            for hit in blinding_violations(key):
                violations.append(f"{source}: column {key!r} -> {hit}")
            for hit in blinding_violations(value):
                violations.append(f"{source}: value of {key!r} -> {hit}")
    return violations


def audit_blinding_text(text: str, *, source: str = "") -> list[str]:
    return [f"{source}: {hit}" for hit in blinding_violations(text)]


def audit_blinding_run_folder(run_root: str | Path) -> list[str]:
    """Scan every text artifact in a materialized run folder for leakage."""

    root = Path(run_root)
    violations: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() in {".png", ".mp4", ".jpg", ".jpeg", ".gif"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rel = path.relative_to(root).as_posix()
        violations.extend(audit_blinding_text(text, source=rel))
    return sorted(set(violations))


# --------------------------------------------------------------------------
# Frozen inputs
# --------------------------------------------------------------------------


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, fields: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_blinded_manifest(path: str | Path) -> list[dict[str, str]]:
    """Read and hard-validate the frozen blinded manifest."""

    manifest = Path(path)
    if not manifest.is_file():
        _fail(f"blinded manifest missing: {manifest}")
    with manifest.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = tuple(reader.fieldnames or ())
        rows = list(reader)
    if fieldnames != BLINDED_COLUMNS:
        _fail(f"blinded manifest columns changed: {fieldnames!r}")
    if len(rows) != EXPECTED_EVENT_COUNT:
        _fail(f"blinded manifest must hold {EXPECTED_EVENT_COUNT} events, got {len(rows)}")

    event_ids = [row["diagnostic_event_id"] for row in rows]
    if len(set(event_ids)) != len(event_ids):
        _fail("duplicate diagnostic_event_id in blinded manifest")
    boundary_ids = [row["boundary_id"] for row in rows]
    if len(set(boundary_ids)) != len(boundary_ids):
        _fail("duplicate boundary_id in blinded manifest")
    episodes = [row["episode_id"] for row in rows]
    if len(set(episodes)) != EXPECTED_DISTINCT_EPISODES:
        _fail(
            "blinded manifest must hold "
            f"{EXPECTED_DISTINCT_EPISODES} distinct episodes, got {len(set(episodes))}"
        )
    set_ids = {row["diagnostic_set_id"] for row in rows}
    if len(set_ids) != 1:
        _fail(f"blinded manifest must reference one diagnostic_set_id, got {sorted(set_ids)}")
    for row in rows:
        if not row["representative_candidate_id"].strip():
            _fail(f"{row['diagnostic_event_id']}: empty representative_candidate_id")
        try:
            int(row["event_frame"])
        except (TypeError, ValueError):
            _fail(f"{row['diagnostic_event_id']}: event_frame is not an integer")

    violations = audit_blinding_rows(rows, source=manifest.name)
    if violations:
        _fail("BLINDING_CONTRACT_FAILED on blinded manifest: " + " | ".join(violations))
    return rows


def verify_frozen_identity(root: Path) -> dict[str, str]:
    config_hash = config_hash_from_path(root / "configs" / G1_P2_CONFIG_PATH.name)
    signal_hash = signal_contract_hash_from_path(root / "configs" / CONFIG_PATH.name)
    if config_hash != EXPECTED_CONFIG_HASH:
        _fail(f"baseline config hash mismatch: {config_hash}")
    if signal_hash != EXPECTED_SIGNAL_HASH:
        _fail(f"signal contract hash mismatch: {signal_hash}")
    return {"config_hash": config_hash, "signal_contract_hash": signal_hash}


def select_diagnostic_event(result: EngineResult, row: Mapping[str, str]) -> BoundaryEvent:
    """Locate the frozen selected Final Boundary; fail fast on any drift."""

    boundary_id = str(row["boundary_id"])
    wanted_frame = int(row["event_frame"])
    wanted_rep = str(row["representative_candidate_id"])
    wanted_members = str(row["member_candidate_ids"])
    for event in result.final_events:
        if event.boundary_id != boundary_id:
            continue
        if int(event.frame) != wanted_frame:
            _fail(f"{boundary_id}: frame drift {event.frame} != {wanted_frame}")
        if str(event.representative_candidate_id) != wanted_rep:
            _fail(
                f"{boundary_id}: representative drift "
                f"{event.representative_candidate_id} != {wanted_rep}"
            )
        if "|".join(str(item) for item in event.member_candidate_ids) != wanted_members:
            _fail(f"{boundary_id}: member lineage drift")
        if str(event.candidate_type) != str(row["event_type"]):
            _fail(f"{boundary_id}: candidate_type drift {event.candidate_type!r}")
        return event
    _fail(
        f"{boundary_id}: selected boundary is not a Final Boundary of {result.episode_id}"
    )
    raise AssertionError("unreachable")


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------


def _video_frame_count(path: Path) -> int | None:
    """Frame count of an existing video, or None when unreadable/incomplete."""

    try:
        return int(count_video_frames(path))
    except Exception:  # noqa: BLE001 - any decode failure means "not usable"
        return None


def _render_video_worker(
    project_root: str,
    episode_id: str,
    video_path: str,
    fps: float,
    expected_frames: int | None = None,
) -> dict[str, Any]:
    """Isolated renderer process; avoids sharing MuJoCo/OpenGL contexts.

    When ``expected_frames`` is given the target is treated as an idempotent
    media-cache entry: an entry whose frame count already matches is reused
    verbatim, otherwise the render is staged to ``*.part.mp4`` and atomically
    moved into place. When it is omitted (legacy call shape) the video is
    rendered straight to ``video_path`` and validated by the caller.
    """

    root = Path(project_root)
    target = Path(video_path)

    if expected_frames is None:
        target.parent.mkdir(parents=True, exist_ok=True)
        return render_episode_audit_video(
            build_can_mh_adapter(load_g1_p1_config(root / "configs" / CONFIG_PATH.name)),
            episode_id,
            target,
            fps=fps,
        )

    expected = int(expected_frames)
    if target.is_file() and _video_frame_count(target) == expected:
        return {"cached": True, "written_frames": expected, "video_path": str(target)}

    config = load_g1_p1_config(root / "configs" / CONFIG_PATH.name)
    adapter = build_can_mh_adapter(config)
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_name(f"{target.stem}.part{target.suffix}")
    if part.exists():
        part.unlink()
    info = render_episode_audit_video(adapter, episode_id, part, fps=fps)
    observed = _video_frame_count(part)
    if int(info["written_frames"]) != expected or observed != expected:
        raise TrajectoryDiagnosticRunError(
            f"{episode_id}: video frames={observed} expected={expected}"
        )
    part.replace(target)
    return {**info, "cached": False, "video_path": str(target)}


def build_trajectory_diagnostic_run(
    *,
    project_root: str | Path,
    blinded_manifest_path: str | Path | None = None,
    registry_path: str | Path,
    runs_root: str | Path,
    owner_db_path: str | Path | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    manifest_path = Path(blinded_manifest_path or (root / BLINDED_MANIFEST_RELPATH))
    rows = load_blinded_manifest(manifest_path)
    identity = verify_frozen_identity(root)
    config_hash = identity["config_hash"]
    signal_hash = identity["signal_contract_hash"]
    diagnostic_set_id = str(rows[0]["diagnostic_set_id"])

    p1_config = load_g1_p1_config(root / "configs" / CONFIG_PATH.name)
    p2_config = load_g1_p2_config(root / "configs" / G1_P2_CONFIG_PATH.name)

    stamp = created_at or now_iso()
    run_id = allocate_run_id(
        run_stage=DESIGN_DIAGNOSTIC_RUN_STAGE,
        config_hash=config_hash,
        created_at=stamp,
        salt=diagnostic_set_id,
    )
    final_root = Path(runs_root).resolve() / run_id
    if final_root.exists():
        _fail(f"immutable run already exists: {final_root}")
    Path(runs_root).mkdir(parents=True, exist_ok=True)

    adapter = build_can_mh_adapter(p1_config)
    catalog = {item.source_episode_id: item for item in enumerate_episodes(adapter)}
    missing = sorted({row["episode_id"] for row in rows} - set(catalog))
    if missing:
        _fail(f"diagnostic episodes missing from dataset: {missing}")

    manifest_rows: list[dict[str, Any]] = []
    selected_frames: dict[str, int] = {}
    video_expected: dict[str, tuple[Path, int]] = {}
    video_cache: dict[str, tuple[Path, int]] = {}

    with tempfile.TemporaryDirectory(prefix=f".{run_id}.staging-", dir=Path(runs_root)) as temp_name:
        staging = Path(temp_name)
        shutil.copyfile(root / "configs" / G1_P2_CONFIG_PATH.name, staging / "config_snapshot.json")
        codebook_src = root / "outputs" / "g1_audit_runs" / "g1_exploratory_audit_20260917_141541_fe251439" / "human_boundary_review_codebook.json"
        if not codebook_src.is_file():
            codebook_src = root / "outputs" / "g1_p2_boundary_audit" / "human_boundary_review_codebook.json"
        shutil.copyfile(codebook_src, staging / "human_boundary_review_codebook.json")

        for row in rows:
            episode_id = str(row["episode_id"])
            identity_row = catalog[episode_id]
            native = identity_row.native_episode_key
            episode = load_formal_episode(adapter, episode_id)
            signals = compute_formal_signals(episode, p1_config)
            result = run_boundary_engine(signals, p2_config)

            selected = select_diagnostic_event(result, row)
            selected_frames[episode_id] = int(selected.frame)
            # Restrict only the review target list; keep the frozen Detector's
            # candidate / decision / segment tables as context.
            restricted = replace(result, events=[selected])

            diagnostic = staging / "diagnostic" / native
            tables = write_episode_audit_tables(diagnostic, restricted)

            plot_episode_signals(
                signals,
                diagnostic / "signal_plot.png",
                privileged=None,
                candidate_boundaries=None,
                suppressed_boundaries=None,
                final_boundaries=None,
                title=f"G1-P1 Formal Signals | {episode_id} | T={signals.n_frames}",
            )
            plot_episode_signals(
                signals,
                diagnostic / "signal_boundary_plot.png",
                privileged=None,
                candidate_boundaries=result.candidate_frames,
                suppressed_boundaries=result.suppressed_frames,
                final_boundaries=[int(selected.frame)],
                final_boundary_annotations=[(int(selected.frame), selected.boundary_id)],
                motion_state_evidence=result.motion_state,
                title=f"G1-P3 Design Diagnostic | {episode_id} | T={signals.n_frames}",
            )

            video_path = staging / "media" / native / "video.mp4"
            # Renders are deterministic per episode, so they live in a shared
            # validated cache; the immutable run folder only ever receives a
            # copy. An interrupted build therefore resumes without re-rendering.
            video_cache[episode_id] = (
                root / MEDIA_CACHE_RELPATH / f"{native}.mp4",
                int(identity_row.num_steps),
            )
            video_expected[episode_id] = (video_path, int(identity_row.num_steps))
            alignment = audit_temporal_alignment(episode, signals, rgb_frame_count=None)
            nan_inf = audit_nan_inf(signals)
            if alignment.status != "PASS" or nan_inf["status"] != "PASS":
                _fail(
                    f"{episode_id}: alignment={alignment.status} nan_inf={nan_inf['status']}"
                )

            decisions = Counter(item.decision for item in result.decisions.values())
            suppressed = sum(
                decisions[name]
                for name in (
                    "SUPPRESS_DEBOUNCE", "SUPPRESS_SHORT_PAUSE",
                    "MERGE_CONSOLIDATION", "MERGE_LEFT", "MERGE_RIGHT",
                )
            )
            weak = adapter.get_weak_reference(episode_id)
            rel = lambda value: Path(value).relative_to(staging).as_posix()
            manifest_rows.append({
                "run_id": run_id,
                "episode_id": episode_id,
                "native_episode_key": native,
                "demo_key": native,
                "source_hdf5": DATASET_RAW_HDF5.name,
                "source_dataset_id": SOURCE_DATASET_ID,
                "set_role": DESIGN_DIAGNOSTIC_SET_ROLE,
                "config_hash": config_hash,
                "signal_contract_version": SIGNAL_CONTRACT_VERSION,
                "signal_contract_hash": signal_hash,
                "video_relpath": rel(video_path),
                "plot_relpath": rel(diagnostic / "signal_boundary_plot.png"),
                "signal_plot_relpath": rel(diagnostic / "signal_plot.png"),
                "candidates_relpath": rel(Path(tables["candidate_boundaries"])),
                "boundaries_relpath": rel(Path(tables["final_boundaries"])),
                "segments_relpath": rel(Path(tables["segment_manifest"])),
                "smoke_relpath": rel(Path(tables["boundary_decisions"])),
                "quality_group": str(weak.get("quality_bucket") or "UNASSIGNED"),
                "review_required": True,
                "length": identity_row.num_steps,
                "candidate_count": len(result.candidates),
                "suppressed_count": suppressed,
                "final_boundary_count": len(restricted.final_events),
                "segment_count": len(result.segments),
                "short_segment_count": sum(bool(item.short_segment_flag) for item in result.segments),
                "long_segment_count": sum(bool(item.long_segment_flag) for item in result.segments),
                "cluster_count": len(result.final_events),
                "deactivated_candidate_count": suppressed,
                "keep_count": decisions["KEEP"],
                "merge_count": decisions["MERGE_CONSOLIDATION"],
                "retain_hard_count": decisions["RETAIN_HARD"],
                "alignment": alignment.status,
                "nan_inf": nan_inf["status"],
            })

        with ProcessPoolExecutor(max_workers=MEDIA_RENDER_WORKERS) as pool:
            futures = {
                pool.submit(
                    _render_video_worker,
                    str(root),
                    episode_id,
                    str(cache_path),
                    float(p1_config.control_frequency_hz),
                    expected_frames,
                ): episode_id
                for episode_id, (cache_path, expected_frames) in video_cache.items()
            }
            for future in as_completed(futures):
                episode_id = futures[future]
                info = future.result()
                cache_path, expected_frames = video_cache[episode_id]
                video_path, _ = video_expected[episode_id]
                # Cache entry is authoritative; the run folder gets a copy.
                video_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(cache_path, video_path)
                observed = count_video_frames(video_path)
                if int(info["written_frames"]) != expected_frames or observed != expected_frames:
                    _fail(
                        f"{episode_id}: video frames={observed} expected={expected_frames}"
                    )

        _write_csv(staging / "episode_manifest.csv", MANIFEST_FIELDS, manifest_rows)
        run_meta = {
            "contract_version": CONTRACT_VERSION,
            "run_id": run_id,
            "run_stage": DESIGN_DIAGNOSTIC_RUN_STAGE,
            "created_at": stamp,
            "parent_run_id": None,
            "config_version": p2_config.config_version,
            "config_hash": config_hash,
            "segmentation_version": p2_config.segmentation_version,
            "signal_contract_version": SIGNAL_CONTRACT_VERSION,
            "signal_contract_hash": signal_hash,
            "source_dataset_id": SOURCE_DATASET_ID,
            "episode_count": len(manifest_rows),
            "codebook_path": "human_boundary_review_codebook.json",
            "manifest_path": "episode_manifest.csv",
            "config_snapshot_path": "config_snapshot.json",
            "final_boundary_semantics": "MATERIALIZED_V1",
            "schema_materialization": "FINAL_BOUNDARY_MEMBER_SEMANTICS_V1",
            "diagnostic_set_id": diagnostic_set_id,
            "blinding_contract": "PASS",
            "detector_modified": False,
            "config_modified": False,
            "parameter_modified": False,
            "threshold_selected": False,
            "human_labels_created": False,
            "selection_recomputed": False,
            "blocked_downstreams": list(blocked_downstreams(DESIGN_DIAGNOSTIC_RUN_STAGE)),
            "human_review_status": "NOT_STARTED",
            "iteration_note": "Design Diagnostic · 设计诊断 · 只用于轨迹机制盲审 · 不进入 GT/Evaluation",
        }
        (staging / "run_meta.json").write_text(
            json.dumps(run_meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        validated = validate_g1_audit_folder(staging)
        if {row["episode_id"] for row in validated["episodes"]} != {
            row["episode_id"] for row in rows
        }:
            _fail("validated run is not an exact blinded episode set")

        violations = audit_blinding_run_folder(staging)
        if violations:
            _fail("BLINDING_CONTRACT_FAILED on materialized run: " + " | ".join(violations))

        staging.rename(final_root)

    record = auto_register(
        registry_path,
        final_root,
        owner_db_path=owner_db_path,
        owner_note=(
            "G1-P3 Trajectory Mechanism Design Diagnostic Set (blinded). "
            "Human review only; never Canonical GT / Calibration Export / Evaluation."
        ),
    )
    return {
        "run_id": run_id,
        "run_root": str(final_root),
        "run_stage": DESIGN_DIAGNOSTIC_RUN_STAGE,
        "set_role": DESIGN_DIAGNOSTIC_SET_ROLE,
        "episode_ids": [row["episode_id"] for row in rows],
        "diagnostic_event_ids": [row["diagnostic_event_id"] for row in rows],
        "selected_frames": selected_frames,
        "event_count": len(rows),
        "distinct_episodes": len({row["episode_id"] for row in rows}),
        "diagnostic_set_id": diagnostic_set_id,
        "config_hash": config_hash,
        "signal_contract_hash": signal_hash,
        "blocked_downstreams": list(blocked_downstreams(DESIGN_DIAGNOSTIC_RUN_STAGE)),
        "registry_status": record.status,
        "blinding_contract": "PASS",
    }
