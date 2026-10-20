(() => {
  const data = window.DASHBOARD_DATA;
  if (!data) {
    document.body.innerHTML = '<main style="padding:2rem"><h1>Dashboard data missing</h1><p>Run <code>wifi-integrity build-ui</code>.</p></main>';
    return;
  }
  const fmt = new Intl.NumberFormat('en-US');
  const f3 = value => value == null || Number.isNaN(Number(value)) ? '—' : Number(value).toFixed(3);
  const f2 = value => value == null || Number.isNaN(Number(value)) ? '—' : Number(value).toFixed(2);
  const esc = value => String(value ?? '—').replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
  const statusClass = value => ['passed','completed'].includes(value) ? 'passed' : ['failed','blocked'].includes(value) ? 'failed' : 'review';

  document.getElementById('versionBadge').textContent = `v${data.meta.version}`;
  document.getElementById('releaseBadge').textContent = data.meta.release_status;
  document.getElementById('resultMode').textContent = data.meta.result_mode.replaceAll('_', ' ');

  const kpis = [
    ['Evaluation units', data.counts.units],
    ['Training scans', fmt.format(data.counts.training_scans)],
    ['Held-out queries', fmt.format(data.counts.test_scans)],
    ['Estimators', data.counts.estimators],
    ['Predictions', fmt.format(data.counts.predictions)],
    ['Indicators', data.counts.indicators],
    ['Case-atlas records', data.counts.cases],
  ];
  document.getElementById('kpiGrid').innerHTML = kpis.map(([label, value]) => `<article class="kpi"><div class="kpi-value">${value}</div><div class="kpi-label">${esc(label)}</div></article>`).join('');

  document.getElementById('pipelineGrid').innerHTML = data.pipeline.map((step, index) => `<article class="pipeline-step" data-step="${index + 1}"><div class="status status-${esc(step.status)}">${esc(step.status)}</div><h3>${esc(step.name)}</h3><p>${esc(step.description)}</p></article>`).join('');

  const datasetBody = document.querySelector('#datasetTable tbody');
  const renderDatasets = query => {
    const q = query.trim().toLowerCase();
    datasetBody.innerHTML = data.units.filter(row => !q || Object.values(row).join(' ').toLowerCase().includes(q)).map(row => `<tr><td><strong>${esc(row.unit_label)}</strong></td><td>${esc(row.dataset)}</td><td>${esc(row.group)}</td><td>${fmt.format(row.n_train)}</td><td>${fmt.format(row.n_test)}</td><td>${fmt.format(row.train_ap_vocabulary)}</td><td>${fmt.format(row.diagnostic_ap_vocabulary)}</td><td>${row.floor_labels ? 'Yes' : 'No'}</td></tr>`).join('');
  };
  renderDatasets('');
  document.getElementById('datasetSearch').addEventListener('input', event => renderDatasets(event.target.value));

  const registry = Object.fromEntries(data.estimator_registry.map(row => [row.estimator_id, row]));
  const metricSelect = document.getElementById('metricSelect');
  const estimatorTableBody = document.querySelector('#estimatorTable tbody');
  const renderEstimators = () => {
    const metric = metricSelect.value;
    const rows = [...data.estimators].sort((a,b) => a[metric] - b[metric]);
    const max = Math.max(...rows.map(row => row[metric]));
    document.getElementById('estimatorBars').innerHTML = rows.map(row => `<div class="bar-row"><div class="bar-label">${esc(row.estimator_label)}</div><div class="bar-track"><div class="bar-fill" style="width:${(row[metric] / max * 100).toFixed(1)}%"></div></div><div class="bar-value">${f3(row[metric])} m</div></div>`).join('');
    estimatorTableBody.innerHTML = rows.map(row => {
      const reg = registry[row.estimator_id] || {};
      return `<tr><td><strong>${esc(row.estimator_label)}</strong></td><td>${esc(row.estimator_family)}</td><td>${row.units_covered}</td><td>${f3(row.median_of_unit_medians_m)}</td><td>${f3(row.median_unit_p90_m)}</td><td>${f3(row.median_unit_rmse_m)}</td><td>${esc(reg.native_adapter || '—')}</td></tr>`;
    }).join('');
  };
  metricSelect.addEventListener('change', renderEstimators);
  renderEstimators();

  const unitSelect = document.getElementById('unitSelect');
  data.matrix.rows.forEach(label => unitSelect.insertAdjacentHTML('beforeend', `<option value="${esc(label)}">${esc(label)}</option>`));
  const renderHeatmap = () => {
    const focus = unitSelect.value;
    const rowIndexes = data.matrix.rows.map((label, index) => [label,index]).filter(([label]) => focus === 'all' || label === focus);
    const vals = data.matrix.values.flat().filter(value => value != null);
    const min = Math.min(...vals), max = Math.max(...vals);
    const color = value => {
      if (value == null) return '#f1f4f6';
      const t = (value - min) / Math.max(max - min, 1e-9);
      return `hsl(203 58% ${94 - t * 48}%)`;
    };
    let html = '<table class="heatmap"><thead><tr><th>Unit</th>' + data.matrix.columns.map(c => `<th>${esc(c)}</th>`).join('') + '</tr></thead><tbody>';
    rowIndexes.forEach(([label, idx]) => {
      html += `<tr><th>${esc(label)}</th>` + data.matrix.values[idx].map(value => `<td style="background:${color(value)};color:${value != null && (value-min)/(max-min) > .62 ? 'white' : '#183b56'}">${value == null ? '—' : f3(value)}</td>`).join('') + '</tr>';
    });
    document.getElementById('heatmap').innerHTML = html + '</tbody></table>';
  };
  unitSelect.addEventListener('change', renderHeatmap);
  renderHeatmap();

  // Reliability indicator explorer.
  const indicatorMetric = document.getElementById('indicatorMetric');
  const indicatorFamily = document.getElementById('indicatorFamily');
  [...new Set(data.indicators.map(row => row.family))].sort().forEach(family => indicatorFamily.insertAdjacentHTML('beforeend', `<option value="${esc(family)}">${esc(family)}</option>`));
  const renderIndicators = () => {
    const metric = indicatorMetric.value;
    const family = indicatorFamily.value;
    const rows = data.indicators.filter(row => family === 'all' || row.family === family).sort((a,b) => (b[metric] ?? -Infinity) - (a[metric] ?? -Infinity));
    const max = Math.max(...rows.map(row => Number(row[metric] || 0)), 1e-9);
    document.getElementById('indicatorBars').innerHTML = rows.map(row => `<div class="indicator-row"><div><strong>${esc(row.label)}</strong><span>${esc(row.family)}</span></div><div class="bar-track"><div class="bar-fill indicator-fill" style="width:${Math.max(0, Number(row[metric] || 0)) / max * 100}%"></div></div><div class="bar-value">${f3(row[metric])}</div></div>`).join('');
    document.querySelector('#indicatorTable tbody').innerHTML = rows.map(row => `<tr><td><strong>${esc(row.label)}</strong></td><td>${esc(row.family)}</td><td>${f3(row.median_aligned_rho)}</td><td>${f3(row.adaptive_auroc)}</td><td>${f3(row.fixed_auroc)}</td><td>${row.n_conditions ?? '—'}</td></tr>`).join('');
  };
  indicatorMetric.addEventListener('change', renderIndicators);
  indicatorFamily.addEventListener('change', renderIndicators);
  renderIndicators();

  // SQS explorer.
  document.getElementById('sqsComponents').innerHTML = data.sqs.components.map(component => `<article class="component-card"><div class="component-weight">${Math.round(component.weight * 100)}%</div><div><strong>${esc(component.label)}</strong><p>Unit-wise robust support component.</p></div></article>`).join('');
  const sqsAudit = data.sqs.reconstruction || {};
  document.getElementById('sqsAudit').innerHTML = `<strong>Verified reconstruction.</strong> ${fmt.format(sqsAudit.matched_rows || 0)} scans linked; maximum published SQS difference <code>${sqsAudit.published_sqs_reconstruction_max_abs_difference ?? '—'}</code>. <span class="muted">Native candidate-tie sensitivity is reported separately.</span>`;
  const sqsMetric = document.getElementById('sqsMetric');
  const renderSqs = () => {
    const metric = sqsMetric.value;
    const rows = [...data.sqs.variants].sort((a,b) => (b[metric] ?? -Infinity) - (a[metric] ?? -Infinity));
    const min = Math.min(...rows.map(row => Number(row[metric] ?? 0)));
    const max = Math.max(...rows.map(row => Number(row[metric] ?? 0)));
    document.getElementById('sqsBars').innerHTML = rows.map(row => {
      const value = Number(row[metric] ?? 0);
      const width = (value - min) / Math.max(max - min, 1e-9) * 100;
      return `<div class="bar-row"><div class="bar-label">${esc(row.label)}</div><div class="bar-track"><div class="bar-fill sqs-fill" style="width:${Math.max(2,width).toFixed(1)}%"></div></div><div class="bar-value">${f3(value)}</div></div>`;
    }).join('');
  };
  sqsMetric.addEventListener('change', renderSqs);
  renderSqs();

  // Gross-error case explorer.
  const caseState = document.getElementById('caseState');
  const caseSelect = document.getElementById('caseSelect');
  [...new Set(data.cases.map(item => item.case_state))].sort().forEach(state => caseState.insertAdjacentHTML('beforeend', `<option value="${esc(state)}">${esc(state.replaceAll('_',' '))}</option>`));
  const availableCases = () => data.cases.filter(item => caseState.value === 'all' || item.case_state === caseState.value);
  const populateCases = () => {
    const cases = availableCases();
    caseSelect.innerHTML = cases.map(item => `<option value="${esc(item.case_id)}">${esc(item.case_id)} · ${esc(item.unit_label)} · ${esc(item.estimator_display)}</option>`).join('');
    renderCase(cases[0]);
  };
  const renderCase = item => {
    const svg = document.getElementById('casePlot');
    if (!item) { svg.innerHTML = '<text x="30" y="50">No case in this category.</text>'; document.getElementById('caseDetails').innerHTML = ''; return; }
    const points = [
      {x:Number(item.x_true), y:Number(item.y_true)},
      {x:Number(item.x_pred), y:Number(item.y_pred)},
      {x:Number(item.diagnostic_x), y:Number(item.diagnostic_y)},
      ...(item.candidates || []).map(c => ({x:Number(c.candidate_x), y:Number(c.candidate_y)})),
    ].filter(p => Number.isFinite(p.x) && Number.isFinite(p.y));
    let minX=Math.min(...points.map(p=>p.x)), maxX=Math.max(...points.map(p=>p.x));
    let minY=Math.min(...points.map(p=>p.y)), maxY=Math.max(...points.map(p=>p.y));
    const padX=Math.max((maxX-minX)*.15,1), padY=Math.max((maxY-minY)*.15,1);
    minX-=padX; maxX+=padX; minY-=padY; maxY+=padY;
    const sx=x=>50+(x-minX)/(maxX-minX)*620;
    const sy=y=>450-(y-minY)/(maxY-minY)*400;
    const grid = Array.from({length:6},(_,i)=>{
      const x=50+i*124, y=50+i*80;
      return `<line x1="${x}" y1="50" x2="${x}" y2="450" class="grid-line"/><line x1="50" y1="${y}" x2="670" y2="${y}" class="grid-line"/>`;
    }).join('');
    const candidates=(item.candidates || []).map(c=>`<circle cx="${sx(Number(c.candidate_x))}" cy="${sy(Number(c.candidate_y))}" r="6" class="candidate-point"><title>Candidate ${c.candidate_rank}; RSS distance ${f3(c.normalized_rss_distance)}</title></circle>`).join('');
    svg.innerHTML = `${grid}<rect x="50" y="50" width="620" height="400" class="plot-frame"/>${candidates}<line x1="${sx(Number(item.x_true))}" y1="${sy(Number(item.y_true))}" x2="${sx(Number(item.x_pred))}" y2="${sy(Number(item.y_pred))}" class="error-vector" marker-end="url(#arrow)"/><defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" class="arrow-head"/></marker></defs><circle cx="${sx(Number(item.diagnostic_x))}" cy="${sy(Number(item.diagnostic_y))}" r="8" class="centroid-point"/><circle cx="${sx(Number(item.x_true))}" cy="${sy(Number(item.y_true))}" r="10" class="true-point"/><circle cx="${sx(Number(item.x_pred))}" cy="${sy(Number(item.y_pred))}" r="10" class="pred-point"/><text x="${sx(Number(item.x_true))+12}" y="${sy(Number(item.y_true))-10}" class="plot-label">Truth</text><text x="${sx(Number(item.x_pred))+12}" y="${sy(Number(item.y_pred))+18}" class="plot-label">Estimate</text>`;
    const metrics = [
      ['Localization error', `${f2(item.error_m)} m`],
      ['Adaptive threshold', `${f2(item.adaptive_threshold_m)} m`],
      ['SQS', f3(item.SQS)],
      ['Warning indicators', `${item.warning_count}/18`],
      ['Nearest-RP distance', `${f2(item.nearest_rp_distance)} m`],
      ['Candidate spread', `${f2(item.sigma_fps)} m`],
      ['Candidate diameter', `${f2(item.D_cand)} m`],
      ['Instability', `${f2(item.I_k)} m`],
      ['Minimum RSS distance', f3(item.min_rss_distance)],
      ['Maximum AP overlap', f3(item.ap_overlap)],
      ['Local RP density', item.local_rp_density],
      ['AP count', item.ap_count],
    ];
    document.getElementById('caseDetails').innerHTML = `<div class="case-head"><div><span class="state-chip state-${esc(item.case_state)}">${esc(item.case_state.replaceAll('_',' '))}</span><h3>${esc(item.case_id)} · ${esc(item.estimator_display)}</h3><p>${esc(item.unit_label)} · row ${esc(item.row_id)}</p></div><div class="error-number">${f2(item.error_m)}<span>m error</span></div></div><div class="metric-grid">${metrics.map(([label,value])=>`<div><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`).join('')}</div><div class="decision-box"><strong>Operational reading</strong><p>${item.gross_error_adaptive ? 'The estimate exceeds its condition-adaptive error threshold.' : 'The estimate remains below its condition-adaptive error threshold.'} ${item.case_state === 'confidently_wrong' ? 'SQS remains comparatively high, illustrating a confidently wrong failure.' : item.warning_fraction >= .5 ? 'Multiple indicators provide a strong warning.' : 'The indicator warning pattern is mixed or limited.'}</p></div>`;
  };
  caseState.addEventListener('change', populateCases);
  caseSelect.addEventListener('change', () => renderCase(data.cases.find(item => item.case_id === caseSelect.value)));
  populateCases();

  document.getElementById('testGrid').innerHTML = data.tests.map(test => `<article class="test-card"><div class="status status-${statusClass(test.status)}">${esc(test.status)}</div><div class="test-title">${esc(test.name)}</div><div class="test-detail">${esc(test.detail)}</div></article>`).join('');
  document.getElementById('reportPreview').textContent = JSON.stringify(data.reports, null, 2);
  document.getElementById('artifactGrid').innerHTML = data.artifacts.map(item => `<article class="artifact-card"><div class="artifact-title"><a href="${esc(item.path)}">${esc(item.label)}</a></div><div class="artifact-meta">${esc(item.description)}</div></article>`).join('');

  const sections = [...document.querySelectorAll('main section')];
  const links = [...document.querySelectorAll('.nav-link')];
  const observer = new IntersectionObserver(entries => entries.filter(entry => entry.isIntersecting).forEach(entry => links.forEach(link => link.classList.toggle('active', link.getAttribute('href') === `#${entry.target.id}`))), {rootMargin: '-20% 0px -70% 0px'});
  sections.forEach(section => observer.observe(section));
})();
