"use strict";
const fmt=(v,d=2)=>(v!==null && v!==undefined && Number.isFinite(Number(v)))?Number(v).toFixed(d):"—";
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
fetch('data/metrics.json').then(r=>{if(!r.ok)throw Error('Synthetic demonstration summary missing');return r.json()}).then(data=>{
 const summary=data.summary, es=data.estimators, ind=data.indicators;
 const tiles=[['Study units',summary.unit_count],['Unique queries',summary.scan_count],['Estimator predictions',summary.prediction_count],['Retained indicators',summary.indicator_count]];
 document.getElementById('kpis').innerHTML=tiles.map(([k,v])=>`<article class="kpi"><strong>${Number(v).toLocaleString()}</strong><span>${esc(k)}</span></article>`).join('');
 const methods=[...new Set(es.map(x=>x.estimator))].sort(), units=[...new Set(es.map(x=>x.unit_id))].sort();
 const methodSel=document.getElementById('estimator'),unitSel=document.getElementById('unit');
 methodSel.innerHTML=methods.map(x=>`<option>${esc(x)}</option>`).join('');unitSel.innerHTML=`<option value="all">All units</option>`+units.map(x=>`<option>${esc(x)}</option>`).join('');
 function render(){const method=methodSel.value,unit=unitSel.value, selection=es.filter(x=>(unit==='all'||x.unit_id===unit)&&(method==='all'||x.estimator===method));
 document.getElementById('estimatorRows').innerHTML=selection.map(x=>`<tr><td>${esc(x.unit_id)}</td><td>${esc(x.estimator)}</td><td>${x.n_scans}</td><td>${fmt(x.mean_error_m)}</td><td>${fmt(x.median_error_m)}</td><td>${fmt(x.p95_error_m)}</td><td>${x.gross_error_n}</td></tr>`).join('');
 const graph=methods.map(name=>{const matches=es.filter(x=>x.estimator===name&&(unit==='all'||x.unit_id===unit));return {name,median:matches.reduce((s,x)=>s+x.median_error_m,0)/Math.max(1,matches.length)}});
 const max=Math.max(...graph.map(x=>x.median),1);document.getElementById('methodPlot').innerHTML=graph.map(x=>`<div class="bar-row"><div class="bar-label">${esc(x.name)}</div><div class="track"><div class="fill" style="width:${100*x.median/max}%"></div></div><div class="bar-val">${fmt(x.median)} m</div></div>`).join('');
 const relevant=ind.filter(x=>(unit==='all'||x.unit_id===unit)&&(method==='all'||x.estimator===method));
 const groups={};relevant.forEach(r=>{if(!groups[r.indicator])groups[r.indicator]=[];if(Number.isFinite(r.spearman_rho))groups[r.indicator].push(r.spearman_rho)});
 const cards=Object.entries(groups).map(([label,vals])=>({label,rho:vals.length?vals.reduce((s,n)=>s+n,0)/vals.length:NaN})).sort((a,b)=>Math.abs(b.rho)-Math.abs(a.rho));
 document.getElementById('indicators').innerHTML=(cards.length?cards.map(x=>`<div class="indicator"><strong>${esc(x.label)}</strong><span>Mean ρ = ${fmt(x.rho,3)}</span><div class="meter"><i style="width:${Number.isFinite(x.rho)?Math.round(Math.min(Math.abs(x.rho),1)*100):0}%"></i></div></div>`).join(''):'<p>Indicators are not evaluated in this entirely synthetic demonstration.</p>');
 }
 methodSel.insertAdjacentHTML('afterbegin','<option value="all">All estimators</option>'); methodSel.value='all';methodSel.addEventListener('change',render);unitSel.addEventListener('change',render);render();
}).catch(err=>{document.getElementById('kpis').textContent='Run python scripts/reproduce_release.py --mode demo and serve this dashboard with python -m http.server. '+err.message});
