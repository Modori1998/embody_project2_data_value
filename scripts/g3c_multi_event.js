"use strict";
// P2 G3C: local-only blind human multi-event audit, no model predictions and no network calls.
(function () {
const $ = id => document.getElementById(id);
const bundle = JSON.parse($("audit-payload").textContent);
const rows=bundle.rows, fields=bundle.fields;
const phases=[["approach","靠近"],["grasp","抓取"],["lift","提起"],["transport","搬运"],["place","放置"],["retract","撤离"],["idle","静止"],["other","其他动作"],["uncertain","无法判断"]];
const assessments=[["event_visible","观察到事件"],["no_event_visible","未观察到事件"],["insufficient_evidence","证据不足"]];
const events=[["grasp_attempt","抓取尝试"],["release_attempt","释放尝试"],["object_motion","物体移动"]];
const primary=[...events,["none","无事件"],["uncertain","无法判断"]];
const qualities=[["sufficient","充分"],["partial","部分充分"],["insufficient","不足"]];
const rubric={phase_ref:phases,event_assessment_ref:assessments,event_type_ref:primary,evidence_quality_ref:qualities};
const types=events.map(v=>v[0]);
const citationFields=Object.fromEntries(types.map(v=>[v,v+"_frames_ref"]));
const multiFields=["event_types_ref",...types.map(v=>citationFields[v])];
const editable=["phase_ref","event_assessment_ref","event_type_ref","evidence_quality_ref","reviewer_id","reviewed_at_utc","explanation",...multiFields];
const oldFields=fields.filter(f=>!multiFields.includes(f));
if(multiFields.some(x=>!fields.includes(x)))throw Error("G3C 多事件字段缺失");
const key="p2_g3_blind_audit_v2_"+bundle.source_manifest_sha256;
const oldKey="p2_g3_blind_audit_v1_"+bundle.source_manifest_sha256;
let answers={},current=0,storageOK=true;
function choices(name){return rubric[name].map(v=>v[0]);}
function members(text,valid) {
 if(!text)return [];
 if(typeof text!=="string")return null;
 const p=text.split(";");
 if(p.some(v=>!valid.includes(v))||new Set(p).size!==p.length)return null;
 return p;
}
function migrate(old) {
 const a={};
 for(const f of editable)if(!multiFields.includes(f))a[f]=String(old[f]||"");
 a.event_types_ref=a.event_assessment_ref==="event_visible"&&types.includes(a.event_type_ref)?a.event_type_ref:"";
 for(const t of types)a[citationFields[t]]="";
 return a; // No invented secondary event or evidence from a legacy label.
}
function valid(a,row) {
 if(!a||typeof a!=="object")return false;
 for(const name of Object.keys(rubric))if(a[name]&&!choices(name).includes(a[name]))return false;
 const selected=members(a.event_types_ref||"",types),allowed=row.target_keyframes.split(";");
 if(selected===null)return false;
 for(const t of types) {
  const refs=members(a[citationFields[t]]||"",allowed);
  if(refs===null||(refs.length&&!selected.includes(t)))return false;
 }
 const assessment=a.event_assessment_ref||"",one=a.event_type_ref||"";
 if(assessment==="event_visible") {
  if(["none","uncertain"].includes(one))return false;
  if(one&&!selected.includes(one))return false;
 } else {
  if(selected.length||types.some(t=>!!a[citationFields[t]]))return false;
  if(assessment==="no_event_visible"&&one&&one!=="none")return false;
  if(assessment==="insufficient_evidence"&&one&&one!=="uncertain")return false;
  if(!assessment&&one)return false;
 }
 return true;
}
function complete(a,row) {
 if(!valid(a,row)||!a.phase_ref||!a.event_assessment_ref||!a.event_type_ref||!a.evidence_quality_ref)return false;
 if(a.event_assessment_ref!=="event_visible")return true;
 const selected=members(a.event_types_ref||"",types);
 return selected.length>0&&selected.includes(a.event_type_ref)&&
  selected.every(t=>(members(a[citationFields[t]]||"",row.target_keyframes.split(";"))||[]).length>=2);
}
function save(){
 try {localStorage.setItem(key,JSON.stringify({reviewer:$("reviewer").value,answers}));storageOK=true;}
 catch(e){storageOK=false;$("save-status").textContent="无法自动保存，请导出 CSV";}
}
function restore(){
 try {
  const now=localStorage.getItem(key),legacy=now?null:localStorage.getItem(oldKey),raw=now||legacy;
  if(!raw)return;
  const data=JSON.parse(raw);
  if(data&&data.answers&&typeof data.answers==="object") {
   for(const r of rows) {
    const a=data.answers[r.segment_id];
    if(a&&typeof a==="object")answers[r.segment_id]=legacy?migrate(a):a;
   }
   $("reviewer").value=String(data.reviewer||"").slice(0,100);
   if(legacy){save();$("toast").textContent="已复制旧版浏览器记录，旧记录未更改。请复核多事件与帧证据。";}
  }
 }catch(e){storageOK=false;$("save-status").textContent="恢复失败，请导入已保存 CSV";}
}
function touch(a) {
 const r=rows[current];
 a.reviewer_id=$("reviewer").value.trim();
 a.reviewed_at_utc=complete(a,r)?new Date().toISOString():"";
 answers[r.segment_id]=a;save();render();
}
function pick(name,value){
 const a={...(answers[rows[current].segment_id]||{})};
 a[name]=value;
 if(name==="event_assessment_ref") {
  if(value!=="event_visible"){
   a.event_type_ref=value==="no_event_visible"?"none":"uncertain";
   a.event_types_ref="";
   for(const t of types)a[citationFields[t]]="";
  } else if(["none","uncertain"].includes(a.event_type_ref))a.event_type_ref="";
 }
 if(name==="event_type_ref") {
  if(types.includes(value)){
   a.event_assessment_ref="event_visible";
   const old=members(a.event_types_ref||"",types)||[];
   a.event_types_ref=types.filter(t=>old.includes(t)||t===value).join(";");
  } else {
   a.event_assessment_ref=value==="none"?"no_event_visible":"insufficient_evidence";
   a.event_types_ref="";
   for(const t of types)a[citationFields[t]]="";
  }
 }
 touch(a);
}
function toggleType(type,checked){
 const a={...(answers[rows[current].segment_id]||{})};
 let selected=members(a.event_types_ref||"",types)||[];
 selected=types.filter(t=>(t===type?checked:selected.includes(t)));
 if(!checked)a[citationFields[type]]="";
 a.event_types_ref=selected.join(";");
 if(checked)a.event_assessment_ref="event_visible";
 if(!selected.includes(a.event_type_ref))a.event_type_ref=selected[0]||"";
 touch(a);
}
function toggleEvidence(type,frame,checked){
 const r=rows[current],a={...(answers[r.segment_id]||{})};
 const allowed=r.target_keyframes.split(";");
 let present=members(a[citationFields[type]]||"",allowed)||[];
 present=present.filter(x=>x!==frame);
 if(checked)present.push(frame);
 a[citationFields[type]]=allowed.filter(x=>present.includes(x)).join(";");
 touch(a);
}
function makeRadios(){
 for(const [name,vals]of Object.entries(rubric)){
  for(const [value,title]of vals) {
   const lab=document.createElement("label");lab.className="choice";
   const inp=document.createElement("input");inp.type="radio";inp.name=name;inp.value=value;
   inp.addEventListener("change",()=>pick(name,value));
   lab.append(inp,document.createTextNode(title));$(name).append(lab);
  }
 }
 for(const [value,title]of events){
  const lab=document.createElement("label");lab.className="choice";
  const inp=document.createElement("input");inp.type="checkbox";inp.name="event_types_ref";inp.value=value;
  inp.addEventListener("change",()=>toggleType(value,inp.checked));
  lab.append(inp,document.createTextNode(title));$("event_types_ref").append(lab);
 }
}
function render(){
 const r=rows[current],a=answers[r.segment_id]||{};
 $("position").textContent=(current+1)+" / "+rows.length;
 $("identity").textContent=r.segment_id+" · Episode "+r.episode_id+" · 冻结区间 ["+r.start_frame+", "+r.end_frame+"]";
 const done=rows.filter(row=>complete(answers[row.segment_id],row)).length;
 $("progress").textContent="已完成 "+done+" / "+rows.length;
 $("progressFill").style.width=(100*done/rows.length)+"%";
 r.images.forEach((img,i)=>{
  const el=$("frame-"+i);el.src=img.src;el.alt="目标段 "+img.role+" 帧 "+img.frame_index;
  $("caption-"+i).textContent=img.role+" · frame "+img.frame_index;
  el.onerror=()=>{$("caption-"+i).textContent="图片未加载：frame "+img.frame_index;$("caption-"+i).className="error";};
  el.onload=()=>{$("caption-"+i).className="";};
 });
 for(const name of Object.keys(rubric))
  for(const inp of document.querySelectorAll('input[name="'+name+'"]'))inp.checked=inp.value===a[name];
 const selected=members(a.event_types_ref||"",types)||[];
 for(const inp of document.querySelectorAll('input[name="event_types_ref"]')){
  inp.checked=selected.includes(inp.value);inp.disabled=a.event_assessment_ref!=="event_visible";
 }
 const box=$("event_evidence_ref");box.replaceChildren();
 for(const [type,label] of events) {
  if(!selected.includes(type))continue;
  const wrapper=document.createElement("div");wrapper.className="evidenceItem";
  const title=document.createElement("strong");title.textContent=label+" · 证据帧：";
  wrapper.append(title);
  const existing=members(a[citationFields[type]]||"",r.target_keyframes.split(";"))||[];
  const line=document.createElement("div");line.className="choices";
  for(const img of r.images){
   const lab=document.createElement("label");lab.className="choice";
   const inp=document.createElement("input");inp.type="checkbox";inp.name=citationFields[type];
   inp.value=String(img.frame_index);inp.checked=existing.includes(inp.value);
   inp.addEventListener("change",()=>toggleEvidence(type,inp.value,inp.checked));
   lab.append(inp,document.createTextNode(img.role+" · "+img.frame_index));line.append(lab);
  }
  wrapper.append(line);box.append(wrapper);
 }
 if(!selected.length)box.textContent="无可见事件时不需要标记证据帧。";
 $("explanation").value=a.explanation||"";
 const consistent=valid(a,r);
 $("caseStatus").textContent=!consistent?"事件组合冲突：需修正后才能导出。":
  complete(a,r)?"已完成并保存在浏览器":"待补审：确认所有事件与每个事件的至少两张证据帧。";
 $("caseStatus").className=consistent?"muted":"error";
 $("prev").disabled=current===0;$("next").disabled=current===rows.length-1;
 $("save-status").textContent=storageOK?"自动保存在当前浏览器；请定期导出 CSV。":"不能自动保存；请导出 CSV。";
}
function csvCell(x){const s=String(x==null?"":x);return /[",\r\n]/.test(s)?'"'+s.replace(/"/g,'""')+'"':s;}
function download(){
 const bad=rows.filter(r=>answers[r.segment_id]&&!valid(answers[r.segment_id],r)).map(r=>r.segment_id);
 if(bad.length){window.alert("存在事件逻辑冲突，请先核验："+bad.join("、"));return;}
 const data=[fields.join(",")];
 for(const r of rows) {
  const a=answers[r.segment_id]||{};
  data.push(fields.map(f=>csvCell(editable.includes(f)?(a[f]||""):(r[f]||""))).join(","));
 }
 const blob=new Blob(["\ufeff"+data.join("\r\n")+"\r\n"],{type:"text/csv;charset=utf-8"});
 const url=URL.createObjectURL(blob),link=document.createElement("a");
 link.href=url;link.download="G3C_12_Segment_Human_MultiEvent_Reference_v2.csv";
 document.body.append(link);link.click();link.remove();
 setTimeout(()=>URL.revokeObjectURL(url),1000);
 const done=rows.filter(r=>complete(answers[r.segment_id],r)).length;
 $("toast").textContent="新版 CSV 已导出：完成 "+done+"/12；未完成行保留为空/待补证据，不计作完成。";
}
function parseCSV(source){
 const text=source.replace(/^\ufeff/,""),data=[];
 let row=[],cell="",quoted=false;
 for(let i=0;i<text.length;i++){
  const c=text[i];
  if(quoted){
   if(c==='"'&&text[i+1]==='"'){cell+='"';i++;}
   else if(c==='"')quoted=false;else cell+=c;
  }else if(c==='"'){if(cell!=="")throw Error("CSV 引号错误");quoted=true;}
  else if(c===","){row.push(cell);cell="";}
  else if(c==="\r"||c==="\n"){
   if(c==="\r"&&text[i+1]==="\n")i++;
   row.push(cell);cell="";if(row.some(x=>x!==""))data.push(row);row=[];
  }else cell+=c;
 }
 if(quoted)throw Error("CSV 引号未结束");
 if(cell||row.length){row.push(cell);data.push(row);}
 return data;
}
function importCSV(source){
 const data=parseCSV(source);
 if(data.length!==rows.length+1)throw Error("审核记录必须为 "+rows.length+" 行");
 const header=data[0],legacy=JSON.stringify(header)===JSON.stringify(oldFields);
 if(!legacy&&JSON.stringify(header)!==JSON.stringify(fields))throw Error("CSV 表头不属于旧版或 G3C v2 版本");
 const incoming={};
 for(let i=0;i<rows.length;i++){
  const values=data[i+1],r=rows[i];
  if(values.length!==header.length)throw Error("CSV 第 "+(i+2)+" 行列数不符");
  const record={};header.forEach((f,n)=>record[f]=values[n]);
  if(record.segment_id!==r.segment_id)throw Error("Segment 顺序/身份不符："+r.segment_id);
  for(const f of oldFields.filter(x=>!editable.includes(x)))
   if(record[f]!==String(r[f]||""))throw Error(r.segment_id+" 冻结来源字段被改动："+f);
  const a={};for(const f of editable)a[f]=record[f]||"";
  incoming[r.segment_id]=legacy?migrate(a):a;
  if(!legacy&&!valid(a,r))throw Error(r.segment_id+" 多事件字段矛盾");
 }
 answers=incoming;save();render();
 const bad=rows.filter(r=>!valid(answers[r.segment_id],r)).map(r=>r.segment_id);
 $("toast").textContent=(legacy?"旧版":"新版")+" CSV 导入成功；旧数据未覆盖。"+
  (legacy?"需补事件证据，不能把迁移的主事件当作完整事件集合。":"")+
  (bad.length?" 原始冲突需核验："+bad.join("、"):"");
}
$("reviewer").addEventListener("change",()=>{
 for(const r of rows){const a=answers[r.segment_id];if(a&&complete(a,r))a.reviewer_id=$("reviewer").value.trim();}
 save();render();
});
$("explanation").addEventListener("input",()=>{
 const r=rows[current],a={...(answers[r.segment_id]||{})};
 a.explanation=$("explanation").value;a.reviewer_id=$("reviewer").value.trim();
 a.reviewed_at_utc=complete(a,r)?new Date().toISOString():"";
 answers[r.segment_id]=a;save();
});
$("prev").addEventListener("click",()=>{if(current>0){current--;render();}});
$("next").addEventListener("click",()=>{if(current+1<rows.length){current++;render();}});
$("export").addEventListener("click",download);
$("import").addEventListener("click",()=>$("importFile").click());
$("importFile").addEventListener("change",async e=>{
 const f=e.target.files[0];if(!f)return;
 try{importCSV(await f.text());}catch(err){window.alert("导入失败（未改动现有数据）："+err.message);}
 e.target.value="";
});
makeRadios();restore();render();
})();
