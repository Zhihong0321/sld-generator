// Invoice lookup against the Eternalgy API gateway (e-api), read-only.
// Every function returns a result object with `notes` for anything that could not be
// read; a missing table or field is labelled, never fatal.

const AGENT_CACHE_MS = 10 * 60 * 1000;
const DETAIL_CONCURRENCY = 4;

const str = (v) => (v == null ? '' : String(v).trim());

// The two SLD kinds this app uploads. Stored in ee_attachment with category "drawing".
const SLD_KINDS = {
  sld_seda: { label: 'SLD for SEDA', doc_type: 'sld_seda' },
  sld_engineering: { label: 'SLD for Engineering Team', doc_type: 'sld_engineering' },
};

// Readable names for the doc types already in use.
const DOC_LABELS = {
  pv_system: 'PV system drawing', roof_angle: 'Roof angle photo', house_db: 'House DB photo', site_other: 'Site photo (other)',
  roof_closeup: 'Roof close-up photo', house_front: 'House front photo', inverter_location: 'Inverter location photo',
  sunpath: 'Sun path', site_video: 'Site video', sld_seda: 'SLD for SEDA', sld_engineering: 'SLD for Engineering Team',
};

// Older file columns still holding links (before ee_attachment existed).
const LEGACY = [
  ['invoice', 'pv_system_drawing', 'PV system drawing (old)'],
  ['invoice', 'linked_roof_image', 'Roof photo (old)'],
  ['invoice', 'site_assessment_image', 'Site photo (old)'],
  ['seda', 'drawing_pdf_system', 'SEDA system drawing (old)'],
  ['seda', 'drawing_engineering_seda_pdf', 'Engineering drawing (old)'],
  ['seda', 'roof_images', 'Roof photo on SEDA form (old)'],
  ['seda', 'site_images', 'Site photo on SEDA form (old)'],
];

function asList(v) {
  if (Array.isArray(v)) return v.filter(Boolean).map(String);
  if (typeof v === 'string' && v.trim()) {
    try { const j = JSON.parse(v); if (Array.isArray(j)) return j.filter(Boolean).map(String); } catch { /* plain url */ }
    return [v.trim()];
  }
  return [];
}
const fixUrl = (u) => (u.startsWith('//') ? 'https:' + u : u);

class InvoiceApi {
  constructor(getConfig) {
    this.getConfig = getConfig;          // () => ({ base, key })
    this.users = null;
    this.usersAt = 0;
  }

  async get(pathAndQuery) {
    const { base, key } = this.getConfig();
    if (!key) { const e = new Error('No e-api key: add it under Settings → Invoices API.'); e.status = 0; throw e; }
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 30000);
    try {
      const r = await fetch(base.replace(/\/+$/, '') + pathAndQuery, { signal: ctrl.signal, headers: { 'x-api-key': key } });
      const text = await r.text();
      let body = null;
      try { body = JSON.parse(text); } catch { /* not json */ }
      if (!r.ok) {
        const e = new Error(`${r.status} ${body?.message || text.slice(0, 160)}`);
        e.status = r.status;
        throw e;
      }
      return body;
    } catch (e) {
      if (e.name === 'AbortError') { const x = new Error('e-api did not answer (timed out)'); x.status = 0; throw x; }
      throw e;
    } finally { clearTimeout(t); }
  }

  async loadUsers() {
    if (this.users && Date.now() - this.usersAt < AGENT_CACHE_MS) return this.users;
    const all = [];
    for (let off = 0; off < 5000; off += 100) {
      const r = await this.get(`/api/data/user?limit=100&offset=${off}`);
      const rows = Array.isArray(r?.data) ? r.data : [];
      all.push(...rows);
      if (rows.length < 100) break;
    }
    this.users = all;
    this.usersAt = Date.now();
    return all;
  }

  async agentName(linkedAgent) {
    if (!linkedAgent) return '';
    try {
      const users = await this.loadUsers();
      const u = users.find((x) => x.linked_agent_profile === linkedAgent || x.bubble_id === linkedAgent);
      return str(u?.name);
    } catch { return ''; }
  }

  rowFromSearch(r, agent = '') {
    return {
      id: r.id, invoice_number: str(r.invoice_number) || String(r.id), invoice_date: r.invoice_date || null,
      status: str(r.status), total_amount: r.total_amount, paid_amount: r.paid_amount,
      customer_name: str(r.customer_name || r.customer_name_snapshot), agent_name: agent,
      address: str(r.customer_address_snapshot),
    };
  }

  // by: 'name' | 'agent' | 'address'
  async search({ by, q, offset = 0, includeDeleted = false }) {
    const query = str(q);
    const notes = [];
    const limit = 50;
    try {
      let rows = [];
      let agents = [];
      if (by === 'agent') {
        const users = await this.loadUsers();
        const needle = query.toLowerCase();
        agents = users.filter((u) => u.linked_agent_profile && str(u.name).toLowerCase().includes(needle)).slice(0, 8);
        if (!agents.length) return { ok: true, rows: [], agents: [], notes: [`No sales agent name contains "${query}".`] };
        for (const a of agents) {
          const r = await this.get(`/api/data/invoice?linked_agent=${encodeURIComponent(a.linked_agent_profile)}&sort=id&order=desc&limit=${limit}&offset=${offset}`);
          rows.push(...(r?.data || []).map((x) => this.rowFromSearch(x, str(a.name))));
        }
        rows.sort((a, b) => (b.id || 0) - (a.id || 0));
        await this.fillCustomerNames(rows);
      } else if (by === 'address') {
        // The CEO key cannot read customer addresses; the invoice address snapshot is the only
        // address field it sees, so scan recent invoices for it and say what was searched.
        const r = await this.get(`/api/data/invoice?sort=id&order=desc&limit=100&offset=${offset}`);
        const needle = query.toLowerCase();
        rows = (r?.data || []).filter((x) => str(x.customer_address_snapshot).toLowerCase().includes(needle)).map((x) => this.rowFromSearch(x));
        await this.fillCustomerNames(rows);
        notes.push('Address search only sees the address copied onto the invoice, and most invoices have none. ' +
          'Full address search needs an e-api key that can read the customer table.');
      } else {
        const r = await this.get(`/api/invoices/search?customer_name=${encodeURIComponent(query)}&limit=${limit}&offset=${offset}`);
        rows = (r?.data || []).map((x) => this.rowFromSearch(x));
      }
      const deleted = rows.filter((x) => x.status === 'deleted').length;
      if (!includeDeleted && deleted) {
        rows = rows.filter((x) => x.status !== 'deleted');
        notes.push(`${deleted} deleted invoice(s) hidden.`);
      }
      return { ok: true, rows, agents: agents.map((a) => str(a.name)), notes, more: rows.length >= limit };
    } catch (e) {
      return { ok: false, rows: [], notes, error: e.message };
    }
  }

  async fillCustomerNames(rows) {
    const todo = rows.filter((r) => !r.customer_name).slice(0, 30);
    let i = 0;
    const worker = async () => {
      while (i < todo.length) {
        const r = todo[i++];
        try {
          const d = await this.get(`/api/invoices/${encodeURIComponent(r.invoice_number || r.id)}`);
          r.customer_name = str(d?.data?.customer?.name);
        } catch { /* leave blank */ }
      }
    };
    await Promise.all(Array.from({ length: DETAIL_CONCURRENCY }, worker));
  }

  // Everything already attached to an invoice: ee_attachment rows plus the older file columns.
  async attachments(inv, sedaRaw) {
    const notes = [];
    let rows = [];
    if (inv?.bubble_id) {
      try {
        const r = await this.get(`/api/data/ee_attachment?owner_type=invoice&owner_id=${encodeURIComponent(inv.bubble_id)}&limit=500`);
        rows = (Array.isArray(r?.data) ? r.data : []).filter((x) => !x.deleted_at);
      } catch (e) { notes.push(`Attachments could not be read: ${e.message}`); }
    }
    const files = rows.map((x) => ({
      source: 'ee_attachment', id: x.id, category: str(x.category), doc_type: str(x.doc_type),
      label: DOC_LABELS[x.doc_type] || `${str(x.category)} / ${str(x.doc_type)}`,
      url: fixUrl(str(x.file_url)), name: str(x.original_filename) || str(x.file_url).split('/').pop(),
      uploaded_at: x.uploaded_at || null, uploaded_by: str(x.uploaded_by_name), caption: str(x.caption),
    }));
    const seen = new Set(files.map((f) => f.url));
    for (const [where, col, label] of LEGACY) {
      const src = where === 'invoice' ? inv : sedaRaw;
      for (const u of asList(src?.[col])) {
        if (seen.has(fixUrl(u))) continue;   // already listed from ee_attachment
        seen.add(fixUrl(u));
        files.push({ source: `${where}.${col}`, category: 'legacy', doc_type: col, label, url: fixUrl(u), name: u.split('/').pop(), uploaded_at: null, uploaded_by: '' });
      }
    }
    const sld = {};
    for (const [k, kind] of Object.entries(SLD_KINDS)) {
      const hits = files.filter((f) => f.doc_type === kind.doc_type).sort((a, b) => String(b.uploaded_at).localeCompare(String(a.uploaded_at)));
      sld[k] = { label: kind.label, uploaded: hits.length > 0, count: hits.length, latest: hits[0] || null };
    }
    return { files, sld, notes };
  }

  // Upload a PDF as one of the SLD kinds. Contract (e-api):
  //   POST /api/attachments/upload  multipart/form-data
  //   file + owner_type, owner_id, linked_customer, module, category, doc_type, caption, uploaded_by_name
  //   -> 201 { data: <ee_attachment row> }
  // No ee_attachment row is ever written without a stored file behind it.
  async uploadSld({ invoiceNumber, kind, pdfPath, uploader }) {
    const fs = require('fs');
    const path = require('path');
    const k = SLD_KINDS[kind];
    if (!k) return { ok: false, error: `Unknown SLD kind "${kind}"` };
    let bytes;
    try { bytes = fs.readFileSync(pdfPath); } catch (e) { return { ok: false, error: `Cannot read ${pdfPath}: ${e.message}` }; }
    let inv;
    try {
      const d = await this.get(`/api/invoices/${encodeURIComponent(invoiceNumber)}`);
      inv = d?.data?.invoice;
    } catch (e) { return { ok: false, error: `Invoice ${invoiceNumber} could not be read: ${e.message}` }; }
    if (!inv?.bubble_id) return { ok: false, error: `Invoice ${invoiceNumber} has no bubble_id to attach to.` };

    const { base, key } = this.getConfig();
    const fd = new FormData();
    fd.append('file', new Blob([bytes], { type: 'application/pdf' }), path.basename(pdfPath));
    const fields = {
      owner_type: 'invoice', owner_id: inv.bubble_id, linked_customer: str(inv.linked_customer),
      module: 'invoice-office', category: 'drawing', doc_type: k.doc_type,
      caption: `${k.label} - ${path.basename(pdfPath)}`, uploaded_by_name: str(uploader) || 'SLD Studio',
    };
    for (const [f, v] of Object.entries(fields)) fd.append(f, v);
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 120000);
    try {
      const r = await fetch(base.replace(/\/+$/, '') + '/api/attachments/upload', { method: 'POST', body: fd, headers: { 'x-api-key': key }, signal: ctrl.signal });
      const text = await r.text();
      let body = null;
      try { body = JSON.parse(text); } catch { /* not json */ }
      if (r.status === 404) {
        return { ok: false, notLive: true, error: 'e-api has no upload route yet (POST /api/attachments/upload returned 404). Nothing was uploaded.' };
      }
      if (!r.ok) return { ok: false, error: `Upload failed: HTTP ${r.status} ${body?.message || text.slice(0, 200)}` };
      const row = body?.data || body || {};
      return { ok: true, row, url: str(row.file_url), kind: k.label, invoiceNumber, size: bytes.length };
    } catch (e) {
      return { ok: false, error: e.name === 'AbortError' ? 'Upload timed out' : `Upload failed: ${e.message}` };
    } finally { clearTimeout(t); }
  }

  async detail(id, hint = {}) {
    const notes = [];
    try {
      const d = await this.get(`/api/invoices/${encodeURIComponent(id)}`);
      const data = d?.data || {};
      const inv = data.invoice || {};
      const customer = data.customer || {};
      const payments = Array.isArray(data.payments) ? data.payments : [];
      const products = Array.isArray(data.products) ? data.products : [];
      const items = Array.isArray(data.invoice_items) ? data.invoice_items : [];
      const sedaRaw = data.seda_registration || null;
      for (const w of d?.warnings || []) notes.push(`e-api: ${String(w)}`);
      const agent = await this.agentName(inv.linked_agent);

      // Package: e-api now returns it with the invoice; older gateways need a separate read.
      let pkg = data.package || null;
      const pkgId = str(inv.linked_package || inv.package_id);
      if (!pkg && pkgId) {
        try {
          const p = await this.get(`/api/data/package/${encodeURIComponent(pkgId)}`);
          pkg = p?.data || p || null;
        } catch (e) {
          notes.push(e.status === 403
            ? `Package ${pkgId} could not be read: the e-api key has no access to the package table.`
            : `Package ${pkgId} could not be read: ${e.message}`);
        }
      } else if (!pkgId) notes.push('This invoice has no linked package.');

      // Only the SEDA fields the drawing needs (the record also holds IC numbers and documents).
      const seda = sedaRaw ? {
        phase_type: str(sedaRaw.phase_type), installation_address: str(sedaRaw.installation_address),
        tnb_account_no: str(sedaRaw.tnb_account_no), city: str(sedaRaw.city), state: str(sedaRaw.state),
        seda_status: str(sedaRaw.seda_status),
      } : null;
      if (!seda && inv.linked_seda_registration) notes.push('SEDA registration was not returned, so supply phase and address come from the package only.');

      const att = await this.attachments(inv, sedaRaw);
      notes.push(...att.notes);
      const name = str(customer.name) || str(inv.customer_name_snapshot) || str(hint.customer_name);
      if (!str(customer.name) && name) notes.push('Customer name taken from the invoice list (customer record not returned).');

      return {
        ok: true,
        invoice: {
          id: inv.id, invoice_number: str(inv.invoice_number) || String(inv.id), status: str(inv.status),
          invoice_date: inv.invoice_date, total_amount: inv.total_amount, paid_amount: inv.paid_amount,
          panel_qty: inv.panel_qty ?? null, panel_rating: inv.panel_rating ?? null,
          package_id: pkgId, package_name: str(pkg?.package_name || inv.package_name_snapshot), package_type: str(pkg?.type || inv.package_type),
          address: str(seda?.installation_address || inv.customer_address_snapshot), agent_name: agent,
          seda_registration: str(inv.linked_seda_registration),
        },
        customer: { id: str(customer.customer_id || inv.linked_customer), name },
        payments_count: payments.length,
        package: pkg, products, items, seda,
        attachments: att.files, sld_uploads: att.sld,
        owner: { owner_type: 'invoice', owner_id: str(inv.bubble_id), linked_customer: str(inv.linked_customer) },
        notes,
      };
    } catch (e) {
      return { ok: false, error: e.message, notes };
    }
  }
}

module.exports = { InvoiceApi, SLD_KINDS };
