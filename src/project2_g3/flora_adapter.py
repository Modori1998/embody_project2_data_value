"""Flora native -> P2 G1 *candidate* links. No model calls; never alters source JSON.

No G1 provenance means no verified alignment. The optional manifest must be
an externally sourced video-frame -> original source-frame record; it is never
inferred from filename or nominal fps.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import zipfile
from collections import Counter
from pathlib import Path

ADAPTER_VERSION = "P2_FLORA_G3_LINK_V0_1_PROPOSED"
EXPECTED_CLOCK = "seconds relative to the first native source presentation timestamp"
G3_FIELDS = (
    "motion_phase", "object_relation", "gripper_state", "event_assessment",
    "events", "evidence_frame_indices", "evidence_quality", "observation_note",
)


class AdapterError(ValueError):
    """Malformed input or provenance contradiction; never repaired silently."""


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _finite(value, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise AdapterError(f"INVALID_{label}")
    return float(value)


def _manifest_by_episode(path: str | Path | None) -> dict:
    if path is None:
        return {}
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    if obj.get("schema_version") != "P2_FLORA_G1_SOURCE_MAPPING_V0_1":
        raise AdapterError("UNKNOWN_MAPPING_MANIFEST_VERSION")
    eps = obj.get("episodes")
    if not isinstance(eps, list):
        raise AdapterError("MAPPING_EPISODES_NOT_ARRAY")
    ids = [ep.get("flora_episode_id") for ep in eps]
    if len(set(ids)) != len(ids):
        raise AdapterError("DUPLICATE_MAPPING_EPISODE")
    return {ep["flora_episode_id"]: ep for ep in eps}


def _mapping(episode_id: str, flora: dict, mapping: dict) -> tuple[list, str]:
    """Return G1 overlap candidates; no verified-source claim is possible here."""
    if mapping.get("source_clock") != EXPECTED_CLOCK:
        return [], "SOURCE_CLOCK_MISMATCH"
    video_sha = flora.get("input_sha256", {}).get("main")
    if mapping.get("flora_video_sha256") != video_sha:
        return [], "VIDEO_SHA_MISMATCH"
    source_sha = mapping.get("source_manifest_sha256")
    if (not mapping.get("source_episode_id") or not isinstance(source_sha, str)
            or len(source_sha) != 64 or any(c not in "0123456789abcdef" for c in source_sha.lower())):
        return [], "MISSING_SOURCE_PROVENANCE"
    frames = mapping.get("frame_map")
    segments = mapping.get("g1_segments")
    if not isinstance(frames, list) or not frames or not isinstance(segments, list) or not segments:
        return [], "MISSING_FRAME_MAP_OR_G1_SEGMENTS"
    try:
        before = (-1, -1.0, -1)
        converted = []
        for entry in frames:
            vi, pts, si = entry["video_frame_index"], _finite(entry["relative_pts_s"], "PTS"), entry["source_frame_index"]
            if type(vi) is not int or type(si) is not int or vi != before[0] + 1 or pts <= before[1] or si <= before[2]:
                raise AdapterError("INVALID_OR_NONMONOTONIC_FRAME_MAP")
            converted.append((pts, si))
            before = (vi, pts, si)
        if converted[0][0] != 0.0:
            raise AdapterError("FIRST_PTS_NOT_ZERO")
        ids = set()
        g1 = []
        for seg in segments:
            seg_id, lo, hi = seg["segment_id"], seg["start_frame"], seg["end_frame"]
            if not isinstance(seg_id, str) or not seg_id or seg_id in ids or type(lo) is not int or type(hi) is not int or lo > hi:
                raise AdapterError("INVALID_G1_SEGMENTS")
            ids.add(seg_id)
            g1.append((seg_id, lo, hi))
        if any(a[2] >= b[1] for a, b in zip(sorted(g1, key=lambda e: e[1]), sorted(g1, key=lambda e: e[1])[1:])):
            raise AdapterError("OVERLAPPING_G1_SEGMENTS")
        return (converted, g1), "SOURCE_MANIFEST_SELF_CONSISTENT"
    except (KeyError, TypeError, AdapterError) as exc:
        return [], "INVALID_MAPPING_MANIFEST:" + str(exc)


def build_links(flora_zip: str | Path, output_dir: str | Path, source_manifest: str | Path | None = None) -> dict:
    """Create inspectable native refs and candidate G1 links; never fabricate GT."""
    flora_zip = Path(flora_zip)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    mappings = _manifest_by_episode(source_manifest)
    links, audit, inventory = [], [], []
    with zipfile.ZipFile(flora_zip) as z:
        members = [n for n in z.namelist() if n.startswith("raw_json/") and n.endswith(".json")]
        if len(members) != len(set(members)):
            raise AdapterError("DUPLICATE_NATIVE_ARCHIVE_MEMBER")
        if not members or z.testzip() is not None:
            raise AdapterError("EMPTY_OR_CORRUPT_NATIVE_ARCHIVE")
        for member in sorted(members):
            if not member.startswith("raw_json/") or Path(member).name != member.split("/")[-1]:
                raise AdapterError("UNSAFE_ARCHIVE_PATH")
            raw = z.read(member)
            obj = json.loads(raw)
            if obj.get("source_clock") != EXPECTED_CLOCK:
                raise AdapterError("UNSUPPORTED_FLORA_SOURCE_CLOCK:" + member)
            episode_id = Path(member).stem
            native_sha = _sha(raw)
            duration = _finite(obj.get("duration_s"), "DURATION")
            segs = obj.get("segments")
            if not isinstance(segs, list) or not segs:
                raise AdapterError("MISSING_NATIVE_SEGMENTS:" + member)
            mapping = mappings.get(episode_id)
            if mapping is None:
                mapped, map_status = [], "MISSING_SOURCE_MANIFEST"
            else:
                mapped, map_status = _mapping(episode_id, obj, mapping)
            inventory.append({"episode_id": episode_id, "raw_json_member": member,
                              "native_json_sha256": native_sha, "segment_count": len(segs),
                              "duration_s": duration, "source_mapping_status": map_status})
            audit.append({"episode_id": episode_id, "status": map_status,
                          "mapping_source": "none" if mapping is None else "external_manifest",
                          "mapped_source_frame_count": len(mapped[0]) if mapped else 0})
            for idx, seg in enumerate(segs):
                a = _finite(seg.get("start_s"), "START_S")
                b = _finite(seg.get("end_s"), "END_S")
                if a < 0 or b <= a or b > duration + 1e-5:
                    raise AdapterError(f"BAD_FLORA_INTERVAL:{episode_id}:{idx}")
                native_ref = {"raw_json_member": member, "native_json_sha256": native_sha,
                              "flora_segment_index": idx, "start_s": a, "end_s": b,
                              "caption": seg.get("caption"), "caption_status": seg.get("status")}
                base = {"adapter_schema_version": ADAPTER_VERSION, "flora_episode_id": episode_id,
                        "flora_native": native_ref, "g3": {"status": "NOT_RUN", "model_owned_fields": list(G3_FIELDS), "prediction": None}}
                overlap = []
                if mapped:
                    points, g1_segments = mapped
                    visible = [(pts, si) for pts, si in points if a <= pts < b]
                    for g1_id, lo, hi in g1_segments:
                        hits = [(pts, si) for pts, si in visible if lo <= si <= hi]
                        if hits:
                            overlap.append({"g1_segment_id": g1_id, "g1_interval_frames_inclusive": [lo, hi],
                                            "source_episode_id": mapping["source_episode_id"],
                                            "matched_video_frame_count": len(hits),
                                            "matched_source_frame_min_max": [min(h[1] for h in hits), max(h[1] for h in hits)]})
                if overlap:
                    for hit in overlap:
                        links.append({**base, "g1_target": {**hit, "mapping_status": "CANDIDATE_SOURCE_UNVERIFIED"}})
                else:
                    links.append({**base, "g1_target": {"segment_id": None,
                                 "mapping_status": "UNALIGNED" if not mapped else "NO_OVERLAPPING_G1_FRAMES",
                                 "reason": map_status if not mapped else "NO_MAPPED_TARGET_FRAMES"}})
    with (output_dir / "flora_g1_links.jsonl").open("w", encoding="utf-8") as f:
        for link in links:
            f.write(json.dumps(link, ensure_ascii=False, sort_keys=True) + "\n")
    for filename, rows, keys in [
        ("native_inventory.csv", inventory, ["episode_id", "raw_json_member", "native_json_sha256", "segment_count", "duration_s", "source_mapping_status"]),
        ("alignment_audit.csv", audit, ["episode_id", "status", "mapping_source", "mapped_source_frame_count"]),
    ]:
        with (output_dir / filename).open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(rows)
    summary = {"adapter_schema_version": ADAPTER_VERSION, "episode_count": len(inventory),
               "flora_segment_count": sum(x["segment_count"] for x in inventory),
               "link_count": len(links), "source_alignment_verified": False,
               "mapping_status_counts": dict(Counter(x["status"] for x in audit)),
               "missing_source_manifest_is_blocker": any(x["status"] == "MISSING_SOURCE_MANIFEST" for x in audit),
               "alignment_blocked": any(x["status"] != "SOURCE_MANIFEST_SELF_CONSISTENT" for x in audit),
               "notes": ["A link is not semantic ground truth.",
                         "No source provenance can be independently verified from the Flora ZIP alone.",
                         "Never infer G1 frame indices from nominal FPS."]}
    (output_dir / "adapter_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return summary


def validate_g3_prediction(raw_text, *, manifest, identity, finish_reason=None):
    """Reuse the original v0.2 validator; never create a second schema."""
    from .semantic_validation import validate_model_output_v0_2
    return validate_model_output_v0_2(raw_text, manifest=manifest,
                                      identity=identity, finish_reason=finish_reason)
