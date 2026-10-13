"use strict";
// Dependency-free DOM simulation for the G3C UI interaction contract; not a Chromium substitute.
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const js=fs.readFileSync("scripts/g3c_multi_event.js","utf8");
const oldFields=["sample_order","cohort","episode_id","segment_id","start_frame","end_frame","segment_length","target_keyframes","frame_png_sha256s","phase_ref","event_assessment_ref","event_type_ref","evidence_quality_ref","reviewer_id","reviewed_at_utc","explanation"];
const extra=["event_types_ref","grasp_attempt_frames_ref","release_attempt_frames_ref","object_motion_frames_ref"];
const fields=[...oldFields,...extra];
const rows=Array.from({length:12},(_,i)=>({
 sample_order:String(i+4),cohort:"microset",episode_id:"data/demo_"+(i+2),
 segment_id:"demo_"+(i+2)+"-S0003",start_frame:"63",end_frame:"106",segment_length:"44",
 target_keyframes:"63;84;106",frame_png_sha256s:"a;b;c",
 images:[{src:"images/a.png",role:"START",frame_index:63},{src:"images/b.png",role:"MIDDLE",frame_index:84},{src:"images/c.png",role:"END",frame_index:106}]
}));
function el(tag){
 return {tag,children:[],handlers:{},value:"",checked:false,disabled:false,
 style:{},textContent:"",className:"",files:[],append(...nodes){this.children.push(...nodes);},
 appendChild(node){this.children.push(node);},replaceChildren(...nodes){this.children=[...nodes];},
 addEventListener(ev,fn){this.handlers[ev]=fn;},click(){if(this.handlers.click)return this.handlers.click();},
 remove(){}};
}
const elements=new Map();
for(const id of ["audit-payload","position","progress","identity","progressFill","save-status",
 "reviewer","event_types_ref","event_evidence_ref","phase_ref","event_assessment_ref",
 "event_type_ref","evidence_quality_ref","explanation","caseStatus",
 "prev","next","import","export","importFile","toast",...Array.from({length:3},(_,i)=>["frame-"+i,"caption-"+i]).flat()]){
 elements.set(id,el("div"));
}
elements.get("audit-payload").textContent=JSON.stringify({rows,fields,source_manifest_sha256:"abc"});
const document={
 getElementById:id=>elements.get(id),
 createElement:tag=>el(tag),
 createTextNode:text=>({tag:"text",textContent:String(text)}),
 body:{append(){}},
 querySelectorAll:selector=>{
  const name=selector.match(/^input\[name="([^"]+)"\]$/)?.[1];
  if(!name)return [];
  const acc=[],walk=n=>{if(n&&typeof n==="object"){if(n.tag==="input"&&n.name===name)acc.push(n);for(const c of n.children||[])walk(c);}};
  for(const r of elements.values())walk(r);
  return acc;
 }
};
const storage=new Map(),alerts=[],blobs=[];
const ctx={
 document,window:{alert:message=>alerts.push(message)},
 localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)},
 URL:{createObjectURL:blob=>{blobs.push(blob);return "blob:mock";},revokeObjectURL:()=>{}},
 Blob,setTimeout:()=>{},Date,console
};
vm.runInNewContext(js,ctx,{filename:"g3c_multi_event.js"});
const get=id=>elements.get(id);
function choose(name,value,checked=true) {
 const input=document.querySelectorAll('input[name="'+name+'"]').find(x=>x.value===value);
 assert.ok(input,"missing control "+name+"="+value);
 input.checked=checked;input.handlers.change();
}
async function run(){
 assert.equal(get("progress").textContent,"已完成 0 / 12");
 choose("phase_ref","transport");
 choose("evidence_quality_ref","sufficient");
 choose("event_assessment_ref","event_visible");
 choose("event_types_ref","object_motion");
 choose("event_type_ref","object_motion");
 choose("object_motion_frames_ref","84");
 choose("object_motion_frames_ref","106");
 choose("event_types_ref","grasp_attempt");
 choose("grasp_attempt_frames_ref","63");
 choose("grasp_attempt_frames_ref","84");
 assert.equal(get("progress").textContent,"已完成 1 / 12");
 get("export").click();
 assert.equal(blobs.length,1);
 const csv=await blobs.at(-1).text();
 assert.ok(csv.includes("event_types_ref,grasp_attempt_frames_ref,release_attempt_frames_ref,object_motion_frames_ref"));
 assert.ok(csv.includes("grasp_attempt;object_motion"));
 assert.ok(csv.includes("63;84"));
 assert.ok(csv.includes("84;106"));
 assert.ok(csv.includes("G3")===false); // only data values and headers
 // Old CSV can be imported without invented event citations.
 const legacy=[oldFields.join(",")];
 for(let i=0;i<12;i++){
  const r=rows[i],a=Object.fromEntries(oldFields.map(f=>[f,r[f]||""]));
  a.phase_ref="transport";a.event_assessment_ref=i===0?"event_visible":"no_event_visible";
  a.event_type_ref=i===0?"object_motion":"none";a.evidence_quality_ref="sufficient";
  legacy.push(oldFields.map(f=>a[f]||"").join(","));
 }
 get("importFile").files=[{text:async()=>legacy.join("\r\n")}];
 await get("importFile").handlers.change({target:get("importFile")});
 assert.equal(get("progress").textContent,"已完成 11 / 12");
 assert.ok(get("toast").textContent.includes("旧版 CSV 导入成功"));
 assert.equal(document.querySelectorAll('input[name="event_types_ref"]').find(x=>x.value==="object_motion").checked,true);
 assert.equal(document.querySelectorAll('input[name="object_motion_frames_ref"]').filter(x=>x.checked).length,0);
 // A no-event->grasp contradiction is preserved, warned and prevents export (no silent repair).
 const bad=legacy.slice();const cols=bad[1].split(",");
 cols[oldFields.indexOf("event_assessment_ref")]="no_event_visible";
 cols[oldFields.indexOf("event_type_ref")]="grasp_attempt";bad[1]=cols.join(",");
 get("importFile").files=[{text:async()=>bad.join("\r\n")}];
 await get("importFile").handlers.change({target:get("importFile")});
 assert.ok(get("toast").textContent.includes("原始冲突需核验"));
 const before=blobs.length;get("export").click();
 assert.equal(blobs.length,before);
 assert.ok(alerts.at(-1).includes("demo_2-S0003"));
 // Correct the contradictory row without dropping the rest.
 choose("event_type_ref","none");
 get("export").click();
 assert.equal(blobs.length,before+1);
 console.log("G3C UI DOM SMOKE PASS: multi-event + frame citation + versioned CSV + legacy migration + contradiction stop");
}
run().catch(e=>{console.error(e);process.exitCode=1;});
