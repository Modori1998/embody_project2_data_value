"""Flora MP4 -> versioned video-only evidence packs, without G1 or GPU.

The caller must supply the exact MP4 that Flora saw. All source time references
are real decoded-video PTS; pixel SHA256 is of decoded RGB24 (not Clean RGB).
No model inference, G1 identity claims, synthetic action labels or schema edits.
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
import subprocess
import zipfile
import zlib
from pathlib import Path

from .semantic_validation import (
    FrameEntry, TargetSegmentIdentity, check_manifest_integrity,
    validate_model_output_v0_2,
)

VERSION = "P2_FLORA_VIDEO_G3_EVIDENCE_V0_1"
CLOCK = "seconds relative to the first native source presentation timestamp"
EPISODE_RE = re.compile(r"demo_[0-9]+\Z")
POLICIES = (3, 5, 9)


class VideoEvidenceError(ValueError):
    """Input, decoding or evidence provenance failure."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_sha(obj: object) -> str:
    return digest(json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode())


def read_native_zip(path: Path) -> dict[str, dict]:
    """Read the untouched ZIP or a native JSON directory; never rewrite originals."""
    if path.is_dir():
        folder = path / "raw_json" if (path / "raw_json").is_dir() else path
        files = sorted(folder.glob("demo_*.json"))
        members = [(f"raw_json/{f.name}", f.read_bytes()) for f in files]
    elif path.is_file():
        try:
            with zipfile.ZipFile(path) as z:
                names = [n for n in z.namelist() if n.startswith("raw_json/") and n.endswith(".json")]
                if len(set(names)) != len(names):
                    raise VideoEvidenceError("DUPLICATE_NATIVE_MEMBER")
                members = [(name, z.read(name)) for name in sorted(names)]
        except zipfile.BadZipFile as exc:
            raise VideoEvidenceError(f"INVALID_NATIVE_ZIP:{path}") from exc
    else:
        raise VideoEvidenceError(f"FLORA_NATIVE_SOURCE_MISSING:{path}")
    if not members:
        raise VideoEvidenceError("EMPTY_NATIVE_SOURCE")
    result = {}
    for name, raw in members:
        episode = Path(name).stem
        if not EPISODE_RE.fullmatch(episode) or name != f"raw_json/{episode}.json" or episode in result:
            raise VideoEvidenceError(f"INVALID_NATIVE_MEMBER:{name}")
        try:
            record = json.loads(raw)
        except (ValueError, UnicodeDecodeError) as exc:
            raise VideoEvidenceError(f"INVALID_NATIVE_JSON:{episode}") from exc
        if not isinstance(record, dict) or record.get("source_clock") != CLOCK:
            raise VideoEvidenceError(f"UNSUPPORTED_CLOCK:{episode}")
        if record.get("camera_roles") != ["main"]:
            raise VideoEvidenceError(f"UNSUPPORTED_CAMERA_ROLES:{episode}")
        value = record.get("input_sha256", {}).get("main", "")
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            raise VideoEvidenceError(f"INVALID_VIDEO_HASH:{episode}")
        segments = record.get("segments")
        if not isinstance(segments, list) or not segments:
            raise VideoEvidenceError(f"EMPTY_SEGMENTS:{episode}")
        result[episode] = {"record": record, "raw_sha256": digest(raw), "member": name}
    return result


def video_for(video_dir: Path, episode: str) -> Path:
    filename = f"{episode}_agentview_20fps.mp4"
    candidates = [video_dir / filename, video_dir / "videos" / filename]
    found = [p for p in candidates if p.is_file()]
    if len(found) != 1:
        raise VideoEvidenceError(f"VIDEO_NOT_FOUND_OR_AMBIGUOUS:{episode}:{[str(p) for p in candidates]}")
    return found[0]


def probe_video(path: Path, ffprobe: str) -> tuple[int, int, list[float]]:
    cmd = [ffprobe, "-v", "error", "-select_streams", "v:0",
           "-show_entries", "stream=width,height:frame=best_effort_timestamp_time",
           "-of", "json", str(path)]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=120)
        obj = json.loads(p.stdout)
        stream = obj["streams"][0]
        width, height = int(stream["width"]), int(stream["height"])
        pts = [float(row["best_effort_timestamp_time"]) for row in obj["frames"]]
    except (OSError, KeyError, ValueError, IndexError, subprocess.SubprocessError) as exc:
        raise VideoEvidenceError(f"FFPROBE_FAILED:{path.name}:{exc}") from exc
    if not (0 < width <= 1920 and 0 < height <= 1080 and pts):
        raise VideoEvidenceError(f"INVALID_VIDEO_SHAPE_OR_PTS:{path.name}")
    if any(not (-1e8 < t < 1e8) for t in pts) or any(b <= a for a, b in zip(pts, pts[1:])):
        raise VideoEvidenceError(f"NON_MONOTONIC_PTS:{path.name}")
    return width, height, [round(t - pts[0], 9) for t in pts]


def decode_rgb(path: Path, ffmpeg: str, width: int, height: int, count: int) -> bytes:
    cmd = [ffmpeg, "-nostdin", "-v", "error", "-i", str(path), "-map", "0:v:0",
           "-an", "-vsync", "0", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"]
    try:
        p = subprocess.run(cmd, capture_output=True, check=True, timeout=240)
    except (OSError, subprocess.SubprocessError) as exc:
        raise VideoEvidenceError(f"FFMPEG_FAILED:{path.name}:{exc}") from exc
    expected = width * height * 3 * count
    if len(p.stdout) != expected:
        raise VideoEvidenceError(f"DECODE_COUNT_MISMATCH:{path.name}:{len(p.stdout)}!={expected}")
    return p.stdout


def png_rgb24(rgb: bytes, width: int, height: int) -> bytes:
    """Deterministic lossless PNG for decoded MP4 RGB; never call this Clean RGB."""
    stride = width * 3
    scanlines = b"".join(b"\x00" + rgb[y * stride:(y + 1) * stride] for y in range(height))
    def chunk(tag: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(scanlines, level=6)) + chunk(b"IEND", b""))


def sample_uniform(eligible: list[int], requested: int) -> list[int]:
    """Evenly spaced *eligible decoded-frame ordinals*, preserving both ends."""
    if requested < 1 or not eligible:
        raise VideoEvidenceError("EMPTY_SAMPLING_DOMAIN")
    count = min(requested, len(eligible))
    if count == 1:
        return [eligible[0]]
    positions = [(i * (len(eligible) - 1) + (count - 1) // 2) // (count - 1)
                 for i in range(count)]
    selected = [eligible[i] for i in positions]
    if len(set(selected)) != count:
        raise VideoEvidenceError("DUPLICATE_SAMPLE")
    return selected


def verify_pack(pack: dict, output_dir: Path) -> tuple[TargetSegmentIdentity, list[FrameEntry]]:
    """Pre-call manifest check plus file integrity; target IDs are VIDEO-ONLY."""
    t = pack["target"]
    identity = TargetSegmentIdentity(t["source_episode_id"], t["target_segment_id"],
                                     t["target_start_frame"], t["target_end_frame"])
    entries = []
    for frame in pack["frames"]:
        path = (output_dir / frame["png_path"]).resolve()
        if not path.is_relative_to(output_dir.resolve()) or not path.is_file():
            raise VideoEvidenceError("EVIDENCE_IMAGE_MISSING_OR_UNSAFE")
        if digest(path.read_bytes()) != frame["png_sha256"]:
            raise VideoEvidenceError("EVIDENCE_PNG_HASH_MISMATCH")
        entries.append(FrameEntry(
            frame_index=frame["frame_index"], role=frame["role"],
            source_episode_id=t["source_episode_id"],
            origin_segment_id=t["target_segment_id"],
            target_segment_id=t["target_segment_id"],
            is_target_segment_frame=True,
            pixel_sha256=frame["decoded_rgb_sha256"],
        ))
    findings = check_manifest_integrity(entries, identity)
    if findings or any(not identity.contains(e.frame_index) for e in entries):
        raise VideoEvidenceError("INVALID_EVIDENCE_MANIFEST:" + ",".join(f.check_id for f in findings))
    return identity, entries


def validate_g3_reply(raw_text: str, pack: dict, output_dir: Path, *, finish_reason: str | None = None) -> dict:
    """Existing v0.2 semantics and frame-QC against a separately named video target."""
    identity, entries = verify_pack(pack, output_dir)
    return validate_model_output_v0_2(
        raw_text, manifest=entries, identity=identity, finish_reason=finish_reason,
    ).to_dict()


def build_video_evidence(flora_zip: str | Path, video_dir: str | Path, output_dir: str | Path,
                         *, episodes: list[str] | None = None,
                         ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe") -> dict:
    """Create all 3/5/9 frame candidates; no model request or annotation is sent."""
    src = read_native_zip(Path(flora_zip))
    chosen = sorted(src) if episodes is None else list(dict.fromkeys(episodes))
    if not chosen or any(x not in src for x in chosen):
        raise VideoEvidenceError("UNKNOWN_OR_EMPTY_EPISODE_SELECTION")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        raise VideoEvidenceError("OUTPUT_DIR_MUST_BE_EMPTY")
    directory = Path(video_dir)
    all_video_frames, packs, sample_rows, episode_rows = [], [], [], []
    for episode in chosen:
        native = src[episode]
        record = native["record"]
        path = video_for(directory, episode)
        video_sha = digest(path.read_bytes())
        if video_sha != record["input_sha256"]["main"]:
            raise VideoEvidenceError(f"FLORA_VIDEO_SHA_MISMATCH:{episode}")
        width, height, pts = probe_video(path, ffprobe)
        raw = decode_rgb(path, ffmpeg, width, height, len(pts))
        stride = width * height * 3
        frame_hashes = [digest(raw[i * stride:(i + 1) * stride]) for i in range(len(pts))]
        all_video_frames += [{"episode_id": episode, "frame_index": i, "pts_s": pts[i],
                              "decoded_rgb_sha256": frame_hashes[i]}
                             for i in range(len(pts))]
        duration = record.get("duration_s")
        if not isinstance(duration, (float, int)) or isinstance(duration, bool) or not 0 < duration < 1e8:
            raise VideoEvidenceError(f"INVALID_FLORA_DURATION:{episode}")
        if pts[-1] > float(duration) + 1e-5:
            raise VideoEvidenceError(f"FLORA_DURATION_SHORTER_THAN_VIDEO:{episode}")
        episode_rows.append({"episode_id": episode, "frame_count": len(pts), "video_sha256": video_sha,
                             "native_json_sha256": native["raw_sha256"], "width": width, "height": height,
                             "flora_segment_count": len(record["segments"])})
        image_cache = {}
        for si, segment in enumerate(record["segments"]):
            start, end = segment.get("start_s"), segment.get("end_s")
            if (not isinstance(start, (int, float)) or isinstance(start, bool)
                    or not isinstance(end, (int, float)) or isinstance(end, bool)
                    or not 0 <= start < end <= float(duration) + 1e-5):
                raise VideoEvidenceError(f"INVALID_SEGMENT_WINDOW:{episode}:{si}")
            # Half-open Flora intervals. Tolerance only absorbs timestamp decimal serialization.
            eligible = [i for i, t in enumerate(pts) if t + 1e-8 >= start and t < end - 1e-8]
            if not eligible:
                raise VideoEvidenceError(f"SEGMENT_HAS_NO_DECODED_FRAMES:{episode}:{si}")
            target_id = f"flora/{episode}/S{si:03d}"
            for requested in POLICIES:
                selected = sample_uniform(eligible, requested)
                frame_rows = []
                for position, i in enumerate(selected):
                    rel = f"images/{episode}/f{i:06d}.png"
                    if i not in image_cache:
                        png = png_rgb24(raw[i * stride:(i + 1) * stride], width, height)
                        dest = out / rel
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes(png)
                        image_cache[i] = digest(png)
                    role = ("TARGET_START" if position == 0 else
                            "TARGET_END" if position == len(selected)-1 else "TARGET_SAMPLED")
                    frame_rows.append({"frame_index": i, "pts_s": pts[i], "role": role,
                                       "png_path": rel, "png_sha256": image_cache[i],
                                       "decoded_rgb_sha256": frame_hashes[i],
                                       "is_target_segment_frame": True})
                pack = {
                    "schema_version": VERSION,
                    "target": {"source_episode_id": f"video/{episode}", "target_segment_id": target_id,
                               "flora_segment_index": si, "start_s": start, "end_s": end,
                               "target_start_frame": eligible[0], "target_end_frame": eligible[-1]},
                    "flora_native": {"member": native["member"], "json_sha256": native["raw_sha256"],
                                     "caption_hint_unverified": segment.get("caption")},
                    "video": {"video_filename": path.name, "input_sha256": video_sha,
                              "frame_source": "MP4_DECODED_RGB24_NOT_P2_CLEAN_RGB",
                              "width": width, "height": height},
                    "sampling": {"policy": f"uniform_{requested}", "requested": requested,
                                 "actual": len(selected), "available_target_frames": len(eligible)},
                    "frames": frame_rows,
                }
                pack["evidence_pack_sha256"] = canonical_sha(pack)
                verify_pack(pack, out)
                packs.append(pack)
                sample_rows.append({"episode_id": episode, "flora_segment_index": si, "policy": f"uniform_{requested}",
                                    "available": len(eligible), "selected": len(selected),
                                    "frame_indices": ";".join(str(v) for v in selected)})
    def write_jsonl(filename: str, rows: list[dict]) -> None:
        with (out / filename).open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    write_jsonl("video_frame_manifest.jsonl", all_video_frames)
    write_jsonl("evidence_packs.jsonl", packs)
    write_jsonl("sampling_comparison.jsonl", sample_rows)
    write_jsonl("episode_inventory.jsonl", episode_rows)
    summary = {"schema_version": VERSION, "processed_episodes": len(episode_rows),
               "processed_flora_segments": sum(x["flora_segment_count"] for x in episode_rows),
               "decoded_frames": len(all_video_frames), "evidence_packs": len(packs),
               "sampling_policies": list(POLICIES), "video_sha_verified": True,
               "g3_v0_2_validator_preflight": "PASS",
               "formal_g1_alignment": "NOT_APPLICABLE_VIDEO_ONLY",
               "qwen_inference": "NOT_RUN", "semantic_accuracy": "NOT_ESTIMABLE"}
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary
