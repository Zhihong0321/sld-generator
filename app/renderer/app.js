/* SLD Studio renderer. Talks to the main process only through window.sld (preload.js). */
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fileUrl = (p) => (p ? encodeURI('file:///' + String(p).replace(/\\/g, '/')).replace(/#/g, '%23') + '?t=' + Date.now() : '');

let LIB = { pv_module: {}, inverter: {} };
const form = $('#form');

// ---------- navigation ----------
$$('.nav').forEach((b) => b.addEventListener('click', () => show(b.dataset.view)));
function show(view) {
  $$('.nav').forEach((b) => b.classList.toggle('active', b.dataset.view === view));
  $$('.view').forEach((v) => v.classList.toggle('active', v.id === 'view-' + view));
  if (view === 'history') loadHistory();
  if (view === 'settings') loadSettings();
}

// ---------- library ----------
async function loadLibrary() {
  const r = await window.sld.library();
  LIB = r.library || { pv_module: {}, inverter: {} };
  const nm = Object.keys(LIB.pv_module || {}).length, ni = Object.keys(LIB.inverter || {}).length;
  $('#engineStatus').textContent = r.ok ? `Library: ${nm} panels, ${ni} inverters` : `Engine problem: ${r.error}`;
  fillSelects();
}

function fillSelects() {
  const mSel = form.module, iSel = form.inverter;
  const keepM = mSel.value, keepI = iSel.value;
  const flag = (e) => (e.verified ? '' : '  (unverified)');
  mSel.innerHTML = '<option value="">Select panel…</option>' + Object.entries(LIB.pv_module || {})
    .sort((a, b) => `${a[1].brand}${a[1].model}`.localeCompare(`${b[1].brand}${b[1].model}`))
    .map(([k, e]) => `<option value="${esc(k)}">${esc(e.brand)} ${esc(e.model)} — ${esc(e.wattage_wp)} Wp${flag(e)}</option>`).join('');
  const phase = Number(form.phase.value || 3);
  const inv = Object.entries(LIB.inverter || {}).sort((a, b) => (a[1].phase - b[1].phase) || `${a[1].brand}`.localeCompare(`${b[1].brand}`) || (a[1].rated_ac_kw - b[1].rated_ac_kw));
  const opt = ([k, e]) => `<option value="${esc(k)}">${esc(e.brand)} ${esc(e.model)} — ${esc(e.rated_ac_kw)} kW, ${esc(e.mppt_count)} MPPT${flag(e)}</option>`;
  const match = inv.filter(([, e]) => Number(e.phase) === phase), other = inv.filter(([, e]) => Number(e.phase) !== phase);
  iSel.innerHTML = '<option value="">Select inverter…</option>' +
    (match.length ? `<optgroup label="${phase}-phase">${match.map(opt).join('')}</optgroup>` : '') +
    (other.length ? `<optgroup label="Other phase">${other.map(opt).join('')}</optgroup>` : '');
  mSel.value = keepM; iSel.value = keepI;
}
$$('input[name=phase]').forEach((r) => r.addEventListener('change', fillSelects));

// ---------- form helpers ----------
function readForm() {
  const o = {};
  for (const el of form.elements) {
    if (!el.name) continue;
    if (el.type === 'radio') { if (el.checked) o[el.name] = el.value; } else o[el.name] = el.value;
  }
  return o;
}

function setField(name, value, mark) {
  if (value === null || value === undefined || value === '') return false;
  const el = form.elements[name];
  if (!el) return false;
  if (el instanceof RadioNodeList) { el.value = String(value); fillSelects(); }
  else {
    if (el.tagName === 'SELECT' && ![...el.options].some((o) => o.value === String(value))) return false;
    el.value = String(value);
  }
  if (mark) { const target = el instanceof RadioNodeList ? el[0]?.closest('.seg') : el; target?.classList.add('filled'); }
  return true;
}

function clearMarks() { $$('.filled').forEach((e) => e.classList.remove('filled')); }

$('#resetBtn').addEventListener('click', () => {
  form.reset(); clearMarks(); fillSelects(); $('#aiNotes').innerHTML = ''; $('#aiStatus').textContent = '';
  $('#formTitle').textContent = 'New SLD';
});

// ---------- AI intake ----------
$('#aiBtn').addEventListener('click', async () => {
  const text = $('#aiText').value.trim();
  if (!text) { $('#aiStatus').textContent = 'Paste some job details first.'; return; }
  const btn = $('#aiBtn'); btn.disabled = true; $('#aiStatus').textContent = 'Reading…'; $('#aiNotes').innerHTML = '';
  try {
    const r = await window.sld.parse(text);
    if (!r.ok) { $('#aiStatus').textContent = 'AI failed: ' + r.error; return; }
    clearMarks();
    const f = r.fields || {};
    if (f.phase) setField('phase', Number(f.phase) === 1 ? 1 : 3, true);
    const filled = [];
    for (const k of ['module', 'qty', 'inverter', 'strings', 'dc_length_m', 'ac_length_m', 'main_switch_a', 'main_rcd_a',
      'main_rcd_ma', 'account_holder', 'address', 'tnb_account_no', 'drawing_no', 'drawn_by', 'qp_name', 'qp_cert_no',
      'rpvsp', 'cp_name', 'cp_category', 'cp_cert_no', 'contractor_reg_no']) {
      if (setField(k, f[k], true)) filled.push(k);
    }
    if (filled.some((k) => !['module', 'qty', 'inverter'].includes(k))) $$('details.card').forEach((d) => { if ($('.filled', d)) d.open = true; });
    $('#aiStatus').textContent = `Filled ${filled.length + (f.phase ? 1 : 0)} field(s) with ${r.model}. Highlighted fields came from AI; please check them.`;
    const notes = [...(r.notes || []), ...(r.unmatched || []).map((u) => `Not in library: ${u}. Add it from its datasheet first.`)];
    $('#aiNotes').innerHTML = notes.map((n) => `<li>${esc(n)}</li>`).join('');
  } catch (e) {
    $('#aiStatus').textContent = 'AI failed: ' + e.message;
  } finally { btn.disabled = false; }
});

// ---------- generate ----------
form.addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const btn = $('#genBtn'); btn.disabled = true; btn.textContent = 'Generating…';
  $('#result').innerHTML = '<div class="spinner"></div><p class="muted" style="text-align:center">Sizing, checking and drawing…</p>';
  try {
    const r = await window.sld.generate(readForm());
    renderResult($('#result'), r);
  } catch (e) {
    $('#result').innerHTML = `<div class="issue error">Generate failed: ${esc(e.message)}</div>`;
  } finally { btn.disabled = false; btn.textContent = 'Generate'; }
});

function statusBadge(result, issues) {
  const errs = (issues || []).filter((i) => i.level === 'error').length;
  const warns = (issues || []).filter((i) => i.level === 'warning').length;
  if (result === 'passed') return warns ? `<span class="badge b-warn">PASSED · ${warns} WARNING${warns > 1 ? 'S' : ''}</span>` : '<span class="badge b-ok">PASSED</span>';
  if (result === 'failed_forced' || result === 'failed') return `<span class="badge b-bad">DESIGN CHECK FAILED · ${errs} ERROR${errs === 1 ? '' : 'S'} · DRAFT</span>`;
  if (result === 'incomplete') return '<span class="badge b-bad">INFORMATION MISSING</span>';
  if (result === 'error') return '<span class="badge b-bad">EXPORT PROBLEM</span>';
  return '<span class="badge b-none">NO CHECK RECORD</span>';
}

function summaryHtml(s) {
  if (!s) return '';
  const rows = [
    ['System', `${s.p_dc_kwp} kWp / ${s.p_ac_kw} kWac (DC/AC ${s.dc_ac_ratio}) · ${s.supply}`],
    ['Strings', (s.strings || []).map((g) => `MPPT${g.mppt}: ${g.parallel}×${g.series} (Voc max ${g.voc_max_v} V)`).join(', ')],
    ['DC cable', `${s.dc_cable_mm2} mm² · ΔV ${s.vd_dc_pct}%`],
    ...(s.string_fuse_a ? [['String fuses', `${s.string_fuse_a} A`]] : []),
    ['AC MCB', s.ac_mcb],
    ['AC cable', `${s.ac_cable} · ΔV ${s.vd_ac_pct}%`],
    ['Total voltage drop', `${s.vd_total_pct}%`],
  ];
  if ((s.unverified_equipment || []).length) rows.push(['Unverified equipment', s.unverified_equipment.join(', ')]);
  const clean = (v) => String(v ?? '—').replace(/\b(None|null|undefined|NaN)\b/g, '—');
  return `<div class="card"><h2>Summary</h2><div class="kv" style="margin-top:10px">${rows.map(([k, v]) => `<div>${esc(k)}</div><div>${esc(clean(v))}</div>`).join('')}</div></div>`;
}

function issuesHtml(issues, notes, problems) {
  const parts = [];
  for (const p of problems || []) parts.push(`<div class="issue error">${esc(p)}</div>`);
  for (const i of issues || []) parts.push(`<div class="issue ${esc(i.level)}"><b>${esc(String(i.level).toUpperCase())}</b> [${esc(i.code)}] ${esc(i.msg)}</div>`);
  for (const n of notes || []) parts.push(`<div class="issue info">Default used: ${esc(n)}</div>`);
  return parts.length ? `<div class="card"><h2>Checks &amp; notes</h2><div style="margin-top:10px">${parts.join('')}</div></div>` : '';
}

function renderResult(el, r, opts = {}) {
  r = r || {};
  const files = r.files || {};
  const title = r.drawing_no ? `${r.drawing_no}${r.revision ? ' Rev ' + r.revision : ''}` : 'Result';
  const preview = files.png || files.svg;
  const btn = (label, p, cls = 'ghost') => (p ? `<button class="${cls}" data-open="${esc(p)}">${label}</button>` : '');
  el.innerHTML = `
    <div class="reshead"><h1>${esc(title)}</h1>${statusBadge(r.result, r.issues)}${r.customer ? `<span class="muted">${esc(r.customer)}</span>` : ''}</div>
    ${r.error ? `<div class="issue error">${esc(r.error)}</div>` : ''}
    ${(r.log || []).map((l) => `<div class="issue error">${esc(l)}</div>`).join('')}
    <div class="btns">
      ${btn('Open PDF', files.pdf, 'primary')}${btn('Open SVG', files.svg)}${btn('Design report', files.report)}
      ${files.svg || files.pdf ? `<button class="ghost" data-folder="${esc(files.pdf || files.svg)}">Show in folder</button>` : ''}
      ${opts.revise && r.project_file ? `<button class="secondary" data-revise="${esc(r.project_file)}" data-rev="${esc(r.revision || '')}">Revise in form</button>` : ''}
    </div>
    ${r.invoice_number && files.pdf ? uploadBarHtml(r.invoice_number, files.pdf, r.result) : ''}
    ${preview ? `<div class="sheet"><img alt="SLD preview" src="${fileUrl(preview)}"></div>` : ''}
    ${summaryHtml(r.summary)}
    ${issuesHtml(r.issues, r.notes, r.problems)}`;
  $$('[data-open]', el).forEach((b) => b.addEventListener('click', async () => {
    const res = await window.sld.openPath(b.dataset.open);
    if (!res.ok) alert(res.error);
  }));
  $$('[data-folder]', el).forEach((b) => b.addEventListener('click', () => window.sld.showInFolder(b.dataset.folder)));
  $$('[data-revise]', el).forEach((b) => b.addEventListener('click', () => reviseFrom(b.dataset.revise, b.dataset.rev)));
  wireUploadButtons(el);
}

// ---------- revise ----------
async function reviseFrom(file, rev) {
  const r = await window.sld.loadProject(file);
  if (!r.ok) { alert(r.error); return; }
  const p = r.project || {};
  form.reset(); clearMarks(); $('#aiNotes').innerHTML = ''; $('#aiStatus').textContent = '';
  const ref = (v) => (typeof v === 'string' ? v : v?.ref || '');
  setField('phase', p.supply?.phase === 1 ? 1 : 3);
  setField('module', ref(p.pv_module));
  setField('inverter', ref(p.inverter));
  const strings = [];
  for (const s of p.array?.strings || []) for (let i = 0; i < (Number(s.count) || 1); i++) strings.push(Number(s.modules) || 0);
  setField('qty', strings.reduce((a, b) => a + b, 0));
  setField('strings', strings.join(','));
  setField('dc_length_m', p.cables?.dc_length_m); setField('ac_length_m', p.cables?.ac_length_m);
  setField('main_switch_a', p.pcc?.main_switch_a); setField('main_rcd_a', p.pcc?.main_rcd_a); setField('main_rcd_ma', p.pcc?.main_rcd_ma);
  for (const k of ['account_holder', 'address', 'tnb_account_no', 'drawing_no', 'drawn_by']) setField(k, p.project?.[k]);
  for (const k of ['qp_name', 'qp_cert_no', 'rpvsp', 'cp_name', 'cp_category', 'cp_cert_no', 'contractor_reg_no']) setField(k, p.people?.[k]);
  const n = parseInt(rev || p.project?.revision, 10);
  setField('revision', String(Number.isFinite(n) ? n + 1 : 1).padStart(2, '0'));
  $$('details.card').forEach((d) => (d.open = true));
  $('#formTitle').textContent = `Revise ${p.project?.drawing_no || ''}`;
  $('#result').innerHTML = '<div class="empty">Change what you need and press <b>Generate</b>.<br>Earlier revisions are kept.</div>';
  show('new');
}

// ---------- history ----------
let HIST = [];
async function loadHistory() {
  $('#histList').innerHTML = '<p class="muted">Loading…</p>';
  try { HIST = await window.sld.history(); } catch (e) { HIST = []; $('#histList').innerHTML = `<div class="issue error">${esc(e.message)}</div>`; return; }
  drawHistory();
}

function drawHistory() {
  const q = $('#histSearch').value.trim().toLowerCase();
  const items = HIST.filter((h) => !q || `${h.drawing_no} ${h.customer}`.toLowerCase().includes(q));
  if (!items.length) { $('#histList').innerHTML = '<p class="muted">No drawings yet.</p>'; return; }
  $('#histList').innerHTML = items.map((h, i) => {
    const s = h.summary;
    const when = h.created ? new Date(h.created).toLocaleString() : '';
    return `<div class="item" data-i="${HIST.indexOf(h)}">
      <div class="t">${esc(h.drawing_no)} <span class="muted">Rev ${esc(h.revision)}</span></div>
      <div>${statusBadge(h.result, h.issues)}</div>
      <div class="s">${esc(h.customer || 'No customer name')}${s ? ` · ${esc(s.p_dc_kwp)} kWp / ${esc(s.p_ac_kw)} kW` : ''} · ${esc(when)}</div>
    </div>`;
  }).join('');
  $$('.item', $('#histList')).forEach((el) => el.addEventListener('click', () => {
    $$('.item').forEach((x) => x.classList.remove('sel')); el.classList.add('sel');
    const h = HIST[Number(el.dataset.i)];
    renderResult($('#histDetail'), h, { revise: true });
  }));
}
$('#histSearch').addEventListener('input', drawHistory);
$('#refreshHist').addEventListener('click', loadHistory);

// ---------- settings ----------
// The boxes show exactly what is stored. Typing stores it (no Save needed); Save stores all.
const SETTING_FIELDS = {
  sBase: 'baseUrl', sModel: 'model', sKey: 'apiKey', sEapiBase: 'eapiBase', sEapiKey: 'eapiKey',
  sUploader: 'uploaderName', sPeBase: 'peBase', sPeModel: 'peModel', sPeEffort: 'peEffort', sPeKey: 'peKey', sPython: 'python',
};
let settingsFilled = false;

async function loadSettings() {
  if (settingsFilled) return;               // fill once; after that the boxes are what you typed
  const s = await window.sld.getSettings();
  for (const [id, k] of Object.entries(SETTING_FIELDS)) {
    const el = document.getElementById(id);
    if (el) el.value = s[k] ?? '';
  }
  settingsFilled = true;
  $('#sFile').textContent = `Stored in ${s.file}`;
  if (s.problem) { $('#sStatus').className = 'issue warning'; $('#sStatus').textContent = s.problem; }
}

async function saveSettingsNow() {
  if (!settingsFilled) await loadSettings();
  const patch = {};
  for (const [id, k] of Object.entries(SETTING_FIELDS)) {
    const el = document.getElementById(id);
    if (el) patch[k] = el.value;
  }
  let r;
  try { r = await window.sld.saveSettings(patch); } catch (e) { r = { ok: false, error: e.message }; }
  $('#sStatus').className = r.ok ? 'saved-ok' : 'issue error';
  $('#sStatus').textContent = r.ok ? `Saved ✓ ${new Date().toLocaleTimeString()}` : r.error;
  return r;
}

let saveTimer = null;
for (const id of Object.keys(SETTING_FIELDS)) {
  const el = document.getElementById(id);
  if (!el) continue;
  el.addEventListener('input', () => { clearTimeout(saveTimer); saveTimer = setTimeout(saveSettingsNow, 500); });
  el.addEventListener('change', () => { clearTimeout(saveTimer); saveSettingsNow(); });
}
$('#saveSettings').addEventListener('click', async () => { clearTimeout(saveTimer); await saveSettingsNow(); loadLibrary(); });

loadLibrary();

// ---------- OTA updates ----------
const UP = { state: null, dismissed: false };
const short = (s) => (s ? String(s).slice(0, 7) : 'unknown');

function bar(html, cls = '') {
  const b = $('#updateBar');
  if (!html) { b.hidden = true; b.innerHTML = ''; return; }
  b.className = 'updatebar ' + cls; b.innerHTML = html; b.hidden = false;
  $('[data-up=apply]', b)?.addEventListener('click', applyUpdate);
  $('[data-up=restart]', b)?.addEventListener('click', () => window.sld.restart());
  $('[data-up=later]', b)?.addEventListener('click', () => { UP.dismissed = true; bar(null); });
  $('[data-up=details]', b)?.addEventListener('click', () => show('settings'));
}

function drawUpdateCard() {
  const s = UP.state || {};
  $('#uApply').hidden = !(s.type === 'check' && s.available);
  $('#uRestart').hidden = !(s.type === 'applied' && s.ok);
  let state = '';
  if (s.type === 'check') {
    if (!s.ok) state = `Could not check: ${s.error}`;
    else if (s.available) state = s.unknownLocal ? 'An update is available (installed version unknown).' : `${s.behind} update${s.behind > 1 ? 's' : ''} available.`;
    else state = 'You have the latest version.';
    if (s.ok && s.mode === 'git' && s.dirty && s.available) state += ` Note: ${s.dirty} file(s) were edited on this PC; if GitHub changed the same files, the update stops and nothing is changed.`;
  } else if (s.type === 'progress') state = s.msg;
  else if (s.type === 'applied') state = s.ok ? 'Update installed. Restart the app to use it.' : `Update did not finish: ${s.error}`;
  $('#uState').textContent = state;
  $('#uChanges').innerHTML = s.type === 'check' && s.available
    ? (s.changes || []).slice(0, 15).map((c) => `<li>${esc(c.msg)} <span class="muted">${esc(c.sha)}</span></li>`).join('') : '';
}

async function drawVersion() {
  try {
    const v = await window.sld.version();
    $('#uVersion').textContent = `SLD Studio ${v.version} · build ${short(v.sha)} · ${v.mode === 'git' ? 'git checkout' : 'zip install'} · ${v.root}`;
  } catch { /* version line is optional */ }
}

// Update notice in the left nav panel: stays visible until the update is installed.
function drawNavUpdate() {
  const s = UP.state || {};
  const n = $('#navUpdate');
  let mode = null, title = '', sub = '';
  if (s.type === 'check' && s.ok && s.available) {
    mode = 'update'; title = 'UPDATE AVAILABLE';
    sub = s.behind > 1 ? `${s.behind} changes · click to update` : 'Click to update';
  } else if (s.type === 'progress') { mode = 'busy'; title = 'UPDATING…'; sub = s.msg || ''; }
  else if (s.type === 'applied' && s.ok) { mode = 'restart'; title = 'UPDATE INSTALLED'; sub = 'Click to restart'; }
  n.hidden = !mode; n.dataset.mode = mode || '';
  n.classList.toggle('ok', mode === 'restart');
  $('#navUpdateTitle').textContent = title; $('#navUpdateSub').textContent = sub;
}
$('#navUpdate').addEventListener('click', () => {
  if ($('#navUpdate').dataset.mode === 'restart') window.sld.restart();
  else show('settings');
});

window.sld.onUpdate((s) => {
  UP.state = s;
  drawUpdateCard();
  drawNavUpdate();
  if (s.type === 'check' && s.ok && s.available && !UP.dismissed) {
    bar(`<span class="grow"><b>Update available</b> · ${s.behind > 1 ? s.behind + ' changes' : esc((s.changes?.[0]?.msg) || '1 change')}</span>
      <button class="ghost" data-up="details">Details</button><button class="ghost" data-up="later">Later</button><button class="primary" data-up="apply">Update now</button>`);
  } else if (s.type === 'progress') bar(`<span class="grow">${esc(s.msg)}</span>`);
  else if (s.type === 'applied') {
    bar(s.ok ? `<span class="grow"><b>Update installed.</b> Restart to use the new version.</span><button class="primary" data-up="restart">Restart now</button>`
      : `<span class="grow"><b>Update did not finish:</b> ${esc(s.error)}</span><button class="ghost" data-up="later">Close</button>`, s.ok ? 'ok' : 'bad');
    drawVersion();
  }
});

async function applyUpdate() {
  $('#uApply').disabled = true;
  try { await window.sld.applyUpdate(); } catch (e) { UP.state = { type: 'applied', ok: false, error: e.message }; drawUpdateCard(); }
  finally { $('#uApply').disabled = false; }
}

$('#uCheck').addEventListener('click', async () => {
  $('#uCheck').disabled = true; $('#uState').textContent = 'Checking GitHub…';
  UP.dismissed = false;
  try { await window.sld.checkUpdate(); } finally { $('#uCheck').disabled = false; }
});
$('#uApply').addEventListener('click', applyUpdate);
$('#uRestart').addEventListener('click', () => window.sld.restart());
drawVersion();


// ---------- invoices ----------
const money = (v) => { const n = Number(v); return Number.isFinite(n) ? 'RM ' + n.toLocaleString('en-MY', { maximumFractionDigits: 2 }) : '—'; };
const day = (v) => (v ? new Date(v).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }) : '');
const INV = { rows: [], offset: 0, args: null, sel: null };

(() => { // hidden field so a generated job remembers its invoice
  const h = document.createElement('input'); h.type = 'hidden'; h.name = 'invoice_number'; form.appendChild(h);
})();

$$('#invBy input').forEach((r) => r.addEventListener('change', () => {
  const ph = { name: 'e.g. Tan', address: 'e.g. Shah Alam', agent: 'e.g. Ng Zhan Yi' };
  $('#invQ').placeholder = ph[r.value] || '';
  $('#invQ').focus();
}));

$('#invForm').addEventListener('submit', (ev) => {
  ev.preventDefault();
  INV.args = { by: $('#invForm').by.value, q: $('#invQ').value, includeDeleted: $('#invDeleted').checked };
  INV.offset = 0; INV.rows = [];
  runInvoiceSearch();
});
$('#invMore').addEventListener('click', () => { INV.offset += 50; runInvoiceSearch(); });

async function runInvoiceSearch() {
  const btn = $('#invGo'); btn.disabled = true; $('#invStatus').textContent = 'Searching…';
  try {
    const r = await window.sld.searchInvoices({ ...INV.args, offset: INV.offset });
    if (!r.ok) {
      $('#invStatus').innerHTML = `<div class="issue error">Search failed: ${esc(r.error)}${/key/i.test(r.error) ? ' <button class="secondary" id="goKey" style="margin-left:8px">Enter key</button>' : ''}</div>`;
      $('#goKey')?.addEventListener('click', () => { show('settings'); setTimeout(() => { $('#sEapiKey').scrollIntoView({ block: 'center' }); $('#sEapiKey').focus(); }, 200); });
      return;
    }
    INV.rows = INV.rows.concat(r.rows || []);
    const head = INV.rows.length ? `${INV.rows.length} invoice(s)${r.agents?.length ? ' · agent: ' + r.agents.join(', ') : ''}` : 'No invoices found.';
    $('#invStatus').innerHTML = esc(head) + (r.notes || []).map((n) => `<div class="issue info" style="margin-top:6px">${esc(n)}</div>`).join('');
    $('#invMore').hidden = !r.more;
    drawInvoiceList();
  } catch (e) {
    $('#invStatus').innerHTML = `<div class="issue error">Search failed: ${esc(e.message)}</div>`;
  } finally { btn.disabled = false; }
}

function drawInvoiceList() {
  $('#invList').innerHTML = INV.rows.map((r, i) => `
    <div class="item${INV.sel === r.invoice_number ? ' sel' : ''}" data-i="${i}">
      <div class="t">${esc(r.customer_name || 'Customer name not loaded')}</div>
      <div class="r">${esc(day(r.invoice_date))}</div>
      <div class="s">${esc(r.invoice_number)} · ${esc(r.status || '—')} · ${esc(money(r.total_amount))}${r.agent_name ? ' · ' + esc(r.agent_name) : ''}${r.address ? ' · ' + esc(r.address) : ''}</div>
    </div>`).join('');
  $$('.item', $('#invList')).forEach((el) => el.addEventListener('click', () => openInvoice(INV.rows[Number(el.dataset.i)])));
}

async function openInvoice(row) {
  INV.sel = row.invoice_number; drawInvoiceList();
  const pane = $('#invDetail');
  pane.innerHTML = '<div class="spinner"></div><p class="muted" style="text-align:center">Loading invoice and package…</p>';
  let d;
  try { d = await window.sld.invoiceDetail(row.invoice_number || row.id, { customer_name: row.customer_name }); }
  catch (e) { d = { ok: false, error: e.message }; }
  if (!d.ok) { pane.innerHTML = `<div class="issue error">Could not load ${esc(row.invoice_number)}: ${esc(d.error)}</div>`; return; }
  const inv = d.invoice, sld = d.sld || { form: {}, notes: [], missing: [] };
  const libName = (kind, key) => { const e = (LIB[kind] || {})[key]; return e ? `${e.brand} ${e.model}` : ''; };
  const kv = [
    ['Customer', d.customer?.name], ['Invoice', `${inv.invoice_number} · ${inv.status || '—'} · ${day(inv.invoice_date)}`],
    ['Amount', `${money(inv.total_amount)} (paid ${money(inv.paid_amount)}, ${d.payments_count} payment${d.payments_count === 1 ? '' : 's'})`],
    ['Sales agent', inv.agent_name], ['Address', inv.address],
    ['Equipment', (d.products || []).map((p) => String(p.name || p.description || '').trim()).filter(Boolean).join(' · ')],
    ['Package', [inv.package_name, inv.package_type, inv.package_id].filter(Boolean).join(' · ')],
  ];
  const f = sld.form || {};
  const ready = [
    ['Supply', f.phase ? (Number(f.phase) === 1 ? 'Single-phase' : 'Three-phase') : ''],
    ['Panel', f.module ? libName('pv_module', f.module) : ''], ['Quantity', f.qty || ''],
    ['Inverter', f.inverter ? libName('inverter', f.inverter) : ''],
    ['Customer name', f.account_holder], ['Address', f.address], ['TNB account no.', f.tnb_account_no], ['Drawing no.', f.drawing_no],
  ];
  const allNotes = [...(d.notes || []), ...(sld.notes || [])];
  const missing = sld.missing || [];
  pane.innerHTML = `
    <div class="reshead"><h1>${esc(inv.invoice_number)}</h1>${sld.complete ? '<span class="badge b-ok">READY FOR SLD</span>' : `<span class="badge b-warn">${missing.length} ITEM${missing.length === 1 ? '' : 'S'} TO PICK</span>`}</div>
    <div class="btns">
      <button class="primary" id="invGen">${sld.complete ? 'Generate SLD' : 'Generate SLD (pick missing items)'}</button>
      <button class="ghost" id="invOpen">Open in form</button>
    </div>
    <div class="card"><h2>Invoice</h2><div class="kv" style="margin-top:10px">${kv.map(([k, v]) => `<div>${esc(k)}</div><div>${esc(v || '—')}</div>`).join('')}</div></div>
    <div class="card"><h2>SLD inputs from this invoice</h2>
      <ul class="ready">${ready.map(([k, v]) => `<li class="${v ? 'y' : 'n'}"><b>${esc(k)}:</b> ${esc(v || 'not available')}</li>`).join('')}</ul></div>
    ${peCardHtml(d)}
    ${attachmentsHtml(d)}
    ${allNotes.length ? `<div class="card"><h2>Notes</h2><div style="margin-top:10px">${allNotes.map((n) => `<div class="issue warning">${esc(n)}</div>`).join('')}</div></div>` : ''}
    ${d.package ? `<details class="card"><summary><h2>Package record</h2></summary><pre class="report">${esc(JSON.stringify(d.package, null, 2))}</pre></details>` : ''}`;
  $$('[data-url]', pane).forEach((a) => a.addEventListener('click', async (ev) => {
    ev.preventDefault();
    const r = await window.sld.openFileUrl(a.dataset.url);
    if (!r.ok) alert(r.error);
  }));
  showLocalDrawings(inv.invoice_number);
  wirePeCard(d);
  $('#invGen').addEventListener('click', () => invoiceToSld(d, sld.complete));
  $('#invOpen').addEventListener('click', () => invoiceToSld(d, false));
}

function invoiceToSld(d, autoGenerate) {
  const sld = d.sld || { form: {}, notes: [] };
  form.reset(); clearMarks(); $('#aiText').value = ''; $('#aiStatus').textContent = '';
  const f = { ...sld.form, invoice_number: d.invoice.invoice_number };
  if (f.phase) setField('phase', f.phase, true);
  for (const [k, v] of Object.entries(f)) if (k !== 'phase') setField(k, v, k !== 'invoice_number');
  $$('details.card').forEach((x) => (x.open = true));
  $('#formTitle').textContent = `SLD for ${d.invoice.invoice_number}`;
  $('#aiNotes').innerHTML = (sld.notes || []).map((n) => `<li>${esc(n)}</li>`).join('');
  $('#aiStatus').textContent = `Filled from invoice ${d.invoice.invoice_number}. Highlighted fields came from the invoice.`;
  $('#result').innerHTML = `<div class="empty">${autoGenerate ? 'Generating…' : 'Pick the items still missing, then press <b>Generate</b>.'}</div>`;
  show('new');
  if (autoGenerate) form.requestSubmit();
  else (form.querySelector('select:invalid, input:invalid') || form.qty).focus();
}


// ---------- attachments ----------
function attachmentsHtml(d) {
  const files = d.attachments || [];
  const up = d.sld_uploads || {};
  const link = (f, text) => `<a href="#" data-url="${esc(f.url)}">${esc(text || f.name || 'open')}</a>`;
  const sldRows = Object.entries(up).map(([, k]) => {
    const l = k.latest;
    const state = k.uploaded
      ? `<span class="badge b-ok">UPLOADED</span> ${link(l, l.name)}${l.uploaded_at ? ' · ' + esc(day(l.uploaded_at)) : ''}${l.uploaded_by ? ' · ' + esc(l.uploaded_by) : ''}${k.count > 1 ? ` · ${k.count} versions` : ''}`
      : '<span class="badge b-none">NOT UPLOADED</span>';
    return `<div>${esc(k.label)}</div><div>${state}</div>`;
  }).join('');
  const groups = {};
  for (const f of files) (groups[f.label] = groups[f.label] || []).push(f);
  const list = Object.entries(groups).sort((a, b) => b[1].length - a[1].length).map(([label, fs]) => `
    <li><b>${esc(label)}</b> (${fs.length}): ${fs.slice(0, 6).map((f, i) => link(f, fs.length > 1 ? String(i + 1) : f.name)).join(', ')}${fs.length > 6 ? ` … +${fs.length - 6}` : ''}</li>`).join('');
  return `<div class="card"><h2>Attachments</h2>
    <div class="kv" style="margin-top:10px">${sldRows}</div>
    <div id="invLocal" style="margin-top:12px"></div>
    <ul class="notes" style="margin-top:12px">${list || '<li class="muted">No files attached to this invoice yet.</li>'}</ul>
  </div>`;
}


// ---------- upload SLD to the invoice ----------
const SLD_KIND_LABEL = { sld_seda: 'SLD for SEDA', sld_engineering: 'SLD for Installation Team' };

function uploadBarHtml(invoiceNumber, pdf, result) {
  const draft = result && result !== 'passed';
  return `<div class="card upbar"><h2>Upload to invoice ${esc(invoiceNumber)}</h2>
    ${draft ? '<div class="issue warning" style="margin-top:8px">This drawing failed the design check (watermarked draft). It can still be uploaded, but check it first.</div>' : ''}
    <div class="btns" style="margin:10px 0 0">
      ${Object.entries(SLD_KIND_LABEL).map(([k, l]) => `<button class="secondary" data-upload="${k}" data-inv="${esc(invoiceNumber)}" data-pdf="${esc(pdf)}">Upload as ${esc(l)}</button>`).join('')}
    </div><div class="upmsg"></div></div>`;
}

function wireUploadButtons(scope) {
  $$('[data-upload]', scope).forEach((b) => b.addEventListener('click', async () => {
    const kind = b.dataset.upload, inv = b.dataset.inv, pdf = b.dataset.pdf;
    const name = pdf.split(/[\\/]/).pop();
    if (!confirm(`Upload ${name}\nto invoice ${inv}\nas "${SLD_KIND_LABEL[kind]}"?\n\nIt will be visible in the ERP.`)) return;
    const msg = b.closest('.card')?.querySelector('.upmsg');
    const all = $$('[data-upload]', b.closest('.card'));
    all.forEach((x) => (x.disabled = true));
    if (msg) msg.innerHTML = '<p class="muted">Uploading…</p>';
    let r;
    try { r = await window.sld.uploadSld({ invoiceNumber: inv, kind, pdfPath: pdf }); }
    catch (e) { r = { ok: false, error: e.message }; }
    all.forEach((x) => (x.disabled = false));
    if (msg) msg.innerHTML = r.ok
      ? `<div class="issue info" style="background:var(--ok-bg);color:var(--ok)"><b>Uploaded</b> as ${esc(r.kind)} to ${esc(r.invoiceNumber)}${r.url ? ` · <a href="#" data-url="${esc(r.url)}">open</a>` : ''}</div>`
      : `<div class="issue ${r.notLive ? 'warning' : 'error'}">${esc(r.error)}</div>`;
    $$('[data-url]', msg || document).forEach((a) => a.addEventListener('click', (ev) => { ev.preventDefault(); window.sld.openFileUrl(a.dataset.url); }));
    if (r.ok && INV.sel === inv && $('#invDetail .reshead')) {
      const row = INV.rows.find((x) => x.invoice_number === inv);
      if (row) openInvoice(row);   // refresh the attachment status
    }
  }));
}

async function showLocalDrawings(invoiceNumber) {
  const box = $('#invLocal');
  if (!box) return;
  let hist = [];
  try { hist = await window.sld.history(); } catch { /* none */ }
  const mine = hist.filter((h) => h.invoice_number === invoiceNumber || h.drawing_no === `SLD-${invoiceNumber}`);
  if (!mine.length) { box.innerHTML = '<p class="muted">No SLD generated for this invoice on this PC yet. Generate it first, then upload.</p>'; return; }
  const h = mine[0];
  box.innerHTML = `<p style="margin:0 0 4px"><b>Latest drawing on this PC:</b> ${esc(h.stem)} ${statusBadge(h.result, h.issues)}${mine.length > 1 ? ` <span class="muted">(${mine.length} revisions)</span>` : ''}</p>
    ${h.files.pdf ? uploadBarHtml(invoiceNumber, h.files.pdf, h.result).replace('class="card upbar"', 'class="upbar"') : '<p class="muted">This drawing has no PDF.</p>'}`;
  wireUploadButtons(box);
}


// ---------- PE drawing (module layout plan) ----------
// Pick a PV drawing on the invoice, trace it with the PE drawing AI, then rebuild the
// sheet with another roof type or rotation without calling the AI again.
const PE_IMG = /\.(png|jpe?g|webp)(\?|$)/i;
const PE_ROT = [['90', 'Turn 90° clockwise'], ['270', 'Turn 90° anticlockwise'], ['0', 'As drawn'], ['180', 'Upside down']];

function pePvDrawings(d) {
  const files = (d.attachments || []).filter((f) => (f.doc_type === 'pv_system' || f.doc_type === 'pv_system_drawing') && PE_IMG.test(f.url));
  return files.sort((a, b) => String(b.uploaded_at || '').localeCompare(String(a.uploaded_at || '')));
}

function peCardHtml(d) {
  const pv = pePvDrawings(d);
  const pick = pv.map((f, i) => `
    <label class="pe-pick"><input type="radio" name="pePv" value="${i}"${i === 0 ? ' checked' : ''}>
      <span class="pe-thumb" data-pe-thumb="${esc(f.url)}"><span class="muted">loading…</span></span>
      <span class="muted">${esc(f.uploaded_at ? day(f.uploaded_at) : (f.source || '').replace('invoice.', ''))}${f.uploaded_by ? ' · ' + esc(f.uploaded_by) : ''}</span></label>`).join('');
  return `<div class="card" id="peCard"><h2>PE drawing (module layout plan)</h2>
    ${pv.length ? `<p class="muted" style="margin:8px 0">PV drawing to trace${pv.length > 1 ? ` (${pv.length} on this invoice, newest first: pick the final one)` : ''}:</p>
      <div class="pe-picks">${pick}</div>`
      : '<div class="issue warning" style="margin-top:10px">This invoice has no PV system drawing image to trace.</div>'}
    <div class="grid3" style="margin-top:10px">
      <label class="field"><span class="lbl">Roof type</span><select id="peRoof">
        <option value="">Let the AI decide</option><option value="tile">Roof tile</option><option value="metal_deck">Metal deck</option></select></label>
      <label class="field"><span class="lbl">Turn the layout</span><select id="peRot">${PE_ROT.map(([v, l]) => `<option value="${v}">${l}</option>`).join('')}</select></label>
      <div class="field"><span class="lbl">&nbsp;</span><div class="row" style="margin:0">
        <button class="primary" id="peTrace"${pv.length ? '' : ' disabled'}>Trace with AI &amp; build</button>
        <button class="ghost" id="peRebuild" hidden>Rebuild</button></div></div>
    </div>
    <div id="peOut" style="margin-top:10px"></div>
  </div>`;
}

function peArgs(d) {
  const f = d.sld?.form || {};
  return { invoiceNumber: d.invoice.invoice_number, clientName: d.customer?.name || f.account_holder || '',
    address: d.invoice.address || f.address || '', module: f.module || '', expected: f.qty ? Number(f.qty) : null,
    roofType: $('#peRoof')?.value || '', rotate: Number($('#peRot')?.value ?? 90) };
}

function peShow(r, d) {
  const out = $('#peOut');
  if (!out) return;
  if (!r || !r.ok) { out.innerHTML = `<div class="issue error">${esc(r?.error || 'PE drawing failed')}</div>`; return; }
  const exp = d.sld?.form?.qty ? Number(d.sld.form.qty) : null;
  const match = exp == null ? '' : (Number(r.modules) === exp ? `<span class="badge b-ok">MATCHES PACKAGE (${exp})</span>`
    : `<span class="badge b-warn">PACKAGE SAYS ${exp}</span>`);
  const notes = [...(r.notes || [])];
  const problems = r.problems || [];
  out.innerHTML = `
    <div class="reshead" style="margin:6px 0 8px"><b>${esc(r.modules)} modules · ${esc(r.kwp)} kWp · ${r.roof_type === 'metal_deck' ? 'Metal deck' : 'Roof tile'}</b> ${match}
      ${problems.length ? `<span class="badge b-warn">${problems.length} TO CHECK</span>` : '<span class="badge b-ok">BUILT</span>'}</div>
    ${r.ai ? `<p class="muted" style="margin:0 0 8px">Traced by ${esc(r.ai.model)} in ${esc(r.ai.seconds)} s${r.ai.stated_module_count ? ` · PV drawing label says ${esc(r.ai.stated_module_count)}` : ''}${r.ai.roof_type ? ` · AI roof guess: ${esc(r.ai.roof_type)}` : ''}</p>` : ''}
    ${[...problems.map((p) => `<div class="issue warning">${esc(p)}</div>`), ...notes.map((n) => `<div class="issue info">${esc(n)}</div>`)].join('')}
    ${r.export_error ? `<div class="issue error">${esc(r.export_error)}</div>` : ''}
    <div class="btns" style="margin-top:8px">
      ${r.files?.pdf ? `<button class="secondary" data-pe-open="${esc(r.files.pdf)}">Open PDF</button>` : ''}
      ${r.files?.pdf || r.files?.svg ? `<button class="ghost" data-pe-folder="${esc(r.files.pdf || r.files.svg)}">Show in folder</button>` : ''}
    </div>
    <div class="pe-compare">
      <div><div class="lbl">PV drawing</div><div class="sheet" id="pePvBig"></div></div>
      <div><div class="lbl">PE drawing</div>${r.files?.png ? `<div class="sheet"><img alt="PE preview" src="${fileUrl(r.files.png)}"></div>` : '<p class="muted">No preview image.</p>'}</div>
    </div>`;
  $$('[data-pe-open]', out).forEach((b) => b.addEventListener('click', () => window.sld.openPath(b.dataset.peOpen)));
  $$('[data-pe-folder]', out).forEach((b) => b.addEventListener('click', () => window.sld.showInFolder(b.dataset.peFolder)));
  const url = r.sourceUrl || pePvDrawings(d)[Number($('#peCard input[name=pePv]:checked')?.value || 0)]?.url;
  if (url) window.sld.peImage(url).then((x) => { const box = $('#pePvBig'); if (box && x.ok) box.innerHTML = `<img alt="PV drawing" src="${x.dataUri}">`; });
  $('#peRebuild').hidden = false;
}

async function wirePeCard(d) {
  const card = $('#peCard');
  if (!card) return;
  const inv = d.invoice.invoice_number;
  $$('[data-pe-thumb]', card).forEach(async (el) => {
    const r = await window.sld.peImage(el.dataset.peThumb).catch((e) => ({ ok: false, error: e.message }));
    if (INV.sel !== inv) return;
    el.innerHTML = r.ok ? `<img alt="PV drawing" src="${r.dataUri}">` : `<span class="issue error">${esc(r.error)}</span>`;
  });
  // an earlier PE for this invoice on this PC
  try {
    const loc = await window.sld.peLocal(inv);
    if (INV.sel !== inv) return;
    if (loc.ok && loc.exists) {
      if (loc.roof_type) $('#peRoof').value = loc.roof_type;
      $('#peRot').value = String(loc.rotate ?? 90);
      const i = pePvDrawings(d).findIndex((f) => f.url === loc.source?.url);
      if (i >= 0) { const r = $(`#peCard input[name=pePv][value="${i}"]`); if (r) r.checked = true; }
      if (loc.files?.png || loc.files?.pdf) {
        peShow({ ok: true, modules: loc.modules, kwp: '', roof_type: loc.roof_type, files: loc.files, problems: [],
          notes: [`Built earlier on this PC${loc.source?.traced ? ' (traced ' + day(loc.source.traced) + ')' : ''}. Trace again or change the roof type / turn, then Rebuild.`],
          sourceUrl: loc.source?.url }, d);
        $('#peOut .reshead').innerHTML = `<b>Earlier PE drawing: ${esc(loc.modules)} modules</b>`;
      }
    }
  } catch { /* nothing earlier */ }

  $('#peTrace').addEventListener('click', async () => {
    const f = pePvDrawings(d)[Number($('#peCard input[name=pePv]:checked')?.value || 0)];
    if (!f) return;
    $('#peTrace').disabled = true; $('#peRebuild').disabled = true;
    $('#peOut').innerHTML = '<p class="muted">Tracing the PV drawing with AI and building the PE sheet… (about 10-40 s)</p>';
    let r;
    try { r = await window.sld.peTrace({ ...peArgs(d), url: f.url }); } catch (e) { r = { ok: false, error: e.message }; }
    $('#peTrace').disabled = false; $('#peRebuild').disabled = false;
    if (INV.sel !== inv) return;
    if (r.ok && !$('#peRoof').value && r.roof_type) $('#peRoof').value = r.roof_type;
    peShow({ ...r, sourceUrl: f.url }, d);
  });
  $('#peRebuild').addEventListener('click', async () => {
    $('#peRebuild').disabled = true;
    let r;
    try { r = await window.sld.peBuild(peArgs(d)); } catch (e) { r = { ok: false, error: e.message }; }
    $('#peRebuild').disabled = false;
    if (INV.sel !== inv) return;
    peShow(r, d);
  });
}
