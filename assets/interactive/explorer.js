/* Interactive, read-only visualization of archived public empirical outputs.
   Data originate from the existing Python indicator pipeline, not this browser.
   No network request leaves the current documentation site. */
'use strict';

const byId = id => document.getElementById(id);
const state = {data:null,unit:'U09',sample:0,step:0,hover:null,truth:false,points:[],hitboxes:[]};
const components = [
  ['signal_match','Signal-match support','Closer fingerprint RSS matches generally support the scan.'],
  ['candidate_geometry','Candidate-geometry support','Candidate reference locations that cluster more tightly provide more coherent evidence.'],
  ['ap_count','AP-count support','How much measured access-point evidence is available in this query.'],
  ['ap_overlap','AP-overlap support','Compatibility between observed access-point sets and the reference radio map.'],
  ['local_density','Reference-point density','Support from nearby reference points in the source radio map.']
];
const stages = [
  ['The phone observes nearby access points','A scan records which anonymous AP labels are visible and their measured RSS values. These are the actual strongest observations for the selected public test scan.','signal-panel'],
  ['The scan is matched to reference fingerprints','The existing Wi-Fi integrity source compares the scan with stored training fingerprints. We show its ten retrieved candidates, ordered by RSS-match distance.','geometry-panel'],
  ['The candidate positions can agree or disagree','Nearby candidate coordinates can cluster or spread across the local coordinate system. These points are radio-map references, not an architectural floor plan or a model prediction.','geometry-panel'],
  ['Five support components summarize the evidence','The existing Python source scales each component using all test scans in the unit and takes an equal-weight average. All five component values shown here reproduce the stored SQS.','sqs-panel'],
  ['Interpret the score without claiming certainty','This output supports inspection and comparison. SQS is not a probability or a calibrated warning; positioning error needs estimator predictions and held-out truth.','interpretation']
];
const fmt = (v,d=2) => v == null || !Number.isFinite(Number(v)) ? 'n/a' : Number(v).toFixed(d);
const currentUnit = () => state.data.units[state.unit];
const current = () => currentUnit().examples[state.sample];
const text = (id,val) => {byId(id).textContent=String(val);};
const create = (tag,cl,content) => {const e=document.createElement(tag);if(cl)e.className=cl;if(content!==undefined)e.textContent=String(content);return e;};
const linePercent = v => `${Math.min(100,Math.max(0,Number(v)*100)).toFixed(2)}%`;
function changeStep(i){
  state.step=Math.max(0,Math.min(4,i));
  document.querySelectorAll('[data-step]').forEach(el=>{const yes=Number(el.dataset.step)===state.step;el.classList.toggle('active',yes);el.setAttribute('aria-current',yes?'step':'false');});
  const step=stages[state.step];text('step-kicker',`STAGE 0${state.step+1} / 05`);text('step-title',step[0]);text('step-description',step[1]);
  document.querySelectorAll('.spotlight').forEach(e=>e.classList.remove('spotlight'));
  const el=byId(step[2]);if(el)el.classList.add('spotlight');
  byId('previous-step').disabled=state.step===0;byId('next-step').disabled=state.step===4;
}
function renderSignals(s){
  const root=byId('ap-bars');root.replaceChildren();
  for(const [ap,rss] of s.strongest_ap){
    const row=create('div','ap-item');row.setAttribute('role','listitem');
    const label=create('span','ap-label',ap),track=create('div','ap-track');
    const bar=create('span','ap-fill');bar.style.width=`${Math.min(100,Math.max(1,(rss+105)/65*100))}%`;
    track.append(bar);const reading=create('span','ap-reading',`${fmt(rss,0)} dBm`);
    row.append(label,track,reading);row.title=`${ap}: ${fmt(rss,1)} dBm`;
    root.append(row);
  }
  text('ap-summary',`Strongest ${s.strongest_ap.length} of ${s.ap_observations} APs`);
}
function renderComponents(s){
  const root=byId('components');root.replaceChildren();
  let sum=0;
  for(const [key,label,desc] of components){
    const value=s.components[key];
    if(!Number.isFinite(value)||value<0||value>1)throw Error('Invalid measured SQS component');
    sum+=value;
    const row=create('div','component-item');row.setAttribute('role','listitem');row.title=desc;
    const name=create('span','component-label',label);const track=create('div','component-track');
    const bar=create('span','component-fill');bar.style.width=linePercent(value);track.append(bar);
    const score=create('span','component-value',fmt(value,3));row.append(name,track,score);root.append(row);
  }
  const mean=sum/5;if(Math.abs(mean-s.sqs)>1e-8)throw Error('Displayed components do not reconstruct stored SQS');
  text('formula-text',`(${components.map(([key])=>fmt(s.components[key],3)).join(' + ')}) ÷ 5`);
  text('sqs-total',fmt(s.sqs,3));text('sqs-explanation',`Original source-derived average: ${fmt(mean,4)}. This is a relative measure of support, not a confidence percentage.`);
}
function renderHistogram(u,s){
  const root=byId('histogram');root.replaceChildren();const bins=u.sqs_histogram_20_bins;
  if(bins.length!==20||bins.reduce((a,b)=>a+b,0)!==u.total_query_scans)throw Error('Invalid full-unit score distribution');
  const max=Math.max(...bins,1);
  bins.forEach((count,i)=>{const bar=create('div','hist-bin');bar.style.setProperty('--bar-height',`${Math.max(2,100*count/max)}%`);bar.setAttribute('data-count',count);bar.title=`SQS ${fmt(i/20,2)}–${fmt((i+1)/20,2)}: ${count} held-out scans`;if(i===Math.min(19,Math.floor(s.sqs*20)))bar.classList.add('selected');root.append(bar);});
  const needle=create('div','hist-needle');needle.style.setProperty('--needle',linePercent(s.sqs));root.append(needle);
  text('distribution-summary',`${u.total_query_scans.toLocaleString()} scans · unit mean ${fmt(u.mean_sqs,3)}`);
}
function canvasSetup(canvas){
  const cssWidth=Math.max(240,canvas.getBoundingClientRect().width || 600);
  const pxRatio=Math.min(2,window.devicePixelRatio||1);const height=cssWidth*410/680;
  canvas.width=Math.round(cssWidth*pxRatio);canvas.height=Math.round(height*pxRatio);
  const ctx=canvas.getContext('2d');if(!ctx)return null;ctx.setTransform(pxRatio,0,0,pxRatio,0,0);return {ctx,width:cssWidth,height};
}
function renderGeometry(s){
  const c=byId('candidate-plot'),v=canvasSetup(c);if(!v)return;
  const {ctx,width,height}=v;const margin={l:47,r:25,t:22,b:44};
  const all=s.candidates.map(p=>[p.x,p.y]);all.push(s.diagnostic_centroid);if(state.truth)all.push(s.reference);
  const minX=Math.min(...all.map(p=>p[0])),maxX=Math.max(...all.map(p=>p[0]));
  const minY=Math.min(...all.map(p=>p[1])),maxY=Math.max(...all.map(p=>p[1]));
  const dX=Math.max(8,maxX-minX),dY=Math.max(8,maxY-minY),padX=dX*.13,padY=dY*.13;
  const bounds=[(minX+maxX)/2-dX/2-padX,(minX+maxX)/2+dX/2+padX,(minY+maxY)/2-dY/2-padY,(minY+maxY)/2+dY/2+padY];
  const toX=x=>margin.l+(x-bounds[0])/(bounds[1]-bounds[0])*(width-margin.l-margin.r);
  const toY=y=>height-margin.b-(y-bounds[2])/(bounds[3]-bounds[2])*(height-margin.t-margin.b);
  ctx.clearRect(0,0,width,height);ctx.font='11px system-ui, sans-serif';ctx.textBaseline='middle';
  ctx.strokeStyle='#e7eef1';ctx.lineWidth=1;
  for(let i=0;i<=4;i++){
    const x=margin.l+i/4*(width-margin.l-margin.r),y=margin.t+i/4*(height-margin.t-margin.b);
    ctx.beginPath();ctx.moveTo(x,margin.t);ctx.lineTo(x,height-margin.b);ctx.stroke();
    ctx.beginPath();ctx.moveTo(margin.l,y);ctx.lineTo(width-margin.r,y);ctx.stroke();
    ctx.fillStyle='#7991a1';ctx.textAlign='center';ctx.fillText(fmt(bounds[0]+i/4*(bounds[1]-bounds[0]),0),x,height-margin.b+16);
    ctx.textAlign='right';ctx.fillText(fmt(bounds[3]-i/4*(bounds[3]-bounds[2]),0),margin.l-9,y);
  }
  ctx.fillStyle='#546f7f';ctx.textAlign='center';ctx.fillText('Local X (metres)',width/2,height-8);ctx.save();ctx.translate(13,height/2);ctx.rotate(-Math.PI/2);ctx.fillText('Local Y (metres)',0,0);ctx.restore();
  state.hitboxes=[];
  s.candidates.forEach((p,i)=>{
    const x=toX(p.x),y=toY(p.y),radius=i===0?8:6;
    ctx.beginPath();ctx.arc(x,y,radius,0,Math.PI*2);ctx.fillStyle=i===0?'#006f74':'#35a2aa';ctx.fill();ctx.strokeStyle='#fff';ctx.lineWidth=2;ctx.stroke();
    if(i<3){ctx.font='bold 11px system-ui';ctx.fillStyle='#1c5672';ctx.textAlign='center';ctx.fillText(String(i+1),x,y-14)}
    state.hitboxes.push({x,y,radius:Math.max(radius,13),data:p});
  });
  const cen=[toX(s.diagnostic_centroid[0]),toY(s.diagnostic_centroid[1])];
  ctx.save();ctx.translate(...cen);ctx.rotate(Math.PI/4);ctx.fillStyle='#fff';ctx.strokeStyle='#18456e';ctx.lineWidth=3;ctx.fillRect(-7,-7,14,14);ctx.strokeRect(-7,-7,14,14);ctx.restore();
  if(state.truth){const x=toX(s.reference[0]),y=toY(s.reference[1]);ctx.save();ctx.translate(x,y);ctx.rotate(Math.PI/4);ctx.fillStyle='#ce8733';ctx.fillRect(-6,-6,12,12);ctx.restore()}
  const byFloor={};s.candidates.forEach(p=>{byFloor[p.floor]=(byFloor[p.floor]||0)+1;});
  text('floor-overview',`Candidate floor categories: ${Object.entries(byFloor).map(([floor,n])=>`${floor} (${n})`).join(', ')}. Floor labels are metadata, not plotted geometry.`);
  byId('truth-legend').hidden=!state.truth;
}
function showHover(event){
  const rect=event.currentTarget.getBoundingClientRect(),x=event.clientX-rect.left,y=event.clientY-rect.top;
  const point=state.hitboxes.find(p=>Math.hypot(p.x-x,p.y-y)<p.radius);
  const tooltip=byId('candidate-hover');if(!point){tooltip.hidden=true;return;}
  const p=point.data;tooltip.hidden=false;
  tooltip.textContent=`Rank ${p.rank} · floor ${p.floor} · (${fmt(p.x,1)}, ${fmt(p.y,1)}) m · RSS distance ${fmt(p.rss_distance,2)}`;
  tooltip.style.left=`${Math.min(x,rect.width-145)}px`;tooltip.style.top=`${Math.max(22,y)}px`;
}
function renderCompare(unit){
  const out=byId('comparison');out.replaceChildren();
  const examples=unit.examples;
  for(const [s,kind] of [[examples[0],'LOW SQS SAMPLE'],[examples[examples.length-1],'HIGH SQS SAMPLE']]){
    const card=create('article','compare-card');const top=create('header');top.append(create('span','role',kind),create('span','id',s.row_id));card.append(top);
    card.append(create('div','sqs',fmt(s.sqs,3)));
    card.append(create('div','short',`${s.ap_observations} observed APs · ${fmt(s.indicators.sigma_fps,1)} m candidate spread`));
    const bars=create('div','mini-components');
    for(const [key,name] of components){const row=create('div','mini-row');row.append(create('span','',name.replace(' support','')));const track=create('span','mini-bar'),fill=create('i');fill.style.width=linePercent(s.components[key]);track.append(fill);row.append(track,create('em','',fmt(s.components[key],2)));bars.append(row)}
    card.append(bars);out.append(card);
  }
}
function populateScans(){
  const unit=currentUnit(),sel=byId('scan');sel.replaceChildren();
  unit.examples.forEach((s,i)=>{const option=create('option','',`${i+1} / ${unit.examples.length} · ${s.row_id} · SQS ${fmt(s.sqs,3)}`);option.value=String(i);sel.append(option);});
  sel.disabled=false;
  text('unit-count',unit.total_query_scans.toLocaleString());text('unit-subtitle',`${unit.training_fingerprints.toLocaleString()} reference fingerprints`);
  renderCompare(unit);
}
function render(){
  if(!state.data)return;
  const s=current(),unit=currentUnit();
  byId('unit').value=state.unit;byId('scan').value=String(state.sample);
  text('m-ap',s.ap_observations);text('m-rss',fmt(s.indicators.min_rss_distance,2));text('m-spread',`${fmt(s.indicators.sigma_fps,1)} m`);text('m-sqs',fmt(s.sqs,3));
  text('sqs-identity',`${s.row_id} · measured`);
  renderSignals(s);renderComponents(s);renderGeometry(s);renderHistogram(unit,s);
}
async function init(){
  try{
    const embedded = window.__MEASURED_EXPLORER_DATA || null;
    const response = embedded ? null : await fetch('sample_scans.json',{cache:'no-store'});
    if(response && !response.ok)throw Error(`HTTP ${response.status}`);
    const data = embedded || await response.json();
    if(data.schema_version!=='1.0'||data.no_calibrated_warning_labels!==true)throw Error('Unknown source data schema');
    for(const unit of ['U01','U02','U03','U09'])if(!data.units[unit]||data.units[unit].examples.length!==22)throw Error(`Missing published ${unit} examples`);
    state.data=data;
    const sel=byId('unit');sel.replaceChildren();
    for(const id of Object.keys(data.units)){const opt=create('option','',`${id} · ${data.units[id].name}`);opt.value=id;sel.append(opt)}
    state.unit='U09';state.sample=Math.floor(currentUnit().examples.length/2);
    populateScans();render();changeStep(0);
    sel.addEventListener('change',event=>{state.unit=event.target.value;state.sample=Math.floor(currentUnit().examples.length/2);populateScans();render()});
    byId('scan').addEventListener('change',event=>{state.sample=Number(event.target.value);render()});
    byId('choose-low').addEventListener('click',()=>{state.sample=0;render()});
    byId('choose-middle').addEventListener('click',()=>{state.sample=Math.floor(currentUnit().examples.length/2);render()});
    byId('choose-high').addEventListener('click',()=>{state.sample=currentUnit().examples.length-1;render()});
    document.querySelectorAll('[data-step]').forEach(button=>button.addEventListener('click',()=>changeStep(Number(button.dataset.step))));
    byId('previous-step').addEventListener('click',()=>changeStep(state.step-1));
    byId('next-step').addEventListener('click',()=>changeStep(state.step+1));
    byId('show-truth').addEventListener('change',event=>{state.truth=event.target.checked;renderGeometry(current())});
    byId('candidate-plot').addEventListener('mousemove',showHover);
    byId('candidate-plot').addEventListener('mouseleave',()=>{byId('candidate-hover').hidden=true});
    let sizeTimer;window.addEventListener('resize',()=>{clearTimeout(sizeTimer);sizeTimer=setTimeout(()=>renderGeometry(current()),120)});
  }catch(error){byId('error').hidden=false;byId('error').textContent=`The data explorer could not load measured examples: ${error.message}. Please open it through the documentation server.`;console.error(error)}
}
function notifyParentHeight() {
  if (window.parent !== window) {
    window.parent.postMessage({
      source:'wifi-integrity-explorer',
      height:Math.max(document.body.scrollHeight,document.documentElement.scrollHeight)
    }, window.location.origin);
  }
}
window.addEventListener('load',notifyParentHeight);
if (typeof ResizeObserver !== 'undefined') {
  new ResizeObserver(notifyParentHeight).observe(document.body);
}
init();
