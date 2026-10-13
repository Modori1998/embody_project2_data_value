"""Build a local, image-verified 12-segment P2-G3 blind human review bundle.

Dependencies: Python stdlib only. Existing v0.2.1 renderer PNG cache is reused;
NO VLM access, NO source-HDF5 access, NO G1/G2 changes, and NO model predictions.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = (
    ROOT / "0-doc/10-design-review/evidence"
    / "P2_G3_Semantic_Blind_Audit_12_Source_20261013.csv"
)
DEFAULT_RGB_CACHE = (
    Path.home() / "embody" / "_local_vlm_deploy" / "rgb_g3_v02"
    / "g3_taxonomy_v02_20261013_r2"
)
DEFAULT_OUT = ROOT / "outputs" / "p2_g3_semantic_blind_audit" / "g3_v02_microset_12"
TEMPLATE = ROOT / "scripts/g3_semantic_blind_audit_template.html"
SOURCE_FIELDS = (
    "sample_order", "cohort", "episode_id", "segment_id", "start_frame",
    "end_frame", "segment_length", "target_keyframes", "frame_png_sha256s",
    "phase_ref", "event_assessment_ref", "event_type_ref", "evidence_quality_ref",
    "reviewer_id", "reviewed_at_utc", "explanation",
)
ANSWER_FIELDS = frozenset((
    "phase_ref", "event_assessment_ref", "event_type_ref", "evidence_quality_ref",
    "reviewer_id", "reviewed_at_utc", "explanation",
))
SEGMENT_ID = re.compile(r"demo_[0-9]+-S[0-9]{4}\Z")
EPISODE_ID = re.compile(r"data/demo_[0-9]+\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
FRAME_ROLES = ("START", "MIDDLE", "END")
ABSTENTION_WARNING = "No model predictions may be included in blind source files."


class AuditBundleError(ValueError):
    """Invalid source, missing/altered RGB, or unsafe output destination."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as inp:
        for chunk in iter(lambda: inp.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_source(source: Path) -> tuple[list[dict[str, str]], str]:
    if not source.is_file():
        raise AuditBundleError(f"Source CSV not found: {source}")
    raw = source.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise AuditBundleError("Source CSV must be UTF-8 without BOM")
    try:
        with source.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != SOURCE_FIELDS:
                raise AuditBundleError(
                    "Unexpected CSV header; refuse fields which may leak labels: "
                    + str(reader.fieldnames)
                )
            rows = list(reader)
    except UnicodeDecodeError as exc:
        raise AuditBundleError("Source CSV must be UTF-8") from exc

    if len(rows) != 12:
        raise AuditBundleError(f"Expected exactly 12 microset rows, got {len(rows)}")
    if any(None in r or any(v is None for v in r.values()) for r in rows):
        raise AuditBundleError("Invalid CSV row width")
    if any(r["cohort"] != "microset" for r in rows):
        raise AuditBundleError("Only microset rows allowed; known_cases prohibited")
    if any(r[f].strip() for r in rows for f in ANSWER_FIELDS):
        raise AuditBundleError(
            "Blind source must have empty human answers; never preload model labels"
        )
    ids = [r["segment_id"] for r in rows]
    episodes = [r["episode_id"] for r in rows]
    if len(set(ids)) != 12 or len(set(episodes)) != 12:
        raise AuditBundleError("Expected 12 unique Segment IDs and Episodes")
    if [int(r["sample_order"]) for r in rows] != list(range(4, 16)):
        raise AuditBundleError("Expected pinned original sample order 4..15")
    for row in rows:
        if not SEGMENT_ID.fullmatch(row["segment_id"]) or not EPISODE_ID.fullmatch(row["episode_id"]):
            raise AuditBundleError("Invalid source ID format")
        if row["segment_id"].split("-")[0] != row["episode_id"].split("/")[-1]:
            raise AuditBundleError("Episode/segment identity mismatch")
        try:
            lo, hi, length = [int(row[k]) for k in ("start_frame", "end_frame", "segment_length")]
            frames = [int(s) for s in row["target_keyframes"].split(";")]
        except ValueError as exc:
            raise AuditBundleError("Malformed frozen interval or keyframes") from exc
        hashes = row["frame_png_sha256s"].split(";")
        if length != hi - lo + 1 or len(frames) != 3 or len(set(frames)) != 3:
            raise AuditBundleError("Frozen interval/keyframe cardinality mismatch")
        if frames != sorted(frames) or not all(lo <= f <= hi for f in frames):
            raise AuditBundleError("Target keyframes outside frozen segment")
        if len(hashes) != 3 or not all(SHA256.fullmatch(h) for h in hashes):
            raise AuditBundleError("Missing or malformed PNG file hashes")
    return rows, hashlib.sha256(raw).hexdigest()


def locate_png(cache: Path, segment_id: str, frame_index: int) -> Path:
    # v0.2.1 paired-run cache uses this exact name, not the other renderer's
    # data_demo_N_fNNNNN.png convention. Explicit --rgb-cache can override root.
    return cache / f"{segment_id}_f{frame_index:05d}.png"


def build_bundle(
    source: Path,
    rgb_cache: Path,
    output: Path,
    template: Path = TEMPLATE,
) -> dict:
    """Verify every frozen PNG file hash before finalizing an offline package."""
    rows, source_sha = load_source(source)
    if not rgb_cache.is_dir():
        raise AuditBundleError(
            f"RGB cache missing: {rgb_cache}\n"
            "Use the existing v0.2.1 run RGB cache or materialize its 36 "
            "target-only keyframes with the frozen renderer; do not guess the hash."
        )
    if output.exists():
        raise AuditBundleError(f"Output already exists (no overwrite): {output}")
    if not template.is_file():
        raise AuditBundleError(f"HTML template missing: {template}")
    html = template.read_text(encoding="utf-8")
    if html.count("__AUDIT_DATA_JSON__") != 1:
        raise AuditBundleError("Expected exactly one data insertion point")

    # Check all 36 source PNGs and hashes before writing anything.
    manifest_images = []
    for row in rows:
        frames = [int(s) for s in row["target_keyframes"].split(";")]
        hashes = row["frame_png_sha256s"].split(";")
        item = []
        for i, (frame_index, expected) in enumerate(zip(frames, hashes)):
            original = locate_png(rgb_cache, row["segment_id"], frame_index)
            if not original.is_file():
                raise AuditBundleError(f"Missing RGB: {original}")
            actual = sha256_file(original)
            if actual != expected:
                raise AuditBundleError(
                    f"PNG_SHA256_MISMATCH {row['segment_id']} frame={frame_index} "
                    f"expected={expected} actual={actual}"
                )
            item.append({
                "role": FRAME_ROLES[i],
                "frame_index": frame_index,
                "src": "images/" + original.name,
                "png_sha256": expected,
                "original": original,
            })
        manifest_images.append(item)

    # Browser receives source identity + images only: never model labels/results.
    visible_rows = []
    for row, imgs in zip(rows, manifest_images):
        visible_rows.append({
            **row,
            "images": [{k: v for k, v in img.items() if k != "original"} for img in imgs],
        })
    payload = {
        "contract": "P2_G3_SEMANTIC_BLIND_HUMAN_REFERENCE_V1",
        "source_manifest_sha256": source_sha,
        "fields": list(SOURCE_FIELDS),
        "rows": visible_rows,
    }
    payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    payload_json = payload_json.replace("<", r"\u003c").replace(">", r"\u003e")
    rendered = html.replace("__AUDIT_DATA_JSON__", payload_json)
    if any(k in rendered for k in (
        '"model_payload"', '"model_prediction"', '"labels_v0_1"',
        '"labels_v0_2"', '"qc_findings"', '"model_score"'
    )):
        raise AuditBundleError(ABSTENTION_WARNING)

    parent = output.parent
    parent.mkdir(parents=True, exist_ok=True)
    tmp = parent / (output.name + ".staging-" + uuid.uuid4().hex[:10])
    try:
        (tmp / "images").mkdir(parents=True)
        for item in manifest_images:
            for img in item:
                dest = tmp / img["src"]
                shutil.copyfile(img["original"], dest)
                if sha256_file(dest) != img["png_sha256"]:
                    raise AuditBundleError(f"Copy hash mismatch: {dest}")
        (tmp / "index.html").write_text(rendered, encoding="utf-8")
        (tmp / "bundle_manifest.json").write_text(
            json.dumps({
                "contract": payload["contract"],
                "source_csv_sha256": source_sha,
                "segments": [r["segment_id"] for r in rows],
                "png_sha256": {
                    im["src"]: im["png_sha256"]
                    for item in manifest_images for im in item
                },
                "model_prediction_embedded": False,
            }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (tmp / "README.txt").write_text(
            "P2-G3 Semantic Blind Audit (12 Development segments)\n"
            "No VLM predictions are in this package.\n"
            "Run from the bundle directory:\n"
            "  python -m http.server 8767 --bind 127.0.0.1\n"
            "Visit http://127.0.0.1:8767/\n"
            "CSV progress stays in your browser until explicitly exported.\n"
            "Export regularly; an import option is provided.\n"
            "Do not upload local PNGs or filled human CSV to public GitHub.\n",
            encoding="utf-8"
        )
        tmp.rename(output)
    finally:
        if tmp.exists():
            shutil.rmtree(tmp)
    return {
        "status": "BUILT_HASH_VERIFIED",
        "segment_count": len(rows),
        "png_verified_count": sum(map(len, manifest_images)),
        "source_manifest_sha256": source_sha,
        "output": str(output),
        "index_html": str(output / "index.html"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--rgb-cache", type=Path, default=DEFAULT_RGB_CACHE,
                        help="v0.2.1 RGB cache RUN DIRECTORY with demo_N-SXXXX_fNNNNN.png")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    try:
        result = build_bundle(args.source, args.rgb_cache, args.output)
    except (AuditBundleError, OSError, ValueError) as exc:
        print(f"G3_BLIND_AUDIT_BLOCKED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("Start local web (from output directory):")
    print(f'  python -m http.server 8767 --bind 127.0.0.1 --directory "{args.output}"')
    print("Open http://127.0.0.1:8767/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
