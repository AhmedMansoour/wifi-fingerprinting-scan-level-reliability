"use strict";
const $=id=>document.getElementById(id);
const C=[["signal_match","Signal match"],["candidate_geometry","Candidate geometry"],["ap_count","AP count"],["ap_overlap","AP overlap"],["local_density","Local RP density"]];
const defs={association:["median_aligned_rho","q25_aligned_rho","q75_aligned_rho","n_conditions_assoc","Aligned Spearman association"],adaptive_auroc:["median_auroc","q25_auroc","q75_auroc","n_conditions_adaptive","Adaptive gross-error AUROC"],adaptive_auprc:["median_auprc","q25_auprc","q75_auprc","n_conditions_adaptive","Adaptive gross-error AUPRC"],fixed_auroc:["median_auroc_fixed7m","q25_auroc_fixed7m","q75_auroc_fixed7m","n_conditions","Fixed 7 m AUROC"],fixed_auprc:["median_auprc_fixed7m","q25_auprc_fixed7m","q75_auprc_fixed7m","n_conditions","Fixed 7 m AUPRC"]};
const order=["SQS_reconstructed","SQS_without_signal","SQS_without_geometry","SQS_without_ap_count","SQS_without_overlap","SQS_without_density","S_signal","S_geometry","S_ap_count","S_overlap","S_density"];
const state={source:null,samples:null,unit:"U09",scan:11,metric:"adaptive_auroc",chosen:"SQS_reconstructed"};
const f=(v,n=3)=>Number.isFinite(Number(v))?Number(v).toFixed(n):"—";
const el=(tag,cl,label)=>{const n=document.createElement(tag);if(cl)n.className=cl;if(label!==undefined)n.textContent=String(label);return n;};
function notify(){window.parent.postMessage({source:"wifi-sqs-ablation",height:Math.ceil(document.documentElement.scrollHeight)},"*")}
function renderScan(){
 const sample=state.samples.units[state.unit].examples[state.scan];
 const values=C.map(([key])=>Number(sample.components[key]));
 if(values.some(x=>!Number.isFinite(x)||x<0||x>1))throw Error("Invalid native SQS component");
 const mean=values.reduce((a,b)=>a+b,0)/5;
 if(Math.abs(mean-sample.sqs)>1e-7)throw Error("Original scan score fails source reconstruction");
 $("native-score").textContent=f(sample.sqs);
 $("recon-status").textContent="Native source · verified";
 $("scan-ref").textContent=sample.row_id+" · original held-out query";
 const root=$("components");root.replaceChildren();
 C.forEach(([key,label],i)=>{
 const card=el("article","component");
 card.append(el("span","n",String(i+1).padStart(2,"0")),el("strong","",label),el("div","pct",f(values[i])));
 const track=el("div","comp-track"),bar=el("span","comp-fill");bar.style.width=(100*values[i]).toFixed(2)+"%";track.append(bar);card.append(track,el("div","weight","20% of full SQS"));root.append(card)
 });
 $("reconstruction").textContent="Reconstructed "+f(mean,6)+" · source "+f(sample.sqs,6)+" · |difference| "+f(Math.abs(mean-sample.sqs),9);
 notify();
}
function setScanOptions(){
 const unit=state.samples.units[state.unit],sel=$("scan");
 sel.replaceChildren();
 unit.examples.forEach((r,i)=>{const o=el("option","",r.row_id+" · SQS "+f(r.sqs));o.value=i;sel.append(o)});
 state.scan=Math.floor(unit.examples.length/2);sel.value=state.scan;sel.disabled=false;
 renderScan();
}
function scale(values){
 const bounds=state.metric==="association"?[-0.15,0.45]:state.metric.endsWith("auprc")?[0,0.65]:[0,1];
 const lo=Math.min(bounds[0],...values.filter(Number.isFinite));const hi=Math.max(bounds[1],...values.filter(Number.isFinite));
 return v=>100*(Math.max(lo,Math.min(hi,v))-lo)/(hi-lo);
}
function renderVariants(){
 const def=defs[state.metric],rows=order.map(id=>state.source.variants.find(x=>x.variant_id===id));
 if(rows.some(x=>!x))throw Error("Missing archive variant");
 const full=rows[0],value=full[def[0]];
 $("metric-info").textContent=def[4]+" · "+full[def[3]]+" evaluation conditions for full SQS";
 const scaleX=scale(rows.flatMap(x=>[x[def[0]],x[def[1]],x[def[2]]]));
 const root=$("variant-list");root.replaceChildren();
 rows.forEach(row=>{
 const id=row.variant_id,button=el("button","variant"+(id==="SQS_reconstructed"?" full":""));
 button.type="button";button.setAttribute("aria-pressed",id===state.chosen?"true":"false");
 button.title=row.label+"; median "+f(row[def[0]])+"; Q25 "+f(row[def[1]])+"; Q75 "+f(row[def[2]])+"; n="+row[def[3]];
 const label=el("span","variant-label",row.label);label.append(el("span","variant-type",row.variant_type));button.append(label);
 const track=el("span","track"),base=el("span","baseline"),band=el("span","band"),tick=el("span","median");
 base.style.left=scaleX(value)+"%";
 band.style.left=scaleX(row[def[1]])+"%";band.style.width=Math.max(.7,scaleX(row[def[2]])-scaleX(row[def[1]]))+"%";
 tick.style.left=scaleX(row[def[0]])+"%";
 track.append(base,band,tick);button.append(track,el("span","number",f(row[def[0]])));
 button.onclick=()=>{state.chosen=id;renderVariants()};root.append(button);
 });
 const selected=rows.find(x=>x.variant_id===state.chosen);
 const delta=selected[def[0]]-full[def[0]],prefix=delta>0?"+":"";
 const detail=$("detail");detail.replaceChildren();
 detail.append(el("h3","",selected.label));
 const p=el("p","",def[4]+" (median across "+selected[def[3]]+" conditions): ");
 p.append(el("span","data",f(selected[def[0]])));detail.append(p);
 const q=el("p","","");
 q.textContent="Interquartile range: "+f(selected[def[1]])+" to "+f(selected[def[2]])+". Difference from the full SQS median: "+prefix+f(delta)+" (metric units).";
 detail.append(q);
 const explanation=selected.variant_type==="Full"?"The full equal-weight SQS includes all five normalized support groups.":selected.variant_type==="Conceptual ablation"?"This archived variant removes one main support group from the score; all reported evaluation values come from the original A1 experiment.":"This archived variant retains one support group on its own; it is not a newly computed score for the selected scan.";
 detail.append(el("p","",explanation));notify();
}
async function init(){
 try{
 const [a,b]=await Promise.all([fetch("sqs_ablation_summary.json"),fetch("sample_scans.json")]);
 if(!a.ok||!b.ok)throw Error("HTTP "+a.status+"/"+b.status);
 state.source=await a.json();state.samples=await b.json();
 if(state.source.schema_version!=="1.0"||state.source.variants.length!==11||state.samples.schema_version!=="1.0"||state.samples.no_calibrated_warning_labels!==true)throw Error("Unrecognized source schema");
 for(const id of ["U01","U02","U03","U09"])if(state.samples.units[id]?.examples.length!==22)throw Error("Missing validated scan examples");
 const unit=$("unit");unit.replaceChildren();
 for(const id of ["U01","U02","U03","U09"]){const opt=el("option","",id+" · "+state.samples.units[id].name);opt.value=id;unit.append(opt)}
 unit.value=state.unit;
 unit.addEventListener("change",()=>{state.unit=unit.value;setScanOptions()});
 $("scan").addEventListener("change",()=>{state.scan=Number($("scan").value);renderScan()});
 $("metric").addEventListener("change",()=>{state.metric=$("metric").value;renderVariants()});
 setScanOptions();renderVariants();
 $("status").textContent="Data: "+state.source.source+"; measured examples: docs/assets/interactive/sample_scans.json. No browser-side fitting or retrospective error reconstruction.";
 window.addEventListener("resize",notify);notify()
 }catch(error){$("status").textContent="Unable to load verified research sources: "+error.message;$("status").setAttribute("role","alert")}
}
init();
