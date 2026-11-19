// SLD Studio - Electron main process.
// Bridges the renderer to the Python engine (`python -m sldgen ...`) and to the LLM.
// Rule: every handler returns a result object; nothing throws to the UI, and a problem
// is reported next to the output instead of hiding it.

const { app, BrowserWindow, ipcMain, shell } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');
const { Updater, REPO_URL } = require('./updater');

const ROOT = path.resolve(__dirname, '..');            // repo root (holds sldgen/, library/, projects/, output/)
const PROJECTS = path.join(ROOT, 'projects');
const OUTPUT = path.join(ROOT, 'output');
const TEMPLATE = path.join(ROOT, 'templates', 'project.json');
const VAULT = 'D:\\Tools\\my-vault\\vault.json';
const VAULT_ENTRY = 'VECTIDE_DEEPSEEK_KEY';
const DEFAULT_MODELS = ['deepseek-v4.1-flash', 'deepseek-v4-flash-0731'];

// ---------- settings ----------
function settingsPath() { return path.join(app.getPath('userData'), 'settings.json'); }

function readJson(file, fallback) {
  try { return JSON.parse(fs.readFileSync(file, 'utf8')); } catch { return fallback; }
}

function vaultLlm() {
  const v = readJson(VAULT, null);
  const find = (x) => {
    if (Array.isArray(x)) { for (const y of x) { const r = find(y); if (r) return r; } }
    else if (x && typeof x === 'object') {
      if (x.name === VAULT_ENTRY) return x;
      for (const y of Object.values(x)) { const r = find(y); if (r) return r; }
    }
    return null;
  };
  const e = v ? find(v) : null;
  return e ? { baseUrl: String(e.baseUrl || ''), apiKey: String(e.secret || '') } : { baseUrl: '', apiKey: '' };
}

function getSettings() {
  const saved = readJson(settingsPath(), {});
  const vault = vaultLlm();
  return {
    python: saved.python || 'python',
    baseUrl: saved.baseUrl || vault.baseUrl || 'https://vectide.cn/v1',
    model: saved.model || DEFAULT_MODELS[0],
    apiKey: saved.apiKey || vault.apiKey,
    keySource: saved.apiKey ? 'settings' : (vault.apiKey ? `vault (${VAULT_ENTRY})` : 'none'),
  };
}

// ---------- python engine ----------
function runSldgen(args) {
  const { python } = getSettings();
  return new Promise((resolve) => {
    let out = '', err = '';
    let child;
    try {
      child = spawn(python, ['-m', 'sldgen', ...args], {
        cwd: ROOT, env: { ...process.env, PYTHONIOENCODING: 'utf-8' }, windowsHide: true,
      });
    } catch (e) {
      return resolve({ code: -1, data: null, stderr: String(e) });
    }
    child.stdout.on('data', (d) => (out += d));
    child.stderr.on('data', (d) => (err += d));
    child.on('error', (e) => resolve({ code: -1, data: null, stderr: `Cannot start "${python}": ${e.message}` }));
    child.on('close', (code) => {
      let data = null;
      try { data = JSON.parse(out); } catch { /* keep raw text */ }
      resolve({ code, data, stdout: out, stderr: err });
    });
  });
}

// ---------- project file ----------
const num = (v, d) => (Number.isFinite(Number(v)) && String(v).trim() !== '' ? Number(v) : d);
const str = (v) => (v == null ? '' : String(v).trim());

function stamp() {
  const d = new Date(), p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}`;
}

function safeName(s) { return str(s).replace(/[\\/:*?"<>|]+/g, '-').replace(/\s+/g, '-'); }

function evenSplit(total, mppts) {
  const n = Math.max(1, Math.floor(total)), m = Math.max(1, Math.min(Math.floor(mppts) || 1, n));
  const base = Math.floor(n / m), extra = n % m;
  return Array.from({ length: m }, (_, i) => base + (i < extra ? 1 : 0));
}

function buildProject(form, library) {
  const p = readJson(TEMPLATE, {});
  const f = form || {};
  const inv = (library?.inverter || {})[str(f.inverter).toLowerCase()] || {};
  p.project = p.project || {};
  Object.assign(p.project, {
    account_holder: str(f.account_holder), address: str(f.address), tnb_account_no: str(f.tnb_account_no),
    drawing_no: safeName(f.drawing_no) || `ATAP-SLD-${stamp()}`, revision: str(f.revision) || '01',
    date: new Date().toISOString().slice(0, 10), drawn_by: str(f.drawn_by),
  });
  p.supply = { phase: Number(f.phase) === 1 ? 1 : 3 };
  p.pv_module = str(f.module);
  p.inverter = str(f.inverter);
  let counts = str(f.strings).split(/[,\s+]+/).map((x) => parseInt(x, 10)).filter((x) => x > 0);
  const qty = num(f.qty, 0);
  if (!counts.length) counts = evenSplit(qty, inv.mppt_count || 2);
  p.array = { strings: counts.map((n, i) => ({ mppt: i + 1, modules: n })) };
  p.cables = { dc_length_m: num(f.dc_length_m, 20), ac_length_m: num(f.ac_length_m, 15) };
  p.pcc = p.pcc || {};
  p.pcc.main_switch_a = num(f.main_switch_a, 63);
  p.pcc.main_rcd_a = num(f.main_rcd_a, 63);
  p.pcc.main_rcd_ma = num(f.main_rcd_ma, 100);
  p.people = p.people || {};
  for (const k of ['qp_name', 'qp_cert_no', 'rpvsp', 'cp_name', 'cp_category', 'cp_cert_no', 'contractor_reg_no']) {
    p.people[k] = str(f[k]);
  }
  const notes = [];
  if (!str(f.strings)) notes.push(`String layout not given: split ${qty} modules as ${counts.join(' + ')} (one string per MPPT).`);
  if (str(f.dc_length_m) === '') notes.push('DC run length not given: used 20 m.');
  if (str(f.ac_length_m) === '') notes.push('AC run length not given: used 15 m.');
  const total = counts.reduce((a, b) => a + b, 0);
  if (qty && total !== qty) notes.push(`String layout has ${total} modules but quantity says ${qty}; the drawing uses the string layout (${total}).`);
  return { project: p, notes };
}

// Keep earlier revisions: if this drawing no + revision already exists, move to the next free revision.
function freeRevision(dn, rev) {
  let r = rev, bumped = false;
  const exists = (x) => fs.existsSync(path.join(PROJECTS, `${dn}_Rev${x}.json`)) ||
    fs.existsSync(path.join(OUTPUT, dn, `${dn}_Rev${x}.svg`));
  while (exists(r)) {
    const n = parseInt(r, 10);
    r = String((Number.isFinite(n) ? n : 0) + 1).padStart(Math.max(2, r.length), '0');
    bumped = true;
  }
  return { rev: r, bumped };
}

// ---------- IPC ----------
ipcMain.handle('library', async () => {
  const r = await runSldgen(['library', '--json']);
  return r.data ? { ok: true, library: r.data } : { ok: false, error: r.stderr || r.stdout || 'library read failed', library: { pv_module: {}, inverter: {} } };
});

ipcMain.handle('generate', async (_e, form) => {
  const log = [];
  try {
    const lib = (await runSldgen(['library', '--json'])).data || {};
    const { project, notes } = buildProject(form, lib);
    const dn = project.project.drawing_no;
    const { rev, bumped } = freeRevision(dn, project.project.revision);
    if (bumped) notes.push(`Rev ${project.project.revision} of ${dn} already exists, so this one is saved as Rev ${rev}.`);
    project.project.revision = rev;
    fs.mkdirSync(PROJECTS, { recursive: true });
    const projFile = path.join(PROJECTS, `${dn}_Rev${rev}.json`);
    fs.writeFileSync(projFile, JSON.stringify(project, null, 2) + '\n', 'utf8');

    const check = await runSldgen(['check', projFile, '--json']);
    const checkResult = check.data?.result || 'error';
    if (checkResult === 'incomplete') {
      return { ok: false, result: 'incomplete', problems: check.data.problems || [], notes, projectFile: projFile };
    }
    // Always produce a drawing. A failed design check gives a watermarked
    // "DESIGN CHECK FAILED" draft with the errors listed, never no output.
    const args = ['build', projFile, '--json'];
    if (checkResult !== 'passed') args.push('--force');
    const build = await runSldgen(args);
    const data = build.data || {};
    if (!build.data) log.push(build.stderr || build.stdout || `build exited with code ${build.code}`);
    const record = {
      drawing_no: dn, revision: rev, created: new Date().toISOString(),
      result: data.result || 'error', summary: data.summary || check.data?.summary || null,
      issues: data.issues || check.data?.issues || [], files: data.files || {}, notes,
      error: data.error || null, customer: project.project.account_holder, project_file: projFile,
    };
    try {
      const outDir = path.join(OUTPUT, dn);
      fs.mkdirSync(outDir, { recursive: true });
      fs.writeFileSync(path.join(outDir, `${dn}_Rev${rev}_job.json`), JSON.stringify(record, null, 2), 'utf8');
    } catch (e) { log.push(`Could not save job record: ${e.message}`); }
    return { ok: true, ...record, log };
  } catch (e) {
    return { ok: false, result: 'error', error: String(e?.message || e), log };
  }
});

ipcMain.handle('history', async () => {
  const items = [];
  let dirs = [];
  try { dirs = fs.readdirSync(OUTPUT, { withFileTypes: true }).filter((d) => d.isDirectory()); } catch { return items; }
  for (const d of dirs) {
    const dir = path.join(OUTPUT, d.name);
    let files = [];
    try { files = fs.readdirSync(dir); } catch { continue; }
    for (const svg of files.filter((f) => f.toLowerCase().endsWith('.svg'))) {
      const stem = svg.slice(0, -4);
      const has = (suffix) => (files.includes(stem + suffix) ? path.join(dir, stem + suffix) : null);
      const job = readJson(path.join(dir, `${stem}_job.json`), null);
      const m = stem.match(/^(.*)_Rev(.+)$/);
      let mtime = 0;
      try { mtime = fs.statSync(path.join(dir, svg)).mtimeMs; } catch { /* ignore */ }
      let projectFile = job?.project_file && fs.existsSync(job.project_file) ? job.project_file : null;
      if (!projectFile) {
        const guess = [path.join(PROJECTS, `${stem}.json`), path.join(PROJECTS, `${d.name}.json`),
          path.join(ROOT, 'examples', `${d.name}.json`)].find((x) => fs.existsSync(x));
        projectFile = guess || null;
      }
      const proj = projectFile ? readJson(projectFile, null) : null;
      items.push({
        folder: dir, stem, drawing_no: m ? m[1] : stem, revision: m ? m[2] : '',
        customer: job?.customer ?? proj?.project?.account_holder ?? '',
        result: job?.result || null, summary: job?.summary || null, issues: job?.issues || [], notes: job?.notes || [],
        created: job?.created || (mtime ? new Date(mtime).toISOString() : ''), mtime,
        files: { svg: path.join(dir, svg), pdf: has('.pdf'), png: has('_preview.png'), report: has('_design-report.md') },
        project_file: projectFile,
      });
    }
  }
  items.sort((a, b) => b.mtime - a.mtime);
  return items;
});

ipcMain.handle('load-project', async (_e, file) => {
  const p = readJson(file, null);
  return p ? { ok: true, project: p } : { ok: false, error: `Cannot read ${file}` };
});

ipcMain.handle('open-path', async (_e, p) => {
  if (!p || !fs.existsSync(p)) return { ok: false, error: `Not found: ${p}` };
  const err = await shell.openPath(p);
  return { ok: !err, error: err || null };
});
ipcMain.handle('show-in-folder', async (_e, p) => { if (p) shell.showItemInFolder(p); return { ok: true }; });
ipcMain.handle('read-text', async (_e, p) => {
  try { return { ok: true, text: fs.readFileSync(p, 'utf8') }; } catch (e) { return { ok: false, error: e.message, text: '' }; }
});

ipcMain.handle('settings:get', async () => {
  const s = getSettings();
  return { ...s, apiKey: s.apiKey ? `${s.apiKey.slice(0, 4)}…${s.apiKey.slice(-4)}` : '', hasKey: !!s.apiKey };
});
ipcMain.handle('settings:save', async (_e, patch) => {
  const saved = readJson(settingsPath(), {});
  for (const k of ['python', 'baseUrl', 'model', 'apiKey']) {
    if (patch && typeof patch[k] === 'string') {
      if (patch[k].trim() === '') delete saved[k]; else saved[k] = patch[k].trim();
    }
  }
  try { fs.mkdirSync(path.dirname(settingsPath()), { recursive: true }); fs.writeFileSync(settingsPath(), JSON.stringify(saved, null, 2)); }
  catch (e) { return { ok: false, error: e.message }; }
  return { ok: true };
});

// ---------- LLM intake ----------
function libraryForPrompt(lib) {
  const mods = Object.entries(lib?.pv_module || {}).map(([k, e]) => `${k}: ${e.brand} ${e.model} ${e.wattage_wp} Wp`);
  const invs = Object.entries(lib?.inverter || {}).map(([k, e]) =>
    `${k}: ${e.brand} ${e.model} ${e.phase}-phase ${e.rated_ac_kw} kW, ${e.mppt_count} MPPT`);
  return `PV MODULES (key: description)\n${mods.join('\n')}\n\nINVERTERS (key: description)\n${invs.join('\n')}`;
}

const SYSTEM_PROMPT = `You read job details for a Malaysian Solar ATAP residential solar PV installation
(WhatsApp messages, quotations, TNB bill text, notes) and return ONLY a JSON object with these keys.
Use null for anything the text does not state. Never guess names, addresses, account numbers or
certificate numbers. Never compute breaker, RCD, isolator, SPD, fuse or cable ratings.

{
  "phase": 1 | 3 | null,                 // single-phase 230 V = 1, three-phase 400 V = 3
  "module": "<library key>" | null,      // ONLY a key from the library list below
  "qty": <number of panels> | null,
  "inverter": "<library key>" | null,    // ONLY a key from the library list below, exact size
  "strings": "9,8" | null,               // modules per string, MPPT order, only if the text states it
  "dc_length_m": number | null, "ac_length_m": number | null,
  "main_switch_a": number | null, "main_rcd_a": number | null, "main_rcd_ma": number | null,
  "account_holder": string | null, "address": string | null, "tnb_account_no": string | null,
  "drawing_no": string | null, "drawn_by": string | null,
  "qp_name": string | null, "qp_cert_no": string | null, "rpvsp": string | null,
  "cp_name": string | null, "cp_category": string | null, "cp_cert_no": string | null,
  "contractor_reg_no": string | null,
  "unmatched": [string],   // panel/inverter models mentioned that are NOT in the library, or ambiguous ones
  "notes": [string]        // short notes: assumptions made, e.g. "assumed SAJ R6-10K-T2 from '10kW SAJ'"
}

If a model in the text is close to a library entry but not certain, still fill the key and add a note.
If the inverter phase contradicts the stated supply, keep the stated supply and add a note.`;

function extractJson(text) {
  const t = String(text || '');
  try { return JSON.parse(t); } catch { /* fall through */ }
  const m = t.match(/\{[\s\S]*\}/);
  if (m) { try { return JSON.parse(m[0]); } catch { /* ignore */ } }
  return null;
}

ipcMain.handle('llm:parse', async (_e, text) => {
  const s = getSettings();
  if (!s.apiKey) return { ok: false, error: 'No API key: add one in Settings or the vault entry ' + VAULT_ENTRY };
  const lib = (await runSldgen(['library', '--json'])).data || {};
  const models = [s.model, ...DEFAULT_MODELS.filter((m) => m !== s.model)];
  const errors = [];
  for (const model of models) {
    try {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 90000);
      const r = await fetch(s.baseUrl.replace(/\/+$/, '') + '/chat/completions', {
        method: 'POST', signal: ctrl.signal,
        headers: { Authorization: `Bearer ${s.apiKey}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model, temperature: 0, response_format: { type: 'json_object' },
          messages: [
            { role: 'system', content: SYSTEM_PROMPT + '\n\n' + libraryForPrompt(lib) },
            { role: 'user', content: String(text || '') },
          ],
        }),
      });
      clearTimeout(timer);
      const body = await r.text();
      if (!r.ok) { errors.push(`${model}: HTTP ${r.status} ${body.slice(0, 160)}`); continue; }
      const content = JSON.parse(body)?.choices?.[0]?.message?.content;
      const fields = extractJson(content);
      if (!fields) { errors.push(`${model}: reply was not JSON`); continue; }
      // Drop keys that are not in the library instead of passing them on.
      const notes = Array.isArray(fields.notes) ? fields.notes.map(String) : [];
      for (const [k, kind] of [['module', 'pv_module'], ['inverter', 'inverter']]) {
        if (fields[k] && !(lib?.[kind] || {})[String(fields[k]).toLowerCase()]) {
          notes.push(`AI suggested ${k} "${fields[k]}", which is not in the library; left blank.`);
          fields[k] = null;
        }
      }
      return { ok: true, model, fields, notes, unmatched: Array.isArray(fields.unmatched) ? fields.unmatched.map(String) : [] };
    } catch (e) {
      errors.push(`${model}: ${e.name === 'AbortError' ? 'timed out' : e.message}`);
    }
  }
  return { ok: false, error: errors.join(' | ') };
});

// ---------- OTA update from GitHub ----------
const updater = new Updater(ROOT);
let mainWin = null;
const UPDATE_EVERY_MS = 6 * 60 * 60 * 1000;

function sendUpdate(payload) {
  try { if (mainWin && !mainWin.isDestroyed()) mainWin.webContents.send('update:status', payload); } catch { /* window gone */ }
}

async function checkForUpdate() {
  const r = await updater.check();
  sendUpdate({ type: 'check', ...r });
  return r;
}

ipcMain.handle('update:check', () => checkForUpdate());
ipcMain.handle('update:apply', async () => {
  const r = await updater.apply((msg) => sendUpdate({ type: 'progress', msg }));
  sendUpdate({ type: 'applied', ...r });
  return r;
});
ipcMain.handle('update:restart', () => { app.relaunch(); app.exit(0); });
ipcMain.handle('app:version', async () => {
  const v = await updater.localVersion();
  let pkg = {};
  try { pkg = JSON.parse(fs.readFileSync(path.join(__dirname, 'package.json'), 'utf8')); } catch { /* ignore */ }
  return { version: pkg.version || '', sha: v.sha, mode: v.mode, repo: REPO_URL, root: ROOT, last: updater.last };
});
ipcMain.handle('open-external', (_e, url) => { if (/^https:\/\/github\.com\//.test(String(url))) shell.openExternal(url); });

// ---------- window ----------
function createWindow() {
  const win = mainWin = new BrowserWindow({
    width: 1400, height: 900, minWidth: 1000, minHeight: 640,
    title: 'SLD Studio', backgroundColor: '#f4f5f7',
    webPreferences: { preload: path.join(__dirname, 'preload.js'), contextIsolation: true, nodeIntegration: false },
  });
  win.setMenuBarVisibility(false);
  win.loadFile(path.join(__dirname, 'renderer', 'index.html'));
  win.webContents.once('did-finish-load', () => setTimeout(checkForUpdate, 3000));
}
setInterval(checkForUpdate, UPDATE_EVERY_MS);

app.whenReady().then(createWindow);
app.on('window-all-closed', () => app.quit());
