"""Read-only loaders for a validated G1 audit run folder."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contract import validate_g1_audit_folder


@dataclass(frozen=True)
class EpisodeRecord:
    run_id: str
    episode_id: str
    native_episode_key: str
    demo_key: str
    source_hdf5: str
    source_dataset_id: str
    set_role: str
    config_hash: str
    signal_contract_version: str
    signal_contract_hash: str
    video_path: Path
    plot_path: Path
    signal_plot_path: Path | None
    candidates_path: Path
    boundaries_path: Path
    segments_path: Path
    smoke_path: Path
    video_relpath: str
    plot_relpath: str
    signal_plot_relpath: str
    quality_group: str
    review_required: bool
    length: int
    candidate_count: int
    suppressed_count: int
    final_boundary_count: int
    segment_count: int
    short_segment_count: int
    long_segment_count: int
    cluster_count: int
    deactivated_candidate_count: int
    keep_count: int
    merge_count: int
    retain_hard_count: int
    alignment: str
    nan_inf: str


def load_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_run(run_root: str | Path) -> dict[str, Any]:
    validated = validate_g1_audit_folder(run_root)
    root = Path(validated["run_root"])
    episodes: list[EpisodeRecord] = []
    for row in validated["episodes"]:
        plot_rel = str(row.get("signal_plot_relpath") or "")
        episodes.append(
            EpisodeRecord(
                run_id=str(row["run_id"]),
                episode_id=str(row["episode_id"]),
                native_episode_key=str(row.get("native_episode_key") or row.get("demo_key") or ""),
                demo_key=str(row["demo_key"]),
                source_hdf5=str(row["source_hdf5"]),
                source_dataset_id=str(row["source_dataset_id"]),
                set_role=str(row["set_role"]),
                config_hash=str(row["config_hash"]),
                signal_contract_version=str(row["signal_contract_version"]),
                signal_contract_hash=str(row["signal_contract_hash"]),
                video_path=root / str(row["video_relpath"]),
                plot_path=root / str(row["plot_relpath"]),
                signal_plot_path=(root / plot_rel) if plot_rel else None,
                candidates_path=root / str(row["candidates_relpath"]),
                boundaries_path=root / str(row["boundaries_relpath"]),
                segments_path=root / str(row["segments_relpath"]),
                smoke_path=root / str(row["smoke_relpath"]),
                video_relpath=str(row["video_relpath"]),
                plot_relpath=str(row["plot_relpath"]),
                signal_plot_relpath=plot_rel,
                quality_group=str(row.get("quality_group") or ""),
                review_required=bool(row["review_required"]),
                length=int(row["length"]),
                candidate_count=int(row["candidate_count"]),
                suppressed_count=int(row["suppressed_count"]),
                final_boundary_count=int(row["final_boundary_count"]),
                segment_count=int(row["segment_count"]),
                short_segment_count=int(row["short_segment_count"]),
                long_segment_count=int(row["long_segment_count"]),
                cluster_count=int(row["cluster_count"]),
                deactivated_candidate_count=int(row["deactivated_candidate_count"]),
                keep_count=int(row["keep_count"]),
                merge_count=int(row["merge_count"]),
                retain_hard_count=int(row["retain_hard_count"]),
                alignment=str(row.get("alignment") or ""),
                nan_inf=str(row.get("nan_inf") or ""),
            )
        )
    by_id = {item.episode_id: item for item in episodes}
    return {
        **validated,
        "episodes": episodes,
        "episodes_by_id": by_id,
    }
