"""Owner-only unblinded review mode for the G1-P3 DESIGN_DIAGNOSTIC run.

This module is strictly additive on top of the blinded Design Diagnostic audit
run. Three invariants hold and are enforced here:

1. **The blind page stays blind.** Nothing in this module is rendered by the
   blinded episode page. The blinded page keeps rendering only what
   ``03_selection_blinded.csv`` legitimately exposes.
2. **The blind review history is never touched.** Unblinded re-reviews are
   appended as *new* revisions of ``predicted_boundary_review_history`` under a
   distinct reviewer identity, so the first blinded decision stays readable and
   the two provenance classes remain distinguishable.
3. **The run folder is never written.** Unblind facts are read at render time
   from the frozen internal selection table that lives outside the audit run
   folder, so the run-folder blinding audit stays ``PASS``.

The join between the frozen internal selection table and the 20 materialized
diagnostic events is strict and fails fast: exact ``episode_id`` + exact
``boundary_id``, one-to-one, 20/20, no fuzzy matching of any kind.
"""

from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .contract import DESIGN_DIAGNOSTIC_RUN_STAGE
from .reviews import BoundaryReview

# --------------------------------------------------------------------------
# Frozen inputs and expectations
# --------------------------------------------------------------------------

#: Frozen internal (unblinded) selection table. Lives in the design-review
#: document tree, deliberately *outside* any audit run folder.
UNBLIND_SOURCE_RELPATH = (
    "0-doc/80-audit-local/g1_p3_trajectory_mechanism_validation/02_selection_internal.csv"
)

EXPECTED_UNBLIND_EVENT_COUNT = 20
EXPECTED_PAIR_COUNT = 10
EXPECTED_ARM_COUNTS = {"A": 10, "B": 10}
UNBLIND_ARMS = ("A", "B")

#: Quartile rule frozen by the design: Arm A = bottom C12 quartile within the
#: P12-eligible pool, Arm B = top C12 quartile.
LOW_C12_QUARTILE_MAX = 0.25
HIGH_C12_QUARTILE_MIN = 0.75
C12_GROUP_LOW = "LOW C12"
C12_GROUP_HIGH = "HIGH C12"

#: Required columns of the internal selection table.
REQUIRED_UNBLIND_COLUMNS = (
    "diagnostic_event_id",
    "arm",
    "pair_id",
    "episode_id",
    "event_frame",
    "boundary_id",
    "representative_candidate_id",
    "P12",
    "P12_percentile",
    "C12",
    "C12_percentile",
    "direction_evidence",
    "direction_evidence_percentile",
    "run_length",
    "run_length_percentile",
    "match_distance",
    "selection_reason",
)

#: Join keys, in order. Exact string equality only — no normalisation.
JOIN_KEY_FIELDS = ("episode_id", "boundary_id")
JOIN_KEY_LABEL = "episode_id+boundary_id"

# --------------------------------------------------------------------------
# Review provenance
# --------------------------------------------------------------------------

#: Reviewer identity recorded for an owner unblinded re-review. Distinct from
#: ``reviews.DEFAULT_REVIEWER`` so provenance is derivable from stored rows
#: without any schema change to the frozen review SSOT.
UNBLINDED_REVIEWER = "DESIGN_OWNER_UNBLINDED"

REVIEW_PROVENANCE_FIRST_BLIND = "FIRST_BLINDED_REVIEW"
REVIEW_PROVENANCE_OWNER_UNBLINDED = "OWNER_UNBLINDED_REVIEW"


def review_provenance(reviewer: str | None) -> str:
    """Classify a stored boundary revision by who authored it."""

    if str(reviewer or "").strip() == UNBLINDED_REVIEWER:
        return REVIEW_PROVENANCE_OWNER_UNBLINDED
    return REVIEW_PROVENANCE_FIRST_BLIND


# --------------------------------------------------------------------------
# Chinese explanations, quoted verbatim from the FROZEN design
# --------------------------------------------------------------------------

C12_EXPLANATION_ZH = (
    "C12 — Trajectory Coherence｜轨迹一致性\n"
    "left_straightness =\n"
    "left_net_displacement / left_path_length\n"
    "over relative_frame [-12,-1]\n"
    "right_straightness =\n"
    "right_net_displacement / right_path_length\n"
    "over relative_frame [0,+11]\n"
    "C12 =\n"
    "min(left_straightness, right_straightness)\n"
    "用途：\n"
    "只验证 trajectory mechanism。"
)

P12_EXPLANATION_ZH = (
    "P12 — Sustained Post-motion Context｜持续后段运动上下文\n"
    "P12 =\n"
    "median(translation_speed_mps)\n"
    "over relative_frame [+4,+12]\n"
    "用途：\n"
    "仅用于控制“后续运动已经足够持续”这一前提。"
)

# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------


class UnblindedError(ValueError):
    """Fail-fast: the unblinded owner view cannot be rendered faithfully."""

    def __init__(self, errors: Iterable[str]):
        self.errors = [str(item) for item in errors if str(item).strip()]
        super().__init__("UNBLINDED_JOIN_FAILED: " + " | ".join(self.errors))


class UnblindedNotApplicable(UnblindedError):
    """The run is not a DESIGN_DIAGNOSTIC run, so this mode does not apply."""


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class UnblindedEvent:
    """One diagnostic event, joined across run folder + unblind source + review."""

    episode_id: str
    boundary_id: str
    diagnostic_event_id: str
    arm: str
    pair_id: str
    event_frame: int
    c12_group: str
    c12: float
    c12_percentile: float
    p12: float
    p12_percentile: float
    direction_evidence: float
    direction_evidence_percentile: float
    run_length: int
    run_length_percentile: float
    match_distance: float
    selection_reason: str
    # --- joined from the materialized run folder (blind side) ---
    run_boundary_frame: int
    candidate_type: str
    representative_candidate_id: str
    # --- joined from the append-only review history ---
    first_blind_decision: str
    first_blind_reason_code: str
    first_blind_comment: str
    first_blind_review_id: int | None
    first_blind_reviewed_at: str
    current_decision: str
    current_reason_code: str
    current_comment: str
    current_corrected_frame: str
    current_review_id: int | None
    current_reviewed_at: str
    current_provenance: str
    revision_count: int

    @property
    def c12_display(self) -> str:
        return f"{self.c12:.4f}"

    @property
    def p12_display(self) -> str:
        return f"{self.p12:.4f}"

    @property
    def direction_evidence_display(self) -> str:
        return f"{self.direction_evidence:.4f}"

    @property
    def has_owner_revision(self) -> bool:
        return self.current_provenance == REVIEW_PROVENANCE_OWNER_UNBLINDED


@dataclass(frozen=True)
class MatchedPair:
    """Arm A + Arm B of one matched pair."""

    pair_id: str
    arm_a: UnblindedEvent
    arm_b: UnblindedEvent


@dataclass(frozen=True)
class UnblindedJoin:
    run_id: str
    source_path: str
    source_sha256: str
    join_key: str
    events: tuple[UnblindedEvent, ...]
    pairs: tuple[MatchedPair, ...]

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def pair_count(self) -> int:
        return len(self.pairs)

    @property
    def low_count(self) -> int:
        return sum(1 for item in self.events if item.c12_group == C12_GROUP_LOW)

    @property
    def high_count(self) -> int:
        return sum(1 for item in self.events if item.c12_group == C12_GROUP_HIGH)

    @property
    def first_blind_review_preserved(self) -> bool:
        return all(item.first_blind_review_id is not None for item in self.events)

    def event(self, episode_id: str) -> UnblindedEvent | None:
        wanted = str(episode_id or "")
        return next((item for item in self.events if item.episode_id == wanted), None)

    def pair(self, pair_id: str) -> MatchedPair | None:
        wanted = str(pair_id or "").strip()
        return next((item for item in self.pairs if item.pair_id == wanted), None)

    def index_of(self, episode_id: str) -> int:
        wanted = str(episode_id or "")
        return next(
            (i for i, item in enumerate(self.events) if item.episode_id == wanted), -1
        )

    def neighbour(self, episode_id: str) -> tuple[UnblindedEvent | None, UnblindedEvent | None]:
        index = self.index_of(episode_id)
        if index < 0:
            return None, None
        previous = self.events[index - 1] if index > 0 else None
        following = self.events[index + 1] if index + 1 < len(self.events) else None
        return previous, following


# --------------------------------------------------------------------------
# Loading the unblind source
# --------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _as_float(value: Any, *, field_name: str, key: str) -> float:
    text = _text(value)
    if text == "":
        raise UnblindedError([f"{key}: {field_name} is empty"])
    try:
        return float(text)
    except ValueError as exc:
        raise UnblindedError([f"{key}: {field_name} is not numeric: {value!r}"]) from exc


def _as_int(value: Any, *, field_name: str, key: str) -> int:
    number = _as_float(value, field_name=field_name, key=key)
    if number != int(number):
        raise UnblindedError([f"{key}: {field_name} is not an integer: {value!r}"])
    return int(number)


def c12_group_from_percentile(percentile: float) -> str:
    """Frozen quartile rule: bottom quartile = LOW, top quartile = HIGH."""

    if float(percentile) <= LOW_C12_QUARTILE_MAX:
        return C12_GROUP_LOW
    if float(percentile) >= HIGH_C12_QUARTILE_MIN:
        return C12_GROUP_HIGH
    raise UnblindedError(
        [
            "C12_percentile={:.6f} falls outside both diagnostic quartiles "
            "(<= {:.2f} or >= {:.2f}); the diagnostic set is not the frozen one".format(
                float(percentile), LOW_C12_QUARTILE_MAX, HIGH_C12_QUARTILE_MIN
            )
        ]
    )


def load_unblind_source(path: str | Path) -> dict[tuple[str, str], dict[str, str]]:
    """Read the frozen internal selection table, keyed by the exact join key.

    Fails fast on a missing file, missing columns, empty values in the join key,
    or a duplicated join key. Duplicates are never silently resolved because a
    duplicated key would make the "20/20" claim meaningless.
    """

    source = Path(path)
    if not source.is_file():
        raise UnblindedError([f"unblind source not found: {source}"])
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        missing = [key for key in REQUIRED_UNBLIND_COLUMNS if key not in fieldnames]
        if missing:
            raise UnblindedError(
                [f"unblind source missing columns: {', '.join(missing)}"]
            )
        rows = list(reader)

    out: dict[tuple[str, str], dict[str, str]] = {}
    duplicates: list[str] = []
    for row in rows:
        episode_id = _text(row.get("episode_id"))
        boundary_id = _text(row.get("boundary_id"))
        if not episode_id or not boundary_id:
            raise UnblindedError(
                [
                    "unblind source has an empty join key: "
                    f"episode_id={episode_id!r} boundary_id={boundary_id!r}"
                ]
            )
        key = (episode_id, boundary_id)
        if key in out:
            duplicates.append(f"{episode_id}/{boundary_id}")
            continue
        out[key] = dict(row)
    if duplicates:
        raise UnblindedError(
            [
                "unblind source has duplicate join keys (exactly one row per event "
                f"is required): {', '.join(sorted(duplicates))}"
            ]
        )
    if not out:
        raise UnblindedError([f"unblind source has no data rows: {source}"])
    return out


# --------------------------------------------------------------------------
# Strict 1:1 join
# --------------------------------------------------------------------------


def run_event_rows(loaded: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The materialized diagnostic events, read from each episode's boundaries file."""

    rows: list[dict[str, Any]] = []
    for episode in loaded["episodes"]:
        with Path(episode.boundaries_path).open("r", encoding="utf-8", newline="") as handle:
            boundaries = list(csv.DictReader(handle))
        rows.append(
            {
                "episode_id": str(episode.episode_id),
                "boundary_ids": [
                    _text(item.get("boundary_id"))
                    for item in boundaries
                    if _text(item.get("boundary_id"))
                ],
                "frames": {
                    _text(item.get("boundary_id")): _text(item.get("frame"))
                    for item in boundaries
                },
                "candidate_types": {
                    _text(item.get("boundary_id")): _text(item.get("candidate_type"))
                    for item in boundaries
                },
                "representatives": {
                    _text(item.get("boundary_id")): _text(
                        item.get("representative_candidate_id")
                    )
                    for item in boundaries
                },
            }
        )
    return rows


def _build_event(
    *,
    key: tuple[str, str],
    source_row: Mapping[str, str],
    run_row: Mapping[str, Any],
    history: Sequence[BoundaryReview],
) -> UnblindedEvent:
    episode_id, boundary_id = key
    label = f"{episode_id}/{boundary_id}"
    arm = _text(source_row.get("arm")).upper()
    if arm not in UNBLIND_ARMS:
        raise UnblindedError([f"{label}: arm must be one of {UNBLIND_ARMS}, got {arm!r}"])
    pair_id = _text(source_row.get("pair_id"))
    if not pair_id:
        raise UnblindedError([f"{label}: pair_id is empty"])

    event_frame = _as_int(source_row.get("event_frame"), field_name="event_frame", key=label)
    run_frame = _as_int(
        run_row["frames"].get(boundary_id), field_name="run frame", key=label
    )
    if event_frame != run_frame:
        raise UnblindedError(
            [
                f"{label}: frame mismatch — unblind source event_frame={event_frame} "
                f"but materialized run frame={run_frame}"
            ]
        )

    c12_percentile = _as_float(
        source_row.get("C12_percentile"), field_name="C12_percentile", key=label
    )
    c12_group = c12_group_from_percentile(c12_percentile)
    expected_group = C12_GROUP_LOW if arm == "A" else C12_GROUP_HIGH
    if c12_group != expected_group:
        raise UnblindedError(
            [
                f"{label}: arm {arm} must sit in {expected_group} but C12_percentile="
                f"{c12_percentile:.6f} places it in {c12_group}"
            ]
        )

    first = history[0] if history else None
    current = history[-1] if history else None
    return UnblindedEvent(
        episode_id=episode_id,
        boundary_id=boundary_id,
        diagnostic_event_id=_text(source_row.get("diagnostic_event_id")),
        arm=arm,
        pair_id=pair_id,
        event_frame=event_frame,
        c12_group=c12_group,
        c12=_as_float(source_row.get("C12"), field_name="C12", key=label),
        c12_percentile=c12_percentile,
        p12=_as_float(source_row.get("P12"), field_name="P12", key=label),
        p12_percentile=_as_float(
            source_row.get("P12_percentile"), field_name="P12_percentile", key=label
        ),
        direction_evidence=_as_float(
            source_row.get("direction_evidence"), field_name="direction_evidence", key=label
        ),
        direction_evidence_percentile=_as_float(
            source_row.get("direction_evidence_percentile"),
            field_name="direction_evidence_percentile",
            key=label,
        ),
        run_length=_as_int(source_row.get("run_length"), field_name="run_length", key=label),
        run_length_percentile=_as_float(
            source_row.get("run_length_percentile"), field_name="run_length_percentile", key=label
        ),
        match_distance=_as_float(
            source_row.get("match_distance"), field_name="match_distance", key=label
        ),
        selection_reason=_text(source_row.get("selection_reason")),
        run_boundary_frame=run_frame,
        candidate_type=_text(run_row["candidate_types"].get(boundary_id)),
        representative_candidate_id=_text(run_row["representatives"].get(boundary_id))
        or _text(source_row.get("representative_candidate_id")),
        first_blind_decision=first.decision if first else "NOT_REVIEWED",
        first_blind_reason_code=_text(first.reason_code) if first else "",
        first_blind_comment=first.comment if first else "",
        first_blind_review_id=first.review_id if first else None,
        first_blind_reviewed_at=first.reviewed_at if first else "",
        current_decision=current.decision if current else "NOT_REVIEWED",
        current_reason_code=_text(current.reason_code) if current else "",
        current_comment=current.comment if current else "",
        current_corrected_frame=(
            ""
            if current is None or current.corrected_frame is None
            else str(current.corrected_frame)
        ),
        current_review_id=current.review_id if current else None,
        current_reviewed_at=current.reviewed_at if current else "",
        current_provenance=review_provenance(current.reviewer if current else ""),
        revision_count=len(history),
    )


def build_unblinded_join(
    *,
    loaded: Mapping[str, Any],
    source_path: str | Path,
    boundary_history: Mapping[str, Mapping[str, Sequence[BoundaryReview]]] | None = None,
) -> UnblindedJoin:
    """Join the 20 materialized diagnostic events to the unblind source.

    Every failure mode is a hard error: a partial match is never rendered,
    because a partial unblinded view would silently misrepresent which cases the
    Design Owner is looking at.
    """

    run_stage = str(loaded.get("run_stage") or "")
    if run_stage != DESIGN_DIAGNOSTIC_RUN_STAGE:
        raise UnblindedNotApplicable(
            [
                f"unblinded owner review applies only to run_stage="
                f"{DESIGN_DIAGNOSTIC_RUN_STAGE}, got {run_stage!r}"
            ]
        )

    source = Path(source_path)
    source_rows = load_unblind_source(source)
    history = boundary_history or {}

    run_rows = run_event_rows(loaded)
    run_keys: list[tuple[str, str]] = []
    duplicate_run_keys: list[str] = []
    seen: set[tuple[str, str]] = set()
    for run_row in run_rows:
        episode_id = str(run_row["episode_id"])
        boundary_ids = list(run_row["boundary_ids"])
        if len(boundary_ids) != 1:
            raise UnblindedError(
                [
                    f"{episode_id}: expected exactly 1 review target boundary, "
                    f"found {len(boundary_ids)}"
                ]
            )
        key = (episode_id, boundary_ids[0])
        if key in seen:
            duplicate_run_keys.append(f"{episode_id}/{boundary_ids[0]}")
            continue
        seen.add(key)
        run_keys.append(key)
    if duplicate_run_keys:
        raise UnblindedError(
            [
                "materialized run has duplicate join keys: "
                + ", ".join(sorted(duplicate_run_keys))
            ]
        )

    errors: list[str] = []

    # Missing side: a run event with no unblind row.
    for key in run_keys:
        if key not in source_rows:
            errors.append(f"MISSING_IN_UNBLIND_SOURCE: {key[0]}/{key[1]}")

    # Extra side: an unblind row with no run event.
    run_key_set = set(run_keys)
    for key in source_rows:
        if key not in run_key_set:
            errors.append(f"EXTRA_IN_UNBLIND_SOURCE: {key[0]}/{key[1]}")

    # Fuzzy-only matches are explicitly rejected rather than resolved.
    if errors:
        run_boundary_ids = {key[1] for key in run_keys}
        run_episode_ids = {key[0] for key in run_keys}
        for key in sorted(source_rows):
            if key in run_key_set:
                continue
            if key[1] in run_boundary_ids:
                errors.append(
                    f"FUZZY_MATCH_REJECTED: boundary_id {key[1]} exists in the run under a "
                    f"different episode_id ({key[0]})"
                )
            elif key[0] in run_episode_ids:
                errors.append(
                    f"FUZZY_MATCH_REJECTED: episode_id {key[0]} exists in the run under a "
                    f"different boundary_id ({key[1]})"
                )

    if len(run_keys) != EXPECTED_UNBLIND_EVENT_COUNT:
        errors.append(
            f"EVENT_COUNT_MISMATCH: run has {len(run_keys)} events, expected "
            f"{EXPECTED_UNBLIND_EVENT_COUNT}"
        )
    if len(source_rows) != EXPECTED_UNBLIND_EVENT_COUNT:
        errors.append(
            f"EVENT_COUNT_MISMATCH: unblind source has {len(source_rows)} rows, expected "
            f"{EXPECTED_UNBLIND_EVENT_COUNT}"
        )
    if errors:
        raise UnblindedError(sorted(set(errors)))

    by_episode = {str(row["episode_id"]): row for row in run_rows}
    events: list[UnblindedEvent] = []
    for key in run_keys:
        events.append(
            _build_event(
                key=key,
                source_row=source_rows[key],
                run_row=by_episode[key[0]],
                history=history.get(key[0], {}).get(key[1], ()),
            )
        )

    arm_counts: dict[str, int] = {}
    for item in events:
        arm_counts[item.arm] = arm_counts.get(item.arm, 0) + 1
    if arm_counts != EXPECTED_ARM_COUNTS:
        raise UnblindedError(
            [
                f"ARM_COUNT_MISMATCH: expected {EXPECTED_ARM_COUNTS}, got "
                f"{dict(sorted(arm_counts.items()))}"
            ]
        )

    grouped: dict[str, list[UnblindedEvent]] = {}
    for item in events:
        grouped.setdefault(item.pair_id, []).append(item)
    pair_errors: list[str] = []
    pairs: list[MatchedPair] = []
    for pair_id in sorted(grouped):
        members = grouped[pair_id]
        arms = sorted(item.arm for item in members)
        if arms != ["A", "B"]:
            pair_errors.append(
                f"PAIR_INCOMPLETE: {pair_id} has arms {arms}, expected exactly ['A', 'B']"
            )
            continue
        by_arm = {item.arm: item for item in members}
        pairs.append(MatchedPair(pair_id=pair_id, arm_a=by_arm["A"], arm_b=by_arm["B"]))
    if pair_errors:
        raise UnblindedError(pair_errors)
    if len(pairs) != EXPECTED_PAIR_COUNT:
        raise UnblindedError(
            [
                f"PAIR_COUNT_MISMATCH: found {len(pairs)} complete pairs, expected "
                f"{EXPECTED_PAIR_COUNT}"
            ]
        )

    return UnblindedJoin(
        run_id=str(loaded.get("run_id") or ""),
        source_path=str(source),
        source_sha256=_sha256(source),
        join_key=JOIN_KEY_LABEL,
        events=tuple(events),
        pairs=tuple(pairs),
    )


# --------------------------------------------------------------------------
# Acceptance summary (used by the return block and by tests)
# --------------------------------------------------------------------------


def unblinded_acceptance(join: UnblindedJoin) -> dict[str, Any]:
    """Machine-checkable acceptance facts for the unblinded owner mode."""

    return {
        "event_count": join.event_count,
        "low_count": join.low_count,
        "high_count": join.high_count,
        "pair_count": join.pair_count,
        "join_key": join.join_key,
        "matched": join.event_count,
        "expected": EXPECTED_UNBLIND_EVENT_COUNT,
        "first_blind_review_preserved": join.first_blind_review_preserved,
        "unblinded_fields_visible": [
            "arm",
            "c12_group",
            "c12",
            "p12",
            "pair_id",
            "direction_evidence",
            "run_length",
            "first_blind_decision",
            "first_blind_reason_code",
            "first_blind_comment",
        ],
        "append_only_review": True,
        "auto_labeling": False,
    }
