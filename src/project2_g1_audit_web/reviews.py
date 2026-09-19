"""G1 Human Review SSOT: append-only Web-owned SQLite.

Audit Run folders are never written. Current values are MAX(review_id)
per the Frozen Design keys. M07 table names are not reused.
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from project2_g1.final_semantics import (
    SEMANTICS_LINEAGE_ONLY,
    candidate_index_from_rows,
    view_members_for_final,
)

DEFAULT_REVIEWER = "DESIGN_OWNER"

SIGNAL_NAMES = (
    "TRANSLATION",
    "DIRECTION",
    "GRIPPER",
    "ROTATION",
    "ACTION",
    "VIDEO_ALIGNMENT",
)

SIGNAL_DECISIONS = ("NOT_REVIEWED", "PASS", "FAIL", "UNCERTAIN")
BOUNDARY_DECISIONS = ("NOT_REVIEWED", "VALID", "REDUNDANT", "MISALIGNED")

REDUNDANT_REASONS = (
    "REDUNDANT_SHORT_PAUSE",
    "REDUNDANT_DIRECTION_JITTER",
    "REDUNDANT_ROTATION",
    "REDUNDANT_ACTION_JITTER",
    "OTHER",
)
MISALIGNED_REASONS = (
    "MISALIGNED_GRIPPER",
    "MISALIGNED_MOTION_CHANGE",
    "OTHER",
)
MISSED_REASONS = (
    "MISSED_GRIPPER_TRANSITION",
    "MISSED_MOVE_STOP",
    "MISSED_STOP_MOVE",
    "MISSED_DIRECTION_CHANGE",
    "OTHER",
)

REVIEWED_SIGNAL = frozenset({"PASS", "FAIL", "UNCERTAIN"})
REVIEWED_BOUNDARY = frozenset({"VALID", "REDUNDANT", "MISALIGNED"})

SIGNAL_TABLE = "signal_review_history"
BOUNDARY_TABLE = "predicted_boundary_review_history"
ADDED_TABLE = "human_added_boundary_history"
NOTE_TABLE = "episode_note_history"


class ValidationFailed(ValueError):
    def __init__(self, errors: list[str]):
        self.errors = [str(item) for item in errors if str(item).strip()]
        super().__init__("VALIDATION_FAILED: " + " | ".join(self.errors))


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _parse_int(value: Any, *, field_name: str) -> int | None:
    text = _text(value)
    if text == "":
        return None
    try:
        number = float(text)
    except ValueError as exc:
        raise ValidationFailed([f"{field_name} must be an integer"]) from exc
    if number != int(number):
        raise ValidationFailed([f"{field_name} must be an integer"])
    return int(number)


def _same(left: Any, right: Any) -> bool:
    return _text(left) == _text(right)


@dataclass(frozen=True)
class SignalReview:
    review_id: int
    episode_id: str
    signal_contract_version: str
    signal_contract_hash: str
    signal_name: str
    decision: str
    comment: str
    source_run_id: str
    reviewer: str
    reviewed_at: str


@dataclass(frozen=True)
class BoundaryReview:
    review_id: int
    run_id: str
    episode_id: str
    boundary_id: str
    predicted_frame: int
    decision: str
    reason_code: str
    corrected_frame: int | None
    comment: str
    reviewer: str
    reviewed_at: str


@dataclass(frozen=True)
class AddedBoundary:
    review_id: int
    run_id: str
    episode_id: str
    added_group_id: str
    human_added_frame: int
    reason_code: str
    comment: str
    reviewer: str
    reviewed_at: str


@dataclass(frozen=True)
class EpisodeNote:
    review_id: int
    run_id: str
    episode_id: str
    comment: str
    reviewer: str
    reviewed_at: str


@dataclass
class EpisodeProgress:
    overall: str
    signal_reviewed: int
    signal_total: int
    boundary_reviewed: int
    boundary_total: int
    missed_n: int
    signal_fail: bool
    has_redundant: bool
    has_misaligned: bool
    has_missed: bool
    reused: bool = False


@dataclass
class SignalFormState:
    signal_name: str
    decision: str
    comment: str
    source_run_id: str = ""
    reviewed_at: str = ""
    reused: bool = False
    history_n: int = 0


@dataclass
class MemberEvidenceView:
    """Read-only merged-member display. Not a review target."""

    candidate_id: str
    candidate_type: str
    frame: int | None
    is_representative: bool


@dataclass
class BoundaryFormState:
    boundary_id: str
    predicted_frame: int
    candidate_type: str
    reason: str
    supporting_reasons: str
    review_flags: str
    member_candidate_ids: str
    decision: str
    reason_code: str
    corrected_frame: str
    comment: str
    history_n: int = 0
    representative_candidate_id: str = ""
    member_candidate_count: int = 0
    members: list[MemberEvidenceView] = field(default_factory=list)
    final_member_semantics: str = SEMANTICS_LINEAGE_ONLY
    show_merged_evidence: bool = False


@dataclass
class AddedFormState:
    added_group_id: str
    display_id: str
    human_added_frame: str
    reason_code: str
    comment: str
    history_n: int = 0


@dataclass
class EpisodeReviewState:
    signals: list[SignalFormState]
    boundaries: list[BoundaryFormState]
    added: list[AddedFormState]
    episode_note: str
    reused: bool
    progress: EpisodeProgress


def _row_signal(row: sqlite3.Row) -> SignalReview:
    return SignalReview(
        review_id=int(row["review_id"]),
        episode_id=str(row["episode_id"]),
        signal_contract_version=str(row["signal_contract_version"]),
        signal_contract_hash=str(row["signal_contract_hash"]),
        signal_name=str(row["signal_name"]),
        decision=str(row["decision"]),
        comment=str(row["comment"] or ""),
        source_run_id=str(row["source_run_id"]),
        reviewer=str(row["reviewer"] or ""),
        reviewed_at=str(row["reviewed_at"]),
    )


def _row_boundary(row: sqlite3.Row) -> BoundaryReview:
    corrected = row["corrected_frame"]
    return BoundaryReview(
        review_id=int(row["review_id"]),
        run_id=str(row["run_id"]),
        episode_id=str(row["episode_id"]),
        boundary_id=str(row["boundary_id"]),
        predicted_frame=int(row["predicted_frame"]),
        decision=str(row["decision"]),
        reason_code=str(row["reason_code"] or ""),
        corrected_frame=None if corrected is None or str(corrected) == "" else int(corrected),
        comment=str(row["comment"] or ""),
        reviewer=str(row["reviewer"] or ""),
        reviewed_at=str(row["reviewed_at"]),
    )


def _row_added(row: sqlite3.Row) -> AddedBoundary:
    return AddedBoundary(
        review_id=int(row["review_id"]),
        run_id=str(row["run_id"]),
        episode_id=str(row["episode_id"]),
        added_group_id=str(row["added_group_id"]),
        human_added_frame=int(row["human_added_frame"]),
        reason_code=str(row["reason_code"]),
        comment=str(row["comment"] or ""),
        reviewer=str(row["reviewer"] or ""),
        reviewed_at=str(row["reviewed_at"]),
    )


def _row_note(row: sqlite3.Row) -> EpisodeNote:
    return EpisodeNote(
        review_id=int(row["review_id"]),
        run_id=str(row["run_id"]),
        episode_id=str(row["episode_id"]),
        comment=str(row["comment"] or ""),
        reviewer=str(row["reviewer"] or ""),
        reviewed_at=str(row["reviewed_at"]),
    )


def compute_overall(
    *,
    signal_reviewed: int,
    signal_total: int,
    boundary_reviewed: int,
    boundary_total: int,
) -> str:
    if signal_reviewed <= 0 and boundary_reviewed <= 0:
        return "NOT_REVIEWED"
    if signal_reviewed >= signal_total and boundary_total >= 0 and boundary_reviewed >= boundary_total:
        return "REVIEWED"
    return "IN_PROGRESS"


class ReviewStore:
    def __init__(self, sqlite_path: str | Path, *, reviewer: str = DEFAULT_REVIEWER):
        self.sqlite_path = Path(sqlite_path)
        self.reviewer = str(reviewer or DEFAULT_REVIEWER).strip() or DEFAULT_REVIEWER
        self.fail_after_signal = False
        self._ensure_schema()

    def connect(self) -> sqlite3.Connection:
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(self.sqlite_path))
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        connection = self.connect()
        try:
            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {SIGNAL_TABLE} (
                    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    episode_id TEXT NOT NULL,
                    signal_contract_version TEXT NOT NULL,
                    signal_contract_hash TEXT NOT NULL,
                    signal_name TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    comment TEXT,
                    source_run_id TEXT NOT NULL,
                    reviewer TEXT NOT NULL,
                    reviewed_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {BOUNDARY_TABLE} (
                    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    episode_id TEXT NOT NULL,
                    boundary_id TEXT NOT NULL,
                    predicted_frame INTEGER NOT NULL,
                    decision TEXT NOT NULL,
                    reason_code TEXT,
                    corrected_frame INTEGER,
                    comment TEXT,
                    reviewer TEXT NOT NULL,
                    reviewed_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {ADDED_TABLE} (
                    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    episode_id TEXT NOT NULL,
                    added_group_id TEXT NOT NULL,
                    human_added_frame INTEGER NOT NULL,
                    reason_code TEXT NOT NULL,
                    comment TEXT,
                    reviewer TEXT NOT NULL,
                    reviewed_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {NOTE_TABLE} (
                    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    episode_id TEXT NOT NULL,
                    comment TEXT,
                    reviewer TEXT NOT NULL,
                    reviewed_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                f"CREATE INDEX IF NOT EXISTS idx_signal_current ON {SIGNAL_TABLE} (episode_id, signal_contract_hash, signal_name, review_id)"
            )
            connection.execute(
                f"CREATE INDEX IF NOT EXISTS idx_boundary_current ON {BOUNDARY_TABLE} (run_id, episode_id, boundary_id, review_id)"
            )
            connection.execute(
                f"CREATE INDEX IF NOT EXISTS idx_added_current ON {ADDED_TABLE} (run_id, episode_id, added_group_id, review_id)"
            )
            connection.execute(
                f"CREATE INDEX IF NOT EXISTS idx_note_current ON {NOTE_TABLE} (run_id, episode_id, review_id)"
            )
            connection.commit()
        finally:
            connection.close()

    def current_signals(
        self,
        *,
        episode_id: str,
        signal_contract_hash: str,
        signal_contract_version: str | None = None,
    ) -> dict[str, SignalReview]:
        connection = self.connect()
        try:
            rows = connection.execute(
                f"""
                SELECT * FROM {SIGNAL_TABLE}
                WHERE episode_id = ? AND signal_contract_hash = ?
                ORDER BY review_id DESC
                """,
                (episode_id, signal_contract_hash),
            ).fetchall()
        finally:
            connection.close()
        out: dict[str, SignalReview] = {}
        for row in rows:
            item = _row_signal(row)
            if signal_contract_version and item.signal_contract_version != signal_contract_version:
                continue
            if item.signal_name not in out:
                out[item.signal_name] = item
        return out

    def signal_history_n(self, *, episode_id: str, signal_contract_hash: str, signal_name: str) -> int:
        connection = self.connect()
        try:
            row = connection.execute(
                f"SELECT COUNT(*) FROM {SIGNAL_TABLE} WHERE episode_id = ? AND signal_contract_hash = ? AND signal_name = ?",
                (episode_id, signal_contract_hash, signal_name),
            ).fetchone()
        finally:
            connection.close()
        return int(row[0] if row else 0)

    def current_boundaries(self, *, run_id: str, episode_id: str) -> dict[str, BoundaryReview]:
        connection = self.connect()
        try:
            rows = connection.execute(
                f"""
                SELECT * FROM {BOUNDARY_TABLE}
                WHERE run_id = ? AND episode_id = ?
                ORDER BY review_id DESC
                """,
                (run_id, episode_id),
            ).fetchall()
        finally:
            connection.close()
        out: dict[str, BoundaryReview] = {}
        for row in rows:
            item = _row_boundary(row)
            if item.boundary_id not in out:
                out[item.boundary_id] = item
        return out

    def current_added(self, *, run_id: str, episode_id: str) -> list[AddedBoundary]:
        connection = self.connect()
        try:
            rows = connection.execute(
                f"""
                SELECT * FROM {ADDED_TABLE}
                WHERE run_id = ? AND episode_id = ?
                ORDER BY review_id DESC
                """,
                (run_id, episode_id),
            ).fetchall()
        finally:
            connection.close()
        latest: dict[str, AddedBoundary] = {}
        for row in rows:
            item = _row_added(row)
            if item.added_group_id not in latest:
                latest[item.added_group_id] = item
        ordered = sorted(latest.values(), key=lambda item: item.review_id)
        return ordered

    def current_note(self, *, run_id: str, episode_id: str) -> EpisodeNote | None:
        connection = self.connect()
        try:
            row = connection.execute(
                f"""
                SELECT * FROM {NOTE_TABLE}
                WHERE run_id = ? AND episode_id = ?
                ORDER BY review_id DESC
                LIMIT 1
                """,
                (run_id, episode_id),
            ).fetchone()
        finally:
            connection.close()
        return _row_note(row) if row is not None else None

    def history_counts(self, *, run_id: str, episode_id: str, signal_contract_hash: str) -> dict[str, int]:
        connection = self.connect()
        try:
            signal_n = connection.execute(
                f"SELECT COUNT(*) FROM {SIGNAL_TABLE} WHERE episode_id = ? AND signal_contract_hash = ?",
                (episode_id, signal_contract_hash),
            ).fetchone()[0]
            boundary_n = connection.execute(
                f"SELECT COUNT(*) FROM {BOUNDARY_TABLE} WHERE run_id = ? AND episode_id = ?",
                (run_id, episode_id),
            ).fetchone()[0]
            added_n = connection.execute(
                f"SELECT COUNT(*) FROM {ADDED_TABLE} WHERE run_id = ? AND episode_id = ?",
                (run_id, episode_id),
            ).fetchone()[0]
            note_n = connection.execute(
                f"SELECT COUNT(*) FROM {NOTE_TABLE} WHERE run_id = ? AND episode_id = ?",
                (run_id, episode_id),
            ).fetchone()[0]
        finally:
            connection.close()
        return {
            "signal": int(signal_n),
            "boundary": int(boundary_n),
            "added": int(added_n),
            "note": int(note_n),
        }

    def progress_for_run(
        self,
        *,
        run_id: str,
        signal_contract_hash: str,
        signal_contract_version: str,
        boundary_ids_by_episode: Mapping[str, Iterable[str]],
        current_run_id: str,
    ) -> dict[str, EpisodeProgress]:
        episode_ids = [str(item) for item in boundary_ids_by_episode.keys()]
        connection = self.connect()
        try:
            signals, signal_objs = self._latest_signals(
                connection, episode_ids, signal_contract_hash, signal_contract_version
            )
            boundaries = self._latest_boundaries(connection, run_id, episode_ids)
            added = self._latest_added(connection, run_id, episode_ids)
        finally:
            connection.close()
        out: dict[str, EpisodeProgress] = {}
        for episode_id, boundary_ids in boundary_ids_by_episode.items():
            ids = [str(item) for item in boundary_ids if str(item).strip()]
            sig_map = signals.get(episode_id, {})
            signal_reviewed = sum(1 for name in SIGNAL_NAMES if sig_map.get(name) in REVIEWED_SIGNAL)
            signal_fail = any(sig_map.get(name) == "FAIL" for name in SIGNAL_NAMES)
            reused = any(
                item.source_run_id != current_run_id
                for item in signal_objs.get(episode_id, {}).values()
            )
            bound_map = boundaries.get(episode_id, {})
            bound_reviewed = 0
            has_redundant = False
            has_misaligned = False
            for bid in ids:
                decision = bound_map.get(bid)
                if decision in REVIEWED_BOUNDARY:
                    bound_reviewed += 1
                if decision == "REDUNDANT":
                    has_redundant = True
                if decision == "MISALIGNED":
                    has_misaligned = True
            missed_n = len(added.get(episode_id, ()))
            out[episode_id] = EpisodeProgress(
                overall=compute_overall(
                    signal_reviewed=signal_reviewed,
                    signal_total=len(SIGNAL_NAMES),
                    boundary_reviewed=bound_reviewed,
                    boundary_total=len(ids),
                ),
                signal_reviewed=signal_reviewed,
                signal_total=len(SIGNAL_NAMES),
                boundary_reviewed=bound_reviewed,
                boundary_total=len(ids),
                missed_n=missed_n,
                signal_fail=signal_fail,
                has_redundant=has_redundant,
                has_misaligned=has_misaligned,
                has_missed=missed_n > 0,
                reused=reused,
            )
        return out

    def _latest_signals(
        self,
        connection: sqlite3.Connection,
        episode_ids: list[str],
        signal_contract_hash: str,
        signal_contract_version: str,
    ) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, SignalReview]]]:
        if not episode_ids:
            return {}, {}
        placeholders = ",".join("?" for _ in episode_ids)
        rows = connection.execute(
            f"""
            SELECT * FROM {SIGNAL_TABLE}
            WHERE signal_contract_hash = ? AND episode_id IN ({placeholders})
            ORDER BY review_id DESC
            """,
            (signal_contract_hash, *episode_ids),
        ).fetchall()
        decisions: dict[str, dict[str, str]] = {}
        objects: dict[str, dict[str, SignalReview]] = {}
        for row in rows:
            item = _row_signal(row)
            if item.signal_contract_version != signal_contract_version:
                continue
            decisions.setdefault(item.episode_id, {})
            objects.setdefault(item.episode_id, {})
            if item.signal_name not in decisions[item.episode_id]:
                decisions[item.episode_id][item.signal_name] = item.decision
                objects[item.episode_id][item.signal_name] = item
        return decisions, objects

    def _latest_boundaries(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        episode_ids: list[str],
    ) -> dict[str, dict[str, str]]:
        if not episode_ids:
            return {}
        placeholders = ",".join("?" for _ in episode_ids)
        rows = connection.execute(
            f"""
            SELECT * FROM {BOUNDARY_TABLE}
            WHERE run_id = ? AND episode_id IN ({placeholders})
            ORDER BY review_id DESC
            """,
            (run_id, *episode_ids),
        ).fetchall()
        out: dict[str, dict[str, str]] = {}
        for row in rows:
            item = _row_boundary(row)
            bucket = out.setdefault(item.episode_id, {})
            if item.boundary_id not in bucket:
                bucket[item.boundary_id] = item.decision
        return out

    def _latest_added(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        episode_ids: list[str],
    ) -> dict[str, set[str]]:
        if not episode_ids:
            return {}
        placeholders = ",".join("?" for _ in episode_ids)
        rows = connection.execute(
            f"""
            SELECT * FROM {ADDED_TABLE}
            WHERE run_id = ? AND episode_id IN ({placeholders})
            ORDER BY review_id DESC
            """,
            (run_id, *episode_ids),
        ).fetchall()
        out: dict[str, set[str]] = {}
        for row in rows:
            item = _row_added(row)
            bucket = out.setdefault(item.episode_id, set())
            if item.added_group_id not in bucket:
                bucket.add(item.added_group_id)
        return out

    def validate_and_collect(
        self,
        *,
        run_id: str,
        episode_id: str,
        signal_contract_version: str,
        signal_contract_hash: str,
        episode_length: int,
        predicted: Mapping[str, int],
        signals: Mapping[str, Mapping[str, str]],
        boundaries: Mapping[str, Mapping[str, str]],
        added: Iterable[Mapping[str, str]],
        episode_note: str,
    ) -> dict[str, Any]:
        errors: list[str] = []
        if int(episode_length) < 1:
            errors.append("episode length missing from validated run")

        current_signals = self.current_signals(
            episode_id=episode_id,
            signal_contract_hash=signal_contract_hash,
            signal_contract_version=signal_contract_version,
        )
        signal_inserts: list[tuple] = []
        for name in SIGNAL_NAMES:
            payload = signals.get(name, {})
            decision = _text(payload.get("decision") or "NOT_REVIEWED")
            comment = str(payload.get("comment") or "")
            if decision not in SIGNAL_DECISIONS:
                errors.append(f"illegal signal decision for {name}: {decision}")
                continue
            existing = current_signals.get(name)
            unchanged = (
                existing is None and decision == "NOT_REVIEWED" and _text(comment) == ""
            ) or (
                existing is not None
                and existing.decision == decision
                and existing.comment == comment
            )
            if unchanged:
                continue
            if decision == "NOT_REVIEWED" and existing is None and _text(comment) == "":
                continue
            signal_inserts.append((name, decision, comment))

        current_bounds = self.current_boundaries(run_id=run_id, episode_id=episode_id)
        bound_inserts: list[tuple] = []
        for boundary_id, payload in boundaries.items():
            bid = _text(boundary_id)
            if bid not in predicted:
                errors.append(f"boundary_id not in final_boundaries.csv: {bid}")
                continue
            decision = _text(payload.get("decision") or "NOT_REVIEWED")
            reason_code = _text(payload.get("reason_code"))
            comment = str(payload.get("comment") or "")
            if decision not in BOUNDARY_DECISIONS:
                errors.append(f"illegal boundary decision for {bid}: {decision}")
                continue
            predicted_frame = int(predicted[bid])
            corrected: int | None = None
            store_reason = ""
            try:
                if decision == "VALID":
                    store_reason = ""
                    corrected = None
                elif decision == "REDUNDANT":
                    if reason_code not in REDUNDANT_REASONS:
                        errors.append(f"REDUNDANT requires a compatible reason_code for {bid}")
                    elif reason_code == "OTHER" and _text(comment) == "":
                        errors.append(f"OTHER requires comment for {bid}")
                    else:
                        store_reason = reason_code
                elif decision == "MISALIGNED":
                    try:
                        corrected = _parse_int(payload.get("corrected_frame"), field_name=f"corrected_frame:{bid}")
                    except ValidationFailed as exc:
                        errors.extend(exc.errors)
                        continue
                    if corrected is None:
                        errors.append(f"MISALIGNED requires corrected_frame for {bid}")
                    elif not (0 <= corrected < int(episode_length)):
                        errors.append(f"corrected_frame out of range for {bid}")
                    if reason_code not in MISALIGNED_REASONS:
                        errors.append(f"MISALIGNED requires a compatible reason_code for {bid}")
                    elif reason_code == "OTHER" and _text(comment) == "":
                        errors.append(f"OTHER requires comment for {bid}")
                    else:
                        store_reason = reason_code
                else:
                    store_reason = ""
                    corrected = None
            except ValidationFailed as exc:
                errors.extend(exc.errors)
                continue
            existing = current_bounds.get(bid)
            existing_corrected = "" if existing is None or existing.corrected_frame is None else str(existing.corrected_frame)
            new_corrected = "" if corrected is None else str(corrected)
            unchanged = (
                existing is None and decision == "NOT_REVIEWED" and _text(comment) == ""
            ) or (
                existing is not None
                and existing.decision == decision
                and _text(existing.reason_code) == store_reason
                and existing_corrected == new_corrected
                and existing.comment == comment
            )
            if unchanged:
                continue
            bound_inserts.append((bid, predicted_frame, decision, store_reason, corrected, comment))

        current_added = {item.added_group_id: item for item in self.current_added(run_id=run_id, episode_id=episode_id)}
        added_inserts: list[tuple] = []
        for payload in added:
            frame_raw = payload.get("human_added_frame")
            reason_code = _text(payload.get("reason_code"))
            comment = str(payload.get("comment") or "")
            group_id = _text(payload.get("added_group_id"))
            blank = _text(frame_raw) == "" and reason_code == "" and _text(comment) == "" and group_id == ""
            if blank:
                continue
            try:
                frame = _parse_int(frame_raw, field_name="human_added_frame")
            except ValidationFailed as exc:
                errors.extend(exc.errors)
                continue
            if frame is None:
                errors.append("MISSED requires human_added_frame")
                continue
            if not (0 <= frame < int(episode_length)):
                errors.append("human_added_frame out of range")
            if reason_code not in MISSED_REASONS:
                errors.append("MISSED requires a compatible reason_code")
            elif reason_code == "OTHER" and _text(comment) == "":
                errors.append("OTHER requires comment for missed boundary")
            if group_id == "":
                group_id = str(uuid.uuid4())
            existing = current_added.get(group_id)
            unchanged = (
                existing is not None
                and existing.human_added_frame == frame
                and existing.reason_code == reason_code
                and existing.comment == comment
            )
            if unchanged:
                continue
            added_inserts.append((group_id, frame, reason_code, comment))

        current_note = self.current_note(run_id=run_id, episode_id=episode_id)
        note_text = str(episode_note or "")
        note_insert = None
        if current_note is None:
            if _text(note_text):
                note_insert = note_text
        elif current_note.comment != note_text:
            note_insert = note_text

        if errors:
            raise ValidationFailed(errors)
        return {
            "signals": signal_inserts,
            "boundaries": bound_inserts,
            "added": added_inserts,
            "note": note_insert,
        }

    def save_episode(
        self,
        *,
        run_id: str,
        episode_id: str,
        signal_contract_version: str,
        signal_contract_hash: str,
        episode_length: int,
        predicted: Mapping[str, int],
        signals: Mapping[str, Mapping[str, str]],
        boundaries: Mapping[str, Mapping[str, str]],
        added: Iterable[Mapping[str, str]],
        episode_note: str,
    ) -> None:
        plan = self.validate_and_collect(
            run_id=run_id,
            episode_id=episode_id,
            signal_contract_version=signal_contract_version,
            signal_contract_hash=signal_contract_hash,
            episode_length=episode_length,
            predicted=predicted,
            signals=signals,
            boundaries=boundaries,
            added=added,
            episode_note=episode_note,
        )
        reviewed_at = _now()
        connection = self.connect()
        try:
            connection.execute("BEGIN")
            for name, decision, comment in plan["signals"]:
                connection.execute(
                    f"""
                    INSERT INTO {SIGNAL_TABLE} (
                        episode_id, signal_contract_version, signal_contract_hash,
                        signal_name, decision, comment, source_run_id, reviewer, reviewed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        episode_id,
                        signal_contract_version,
                        signal_contract_hash,
                        name,
                        decision,
                        comment,
                        run_id,
                        self.reviewer,
                        reviewed_at,
                    ),
                )
            if self.fail_after_signal:
                raise ValidationFailed(["forced review transaction failure"])
            for bid, predicted_frame, decision, reason_code, corrected, comment in plan["boundaries"]:
                connection.execute(
                    f"""
                    INSERT INTO {BOUNDARY_TABLE} (
                        run_id, episode_id, boundary_id, predicted_frame,
                        decision, reason_code, corrected_frame, comment, reviewer, reviewed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        episode_id,
                        bid,
                        predicted_frame,
                        decision,
                        reason_code,
                        corrected,
                        comment,
                        self.reviewer,
                        reviewed_at,
                    ),
                )
            for group_id, frame, reason_code, comment in plan["added"]:
                connection.execute(
                    f"""
                    INSERT INTO {ADDED_TABLE} (
                        run_id, episode_id, added_group_id, human_added_frame,
                        reason_code, comment, reviewer, reviewed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        episode_id,
                        group_id,
                        frame,
                        reason_code,
                        comment,
                        self.reviewer,
                        reviewed_at,
                    ),
                )
            if plan["note"] is not None:
                connection.execute(
                    f"""
                    INSERT INTO {NOTE_TABLE} (
                        run_id, episode_id, comment, reviewer, reviewed_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (run_id, episode_id, plan["note"], self.reviewer, reviewed_at),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


def predicted_frames(boundaries: Iterable[Mapping[str, str]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in boundaries:
        bid = _text(row.get("boundary_id"))
        if not bid:
            continue
        frame = _parse_int(row.get("frame"), field_name=f"predicted_frame:{bid}")
        if frame is None:
            raise ValidationFailed([f"predicted_frame missing for {bid}"])
        out[bid] = frame
    return out


def parse_form(form: Mapping[str, Any]) -> dict[str, Any]:
    signals = {
        name: {
            "decision": _text(form.get(f"signal_{name}_decision") or "NOT_REVIEWED"),
            "comment": str(form.get(f"signal_{name}_comment") or ""),
        }
        for name in SIGNAL_NAMES
    }
    boundaries: dict[str, dict[str, str]] = {}
    added: list[dict[str, str]] = []
    for key in form.keys():
        text = str(key)
        if text.startswith("bound_") and text.endswith("_decision"):
            bid = text[len("bound_") : -len("_decision")]
            boundaries[bid] = {
                "decision": str(form.get(f"bound_{bid}_decision") or "NOT_REVIEWED"),
                "reason_code": str(form.get(f"bound_{bid}_reason_code") or ""),
                "corrected_frame": str(form.get(f"bound_{bid}_corrected_frame") or ""),
                "comment": str(form.get(f"bound_{bid}_comment") or ""),
            }
        if text.startswith("missed_") and text.endswith("_frame"):
            index = text[len("missed_") : -len("_frame")]
            added.append(
                {
                    "added_group_id": str(form.get(f"missed_{index}_group_id") or ""),
                    "human_added_frame": str(form.get(f"missed_{index}_frame") or ""),
                    "reason_code": str(form.get(f"missed_{index}_reason_code") or ""),
                    "comment": str(form.get(f"missed_{index}_comment") or ""),
                }
            )
    return {
        "action": _text(form.get("action") or "save") or "save",
        "signals": signals,
        "boundaries": boundaries,
        "added": added,
        "episode_note": str(form.get("episode_note") or ""),
    }


def _member_views_for_boundary(
    row: Mapping[str, Any],
    candidates_by_id: Mapping[str, Mapping[str, Any]],
    *,
    schema: str,
) -> tuple[list[MemberEvidenceView], str]:
    raw_members = view_members_for_final(row, candidates_by_id, schema=schema)
    views: list[MemberEvidenceView] = []
    for item in raw_members:
        frame_raw = item.get("frame")
        frame: int | None
        try:
            frame = int(frame_raw) if frame_raw is not None and str(frame_raw).strip() != "" else None
        except (TypeError, ValueError):
            frame = None
        views.append(
            MemberEvidenceView(
                candidate_id=str(item.get("candidate_id") or ""),
                candidate_type=str(item.get("candidate_type") or "UNKNOWN"),
                frame=frame,
                is_representative=bool(item.get("is_representative")),
            )
        )
    representative = next(
        (item.candidate_id for item in views if item.is_representative),
        str(row.get("representative_candidate_id") or ""),
    )
    return views, representative


def build_episode_review_state(
    store: ReviewStore,
    *,
    run_id: str,
    episode_id: str,
    signal_contract_version: str,
    signal_contract_hash: str,
    boundary_rows: Iterable[Mapping[str, str]],
    overlay: Mapping[str, Any] | None = None,
    candidate_rows: Iterable[Mapping[str, str]] | None = None,
    final_member_semantics: str = SEMANTICS_LINEAGE_ONLY,
) -> EpisodeReviewState:
    overlay = overlay or {}
    overlay_signals = overlay.get("signals") or {}
    overlay_bounds = overlay.get("boundaries") or {}
    overlay_added = overlay.get("added")
    current_signals = store.current_signals(
        episode_id=episode_id,
        signal_contract_hash=signal_contract_hash,
        signal_contract_version=signal_contract_version,
    )
    signals: list[SignalFormState] = []
    reused = False
    for name in SIGNAL_NAMES:
        existing = current_signals.get(name)
        posted = overlay_signals.get(name) or {}
        decision = _text(posted.get("decision")) or (existing.decision if existing else "NOT_REVIEWED")
        comment = posted.get("comment") if "comment" in posted else (existing.comment if existing else "")
        is_reused = bool(existing and existing.source_run_id != run_id)
        if is_reused:
            reused = True
        signals.append(
            SignalFormState(
                signal_name=name,
                decision=decision,
                comment=str(comment or ""),
                source_run_id=existing.source_run_id if existing else "",
                reviewed_at=existing.reviewed_at if existing else "",
                reused=is_reused,
                history_n=store.signal_history_n(
                    episode_id=episode_id,
                    signal_contract_hash=signal_contract_hash,
                    signal_name=name,
                ),
            )
        )
    current_bounds = store.current_boundaries(run_id=run_id, episode_id=episode_id)
    candidates_by_id = candidate_index_from_rows(candidate_rows or [])
    schema = str(final_member_semantics or SEMANTICS_LINEAGE_ONLY)
    boundaries: list[BoundaryFormState] = []
    ids: list[str] = []
    for row in boundary_rows:
        bid = _text(row.get("boundary_id"))
        if not bid:
            continue
        ids.append(bid)
        existing = current_bounds.get(bid)
        posted = overlay_bounds.get(bid) or {}
        decision = _text(posted.get("decision")) or (existing.decision if existing else "NOT_REVIEWED")
        reason_code = posted.get("reason_code") if "reason_code" in posted else (existing.reason_code if existing else "")
        if "corrected_frame" in posted:
            corrected = str(posted.get("corrected_frame") or "")
        elif existing and existing.corrected_frame is not None:
            corrected = str(existing.corrected_frame)
        else:
            corrected = ""
        comment = posted.get("comment") if "comment" in posted else (existing.comment if existing else "")
        frame = int(_parse_int(row.get("frame"), field_name=f"frame:{bid}") or 0)
        members, representative_id = _member_views_for_boundary(
            row,
            candidates_by_id,
            schema=schema,
        )
        boundaries.append(
            BoundaryFormState(
                boundary_id=bid,
                predicted_frame=frame,
                candidate_type=str(row.get("candidate_type") or ""),
                reason=str(row.get("reason") or ""),
                supporting_reasons=str(row.get("supporting_reasons") or ""),
                review_flags=str(row.get("review_flags") or ""),
                member_candidate_ids=str(row.get("member_candidate_ids") or ""),
                decision=decision,
                reason_code=_text(reason_code),
                corrected_frame=corrected,
                comment=str(comment or ""),
                history_n=1 if existing else 0,
                representative_candidate_id=representative_id,
                member_candidate_count=len(members),
                members=members,
                final_member_semantics=schema,
                show_merged_evidence=len(members) > 1,
            )
        )
    if overlay_added is not None:
        added_src = list(overlay_added)
    else:
        added_src = [
            {
                "added_group_id": item.added_group_id,
                "human_added_frame": str(item.human_added_frame),
                "reason_code": item.reason_code,
                "comment": item.comment,
            }
            for item in store.current_added(run_id=run_id, episode_id=episode_id)
        ]
    added: list[AddedFormState] = []
    for index, payload in enumerate(added_src, start=1):
        group_id = _text(payload.get("added_group_id"))
        added.append(
            AddedFormState(
                added_group_id=group_id,
                display_id=f"HUMAN_ADD_{index}",
                human_added_frame=str(payload.get("human_added_frame") or ""),
                reason_code=_text(payload.get("reason_code")),
                comment=str(payload.get("comment") or ""),
            )
        )
    note_existing = store.current_note(run_id=run_id, episode_id=episode_id)
    if "episode_note" in overlay:
        note_text = str(overlay.get("episode_note") or "")
    else:
        note_text = note_existing.comment if note_existing else ""
    reviewed_signals = sum(1 for item in signals if item.decision in REVIEWED_SIGNAL)
    reviewed_bounds = sum(1 for item in boundaries if item.decision in REVIEWED_BOUNDARY)
    progress = EpisodeProgress(
        overall=compute_overall(
            signal_reviewed=reviewed_signals,
            signal_total=len(SIGNAL_NAMES),
            boundary_reviewed=reviewed_bounds,
            boundary_total=len(boundaries),
        ),
        signal_reviewed=reviewed_signals,
        signal_total=len(SIGNAL_NAMES),
        boundary_reviewed=reviewed_bounds,
        boundary_total=len(boundaries),
        missed_n=len([item for item in added if item.added_group_id or item.human_added_frame]),
        signal_fail=any(item.decision == "FAIL" for item in signals),
        has_redundant=any(item.decision == "REDUNDANT" for item in boundaries),
        has_misaligned=any(item.decision == "MISALIGNED" for item in boundaries),
        has_missed=any(bool(item.added_group_id or item.human_added_frame) for item in added),
        reused=reused,
    )
    return EpisodeReviewState(
        signals=signals,
        boundaries=boundaries,
        added=added,
        episode_note=note_text,
        reused=reused,
        progress=progress,
    )


def empty_progress(boundary_total: int) -> EpisodeProgress:
    return EpisodeProgress(
        overall="NOT_REVIEWED",
        signal_reviewed=0,
        signal_total=len(SIGNAL_NAMES),
        boundary_reviewed=0,
        boundary_total=boundary_total,
        missed_n=0,
        signal_fail=False,
        has_redundant=False,
        has_misaligned=False,
        has_missed=False,
    )
