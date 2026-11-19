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
    ['DC isolator / SPD', `${s.dc_isolator} · Ucpv ${s.dc_spd_ucpv_v} V${s.string_fuse_a ? ` · string fuses ${s.string_fuse_a} A` : ''}`],
    ['AC MCB / RCD', `${s.ac_mcb} · ${s.ac_rcd}`],
    ['AC isolator', s.ac_isolator],
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
    ${preview ? `<div class="sheet"><img alt="SLD preview" src="${fileUrl(preview)}"></div>` : ''}
    ${summaryHtml(r.summary)}
    ${issuesHtml(r.issues, r.notes, r.problems)}`;
  $$('[data-open]', el).forEach((b) => b.addEventListener('click', async () => {
    const res = await window.sld.openPath(b.dataset.open);
    if (!res.ok) alert(res.error);
  }));
  $$('[data-folder]', el).forEach((b) => b.addEventListener('click', () => window.sld.showInFolder(b.dataset.folder)));
  $$('[data-revise]', el).forEach((b) => b.addEventListener('click', () => reviseFrom(b.dataset.revise, b.dataset.rev)));
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
async function loadSettings() {
  const s = await window.sld.getSettings();
  $('#sBase').value = s.baseUrl || ''; $('#sModel').value = s.model || ''; $('#sPython').value = s.python || '';
  $('#sEapiBase').value = s.eapiBase || ''; $('#sEapiKey').value = '';
  $('#sEapiKey').placeholder = s.hasEapiKey ? `in use: ${s.eapiKey}` : 'not set: needed for the Invoices page';
  $('#sKey').value = ''; $('#sKey').placeholder = s.hasKey ? `in use: ${s.apiKey}` : 'none';
  $('#sKeySource').textContent = `Key source: ${s.keySource}`;
}
$('#saveSettings').addEventListener('click', async () => {
  const patch = { baseUrl: $('#sBase').value, model: $('#sModel').value, python: $('#sPython').value };
  if ($('#sKey').value.trim()) patch.apiKey = $('#sKey').value;
  patch.eapiBase = $('#sEapiBase').value;
  if ($('#sEapiKey').value.trim()) patch.eapiKey = $('#sEapiKey').value;
  const r = await window.sld.saveSettings(patch);
  $('#sStatus').textContent = r.ok ? 'Saved.' : 'Save failed: ' + r.error;
  loadSettings(); loadLibrary();
});

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

window.sld.onUpdate((s) => {
  UP.state = s;
  drawUpdateCard();
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
    if (!r.ok) { $('#invStatus').innerHTML = `<div class="issue error">Search failed: ${esc(r.error)}</div>`; return; }
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
    ${allNotes.length ? `<div class="card"><h2>Notes</h2><div style="margin-top:10px">${allNotes.map((n) => `<div class="issue warning">${esc(n)}</div>`).join('')}</div></div>` : ''}
    ${d.package ? `<details class="card"><summary><h2>Package record</h2></summary><pre class="report">${esc(JSON.stringify(d.package, null, 2))}</pre></details>` : ''}`;
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
