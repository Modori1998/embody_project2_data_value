"""Build an interactive blind Calibration reviewer page from a Formal Stage1 run."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FORMAL_RUN = (
    ROOT
    / "outputs/mvp_core_retrieval_formal/mvp_core_retrieval_formal_stage1_20261009"
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build_page(
    formal_run: Path,
    output: Path,
    *,
    segment_gifs: dict[str, str] | None = None,
    allow_existing_output: bool = False,
    audit_rows: list[dict[str, str]] | None = None,
    page_title: str = "Calibration Blind Human Audit",
    storage_key_suffix: str = "",
    export_filename: str = "calibration_human_audit_pairs_filled.csv",
) -> dict[str, int | str]:
    source_csv = formal_run / "calibration_human_audit_pairs.csv"
    keyframe_csv = formal_run / "m2/keyframe_manifest.csv"
    if not keyframe_csv.is_file() or (audit_rows is None and not source_csv.is_file()):
        raise FileNotFoundError("Formal Stage1 audit CSV or keyframe manifest is missing")
    rows = [dict(row) for row in audit_rows] if audit_rows is not None else read_csv(source_csv)
    keyframes = read_csv(keyframe_csv)
    if not rows:
        raise ValueError("Calibration blind audit package is empty")
    forbidden = {"method", "similarity", "rank", "copy_index", "hidden_repeat"}
    lowered = {field.lower() for field in rows[0]}
    if forbidden & lowered:
        raise ValueError(f"Reviewer source contains forbidden fields: {sorted(forbidden & lowered)}")

    output.mkdir(parents=True, exist_ok=allow_existing_output)
    segment_gifs = segment_gifs or {}
    by_segment: dict[str, list[dict[str, str]]] = {}
    for row in keyframes:
        by_segment.setdefault(row["segment_id"], []).append(row)

    items = []
    for row in rows:
        query_id = row["query_segment_id"]
        candidate_id = row["candidate_segment_id"]

        def images(segment_id: str) -> list[dict[str, str]]:
            result = []
            for frame in sorted(
                by_segment[segment_id], key=lambda item: int(item["frame_index"])
            ):
                target = formal_run / "m2" / frame["png_relpath"]
                if not target.is_file():
                    raise FileNotFoundError(f"Audit keyframe is missing: {target}")
                relative = Path(os.path.relpath(target, output)).as_posix()
                result.append({"src": relative, "roles": frame["roles"]})
            return result

        items.append(
            {
                "row": row,
                "query_gif": segment_gifs.get(query_id, ""),
                "candidate_gif": segment_gifs.get(candidate_id, ""),
                "query_images": images(query_id),
                "candidate_images": images(candidate_id),
            }
        )

    payload = json.dumps(items, ensure_ascii=False).replace("</", "<\\/")
    storage_key = "project2-calibration-audit:" + formal_run.name
    if storage_key_suffix:
        storage_key += ":" + storage_key_suffix
    escaped_page_title = html.escape(page_title)
    page = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Project 2 {escaped_page_title}</title>
<style>
:root{{--bg:#f4f6f8;--card:#fff;--line:#d8dee6;--ink:#17202a;--muted:#627080;--accent:#1769aa;--chosen:#d9ecff}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font-family:Arial,"Microsoft YaHei",sans-serif}}
header{{position:sticky;top:0;z-index:10;background:#fff;border-bottom:1px solid var(--line);padding:12px 20px;display:flex;gap:20px;align-items:center;flex-wrap:wrap}}
header strong{{font-size:18px}}.metric{{color:var(--muted)}}main{{max-width:1560px;margin:16px auto;padding:0 16px 120px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px;box-shadow:0 2px 8px #0000000d}}
h2{{margin-top:0}}h3{{margin:0 0 10px}}.compare{{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:18px;align-items:start}}
.compare-panel{{min-width:0;border:1px solid var(--line);border-radius:8px;padding:14px;background:#fbfcfd}}
.strip{{display:flex;gap:8px;flex-wrap:wrap}}
figure{{margin:0}}img{{width:118px;height:118px;object-fit:contain;background:#111;border-radius:4px}}figcaption{{text-align:center;color:var(--muted);margin-top:4px;font-size:12px}}
.temporal{{margin:0 0 12px}}.temporal img{{display:block;width:100%;height:360px;object-fit:contain;image-rendering:auto}}
.meta{{background:#f7f9fb;border-left:4px solid #a9b7c6;padding:10px;margin:10px 0 0;line-height:1.55;overflow-wrap:anywhere;font-size:14px}}
.choices{{display:grid;grid-template-columns:repeat(5,minmax(140px,1fr));gap:10px;margin-top:18px}}
.choice{{border:2px solid var(--line);border-radius:8px;padding:14px 8px;text-align:center;cursor:pointer;font-weight:700;background:#fff}}
.choice:has(input:checked){{border-color:var(--accent);background:var(--chosen)}}.choice input{{margin-right:7px}}
footer{{position:fixed;bottom:0;left:0;right:0;background:#fff;border-top:1px solid var(--line);padding:12px 20px;display:flex;justify-content:center;gap:12px;flex-wrap:wrap}}
button{{border:1px solid #9aa7b5;border-radius:6px;background:#fff;padding:10px 18px;cursor:pointer;font-weight:700}}button.primary{{background:var(--accent);color:#fff;border-color:var(--accent)}}button:disabled{{opacity:.45;cursor:not-allowed}}
@media(max-width:980px){{.compare{{grid-template-columns:1fr}}.choices{{grid-template-columns:1fr}}.temporal img{{height:320px}}img{{width:140px;height:140px}}}}
</style></head><body>
<header><strong>{escaped_page_title}</strong><span class="metric" id="position"></span><span class="metric" id="completed"></span><span class="metric" id="remaining"></span></header>
<main><article class="card"><h2 id="itemId"></h2><div class="compare"><section class="compare-panel"><h3>Query</h3><div class="temporal" id="queryTemporal"><img id="queryGif" alt="Query segment temporal GIF"></div><div class="strip" id="queryStrip"></div><div class="meta" id="queryMeta"></div></section><section class="compare-panel"><h3>Candidate</h3><div class="temporal" id="candidateTemporal"><img id="candidateGif" alt="Candidate segment temporal GIF"></div><div class="strip" id="candidateStrip"></div><div class="meta" id="candidateMeta"></div></section></div><div class="choices" id="choices"></div></article></main>
<footer><button id="previous">上一条</button><button id="next">下一条</button><button class="primary" id="export">导出填写好的 CSV</button></footer>
<script>
const items={payload};
const labels=['RELEVANT','PARTIAL','NOT_RELEVANT','BAD_SEGMENT','UNSURE'];
const storageKey={json.dumps(storage_key)};
function loadAnswers(){{try{{return JSON.parse(localStorage.getItem(storageKey)||'{{}}')}}catch(error){{console.warn('Browser storage unavailable; answers remain available for CSV export in this tab.',error);return {{}}}}}}
function saveAnswers(){{try{{localStorage.setItem(storageKey,JSON.stringify(answers))}}catch(error){{console.warn('Browser storage unavailable; export the CSV before closing this tab.',error)}}}}
let answers=loadAnswers();
let current=0;
const esc=value=>String(value??'').replace(/[&<>"']/g,ch=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[ch]));
function strip(target,images){{document.getElementById(target).innerHTML=images.map(image=>`<figure><img src="${{esc(image.src)}}" alt="keyframe"><figcaption>${{esc(image.roles)}}</figcaption></figure>`).join('')}}
function temporal(container,image,source){{const box=document.getElementById(container),img=document.getElementById(image);if(source){{box.hidden=false;img.src=source}}else{{box.hidden=true;img.removeAttribute('src')}}}}
function metadata(prefix,row){{return `duration=${{esc(row[prefix+'_duration_sec'])}}s | gripper=${{esc(row[prefix+'_gripper_start_state'])}} → ${{esc(row[prefix+'_gripper_end_state'])}} | transition=${{esc(row[prefix+'_gripper_transition_present'])}}<br>displacement=${{esc(row[prefix+'_eef_displacement_xyz'])}} | direction-change=${{esc(row[prefix+'_coarse_direction_change_rad'])}}`}}
function render(){{
 const item=items[current],row=item.row,id=row.audit_item_id;
 document.getElementById('itemId').textContent=id;
 temporal('queryTemporal','queryGif',item.query_gif);temporal('candidateTemporal','candidateGif',item.candidate_gif);
 strip('queryStrip',item.query_images);strip('candidateStrip',item.candidate_images);
 document.getElementById('queryMeta').innerHTML=metadata('query',row);
 document.getElementById('candidateMeta').innerHTML=metadata('candidate',row);
 document.getElementById('choices').innerHTML=labels.map(label=>`<label class="choice"><input type="radio" name="label" value="${{label}}" ${{answers[id]===label?'checked':''}}>${{label}}</label>`).join('');
 document.querySelectorAll('input[name="label"]').forEach(input=>input.addEventListener('change',event=>{{answers[id]=event.target.value;saveAnswers();updateProgress()}}));
 document.getElementById('previous').disabled=current===0;document.getElementById('next').disabled=current===items.length-1;
 document.getElementById('position').textContent=`当前条目：${{current+1}} / ${{items.length}}`;updateProgress();window.scrollTo(0,0);
}}
function updateProgress(){{const done=items.filter(item=>answers[item.row.audit_item_id]).length;document.getElementById('completed').textContent=`已完成：${{done}} / ${{items.length}}`;document.getElementById('remaining').textContent=`未完成：${{items.length-done}}`}}
document.getElementById('previous').onclick=()=>{{if(current>0){{current--;render()}}}};
document.getElementById('next').onclick=()=>{{if(current<items.length-1){{current++;render()}}}};
function csvCell(value){{const text=String(value??'');return /[",\\r\\n]/.test(text)?'"'+text.replace(/"/g,'""')+'"':text}}
document.getElementById('export').onclick=()=>{{
 const fields=Object.keys(items[0].row);const lines=[fields.map(csvCell).join(',')];
 for(const item of items){{const row={{...item.row,review_label:answers[item.row.audit_item_id]||''}};lines.push(fields.map(field=>csvCell(row[field])).join(','))}}
 const blob=new Blob(['\ufeff'+lines.join('\\r\\n')+'\\r\\n'],{{type:'text/csv;charset=utf-8'}});const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download={json.dumps(export_filename)};link.click();URL.revokeObjectURL(link.href);
}};
render();
</script></body></html>"""
    (output / "index.html").write_text(page, encoding="utf-8")
    (output / "ui_meta.json").write_text(
        json.dumps(
            {
                "formal_run": str(formal_run.resolve()),
                "source_csv": str(source_csv.resolve()),
                "audit_items": len(rows),
                "labels": [
                    "RELEVANT",
                    "PARTIAL",
                    "NOT_RELEVANT",
                    "BAD_SEGMENT",
                    "UNSURE",
                ],
                "browser_persistence": "localStorage",
                "export_filename": export_filename,
                "blind_fields_exposed": False,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {"audit_items": len(rows), "output": str(output.resolve())}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--formal-run", type=Path, default=DEFAULT_FORMAL_RUN)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)
    output = ROOT / "outputs/mvp_core_retrieval_human_audit" / args.run_id
    print(json.dumps(build_page(args.formal_run.resolve(), output), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
