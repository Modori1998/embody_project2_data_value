"""Assemble the private G3F-P1 report from the frozen local run.

The generated HTML contains private images and observations; never commit it.
"""
import argparse
import base64
import csv
import hashlib
import json
import re
from pathlib import Path


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def unique_rows(rows, key, expected):
    result = {}
    for row in rows:
        identity = key(row)
        if identity in result:
            raise ValueError(f"duplicate identity: {identity}")
        result[identity] = row
    if set(result) != set(expected):
        raise ValueError(f"identity mismatch: missing={set(expected)-set(result)}, extra={set(result)-set(expected)}")
    return result


def events(pred):
    return [e if isinstance(e, str) else e["event_type"] for e in pred["events"]]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--human", type=Path, required=True)
    parser.add_argument("--rgb", type=Path, required=True)
    parser.add_argument("--sample-manifest", type=Path, required=True)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    template = args.template.read_text(encoding="utf-8")
    match = re.search(r'(<script id="preset" type="application/json">)(.*?)(</script>)', template, re.S)
    if not match:
        raise ValueError("template preset missing")
    preset = json.loads(match.group(2))
    ids = [d["id"] for d in preset]
    if len(ids) != 12 or len(set(ids)) != 12:
        raise ValueError("template must contain 12 unique segments")
    by_id = {d["id"]: d for d in preset}
    manifest = json.loads((args.run / "run_manifest.json").read_text(encoding="utf-8"))
    if manifest["sample_order"] != ids or manifest["expected_calls"] != 36:
        raise ValueError("run identity differs from template")
    expected = [(sid, arm) for sid in ids for arm in "ABC"]
    segments = unique_rows(read_jsonl(args.run / "per_segment.jsonl"), lambda x: x["segment_id"], ids)
    responses = unique_rows(read_jsonl(args.run / "responses.jsonl"), lambda x: (x["segment_id"], x["arm"]), expected)
    inputs = unique_rows(read_jsonl(args.run / "inputs.jsonl"), lambda x: (x["segment_id"], x["arm"]), expected)
    with args.human.open(encoding="utf-8-sig", newline="") as f:
        human = unique_rows(list(csv.DictReader(f)), lambda x: x["segment_id"], ids)
    with args.sample_manifest.open(encoding="utf-8-sig", newline="") as f:
        samples = {r["segment_id"]: r for r in csv.DictReader(f) if r["segment_id"] in by_id}
    if set(samples) != set(ids):
        raise ValueError("frozen sample manifest is incomplete")
    sample_sha = hashlib.sha256((args.sample_manifest.parent / "run_manifest.json").read_bytes()).hexdigest()
    if sample_sha != manifest["frozen_manifest_sha256"]:
        raise ValueError("frozen sample manifest SHA mismatch")
    scores = json.loads((args.run / "scores.json").read_text(encoding="utf-8"))
    expected_scores = {"A": (.636, 5, 7, (0, 0, 3)), "B": (.533, 2, 7, (2, 7, 1)), "C": (.560, 3, 6, (0, 2, 3))}
    for arm, (f1, exact, phase, motion) in expected_scores.items():
        s = scores[arm]
        m = s["by_type"]["object_motion"]
        if (round(s["event_type_micro_f1"], 3), s["exact_match"], s["phase_correct"], (m["tp"], m["fp"], m["fn"])) != (f1, exact, phase, motion):
            raise ValueError(f"official score mismatch: {arm}")
    summary = json.loads((args.run / "summary.json").read_text(encoding="utf-8"))
    payload = {"rows": {}, "images": {}, "human": {}, "scores": scores, "summary": summary}
    for sid in ids:
        d = by_id[sid]
        seg = segments[sid]
        h = human[sid]
        frames = d["frames"]
        if [int(v) for v in samples[sid]["target_keyframes"].split(";")] != frames or [int(v) for v in h["target_keyframes"].split(";")] != frames:
            raise ValueError(f"frame mismatch: {sid}")
        if h["phase_ref"] != d["gold"]["phase"] or set(h["event_types_ref"].split(";")) - {""} != set(d["gold"]["events"]):
            raise ValueError(f"human gold mismatch: {sid}")
        if seg["human"]["motion_phase"] != h["phase_ref"] or set(events(seg["human"])) != set(d["gold"]["events"]):
            raise ValueError(f"run human gold mismatch: {sid}")
        hframes = {e: [int(v) for v in h[e + "_frames_ref"].split(";") if v] for e in ("grasp_attempt", "release_attempt", "object_motion")}
        if any(v not in frames for vv in hframes.values() for v in vv):
            raise ValueError(f"human evidence frame mismatch: {sid}")
        payload["human"][sid] = {"frames": hframes, "explanation": h["explanation"]}
        hashes = manifest["rgb_sha256"][sid].split(";")
        sample_hashes = samples[sid]["frame_png_sha256s"].split(";")
        if hashes != sample_hashes or len(hashes) != 3:
            raise ValueError(f"RGB manifest mismatch: {sid}")
        for index, digest in zip(frames, hashes):
            path = args.rgb / f"{sid}_f{index:05d}.png"
            binary = path.read_bytes()
            if hashlib.sha256(binary).hexdigest() != digest:
                raise ValueError(f"RGB SHA mismatch: {path}")
            payload["images"][f"{sid}|{index}"] = "data:image/png;base64," + base64.b64encode(binary).decode("ascii")
        for arm in "ABC":
            key = (sid, arm)
            r, inp, pred = responses[key], inputs[key], seg[arm]
            if r["request_sha256"] != inp["request_sha256"] or r["prompt_sha256"] != inp["prompt_sha256"] or r["rgb_sha256"] != hashes or inp["rgb_sha256"] != hashes:
                raise ValueError(f"request identity mismatch: {key}")
            parsed = r["parsed"]
            if parsed != pred or parsed["motion_phase"] != d["arms"][arm]["phase"] or set(events(parsed)) != set(d["arms"][arm]["events"]):
                raise ValueError(f"prediction mismatch: {key}")
            text = next(c["text"] for c in inp["request"]["messages"][0]["content"] if c["type"] == "text")
            if hashlib.sha256(text.encode()).hexdigest() != inp["prompt_sha256"]:
                raise ValueError(f"prompt SHA mismatch: {key}")
            if not parsed.get("observation_note") or not isinstance(r.get("qc"), dict) or not isinstance(r.get("phase_event_qc"), dict):
                raise ValueError(f"incomplete note or QC: {key}")
            payload["rows"][sid + "|" + arm] = {"prediction": parsed, "prompt": text, "qc": r["qc"], "phase_event_qc": r["phase_event_qc"]}
    for arm, (f1, exact, phase, motion) in expected_scores.items():
        tp = fp = fn = correct = matches = 0
        for sid in ids:
            gold = set(by_id[sid]["gold"]["events"])
            pred = payload["rows"][sid + "|" + arm]["prediction"]
            got = set(events(pred))
            tp += len(gold & got); fp += len(got - gold); fn += len(gold - got)
            matches += gold == got; correct += pred["motion_phase"] == by_id[sid]["gold"]["phase"]
        if (round(2*tp/(2*tp+fp+fn), 3), matches, correct) != (f1, exact, phase):
            raise ValueError(f"recomputed score mismatch: {arm}")
    injected = "\nconst embedded=" + json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + ";\n"
    injected += "for(const [key,row] of Object.entries(embedded.rows)){const p=row.prediction;rawPredictions.set(key,{...p,phase:p.motion_phase,events:canonicalEvents(p.events)});prompts.set(key,row.prompt);qcRecords.set(key,{...row.qc,phase_event_qc:row.phase_event_qc});}\n"
    injected += "for(const [key,url] of Object.entries(embedded.images))images.set(key,url);for(const [key,value] of Object.entries(embedded.human))humanEvidence.set(key,value);imported={per:true,response:true,prompt:true,image:36,human:true};showImport('已自动加载：12/12 Segment · 36/36 RGB SHA · 12/12 人工金标 · 36/36 完整输出、Prompt、QC');\n"
    template = template.replace("\nrenderAll();\n</script>", injected + "renderAll();\n</script>")
    template = template.replace("${qc.findings.map(f=>esc(f.check_id||'review')).join('；')}", "${qc.findings.map(f=>esc((f.check_id||'review')+': '+(f.message||''))).join('；')}")
    template = template.replace("${raw?`<details class=", "<div class=\"statblock\"><div class=\"label\">Object Relation / Gripper State / Event Assessment / Evidence / Quality</div><div class=\"note\">${esc(JSON.stringify({object_relation:p.object_relation,gripper_state:p.gripper_state,event_assessment:p.event_assessment,evidence_frame_indices:p.evidence_frame_indices,evidence_quality:p.evidence_quality},null,2))}</div></div>${raw?`<details class=")
    template = template.replace("${raw?`<details class=", "${raw?`<details class=", 1)
    template = template.replace("</section>`}).join('')}</div>", "<details class=\"rawdetails\"><summary>展开完整 QC JSON ▾</summary><pre>${safeJson(qc)}</pre></details></section>`}).join('')}</div>")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(template, encoding="utf-8")
    print(f"BUILT {args.output.resolve()} segments=12 rgb_sha=36 gold=12 outputs=36 prompts=36 qc=36")


if __name__ == "__main__":
    main()
