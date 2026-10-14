"""Offline unit tests for the 12-segment G3 blind audit builder. No GPU/HDF5."""
import csv
import hashlib
import json
from pathlib import Path

import pytest

from scripts.build_g3_semantic_blind_audit import (
    AuditBundleError,
    SOURCE_FIELDS,
    TEMPLATE,
    build_bundle,
    load_source,
)


def make_fixture(tmp_path: Path):
    source = tmp_path / "source.csv"
    cache = tmp_path / "rgb"
    cache.mkdir()
    rows = []
    for k in range(12):
        episode_num = k + 400
        name = f"demo_{episode_num}-S0001"
        hashes = []
        for j in range(3):
            index = j
            data = b"\x89PNG\r\n\x1a\n" + f"{k}-{j}".encode("utf-8")
            (cache / f"{name}_f{index:05d}.png").write_bytes(data)
            hashes.append(hashlib.sha256(data).hexdigest())
        rows.append({
            "sample_order":str(k+4), "cohort":"microset",
            "episode_id":f"data/demo_{episode_num}", "segment_id":name,
            "start_frame":"0", "end_frame":"2", "segment_length":"3",
            "target_keyframes":"0;1;2", "frame_png_sha256s":";".join(hashes),
            **{col:"" for col in SOURCE_FIELDS if col.endswith("_ref") or col in (
                "reviewer_id","reviewed_at_utc","explanation"
            )}
        })
    with source.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=SOURCE_FIELDS)
        w.writeheader();w.writerows(rows)
    return source,cache,rows


def test_real_template_contains_no_model_predictions():
    html=TEMPLATE.read_text(encoding="utf-8")
    assert html.count("__AUDIT_DATA_JSON__")==1
    for field in ("phase_ref","event_assessment_ref","event_type_ref","evidence_quality_ref"):
        assert 'id="'+field+'"' in html
    assert "localStorage" in html
    assert "importCsv" in html
    assert "exportCsv" in html
    assert "labels_v0_2.jsonl" not in html


def test_happy_path_12_segments_36_verified_images(tmp_path):
    src,cache,rows=make_fixture(tmp_path)
    out=tmp_path/"bundle"
    result=build_bundle(src,cache,out)
    assert result["segment_count"]==12
    assert result["png_verified_count"]==36
    manifest=json.loads((out/"bundle_manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["segments"])==12
    assert len(manifest["png_sha256"])==36
    assert manifest["model_prediction_embedded"] is False
    html=(out/"index.html").read_text(encoding="utf-8")
    assert html.count('"src":"images/')==36
    assert '"segment_id":"demo_400-S0001"' in html
    assert '"model_payload"' not in html
    assert '"label_qc_status"' not in html
    assert (out/"README.txt").is_file()
    assert len(list((out/"images").glob("*.png")))==36


def test_png_hash_mismatch_fail_closed(tmp_path):
    src,cache,rows=make_fixture(tmp_path)
    first=cache/f"{rows[0]['segment_id']}_f00000.png"
    first.write_bytes(b"changed")
    with pytest.raises(AuditBundleError,match="PNG_SHA256_MISMATCH"):
        build_bundle(src,cache,tmp_path/"out")
    assert not (tmp_path/"out").exists()


def test_missing_png_no_partial_output(tmp_path):
    src,cache,rows=make_fixture(tmp_path)
    (cache/f"{rows[0]['segment_id']}_f00000.png").unlink()
    with pytest.raises(AuditBundleError,match="Missing RGB"):
        build_bundle(src,cache,tmp_path/"out")
    assert not (tmp_path/"out").exists()


@pytest.mark.parametrize("bad_col,bad_value",[
    ("cohort","known_cases"),
    ("phase_ref","grasp"),
    ("segment_id","../bad"),
    ("episode_id","data/demo_999"),
    ("target_keyframes","0;1;20"),
    ("frame_png_sha256s","invalid"),
])
def test_bad_identity_or_nonblind_input_rejected(tmp_path,bad_col,bad_value):
    src,cache,rows=make_fixture(tmp_path)
    rows[0][bad_col]=bad_value
    with src.open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=SOURCE_FIELDS)
        writer.writeheader();writer.writerows(rows)
    with pytest.raises(AuditBundleError):
        build_bundle(src,cache,tmp_path/"out")


def test_extra_model_column_rejected(tmp_path):
    src,cache,rows=make_fixture(tmp_path)
    text=src.read_text(encoding="utf-8")
    src.write_text(text.replace("explanation\n","explanation,model_prediction\n",1),
                   encoding="utf-8")
    with pytest.raises(AuditBundleError,match="Unexpected CSV header"):
        load_source(src)


def test_refuse_overwrite_existing_audit_bundle(tmp_path):
    src,cache,rows=make_fixture(tmp_path)
    out=tmp_path/"bundle"
    out.mkdir()
    (out/"saved_human.csv").write_text("keep",encoding="utf-8")
    with pytest.raises(AuditBundleError,match="already exists"):
        build_bundle(src,cache,out)
    assert (out/"saved_human.csv").read_text(encoding="utf-8")=="keep"


def test_real_frozen_microset_csv_12_only():
    from scripts.build_g3_semantic_blind_audit import DEFAULT_SOURCE
    rows,_=load_source(DEFAULT_SOURCE)
    assert len(rows)==12
    assert {r["cohort"] for r in rows}=={"microset"}
    assert len({r["episode_id"] for r in rows})==12
    assert "demo_47-S0003" not in {r["segment_id"] for r in rows}


def test_frontend_javascript_has_valid_syntax(tmp_path):
    """Node is available on GitHub Actions ubuntu runner; no browser deps."""
    import shutil
    import subprocess
    if not shutil.which("node"):
        pytest.skip("Node unavailable; manual browser smoke test still required")
    html = TEMPLATE.read_text(encoding="utf-8")
    script = html.rsplit("<script>", 1)[-1].split("</script>", 1)[0]
    assert 'function exportCsv()' in script
    assert 'function importCsv(raw)' in script
    source = tmp_path / "g3_audit.js"
    source.write_text(script, encoding="utf-8")
    result = subprocess.run(
        ["node", "--check", str(source)],
        capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr
