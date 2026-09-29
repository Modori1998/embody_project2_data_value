"""G1 Audit Web view models. Human Review persistence lives in reviews.py."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import quote

from .input import EpisodeRecord, load_csv_rows
from .media import media_url
from .reviews import EpisodeProgress, empty_progress
from .contract import DESIGN_DIAGNOSTIC_RUN_STAGE

QUEUE_FILTERS = (
    "ALL",
    "NOT_REVIEWED",
    "IN_PROGRESS",
    "REVIEWED",
    "SIGNAL_FAIL",
    "HAS_REDUNDANT",
    "HAS_MISALIGNED",
    "HAS_MISSED",
    "REVIEW_REQUIRED",
)
CONTROL_HZ = 20.0
SUPPRESSED_DECISIONS = frozenset(
    {
        "SUPPRESS_DEBOUNCE",
        "SUPPRESS_SHORT_PAUSE",
        "MERGE_CONSOLIDATION",
        "MERGE_LEFT",
        "MERGE_RIGHT",
    }
)


class AuditViewError(ValueError):
    pass


class QueueRow:
    def __init__(self, episode: EpisodeRecord, progress: EpisodeProgress):
        self.episode = episode
        self.progress = progress

    def __getattr__(self, name: str):
        return getattr(self.episode, name)


@dataclass
class MediaItem:
    key: str
    kind: str
    present: bool
    url: str = ""
    source_sha256: str = ""
    needs_proxy: bool = False
    proxy_profile_version: str = ""


@dataclass
class EpisodeView:
    episode: EpisodeRecord
    index_in_filter: int
    filter_count: int
    previous_episode_id: str | None
    next_episode_id: str | None
    encoded_id: str
    media: list[MediaItem]
    candidates: list[dict[str, str]]
    boundaries: list[dict[str, str]]
    decisions: list[dict[str, str]]
    segments: list[dict[str, str]]
    final_ids: set[str] = field(default_factory=set)
    frame_groups: list[dict[str, Any]] = field(default_factory=list)
    control_hz: float = CONTROL_HZ


ITERATION_NOTE_MATERIALIZED = "合并切割信息更全"
ITERATION_NOTE_ORIGINAL = "原始 Exploratory 切分"
ITERATION_NOTE_CHILD = "相对 parent 的迭代"


@dataclass(frozen=True)
class IndexRunRow:
    run_id: str
    run_stage: str
    created_at: str
    config_version: str
    config_hash: str
    parent_run_id: str | None
    episode_count: int
    path_source: str
    status: str
    enabled: bool
    iteration_note: str


def load_run_meta_lite(audit_folder: str | Path) -> dict[str, Any]:
    path = Path(audit_folder) / "run_meta.json"
    try:
        if not path.is_file():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def iteration_note_from_meta(meta: Mapping[str, Any] | None) -> str:
    """One-line homepage blurb. Prefer explicit run_meta.iteration_note."""

    payload = dict(meta or {})
    explicit = str(payload.get("iteration_note") or "").strip()
    if explicit:
        return explicit
    semantics = str(payload.get("final_boundary_semantics") or "").strip().upper()
    schema = str(payload.get("schema_materialization") or "").strip().upper()
    if semantics == "MATERIALIZED_V1" or "FINAL_BOUNDARY_MEMBER_SEMANTICS" in schema:
        return ITERATION_NOTE_MATERIALIZED
    parent = payload.get("parent_run_id")
    if payload.get("bootstrap") or parent in (None, "", "null"):
        return ITERATION_NOTE_ORIGINAL
    return ITERATION_NOTE_CHILD


def index_run_rows(records: Iterable[Any]) -> list[IndexRunRow]:
    rows: list[IndexRunRow] = []
    for record in records:
        meta = load_run_meta_lite(getattr(record, "audit_folder_path", ""))
        if "parent_run_id" not in meta:
            meta = {**meta, "parent_run_id": getattr(record, "parent_run_id", None)}
        rows.append(
            IndexRunRow(
                run_id=str(record.run_id),
                run_stage=str(record.run_stage),
                created_at=str(record.created_at),
                config_version=str(record.config_version),
                config_hash=str(record.config_hash),
                parent_run_id=record.parent_run_id,
                episode_count=int(record.episode_count),
                path_source=str(record.path_source),
                status=str(record.status),
                enabled=bool(record.enabled),
                iteration_note=iteration_note_from_meta(meta),
            )
        )
    return rows


@dataclass
class RunHeader:
    run_id: str
    run_stage: str
    created_at: str
    parent_run_id: str
    config_version: str
    config_hash: str
    config_hash_short: str
    segmentation_version: str
    signal_contract_version: str
    signal_contract_hash: str
    source_dataset_id: str
    episode_count: int
    contract_version: str
    exploratory_only: bool
    evaluation_no_tuning: bool
    design_diagnostic_only: bool
    calibration_role: str
    calibration_config_role: str
    human_review_status: str
    search_gate: str
    parameter_search_executed: bool
    evaluation_manifest_version: str
    frozen_config_identity: str
    must_not_feed_back_to_calibration: bool


def encode_episode_id(episode_id: str) -> str:
    return quote(str(episode_id or "").replace("/", "--"), safe="-_.")


def decode_episode_id(encoded: str) -> str:
    from urllib.parse import unquote

    return unquote(str(encoded or "")).replace("--", "/")


def run_header(loaded: dict[str, Any]) -> RunHeader:
    meta = loaded["run_meta"]
    stage = str(meta.get("run_stage") or "")
    digest = str(meta.get("config_hash") or "")
    parent = meta.get("parent_run_id")
    return RunHeader(
        run_id=str(meta["run_id"]),
        run_stage=stage,
        created_at=str(meta.get("created_at") or ""),
        parent_run_id="" if parent in (None, "", "null") else str(parent),
        config_version=str(meta.get("config_version") or ""),
        config_hash=digest,
        config_hash_short=digest[:12],
        segmentation_version=str(meta.get("segmentation_version") or ""),
        signal_contract_version=str(meta.get("signal_contract_version") or ""),
        signal_contract_hash=str(meta.get("signal_contract_hash") or ""),
        source_dataset_id=str(meta.get("source_dataset_id") or ""),
        episode_count=int(meta.get("episode_count") or 0),
        contract_version=str(meta.get("contract_version") or ""),
        exploratory_only=stage == "EXPLORATORY_AUDIT",
        evaluation_no_tuning=stage == "EVALUATION",
        design_diagnostic_only=stage == DESIGN_DIAGNOSTIC_RUN_STAGE,
        calibration_role=str(meta.get("calibration_role") or ""),
        calibration_config_role=str(meta.get("calibration_config_role") or ""),
        human_review_status=str(meta.get("human_review_status") or ""),
        search_gate=str(meta.get("search_gate") or ""),
        parameter_search_executed=bool(meta.get("parameter_search_executed", False)),
        evaluation_manifest_version=str(meta.get("evaluation_manifest_version") or ""),
        frozen_config_identity=str(meta.get("frozen_config_identity") or ""),
        must_not_feed_back_to_calibration=bool(meta.get("must_not_feed_back_to_calibration", False)),
    )


def normalize_filter(name: str | None) -> str:
    text = str(name or "ALL").strip().upper()
    if text not in QUEUE_FILTERS:
        raise AuditViewError(f"unsupported queue filter: {name}")
    return text


def _as_int(value: Any) -> int | None:
    text = str(value or "").strip()
    if text == "":
        return None
    try:
        return int(text)
    except ValueError:
        try:
            return int(float(text))
        except ValueError:
            return None


def filter_episodes(
    episodes: list[EpisodeRecord],
    *,
    filter_name: str,
    quality_group: str = "",
    episode_id: str = "",
    short_segment_count: str = "",
    final_boundary_count: str = "",
    progress_by_episode: dict[str, EpisodeProgress] | None = None,
) -> list[EpisodeRecord]:
    selected = normalize_filter(filter_name)
    quality = str(quality_group or "").strip()
    wanted_id = str(episode_id or "").strip()
    short_n = _as_int(short_segment_count)
    final_n = _as_int(final_boundary_count)
    progress_by_episode = progress_by_episode or {}
    out: list[EpisodeRecord] = []
    for item in episodes:
        progress = progress_by_episode.get(item.episode_id) or empty_progress(item.final_boundary_count)
        if selected == "REVIEW_REQUIRED" and not item.review_required:
            continue
        if selected == "NOT_REVIEWED" and progress.overall != "NOT_REVIEWED":
            continue
        if selected == "IN_PROGRESS" and progress.overall != "IN_PROGRESS":
            continue
        if selected == "REVIEWED" and progress.overall != "REVIEWED":
            continue
        if selected == "SIGNAL_FAIL" and not progress.signal_fail:
            continue
        if selected == "HAS_REDUNDANT" and not progress.has_redundant:
            continue
        if selected == "HAS_MISALIGNED" and not progress.has_misaligned:
            continue
        if selected == "HAS_MISSED" and not progress.has_missed:
            continue
        if quality and item.quality_group != quality:
            continue
        if wanted_id and wanted_id not in item.episode_id and wanted_id not in item.native_episode_key:
            continue
        if short_n is not None and item.short_segment_count != short_n:
            continue
        if final_n is not None and item.final_boundary_count != final_n:
            continue
        out.append(item)
    return out


def boundary_ids_by_episode(episodes: list[EpisodeRecord]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for item in episodes:
        rows = load_csv_rows(item.boundaries_path)
        out[item.episode_id] = [str(row.get("boundary_id") or "") for row in rows if str(row.get("boundary_id") or "")]
    return out


def _media_items(run_id: str, episode: EpisodeRecord) -> list[MediaItem]:
    items = [
        MediaItem(
            key="video",
            kind="video",
            present=episode.video_path.is_file(),
            url=media_url(run_id, episode.episode_id, "video"),
        ),
        MediaItem(
            key="signal_boundary_plot",
            kind="image",
            present=episode.plot_path.is_file(),
            url=media_url(run_id, episode.episode_id, "signal_boundary_plot"),
        ),
    ]
    if episode.signal_plot_path is not None and episode.signal_plot_path.is_file():
        items.append(
            MediaItem(
                key="signal_plot",
                kind="image",
                present=True,
                url=media_url(run_id, episode.episode_id, "signal_plot"),
            )
        )
    return items


def _short_id(raw: str) -> str:
    text = str(raw or "").strip()
    if "-" in text:
        return text.rsplit("-", 1)[-1]
    return text


def build_frame_groups(
    *,
    length: int,
    candidates: list[dict[str, str]],
    boundaries: list[dict[str, str]],
    decisions: list[dict[str, str]],
) -> list[dict[str, Any]]:
    span = max(int(length) - 1, 1)
    suppressed_ids = {
        str(row.get("candidate_id") or "")
        for row in decisions
        if str(row.get("decision") or "").strip() in SUPPRESSED_DECISIONS
    }
    target_by_candidate = {
        str(row.get("candidate_id") or ""): str(row.get("target_boundary_id") or "")
        for row in decisions
    }
    by_frame: dict[int, list[dict[str, str]]] = {}

    def add(frame: int, kind: str, event_id: str, extra: dict[str, str]) -> None:
        if frame < 0 or not event_id:
            return
        by_frame.setdefault(frame, []).append(
            {
                "kind": kind,
                "event_id": event_id,
                "short": _short_id(event_id),
                **extra,
            }
        )

    for row in boundaries:
        frame = _as_int(row.get("frame"))
        if frame is None:
            continue
        add(
            frame,
            "final",
            str(row.get("boundary_id") or ""),
            {
                "type": str(row.get("candidate_type") or ""),
                "members": str(row.get("member_candidate_ids") or ""),
                "boundary_id": str(row.get("boundary_id") or ""),
            },
        )
    for row in candidates:
        frame = _as_int(row.get("frame"))
        if frame is None:
            continue
        cid = str(row.get("candidate_id") or "")
        kind = "suppressed" if cid in suppressed_ids else "candidate"
        add(
            frame,
            kind,
            cid,
            {
                "type": str(row.get("candidate_type") or ""),
                "members": cid,
                "boundary_id": target_by_candidate.get(cid, ""),
            },
        )
    groups = []
    for frame in sorted(by_frame):
        items = by_frame[frame]
        items.sort(key=lambda item: ({"final": 0, "candidate": 1, "suppressed": 2}.get(item["kind"], 9), item["event_id"]))
        groups.append(
            {
                "frame": frame,
                "pct": round(100.0 * frame / span, 3),
                "marks": items,
            }
        )
    return groups


def build_episode_view(
    loaded: dict[str, Any],
    *,
    episode_id: str,
    filter_name: str = "ALL",
    quality_group: str = "",
    episode_query: str = "",
    short_segment_count: str = "",
    final_boundary_count: str = "",
    progress_by_episode: dict[str, EpisodeProgress] | None = None,
) -> tuple[list[QueueRow], EpisodeView]:
    episodes: list[EpisodeRecord] = list(loaded["episodes"])
    progress_by_episode = progress_by_episode or {}
    filtered = filter_episodes(
        episodes,
        filter_name=filter_name,
        quality_group=quality_group,
        episode_id=episode_query,
        short_segment_count=short_segment_count,
        final_boundary_count=final_boundary_count,
        progress_by_episode=progress_by_episode,
    )
    queue = [
        QueueRow(item, progress_by_episode.get(item.episode_id) or empty_progress(item.final_boundary_count))
        for item in filtered
    ]
    wanted = str(episode_id or "").strip()
    index = next((i for i, item in enumerate(queue) if item.episode_id == wanted), None)
    if index is None:
        raise AuditViewError(f"episode not in current filter: {wanted}")
    current = queue[index].episode
    prev_id = queue[index - 1].episode_id if index > 0 else None
    next_id = queue[index + 1].episode_id if index + 1 < len(queue) else None
    boundaries = load_csv_rows(current.boundaries_path)
    candidates = load_csv_rows(current.candidates_path)
    decisions = load_csv_rows(current.smoke_path)
    segments = load_csv_rows(current.segments_path)
    view = EpisodeView(
        episode=current,
        index_in_filter=index + 1,
        filter_count=len(queue),
        previous_episode_id=prev_id,
        next_episode_id=next_id,
        encoded_id=encode_episode_id(current.episode_id),
        media=_media_items(str(loaded["run_id"]), current),
        candidates=candidates,
        boundaries=boundaries,
        decisions=decisions,
        segments=segments,
        final_ids={str(row.get("boundary_id") or "") for row in boundaries},
        frame_groups=build_frame_groups(
            length=current.length,
            candidates=candidates,
            boundaries=boundaries,
            decisions=decisions,
        ),
        control_hz=CONTROL_HZ,
    )
    return queue, view


def quality_groups(episodes: list[EpisodeRecord]) -> list[str]:
    found = []
    for item in episodes:
        if item.quality_group and item.quality_group not in found:
            found.append(item.quality_group)
    return found
