// PE drawing (module layout plan) for an invoice: fetch the invoice's roof PV drawing,
// trace it with a vision model (Lingsuan, OpenAI Responses API) into module rectangles and
// roof outlines, write projects/PE-<invoice>.json and let `sldgen pe` draw it.
// Every function returns a result object; problems are reported, never thrown to the UI.

const fs = require('fs');
const path = require('path');

const str = (v) => (v == null ? '' : String(v).trim());
const numOr = (v, d) => (Number.isFinite(Number(v)) ? Number(v) : d);

const TRACE_PROMPT = `You trace a solar PV roof layout drawing (an aerial roof photo with solar module rectangles drawn on it, usually with white outlines around roof areas) into JSON for a CAD redraw.

Return ONLY this JSON object, all coordinates in image pixels (origin top-left, y down):
{
  "modules": [[x, y, w, h], ...],
  "outlines": [ {"points": [[x, y], ...]} ],
  "stated_module_count": <number shown in a "PV MODULES n/n" label, or null>,
  "roof_type": "tile" | "metal_deck" | "unknown",
  "notes": [string]
}

- "modules": EVERY solar module rectangle drawn on the roof, one entry each. For a tilted module give its axis-aligned bounding box.
- "outlines": the roof edge outlines (white line polygons), ridge or hip lines (2-point lines) and boxes around obstructions (water heater, skylight, AC units) that modules avoid. Keep it simple: 1 to 8 entries.
- "roof_type": clay or concrete roof tiles = "tile"; corrugated metal sheet roof = "metal_deck".
- Count modules carefully, row by row. Do not count the dark info bar at the bottom, or existing panels / water heaters.
- Modules in the same row share the same y and h; modules in the same column share the same x and w.`;

function guessType(buf, url) {
  if (buf.length > 4 && buf[0] === 0x89 && buf[1] === 0x50) return 'image/png';
  if (buf.length > 3 && buf[0] === 0xff && buf[1] === 0xd8) return 'image/jpeg';
  if (buf.length > 12 && buf.toString('ascii', 8, 12) === 'WEBP') return 'image/webp';
  const ext = String(url).split('?')[0].split('.').pop().toLowerCase();
  return { png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg', webp: 'image/webp' }[ext] || 'image/png';
}

async function fetchImage(url) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 60000);
  try {
    const r = await fetch(url, { signal: ctrl.signal, headers: { 'User-Agent': 'sld-studio' } });
    if (!r.ok) return { ok: false, error: `Download failed: HTTP ${r.status}` };
    const buf = Buffer.from(await r.arrayBuffer());
    const type = guessType(buf, url);
    return { ok: true, dataUri: `data:${type};base64,${buf.toString('base64')}`, bytes: buf.length, type };
  } catch (e) {
    return { ok: false, error: e.name === 'AbortError' ? 'Download timed out' : `Download failed: ${e.message}` };
  } finally { clearTimeout(t); }
}

function extractJson(text) {
  const t = String(text || '');
  try { return JSON.parse(t); } catch { /* fall through */ }
  const m = t.match(/\{[\s\S]*\}/);
  if (m) { try { return JSON.parse(m[0]); } catch { /* ignore */ } }
  return null;
}

function responseText(d) {
  if (typeof d?.output_text === 'string' && d.output_text) return d.output_text;
  const parts = [];
  for (const o of Array.isArray(d?.output) ? d.output : []) {
    if (o?.type !== 'message') continue;
    for (const c of Array.isArray(o.content) ? o.content : []) if (typeof c?.text === 'string') parts.push(c.text);
  }
  return parts.join('');
}

// cfg: { base, model, key, effort }
async function traceImage(dataUri, cfg) {
  if (!cfg.key) return { ok: false, error: 'No PE drawing AI key: add it under Settings → PE drawing AI.' };
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 240000);
  const started = Date.now();
  try {
    const r = await fetch(cfg.base.replace(/\/+$/, '') + '/responses', {
      method: 'POST', signal: ctrl.signal,
      headers: {
        Authorization: `Bearer ${cfg.key}`, 'Content-Type': 'application/json', 'User-Agent': 'sld-studio',
        'x-openai-actor-authorization': 'local-image-extension',
      },
      body: JSON.stringify({
        model: cfg.model, reasoning: { effort: cfg.effort || 'medium' },
        instructions: TRACE_PROMPT,
        input: [{ role: 'user', content: [
          { type: 'input_text', text: 'Trace this PV layout drawing.' },
          { type: 'input_image', image_url: dataUri },
        ] }],
      }),
    });
    const body = await r.text();
    if (!r.ok) return { ok: false, error: `${cfg.model}: HTTP ${r.status} ${body.slice(0, 200)}` };
    let d = null;
    try { d = JSON.parse(body); } catch { return { ok: false, error: `${cfg.model}: reply was not JSON` }; }
    const trace = extractJson(responseText(d));
    if (!trace) return { ok: false, error: `${cfg.model}: the answer had no layout JSON`, raw: responseText(d).slice(0, 500) };
    return { ok: true, trace, model: d.model || cfg.model, seconds: Math.round((Date.now() - started) / 100) / 10, tokens: d.usage?.total_tokens ?? null };
  } catch (e) {
    return { ok: false, error: e.name === 'AbortError' ? `${cfg.model}: timed out` : `${cfg.model}: ${e.message}` };
  } finally { clearTimeout(t); }
}

// Pixel trace -> PE layout in module units (1 = module short side). Never throws.
function traceToLayout(trace) {
  const notes = [];
  const rects = (Array.isArray(trace?.modules) ? trace.modules : [])
    .map((m) => (Array.isArray(m) ? m : [m?.x, m?.y, m?.w, m?.h]).map(Number))
    .filter((m) => m.length >= 4 && m.every(Number.isFinite) && m[2] > 0 && m[3] > 0);
  const dropped = (Array.isArray(trace?.modules) ? trace.modules.length : 0) - rects.length;
  if (dropped > 0) notes.push(`${dropped} module entr${dropped === 1 ? 'y' : 'ies'} from the AI could not be read and were left out.`);
  const shorts = rects.map((m) => Math.min(m[2], m[3])).sort((a, b) => a - b);
  const u = shorts.length ? shorts[Math.floor(shorts.length / 2)] : 1;
  const r3 = (v) => Math.round(v / u * 1000) / 1000;
  // The AI's pixel positions jitter by a few pixels: snap left edges that are within a
  // quarter module of each other to their average, and the same for top edges.
  const snap = (vals) => {
    const order = vals.map((v, i) => [v, i]).sort((a, b) => a[0] - b[0]);
    const out = vals.slice();
    let group = [];
    const flush = () => { const avg = group.reduce((s, [v]) => s + v, 0) / group.length; for (const [, i] of group) out[i] = avg; group = []; };
    for (const [v, i] of order) { if (group.length && v - group[group.length - 1][0] > 0.25 * u) flush(); group.push([v, i]); }
    if (group.length) flush();
    return out;
  };
  const xs = snap(rects.map((m) => m[0])), ys = snap(rects.map((m) => m[1]));
  const modules = rects.map((m, i) => ({ rect: [r3(xs[i]), r3(ys[i]), r3(m[2]), r3(m[3])] }));
  const outlines = [];
  for (const o of Array.isArray(trace?.outlines) ? trace.outlines : []) {
    const pts = (Array.isArray(o?.points) ? o.points : Array.isArray(o) ? o : [])
      .map((p) => [Number(p?.[0]), Number(p?.[1])]).filter((p) => p.every(Number.isFinite));
    if (pts.length >= 2) outlines.push({ points: pts.map(([x, y]) => [r3(x), r3(y)]) });
  }
  return { layout: { outlines, modules }, count: modules.length, notes };
}

// Write projects/PE-<invoice>.json (keeping the earlier trace) and return its path.
function writePeProject(dir, a) {
  const inv = str(a.invoiceNumber) || 'NO-INVOICE';
  const file = path.join(dir, `PE-${inv.replace(/[\\/:*?"<>|\s]+/g, '-')}.json`);
  let prev = {};
  try { prev = JSON.parse(fs.readFileSync(file, 'utf8')); } catch { /* new */ }
  const p = {
    drawing: 'pe',
    project: {
      client_name: str(a.clientName), address: str(a.address),
      drawing_no: `PE-${inv}`, revision: str(prev?.project?.revision) || '00',
      date: new Date().toISOString().slice(0, 10), drawn_by: '', approved_by: '',
      invoice_number: inv,
    },
    pv_module: str(a.module) || prev.pv_module || '',
    roof_type: str(a.roofType) || prev.roof_type || 'tile',
    expected_modules: a.expected ?? prev.expected_modules ?? null,
    layout: { ...(a.layout || prev.layout || {}), rotate: numOr(a.rotate, numOr(prev?.layout?.rotate, 90)) },
    source: a.source || prev.source || null,
  };
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(file, JSON.stringify(p, null, 2) + '\n', 'utf8');
  return file;
}

module.exports = { fetchImage, traceImage, traceToLayout, writePeProject, TRACE_PROMPT };
