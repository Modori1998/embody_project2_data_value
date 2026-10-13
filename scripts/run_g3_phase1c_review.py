"""Local Phase 1C reviewer; Python standard library only."""
import argparse
import csv
import json
import mimetypes
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from project2_g3.human_review import METRICS, blank, read_csv, save_review, sha, summarize, validate_assets

PAGE = '''<!doctype html><html lang="zh"><meta charset="utf-8"><title>G3 Phase 1C 人工审核</title>
<style>body{font:16px system-ui;max-width:1400px;margin:auto;padding:20px;background:#f5f6f8;color:#171717}button,input,select,textarea{font:inherit;margin:4px;padding:5px}img{max-width:100%;cursor:zoom-in;background:white}section{background:white;padding:16px;margin:12px 0;border-radius:8px}table{border-collapse:collapse}td,th{border:1px solid #bbb;padding:5px}textarea{width:95%}.panels{display:grid;grid-template-columns:1fr 1fr;gap:12px}dialog img{max-width:90vw;max-height:85vh}</style>
<h1>Phase 1C 人工可观测性审核</h1><p>这是 Development 审核。面板按锁定规则排列；B 帧数较多，不能视为完全双盲。评估目标段内事件；邻段的释放不得算作目标段内释放。</p>
<label>审核者 ID <input id="reviewer" value="owner"></label><button onclick="load()">载入进度</button><button onclick="exportData('json')">导出 JSON</button><button onclick="exportData('csv')">导出 CSV</button>
<section><button onclick="move(-1)">上一条 ←</button><strong id="progress"></strong><button onclick="move(1)">下一条 →</button><button onclick="nextMissing()">查看未完成项</button><p id="identity"></p><p id="status"></p></section>
<div class="panels"><section><h2>面板 1</h2><img id="panel1" onclick="zoom(this.src)"></section><section><h2>面板 2</h2><img id="panel2" onclick="zoom(this.src)"></section></div>
<section><p>面板图像没有来源标签。需要核对时间与来源时，可打开 <button onclick="source()">来源说明图</button>；该图显示目标帧和邻段帧的位置，会解除匿名。</p>
<table id="scores"><tr><th>指标</th><th>面板 1</th><th>面板 2</th></tr></table>
<p><label>邻段上下文有帮助 <select id="neighbor_context_helpful"></select></label><label>事件发生在目标段外 <select id="event_outside_target"></select></label><label>主要限制 <select id="primary_limitation"></select></label></p>
<p><label>备注 <textarea id="review_notes" rows="3"></textarea></label></p><p><label>跳过原因 <input id="skip_reason"></label></p>
<button onclick="save('COMPLETE')">保存本条评分</button><button onclick="save('SKIPPED')">跳过并保存原因</button><button onclick="save('UNSCORED')">保存草稿</button><span id="message"></span></section>
<dialog id="lightbox" onclick="this.close()"><img id="large"></dialog>
<script>
let rows=[],data={},index=0;const metrics=['object_visible','motion_phase_decidable','gripper_transition_visible','object_following_decidable','release_decidable'];
const names=['目标物体清楚可见','目标段主要动作阶段可判断','夹爪开合变化可见','物体是否跟随夹爪可判断','目标段内释放可判断'];
const levels=['UNSCORED','SUFFICIENT','PARTIAL','INSUFFICIENT','NOT_APPLICABLE'];
function opt(id,values){let e=document.getElementById(id);e.innerHTML=values.map(x=>`<option>${x}</option>`).join('')}
function setup(){opt('neighbor_context_helpful',['UNSCORED','YES','NO','UNCLEAR']);opt('event_outside_target',['UNSCORED','YES','NO','UNCLEAR']);opt('primary_limitation',['UNSCORED','NONE','LOW_RESOLUTION','OCCLUSION','OUT_OF_FRAME','TEMPORAL_GAP','OTHER']);document.getElementById('scores').innerHTML+='<tr><td colspan="3">SUFFICIENT 足以判断；PARTIAL 有帮助但不能确认；INSUFFICIENT 不足；NOT_APPLICABLE 不适用</td></tr>'+metrics.map((m,i)=>`<tr><td>${names[i]}</td>${[1,2].map(a=>`<td><select id="panel${a}_${m}">${levels.map(v=>`<option>${v}</option>`).join('')}</select></td>`).join('')}</tr>`).join('')}
async function api(path,body){let x=await fetch(path,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});let v=await x.json();if(!x.ok)throw Error(v.error);return v}
async function load(){try{rows=await api('/api/selection');data=await api('/api/reviews?reviewer='+encodeURIComponent(document.getElementById('reviewer').value));show()}catch(e){message.textContent=e.message}}
function show(){if(!rows.length)return;let r=rows[index],d=data[r.segment_id]||{};progress.textContent=` ${index+1}/${rows.length}　已完成 ${Object.values(data).filter(x=>x.status==='COMPLETE').length} 条`;identity.textContent=`${r.episode_id} / ${r.segment_id} / 目标帧 ${r.start_frame}–${r.end_frame} / ${r.selection_strata}`;status.textContent=d.status||'UNSCORED';panel1.src='/image/'+r.segment_id+'/1';panel2.src='/image/'+r.segment_id+'/2';for(let k of [...metrics.flatMap(m=>['panel1_'+m,'panel2_'+m]),'neighbor_context_helpful','event_outside_target','primary_limitation','review_notes','skip_reason'])document.getElementById(k).value=d[k]||((k==='review_notes'||k==='skip_reason')?'':'UNSCORED');message.textContent=''}
function move(n){index=Math.max(0,Math.min(rows.length-1,index+n));show()}function nextMissing(){let i=rows.findIndex(r=>!data[r.segment_id]||data[r.segment_id].status!=='COMPLETE');if(i>=0){index=i;show()}}
function zoom(url){large.src=url;lightbox.showModal()}function source(){zoom('/source/'+rows[index].segment_id)}
async function save(status){let r=rows[index],d={episode_id:r.episode_id,segment_id:r.segment_id,reviewer_id:reviewer.value,status,review_timestamp:new Date().toISOString()};for(let k of [...metrics.flatMap(m=>['panel1_'+m,'panel2_'+m]),'neighbor_context_helpful','event_outside_target','primary_limitation','review_notes','skip_reason'])d[k]=document.getElementById(k).value;try{await api('/api/save',d);data[r.segment_id]=d;show();message.textContent='已保存'}catch(e){message.textContent=e.message}}
function exportData(fmt){window.location='/export/'+fmt+'?reviewer='+encodeURIComponent(reviewer.value)}
document.addEventListener('keydown',e=>{if(['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName))return;if(e.key==='ArrowLeft')move(-1);if(e.key==='ArrowRight')move(1)});setup();load();
</script></html>'''

def main():
    p=argparse.ArgumentParser();p.add_argument('--assets',type=Path,required=True);p.add_argument('--selection',type=Path,default=Path('0-doc/90-implementation-local/phase1c_review_selection_manifest.csv'));p.add_argument('--results',type=Path,default=Path('outputs/g3_phase1c_reviews'));p.add_argument('--port',type=int,default=8765);args=p.parse_args()
    rows=read_csv(args.selection);selected={r['segment_id']:r for r in rows};assets=args.assets.resolve();results=args.results.resolve()
    phase=read_csv(assets/'ab_review_sheet_UNSCORED.csv');keyrows=read_csv(assets/'ab_blinding_key_SEALED.csv');keys={r['segment_id']:r for r in keyrows};validate_assets(phase,keyrows,read_csv(assets/'evidence_frame_manifest.csv'),assets)
    for r in rows:
        source=next(x for x in phase if x['segment_id']==r['segment_id'])
        for k in ('blinded_panel1','blinded_panel2','analyst_sheet'):
            if sha(assets/source[k])!=r[k+'_sha256']:raise ValueError('asset hash mismatch: '+r['segment_id'])
    class Handler(BaseHTTPRequestHandler):
        def reply(self,content,kind='application/json',code=200):
            if isinstance(content,(dict,list)):content=json.dumps(content,ensure_ascii=False).encode()
            elif isinstance(content,str):content=content.encode()
            self.send_response(code);self.send_header('Content-Type',kind+'; charset=utf-8');self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content)
        def do_GET(self):
            u=urlparse(self.path);q=parse_qs(u.query);reviewer=q.get('reviewer',['owner'])[0]
            if u.path=='/':return self.reply(PAGE,'text/html')
            if u.path=='/api/selection':return self.reply([{k:v for k,v in r.items() if k not in ('panel1_is','panel2_is')} for r in rows])
            if u.path=='/api/reviews':
                if not reviewer.replace('_','').replace('-','').isalnum():return self.reply({'error':'invalid reviewer'},code=400)
                f=results/(reviewer+'.json');stored=json.loads(f.read_text(encoding='utf-8')) if f.exists() else {}
                visible={}
                for sid,d in stored.items():
                    v=dict(d)
                    for panel in (1,2):
                        arm=keys[sid][f'panel{panel}_is']
                        for metric in METRICS:v[f'panel{panel}_{metric}']=v.pop(f'{arm}_{metric}')
                    visible[sid]=v
                return self.reply(visible)
            parts=u.path.strip('/').split('/')
            if len(parts)>=2 and parts[0] in ('image','source') and parts[1] in selected:
                r=selected[parts[1]];field='analyst_sheet' if parts[0]=='source' else 'blinded_panel'+(parts[2] if len(parts)>2 else '')
                if field not in ('analyst_sheet','blinded_panel1','blinded_panel2'):return self.reply({'error':'bad panel'},code=400)
                f=assets/r[field];return self.reply(f.read_bytes(),'image/png')
            if len(parts)==2 and parts[0]=='export' and parts[1] in ('json','csv'):
                f=results/(reviewer+'.json');d=json.loads(f.read_text(encoding='utf-8')) if f.exists() else {};values=list(d.values())
                if parts[1]=='json':return self.reply(values)
                import io
                s=io.StringIO();fields=list(blank(rows[0],reviewer));w=csv.DictWriter(s,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(values);return self.reply(s.getvalue(),'text/csv')
            self.reply({'error':'not found'},code=404)
        def do_POST(self):
            if self.path!='/api/save':return self.reply({'error':'not found'},code=404)
            try:
                n=int(self.headers.get('Content-Length','0'))
                if n>100000:raise ValueError('body too large')
                d=json.loads(self.rfile.read(n));sid=d.get('segment_id')
                if sid not in selected:raise ValueError('segment not selected')
                for panel in (1,2):
                    arm=keys[sid][f'panel{panel}_is']
                    for metric in METRICS:d[f'{arm}_{metric}']=d.pop(f'panel{panel}_{metric}')
                save_review(results,d,selected)
                return self.reply({'ok':True})
            except (ValueError,KeyError,TypeError) as e:return self.reply({'error':str(e)},code=400)
    print(f'http://127.0.0.1:{args.port}/',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()

if __name__=='__main__':main()
