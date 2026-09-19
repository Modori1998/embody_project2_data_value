"""Denormalized Final Boundary member semantics.

Detector / consolidation decisions are not computed here. These fields are
MATERIALIZED copies of Candidate records so downstream consumers do not
need to join. Candidate CSVs remain the provenance SSOT.

Member pipe fields are positional:
  member_candidate_ids[i] ↔ member_candidate_types[i] ↔ member_candidate_frames[i]

Ordering (deterministic, not dict/set/filesystem order):
  frame ASC, then candidate_id ASC

representative_candidate_id is the real consolidation representative. It is
never inferred as "first member after sort".
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

SEMANTICS_LINEAGE_ONLY = "LINEAGE_ONLY"
SEMANTICS_MATERIALIZED = "MATERIALIZED"
FINAL_BOUNDARY_SEMANTICS_V1 = "MATERIALIZED_V1"

MATERIALIZED_COLUMNS = (
    "representative_candidate_id",
    "member_candidate_types",
    "member_candidate_frames",
    "member_candidate_count",
)

# Existing lineage column; kept and aligned with the new type/frame pipes.
LINEAGE_ID_COLUMN = "member_candidate_ids"


class FinalSemanticsError(ValueError):
    """Fail-fast: materialized Final fields disagree with Candidate SSOT."""


def split_pipe(value: Any) -> list[str]:
    text = str(value or "").strip()
    if text == "":
        return []
    return [part.strip() for part in text.split("|")]


def join_pipe(parts: Iterable[Any]) -> str:
    return "|".join(str(part).strip() for part in parts if str(part).strip() != "")


def detect_final_schema(fieldnames: Iterable[str] | None) -> str:
    names = {str(name or "").strip() for name in (fieldnames or [])}
    present = [name for name in MATERIALIZED_COLUMNS if name in names]
    if not present:
        return SEMANTICS_LINEAGE_ONLY
    if len(present) != len(MATERIALIZED_COLUMNS):
        missing = [name for name in MATERIALIZED_COLUMNS if name not in names]
        raise FinalSemanticsError(
            "partial materialized Final schema; missing columns: " + ", ".join(missing)
        )
    return SEMANTICS_MATERIALIZED


def sort_member_records(members: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Stable display/materialization order: frame ASC, candidate_id ASC."""

    records = []
    for item in members:
        cid = str(item.get("candidate_id") or "").strip()
        if not cid:
            raise FinalSemanticsError("member record missing candidate_id")
        try:
            frame = int(item.get("frame"))
        except (TypeError, ValueError) as exc:
            raise FinalSemanticsError(f"{cid}: member frame is not an integer") from exc
        records.append(
            {
                "candidate_id": cid,
                "candidate_type": str(item.get("candidate_type") or "").strip(),
                "frame": frame,
            }
        )
    records.sort(key=lambda item: (int(item["frame"]), str(item["candidate_id"])))
    return records


def build_materialized_fields(
    *,
    representative_candidate_id: str,
    members: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    ordered = sort_member_records(members)
    rep = str(representative_candidate_id or "").strip()
    if not ordered:
        raise FinalSemanticsError("Final Boundary has no member candidates")
    if not rep:
        raise FinalSemanticsError("representative_candidate_id is empty")
    ids = [item["candidate_id"] for item in ordered]
    if rep not in ids:
        raise FinalSemanticsError(
            f"representative_candidate_id {rep} is not in member_candidate_ids"
        )
    return {
        "representative_candidate_id": rep,
        "member_candidate_ids": join_pipe(ids),
        "member_candidate_types": join_pipe(item["candidate_type"] for item in ordered),
        "member_candidate_frames": join_pipe(item["frame"] for item in ordered),
        "member_candidate_count": len(ordered),
        "members": ordered,
    }


def recover_representative_id(
    *,
    final_frame: int,
    final_type: str,
    members: Iterable[Mapping[str, Any]],
) -> str:
    """Recover representative from already-chosen Final frame+type.

    Used only when rewriting a lineage-only CSV. Does not use list[0].
    Ambiguous or missing matches fail fast.
    """

    wanted_type = str(final_type or "").strip()
    matches = [
        item
        for item in members
        if int(item["frame"]) == int(final_frame) and str(item.get("candidate_type") or "").strip() == wanted_type
    ]
    if len(matches) != 1:
        raise FinalSemanticsError(
            f"cannot recover unique representative for type={wanted_type!r} frame={final_frame}; "
            f"matches={len(matches)}"
        )
    return str(matches[0]["candidate_id"])


def _candidate_index(rows: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    out: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        cid = str(row.get("candidate_id") or "").strip()
        if cid:
            out[cid] = row
    return out


def members_from_lineage_ids(
    member_ids: Iterable[str],
    candidates_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    records = []
    for cid in member_ids:
        raw = candidates_by_id.get(cid)
        if raw is None:
            raise FinalSemanticsError(f"member_candidate_id not in candidate table: {cid}")
        records.append(
            {
                "candidate_id": cid,
                "candidate_type": str(raw.get("candidate_type") or "").strip(),
                "frame": int(raw.get("frame")),
            }
        )
    return sort_member_records(records)


def materialize_final_row(
    final_row: Mapping[str, Any],
    candidates_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Copy a lineage Final row and attach materialized member columns from Candidate SSOT."""

    row = dict(final_row)
    ids = split_pipe(row.get(LINEAGE_ID_COLUMN))
    members = members_from_lineage_ids(ids, candidates_by_id)
    try:
        final_frame = int(row.get("frame"))
    except (TypeError, ValueError) as exc:
        raise FinalSemanticsError(
            f"{row.get('boundary_id')}: Final frame is not an integer"
        ) from exc
    rep = recover_representative_id(
        final_frame=final_frame,
        final_type=str(row.get("candidate_type") or ""),
        members=members,
    )
    fields = build_materialized_fields(representative_candidate_id=rep, members=members)
    row.update(fields)
    validate_materialized_final_row(row, candidates_by_id)
    return row


def validate_materialized_final_row(
    row: Mapping[str, Any],
    candidates_by_id: Mapping[str, Mapping[str, Any]],
) -> None:
    bid = str(row.get("boundary_id") or "").strip() or "unknown-boundary"
    ids = split_pipe(row.get(LINEAGE_ID_COLUMN))
    types = split_pipe(row.get("member_candidate_types"))
    frames = split_pipe(row.get("member_candidate_frames"))
    try:
        count = int(str(row.get("member_candidate_count")).strip())
    except (TypeError, ValueError) as exc:
        raise FinalSemanticsError(f"{bid}: member_candidate_count is not an integer") from exc
    if not (len(ids) == len(types) == len(frames) == count):
        raise FinalSemanticsError(
            f"{bid}: member pipe length mismatch "
            f"ids={len(ids)} types={len(types)} frames={len(frames)} count={count}"
        )
    if count < 1:
        raise FinalSemanticsError(f"{bid}: member_candidate_count must be >= 1")
    rep = str(row.get("representative_candidate_id") or "").strip()
    if rep not in ids:
        raise FinalSemanticsError(f"{bid}: representative_candidate_id not in member_candidate_ids")
    try:
        final_frame = int(row.get("frame"))
    except (TypeError, ValueError) as exc:
        raise FinalSemanticsError(f"{bid}: Final frame is not an integer") from exc
    final_type = str(row.get("candidate_type") or "").strip()
    for cid, mtype, mframe in zip(ids, types, frames):
        raw = candidates_by_id.get(cid)
        if raw is None:
            raise FinalSemanticsError(f"{bid}: member_candidate_id not in candidate table: {cid}")
        cand_type = str(raw.get("candidate_type") or "").strip()
        try:
            cand_frame = int(raw.get("frame"))
        except (TypeError, ValueError) as exc:
            raise FinalSemanticsError(f"{bid}: candidate {cid} frame is not an integer") from exc
        try:
            want_frame = int(mframe)
        except (TypeError, ValueError) as exc:
            raise FinalSemanticsError(f"{bid}: member_candidate_frames contains a non-integer") from exc
        if mtype != cand_type:
            raise FinalSemanticsError(
                f"{bid}: materialized type for {cid} is {mtype!r}, candidate table has {cand_type!r}"
            )
        if want_frame != cand_frame:
            raise FinalSemanticsError(
                f"{bid}: materialized frame for {cid} is {want_frame}, candidate table has {cand_frame}"
            )
    raw_rep = candidates_by_id.get(rep)
    if raw_rep is None:
        raise FinalSemanticsError(f"{bid}: representative_candidate_id missing from candidate table: {rep}")
    if str(raw_rep.get("candidate_type") or "").strip() != final_type:
        raise FinalSemanticsError(
            f"{bid}: representative type {raw_rep.get('candidate_type')!r} != Final candidate_type {final_type!r}"
        )
    try:
        rep_frame = int(raw_rep.get("frame"))
    except (TypeError, ValueError) as exc:
        raise FinalSemanticsError(f"{bid}: representative frame is not an integer") from exc
    if rep_frame != final_frame:
        raise FinalSemanticsError(
            f"{bid}: representative frame {rep_frame} != Final frame {final_frame}"
        )


def view_members_for_final(
    row: Mapping[str, Any],
    candidates_by_id: Mapping[str, Mapping[str, Any]],
    *,
    schema: str,
) -> list[dict[str, Any]]:
    """Presentation helper. Legacy runs join Candidate; materialized runs trust Final columns.

    Missing Candidate rows on lineage-only runs are still shown (UNKNOWN type), never hidden.
    """

    ids = split_pipe(row.get(LINEAGE_ID_COLUMN))
    if schema == SEMANTICS_MATERIALIZED:
        types = split_pipe(row.get("member_candidate_types"))
        frames = split_pipe(row.get("member_candidate_frames"))
        rep = str(row.get("representative_candidate_id") or "").strip()
        out = []
        for cid, mtype, mframe in zip(ids, types, frames):
            try:
                frame = int(mframe)
            except (TypeError, ValueError):
                frame = None
            out.append(
                {
                    "candidate_id": cid,
                    "candidate_type": mtype or "UNKNOWN",
                    "frame": frame,
                    "is_representative": cid == rep,
                }
            )
        return out

    records = []
    for cid in ids:
        raw = candidates_by_id.get(cid)
        if raw is None:
            records.append(
                {
                    "candidate_id": cid,
                    "candidate_type": "UNKNOWN",
                    "frame": None,
                    "is_representative": False,
                }
            )
            continue
        try:
            frame = int(raw.get("frame"))
        except (TypeError, ValueError):
            frame = None
        records.append(
            {
                "candidate_id": cid,
                "candidate_type": str(raw.get("candidate_type") or "").strip() or "UNKNOWN",
                "frame": frame,
                "is_representative": False,
            }
        )
    records.sort(key=lambda item: (item["frame"] is None, item["frame"] if item["frame"] is not None else 0, item["candidate_id"]))
    try:
        final_frame = int(row.get("frame"))
    except (TypeError, ValueError):
        final_frame = None
    final_type = str(row.get("candidate_type") or "").strip()
    matched = [
        item
        for item in records
        if item["frame"] == final_frame and item["candidate_type"] == final_type
    ]
    if len(matched) == 1:
        matched[0]["is_representative"] = True
    return records


def candidate_index_from_rows(rows: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return _candidate_index(rows)
