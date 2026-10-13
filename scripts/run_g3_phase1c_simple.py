"""Minimal Phase 1C A-first review page using existing Phase 1B images."""
import argparse
import base64
import binascii
import csv
import hmac
import io
import json
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from project2_g3.simple_review import a_panel_field, blank, can_view_b, read_csv, save_review, sha, validate_assets

PAGE = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>G3 十条简易审核</title>
<style>body{font:17px system-ui;max-width:1100px;margin:auto;padding:18px;background:#f6f7f9;color:#18202a}section{background:white;border-radius:12px;padding:20px;margin:14px 0;box-shadow:0 2px 10px #0001}button{font:inherit;border:1px solid #adb5bd;background:white;border-radius:8px;padding:10px 16px;margin:5px;cursor:pointer}button:hover{background:#eaf2fa}.choice{background:#e6f0ff;border-color:#99bceb}img{max-width:100%;cursor:zoom-in}textarea{font:inherit;width:96%;min-height:65px}#message{color:#ad3300}dialog img{max-width:92vw;max-height:88vh}</style>
<h1>机器人动作：10 条简易审核</h1><p>先只看 A（目标段），保存第一题后才会显示 B（目标段加相邻上下文）。这是主观可理解性检查，不是语义标签或模型准确率评测。</p>
<section><button onclick="move(-1)">← 上一条</button><strong id="progress"></strong><button onclick="move(1)">下一条 →</button><button onclick="nextOpen()">跳到未完成</button><p id="identity"></p><p id="saved"></p></section>
<section id="stageA"><h2>1. 只看目标 Segment 的图片（A）</h2><img id="imageA" onclick="zoom(this.src)"><p>只看这些图片，你能判断机器人在做什么吗？</p><div id="choicesA"></div></section>
<section id="stageB" hidden><h2>2. 加上相邻 Segment 图片（B）</h2><p>图中上排为 A；下排为 B。B 的绿色标签是目标段，橙色标签是邻居段，按时间顺序排列。邻段动作不属于目标段。</p><img id="imageB" onclick="zoom(this.src)"><p>加上前后的图片，现在能判断机器人在做什么吗？</p><div id="choicesB"></div><button onclick="editA()">修改第一题</button></section>
<section id="stageLimit" hidden><h2>3. 选择一个主要限制原因</h2><p>如果仍有困难，主要原因是什么？</p><label>可选备注<br><textarea id="notes" oninput="draft()"></textarea></label><div id="choicesLimit"></div><button onclick="editB()">修改第二题</button></section>
<section><button onclick="skip()">跳过这一条</button><button onclick="exportData('csv')">导出 CSV</button><button onclick="exportData('json')">导出 JSON</button><span id="message"></span></section>
<dialog id="lightbox" onclick="this.close()"><img id="large"></dialog>
<script>
let rows=[],data={},index=0,stage='A';const labels={CANNOT:'不能',UNCERTAIN:'不确定',CAN:'能'};
const limits={MISSING_ACTION_CONTEXT:'缺少前后的动作过程',LOW_RESOLUTION:'图片太小，看不清物体',OCCLUDED_OR_OUT_OF_FRAME:'机械臂遮挡或物体出画',OTHER:'其他原因',NONE:'没有明显问题'};
async function api(path,body){let r=await fetch(path,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});let v=await r.json();if(!r.ok)throw Error(v.error);return v}
function choices(id,items,fn){document.getElementById(id).innerHTML=Object.entries(items).map(([value,label])=>`<button class="choice" onclick="${fn}('${value}')">${label}</button>`).join('')}
async function load(){try{rows=await api('/api/selection');data=await api('/api/reviews');show()}catch(e){message.textContent=e.message}}
function show(){if(!rows.length)return;let r=rows[index],d=data[r.segment_id]||{};progress.textContent=` ${index+1}/${rows.length}　已完成 ${Object.values(data).filter(x=>x.status==='COMPLETE').length}/${rows.length}`;identity.textContent=`${r.episode_id} / ${r.segment_id} / 目标帧 ${r.start_frame}–${r.end_frame}`;saved.textContent=`已保存：A ${labels[d.a_answer]||'未答'}；B ${labels[d.b_answer]||'未答'}；限制 ${limits[d.primary_limitation]||'未选'}${d.status==='SKIPPED'?'（已跳过）':''}`;notes.value=d.review_notes||'';stage=d.a_answer&&d.a_answer!=='UNSCORED'?(d.b_answer&&d.b_answer!=='UNSCORED'?'LIMIT':'B'):'A';render()}
function render(){let r=rows[index];stageA.hidden=stage!=='A';stageB.hidden=stage!=='B';stageLimit.hidden=stage!=='LIMIT';if(stage==='A')imageA.src='/image/'+r.segment_id+'/A';if(stage==='B')imageB.src='/image/'+r.segment_id+'/B';message.textContent=''}
function move(n){index=Math.max(0,Math.min(rows.length-1,index+n));show()}function nextOpen(){let i=rows.findIndex(r=>!data[r.segment_id]||!['COMPLETE','SKIPPED'].includes(data[r.segment_id].status));if(i>=0){index=i;show()}}
function zoom(url){large.src=url;lightbox.showModal()}function editA(){stage='A';render()}function editB(){stage='B';render()}
function draft(){let r=rows[index],d=data[r.segment_id];if(d)d.review_notes=notes.value}
async function savePatch(patch){let r=rows[index],d=Object.assign({episode_id:r.episode_id,segment_id:r.segment_id,a_answer:'UNSCORED',b_answer:'UNSCORED',primary_limitation:'UNSCORED',status:'UNSCORED',review_notes:'',review_timestamp:''},data[r.segment_id]||{},patch);d.review_timestamp=new Date().toISOString();try{await api('/api/save',d);data[r.segment_id]=d;show();return true}catch(e){message.textContent=e.message;return false}}
async function answerA(value){await savePatch({a_answer:value,b_answer:'UNSCORED',primary_limitation:'UNSCORED',status:'A_SCORED'})}
async function answerB(value){await savePatch({b_answer:value,primary_limitation:'UNSCORED',status:'B_SCORED'})}
async function answerLimit(value){if(await savePatch({primary_limitation:value,review_notes:notes.value,status:'COMPLETE'})){if(index<rows.length-1)move(1)}}
async function skip(){if(await savePatch({review_notes:notes.value,status:'SKIPPED'})){if(index<rows.length-1)move(1)}}
function exportData(kind){window.location='/export/'+kind}
choices('choicesA',labels,'answerA');choices('choicesB',labels,'answerB');choices('choicesLimit',limits,'answerLimit');load();
</script></html>'''

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--assets', type=Path, required=True)
    p.add_argument('--selection', type=Path, default=Path('0-doc/90-implementation-local/review_selection.csv'))
    p.add_argument('--results', type=Path, default=Path('outputs/g3_phase1c_reviews'))
    p.add_argument('--port', type=int, default=18871)
    p.add_argument('--auth-file', type=Path, help='file containing remote access password')
    args = p.parse_args()
    password = args.auth_file.read_text(encoding='utf-8').strip() if args.auth_file else None
    if args.auth_file and not password:
        raise ValueError('empty auth file')
    assets = args.assets.resolve()
    rows = read_csv(args.selection)
    if len(rows) != 10 or len({r['segment_id'] for r in rows}) != 10:
        raise ValueError('expected ten unique selections')
    selected = {r['segment_id']: r for r in rows}
    source = read_csv(assets / 'ab_review_sheet_UNSCORED.csv')
    key_rows = read_csv(assets / 'ab_blinding_key_SEALED.csv')
    keys = {r['segment_id']: r for r in key_rows}
    validate_assets(source, key_rows, read_csv(assets / 'evidence_frame_manifest.csv'), assets)
    source_by_id = {r['segment_id']: r for r in source}
    for r in rows:
        original = source_by_id[r['segment_id']]
        for field in ('analyst_sheet', 'blinded_panel1', 'blinded_panel2'):
            if sha(assets / original[field]) != r[field+'_sha256']:
                raise ValueError('asset hash mismatch: '+r['segment_id'])
    results_file = args.results.resolve() / 'simple_review.json'

    class Handler(BaseHTTPRequestHandler):
        def authorized(self):
            if password is None:
                return True
            try:
                scheme, encoded = self.headers.get('Authorization', '').split(' ', 1)
                user, supplied = base64.b64decode(encoded, validate=True).decode().split(':', 1)
                if scheme == 'Basic' and user == 'reviewer' and hmac.compare_digest(supplied, password):
                    return True
            except (ValueError, UnicodeError, binascii.Error):
                pass
            self.send_response(401)
            self.send_header('WWW-Authenticate', 'Basic realm="G3 simple review"')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return False

        def reply(self, content, kind='application/json', code=200):
            if isinstance(content, (dict, list)):
                content = json.dumps(content, ensure_ascii=False).encode()
            elif isinstance(content, str):
                content = content.encode()
            self.send_response(code)
            self.send_header('Content-Type', kind + '; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def records(self):
            return json.loads(results_file.read_text(encoding='utf-8')) if results_file.exists() else {}

        def do_GET(self):
            if not self.authorized():
                return
            parts = urlparse(self.path).path.strip('/').split('/')
            if parts == ['']:
                return self.reply(PAGE, 'text/html')
            if parts == ['api', 'selection']:
                return self.reply([{k:v for k,v in r.items() if k not in ('panel1_is','panel2_is')} for r in rows])
            if parts == ['api', 'reviews']:
                return self.reply(self.records())
            if len(parts) == 3 and parts[0] == 'image' and parts[1] in selected and parts[2] in ('A','B'):
                sid, arm = parts[1], parts[2]
                if arm == 'B' and not can_view_b(self.records().get(sid, {})):
                    return self.reply({'error':'save A before viewing B'}, code=403)
                src = source_by_id[sid]
                if arm == 'A':
                    path = assets / src[a_panel_field(keys[sid])]
                else:
                    path = assets / src['analyst_sheet']
                return self.reply(path.read_bytes(), 'image/png')
            if len(parts) == 2 and parts[0] == 'export' and parts[1] in ('csv','json'):
                records = self.records()
                ordered = [records.get(r['segment_id'], blank(r)) for r in rows]
                if parts[1] == 'json':
                    return self.reply(ordered)
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=list(blank(rows[0])), extrasaction='ignore')
                writer.writeheader()
                writer.writerows(ordered)
                return self.reply(output.getvalue(), 'text/csv')
            return self.reply({'error':'not found'}, code=404)

        def do_POST(self):
            if not self.authorized():
                return
            if urlparse(self.path).path != '/api/save':
                return self.reply({'error':'not found'}, code=404)
            try:
                n = int(self.headers.get('Content-Length', '0'))
                if n <= 0 or n > 10000:
                    raise ValueError('invalid body length')
                record = json.loads(self.rfile.read(n))
                sid = record.get('segment_id')
                if sid not in selected:
                    raise ValueError('segment not selected')
                previous = self.records().get(sid, {})
                if record.get('b_answer') != 'UNSCORED' and previous.get('a_answer', 'UNSCORED') == 'UNSCORED':
                    raise ValueError('B requires previously saved A')
                save_review(args.results, record, selected)
                return self.reply({'ok': True})
            except (ValueError, KeyError, TypeError) as exc:
                return self.reply({'error':str(exc)}, code=400)

    print(f'http://127.0.0.1:{args.port}/', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()

if __name__ == '__main__':
    main()
