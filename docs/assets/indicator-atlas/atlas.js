/* Interactive formula atlas. All measured values come from the committed public
   native outputs; drawings that require non-exported data are explicitly schematic.
   No science is recomputed, no thresholds or warning labels are inferred here. */
'use strict';
const el=id=>document.getElementById(id);
const ns='http://www.w3.org/2000/svg';
const state={items:[],data:null,composites:null,unit:'U09',scan:11,indicator:'sigma_fps',filter:'',motion:true};
const dataKey={d_cand:'D_cand',i_k:'I_k',sqs:'sqs',c_sigma:'c_sigma',fii:'fii'};
const eqFallback={
 ap_count:'N_AP = number of observed APs',rss_std:'σ_RSS = √[(1/N) Σ (RSS − mean RSS)²]',rss_range:'R_RSS = max(RSS) − min(RSS)',
 min_rss_distance:'d₁ = min ||q − tⱼ||₂ / √D',nearest_match_isolation:'I_near = max(d₂ − d₁, 0) / (d₂ + 10⁻⁶)',
 max_cosine_similarity:'cos(q + 110, t₁ + 110)',ap_overlap:'J_max = max |A_q ∩ Aⱼ| / |A_q ∪ Aⱼ|',
 mean_ap_overlap:'J_mean = mean(|A_q ∩ Aⱼ| / |A_q ∪ Aⱼ|)',ap_set_novelty:'N_APset = 1 − J_max',
 nearest_rp_distance:'d_RP = min ||x̂ − p||₂',local_rp_density:'ρ_RP = number of RPs within radius r of centroid',
 sigma_fps:'σ_FP = √[(1/10) Σ ||pⱼ − p̄||²]',d_cand:'D_cand = max ||pᵢ − pⱼ||₂',
 i_k:'I_k = max ||mean(p₁ … p_k) − p̄||₂',rss_gradient_proxy:'G_RSS = σ_FP / max(d₁₀ − d₁, 10⁻⁶)',
 sqs:'SQS = mean(signal, geometry, AP count, overlap, density)',
 c_sigma:'C_σ = [1 − R(d₁)] / [1 + R(σ_FP)]',
 fii:'FII = mean(signal, AP count, overlap, isolation, inverse novelty)'
};
const current=()=>state.data.units[state.unit].examples[state.scan];
const num=(v,d=3)=>v===undefined||v===null||!Number.isFinite(Number(v))?'not available':Number(v).toFixed(d);
const escaped=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const svg=(markup,label,caption,schematic=false)=>{
  let root=el('diagram');
  if(!root){
    root=document.createElementNS(ns,'svg');root.setAttribute('id','diagram');
    root.setAttribute('viewBox','0 0 720 300');root.setAttribute('role','img');
    root.setAttribute('preserveAspectRatio','xMidYMid meet');
    el('diagram-container').append(root);
  }
  root.innerHTML=`<title>${escaped(label)}</title>${markup}`;
  root.setAttribute('aria-label',label);root.classList.toggle('motion',state.motion);
  el('figure-title').textContent=schematic?'Animated schematic':'Measured-scan visual representation';
  el('figure-caption').textContent=caption+(schematic?' The drawing is schematic; its coordinates are not measured predictions.':' Source coordinates are local 2D metres; no building floor plan is displayed.');
};
const tx=(x,y,s,size=13,color='#537182',anchor='middle')=>`<text x="${x}" y="${y}" text-anchor="${anchor}" fill="${color}" font-size="${size}" font-family="system-ui">${escaped(s)}</text>`;
const circle=(x,y,r,fill='#168c8a',extra='')=>`<circle cx="${x}" cy="${y}" r="${r}" fill="${fill}" ${extra}/>`;
const line=(x1,y1,x2,y2,stroke='#297e86',w=2,extra='')=>`<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${stroke}" stroke-width="${w}" ${extra}/>`;
const panel=(content)=>`<rect x="16" y="12" width="688" height="273" rx="13" fill="#f8fbfc" stroke="#dfebef"/>${content}`;
function pointMapper(sample){
 const p=sample.candidates.map(q=>[Number(q.x),Number(q.y)]),c=sample.diagnostic_centroid;
 let xx=p.map(t=>t[0]), yy=p.map(t=>t[1]);xx.push(c[0]);yy.push(c[1]);
 let minX=Math.min(...xx),maxX=Math.max(...xx),minY=Math.min(...yy),maxY=Math.max(...yy);
 const sx=(maxX-minX)||1,sy=(maxY-minY)||1;
 const scale=Math.min(500/(sx*1.25),208/(sy*1.25));
 const x0=360-(minX+maxX)/2*scale,y0=145+(minY+maxY)/2*scale;
 return {p,c,scale,map:v=>[x0+v[0]*scale,y0-v[1]*scale]};
}
function geometryDiagram(item,s){
 const m=pointMapper(s),cp=m.map(m.c);let marks='';
 for(let i=0;i<m.p.length;i++){const p=m.map(m.p[i]);marks+=circle(p[0],p[1],i===0?8:6,i===0?'#035a6b':'#159697',`class="pulse" style="animation-delay:${(i*.22).toFixed(2)}s"`);if(i<3)marks+=tx(p[0]+12,p[1]-8,i+1,11);}
 marks+=`<rect x="${cp[0]-6}" y="${cp[1]-6}" width="12" height="12" transform="rotate(45 ${cp[0]} ${cp[1]})" fill="white" stroke="#123b59" stroke-width="3"/>`;
 const k=item.id;
 if(k==='sigma_fps'){for(const pt of m.p){const q=m.map(pt);marks+=line(q[0],q[1],cp[0],cp[1],'#6c9fb0',1.7,'stroke-dasharray="4 4" class="walk"')}marks+=tx(360,269,'Mean squared distance to the candidate centroid',12)}
 if(k==='d_cand'){let far=-1,a=0,b=0;for(let i=0;i<m.p.length;i++)for(let j=i+1;j<m.p.length;j++){let d=Math.hypot(m.p[i][0]-m.p[j][0],m.p[i][1]-m.p[j][1]);if(d>far){far=d;a=i;b=j}}const p=m.map(m.p[a]),q=m.map(m.p[b]);marks+=line(...p,...q,'#dc8a46',4,'class="draw"');marks+=tx(360,269,`Maximum pairwise distance: ${num(far,1)} m`,12)}
 if(k==='i_k'){let cumul=[],sx=0,sy=0;for(let i=0;i<m.p.length;i++){sx+=m.p[i][0];sy+=m.p[i][1];cumul.push(m.map([sx/(i+1),sy/(i+1)]))}let points=cumul.map(v=>v.join(',')).join(' ');marks+=`<polyline points="${points}" stroke="#d98646" stroke-width="3.5" fill="none" class="draw"/>`;cumul.forEach((p,i)=>{if(i===0||i===9)marks+=circle(...p,5,'#cb7531')});marks+=tx(360,269,'Path of cumulative centroids from rank 1 to rank 10',12)}
 if(k==='rss_gradient_proxy') {marks+=line(cp[0]-55,cp[1]+25,cp[0]+55,cp[1]+25,'#dc8a46',4,'class="draw"');marks+=tx(360,269,'Large spatial extent relative to RSS-distance separation',12)}
 const label=(k==='d_cand'?'Farthest candidate pair':k==='i_k'?'Rank-dependent cumulative centroids':k==='rss_gradient_proxy'?'Spatial–signal ambiguity':'Candidate spread around centroid');
 svg(panel(marks),label,`This plot uses the ten retrieved reference coordinates for ${s.row_id}. The value is calculated by the original Python pipeline.`);
}
function signalDiagram(item,s){
 const readings=s.strongest_ap.slice(0,10);let chart='';
 if(readings.length===0) chart+=tx(360,137,'No retained RSS observations in this selected query',15,'#bd6a42');
 else readings.forEach(([ap,rss],i)=>{const v=Math.max(2,((rss+110)/75)*435),y=42+i*20;chart+=tx(105,y+11,ap,11,'#416477','end')+`<rect x="123" y="${y}" width="450" height="13" rx="4" fill="#e9f0f3"/><rect x="123" y="${y}" width="${v}" height="13" rx="4" fill="${i%2?'#50a9b9':'#188985'}" class="fill"/>`+tx(580,y+11,`${rss} dBm`,11,'#416477','start')});
 chart+=tx(360,265,'Stronger received power appears farther to the right',12);
 svg(panel(chart),`Received signal strengths for ${s.row_id}`,'Bars show up to ten strongest observed APs. RSS standard deviation and range are calculated from ALL retained query RSS values, not just these bars.');
}
function matchDiagram(item,s){
 const dist=s.candidates.map(q=>Number(q.rss_distance));const mx=Math.max(...dist,0.1)*1.1;
 let bar=dist.map((d,i)=>{let x=64+i*61,w=d/mx*170;return `<rect x="${x}" y="${235-w}" width="35" height="${w}" rx="5" fill="${i===0?'#158980':'#92bfce'}" class="fill"/>`+tx(x+17,254,i+1,11)}).join('');
 bar+=tx(360,276,'Reference template rank (1 = nearest in RSS space)',11)+tx(360,29,'Normalized RSS-template distances for the 10 retrieved candidates',13);
 if(item.id==='nearest_match_isolation'){bar+=line(81,235-dist[0]/mx*170,142,235-dist[1]/mx*170,'#d98b4a',3,'class="draw"');}
 svg(panel(bar),`RSS-template distances of ten reference matches for ${s.row_id}`,'Bars show stored RSS-space distances; smaller values correspond to closer RSS matches. Cosine similarity requires original full template vectors, which this browser export does not contain.');
}
function overlapDiagram(item,s){
 const observed=s.ap_observations;const v=item.id==='ap_set_novelty'?s.indicators.ap_set_novelty:item.id==='mean_ap_overlap'?s.indicators.mean_ap_overlap:s.indicators.ap_overlap;
 let parts=`<circle cx="296" cy="136" r="94" fill="#188b98" fill-opacity=".23" stroke="#188b98" stroke-width="3"/><circle cx="422" cy="136" r="94" fill="#d09b59" fill-opacity=".22" stroke="#c48d49" stroke-width="3"/>`;
 parts+=tx(251,137,'Query APs',15,'#164e68')+tx(467,137,'Template APs',15,'#755532')+tx(358,116,'Intersection',13,'#37666c');
 parts+=`<circle cx="358" cy="136" r="28" fill="#b9d7c0" opacity=".46" class="pulse"/>`;
 parts+=tx(360,269,`Measured AP count: ${observed} · reported indicator: ${num(v)}`,12);
 svg(panel(parts),'Query and template AP-set Jaccard overlap',`Venn sets illustrate the definition only. The numeric ${item.label.toLowerCase()} shown above is an original measured value; the circles do not depict the actual AP memberships.`,true);
}
function densityDiagram(item,s){const m=pointMapper(s),o=m.map(m.c);let pts=m.p.map((p,i)=>{const q=m.map(p);return circle(...q,6,'#159594',`class="pulse" style="animation-delay:${i*.2}s"`)}).join('');
 pts+=`<circle cx="${o[0]}" cy="${o[1]}" r="90" fill="#a3e0d4" fill-opacity=".18" stroke="#ca8947" stroke-width="3" stroke-dasharray="7 5" class="pulse"/>`+circle(...o,6,'#123d62')+tx(360,269,'Radius determined from spacing of distinct reference points',12);
 svg(panel(pts),'Adaptive neighborhood around the candidate centroid','The centre uses the measured candidate centroid. The displayed radius is schematic: the full reference map and true adaptive radius are not exported to the browser. Density counts distinct training coordinates, not ten candidates.',true);
}
function estimatorDiagram(item,s){let v=`<circle cx="240" cy="128" r="7" fill="#197f86"/>`+tx(238,105,'Predicted point',13);
 v+=`<circle cx="430" cy="136" r="6" fill="#d0924a"/>`+tx(435,112,'Closest radio-map RP',13);
 for(const [x,y] of [[525,58],[335,65],[520,204],[380,219],[190,223]])v+=circle(x,y,6,'#9bbbc7');
 v+=line(240,128,430,136,'#d08946',3,'class="draw"')+tx(360,269,'Requires estimator output; not available in these scan-only examples',12);
 svg(panel(v),'Nearest reference point to an estimator prediction','Estimator-specific distance requires predicted XY coordinates. The geometry is schematic and no prediction is fabricated.',true);
}
function compositeDiagram(item,s){
 const record=state.composites?.units?.[state.unit]?.[s.row_id];
 const base=s.components;
 let bars,fig;
 if(item.id==='c_sigma'&&record){
   bars=[['Signal-match support',record.signal],['Normalized spatial spread (penalty)',record.spread_risk]];
   fig='Cσ = signal-match support / (1 + normalized spatial spread)';
 }else if(item.id==='fii'&&record){
   bars=[['Signal-match support',record.signal],['AP-count support',record.ap_count],['Maximum AP-overlap support',record.ap_overlap],['Nearest-match isolation support',record.isolation],['Inverse AP-set novelty support',record.inverse_novelty]];
   fig='FII = arithmetic mean of the five displayed source-derived terms';
 }else{
   bars=[['Signal-match support',base.signal_match],['Candidate-geometry support',base.candidate_geometry],['AP-count support',base.ap_count],['Maximum AP-overlap support',base.ap_overlap],['Local RP-density support',base.local_density]];
   fig='SQS = arithmetic mean of the five displayed source-derived terms';
 }
 const h=bars.length<=2?72:41,top=bars.length<=2?80:41;
 let markup=bars.map(([name,v],i)=>{
   const y=top+i*h,width=v==null?0:Math.max(0,Number(v))*315;
   return tx(211,y+15,name,11,'#36566a','end')+
     `<rect x="230" y="${y}" width="315" height="19" rx="6" fill="#e7eff1"/>`+
     `<rect x="230" y="${y}" width="${width}" height="19" rx="6" fill="${i===0?'#0e6687':'#008f82'}" class="fill"/>`+
     tx(553,y+15,v==null?'n/a':num(v),11,'#285365','start');
 }).join('');
 markup+=tx(360,270,fig,12);
 svg(panel(markup),`Source-derived ${item.label} components for ${s.row_id}`,'The bars are the exact component terms of the selected composite, using original complete-unit percentile normalization. The displayed result equals its native archived value.');
}

function draw(item,s){if(item.kind==='rss')signalDiagram(item,s);else if(item.kind==='match')matchDiagram(item,s);else if(item.kind==='overlap')overlapDiagram(item,s);else if(item.kind==='geometry'||item.kind==='gradient')geometryDiagram(item,s);else if(item.kind==='density')densityDiagram(item,s);else if(item.kind==='estimator')estimatorDiagram(item,s);else compositeDiagram(item,s)}
function displayValue(item,s){
 const key=dataKey[item.id]||item.id;
 let val;
 if(['sqs','c_sigma','fii'].includes(item.id)){val=s[item.id==='sqs'?'sqs':item.id];}
 else val=s.indicators?.[key];
 let descr=val==null?'not in scan-only output':item.unit;
 return {label:val==null?'n/a':num(val,3),descr};
}
function listIndicators(){const root=el('indicator-list');root.replaceChildren();let count=0,prev='';
 for(const i of state.items){if(state.filter&&!`${i.label} ${i.id} ${i.group}`.toLowerCase().includes(state.filter))continue;
 if(i.group!==prev){const d=document.createElement('div');d.className='group-header';d.textContent=i.group;root.append(d);prev=i.group;}
 const b=document.createElement('button');b.type='button';b.setAttribute('aria-current',String(i.id===state.indicator));b.textContent=i.label;
 b.addEventListener('click',()=>{state.indicator=i.id;listIndicators();render()});root.append(b);count++;
 }el('found-count').textContent=String(count);
}
function render(){const i=state.items.find(x=>x.id===state.indicator);if(!i)return;const s=current();
 el('indicator-name').textContent=i.label;el('group-name').textContent=i.group;el('symbol').textContent=i.id==='nearest_rp_distance'?'prediction-specific':'configuration ID: '+i.id;
 el('definition').textContent=i.definition;el('interpretation').textContent=i.details;
 const val=displayValue(i,s);el('observed-value').textContent=val.label;el('observed-description').textContent=val.descr;
 el('source-note').textContent=(i.id==='nearest_rp_distance'? 'Computed after an estimator produces XY predictions. Other examples originate from stored native scan results.':`Stored indicator for row ${s.row_id}. Values are calculated by the native Python pipeline using full-unit scaling where applicable.`);
 const eq=el('equation');eq.textContent='\\('+i.eq+'\\)';
 if(window.MathJax?.typesetPromise)window.MathJax.typesetPromise([eq]).catch(()=>eq.textContent=eqFallback[i.id]);
 else{eq.textContent=eqFallback[i.id];window.setTimeout(()=>{if(window.MathJax?.typesetPromise){eq.textContent='\\('+i.eq+'\\)';window.MathJax.typesetPromise([eq]).catch(()=>{});}},1000);}
 el('direction').textContent=`Prespecified adverse direction: ${i.adverse}`;
 el('identity').textContent=`${state.unit} · ${s.row_id}`;
 draw(i,s);
}
function changeUnit(){const sel=el('scan'),meta=state.data.units[state.unit];sel.replaceChildren();meta.examples.forEach((s,k)=>{const o=document.createElement('option');o.value=String(k);o.textContent=`${s.row_id} · SQS ${num(s.sqs)}`;sel.append(o)});state.scan=11;sel.value=String(state.scan);render()}
async function init(){try{
 const [ir,sr,cr]=await Promise.all([fetch('indicators.json'),fetch('../interactive/sample_scans.json'),fetch('composites.json')]);
 if(!ir.ok||!sr.ok||!cr.ok)throw Error('Failed to load the published indicator inventory or measured scans');
 state.items=await ir.json();state.data=await sr.json();state.composites=await cr.json();
 if(state.items.length!==18||Object.keys(state.data.units).length!==4||state.composites.schema_version!=='1.0')throw Error('Unexpected indicator or measured-data schema');
 const sel=el('unit');for(const [uid,m] of Object.entries(state.data.units)){const o=document.createElement('option');o.value=uid;o.textContent=`${uid} · ${m.name}`;sel.append(o)}
 sel.value=state.unit;sel.addEventListener('change',e=>{state.unit=e.target.value;changeUnit()});
 el('scan').addEventListener('change',e=>{state.scan=Number(e.target.value);render()});
 el('search').addEventListener('input',e=>{state.filter=e.target.value.trim().toLowerCase();listIndicators()});
 el('motion').addEventListener('click',()=>{state.motion=!state.motion;el('diagram').classList.toggle('motion',state.motion);el('motion').setAttribute('aria-pressed',String(state.motion));el('motion').textContent=state.motion?'Pause animation':'Play animation'});
 listIndicators();changeUnit();
}catch(err){el('error').hidden=false;el('error').textContent=`Indicator atlas could not load: ${err.message}`;console.error(err)}}
init();

function notifyHeight(){if(window.parent===window)return;requestAnimationFrame(()=>window.parent.postMessage({source:'wifi-indicator-atlas',height:Math.max(document.body.scrollHeight,document.documentElement.scrollHeight)},window.location.origin));}
window.addEventListener('resize',notifyHeight);
if(typeof ResizeObserver!=='undefined')new ResizeObserver(notifyHeight).observe(document.body);
