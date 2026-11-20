// SLD Studio settings: what the user types is stored, and the app uses what is stored.
//
// - Loaded once at start and kept in memory. A failed disk read can never make a key vanish.
// - Every save writes a temp file and swaps it in (atomic), after keeping settings.json.bak.
// - A settings file that cannot be read is copied aside and the backup is used; it is never
//   silently replaced by empty settings.

const fs = require('fs');
const path = require('path');

const DEFAULTS = {
  python: 'python',
  baseUrl: 'https://vectide.cn/v1', model: 'deepseek-v4.1-flash', apiKey: '',
  eapiBase: 'https://e-api.up.railway.app', eapiKey: '', uploaderName: '',
  peBase: 'https://api.lingsuan.si/v1', peModel: 'gpt-6.1-terra', peEffort: 'medium', peKey: '',
};
const FIELDS = Object.keys(DEFAULTS);

class SettingsStore {
  constructor(dir) {
    this.dir = dir;
    this.file = path.join(dir, 'settings.json');
    this.bak = this.file + '.bak';
    this.data = {};
    this.problem = null;
    this.load();
  }

  readFile(f) {
    const text = fs.readFileSync(f, 'utf8').replace(/^﻿/, '');
    const j = JSON.parse(text);
    if (!j || typeof j !== 'object' || Array.isArray(j)) throw new Error('not a settings object');
    return j;
  }

  load() {
    for (const f of [this.file, this.bak]) {
      if (!fs.existsSync(f)) continue;
      try {
        this.data = this.readFile(f);
        if (f === this.bak) this.problem = `${path.basename(this.file)} could not be read, so the backup was used.`;
        return;
      } catch (e) {
        this.problem = `${path.basename(f)} could not be read (${e.message}); a copy was kept beside it.`;
        try { fs.copyFileSync(f, `${f}.unreadable-${Date.now()}`); } catch { /* keep going */ }
      }
    }
  }

  // Fill a key that was never set (not one the user cleared) from another source, once.
  seed(values) {
    let changed = false;
    for (const [k, v] of Object.entries(values || {})) {
      if (FIELDS.includes(k) && this.data[k] === undefined && typeof v === 'string' && v.trim()) {
        this.data[k] = v.trim();
        changed = true;
      }
    }
    if (changed) this.write();
  }

  get() {
    const out = {};
    for (const k of FIELDS) {
      const v = this.data[k];
      out[k] = typeof v === 'string' && v !== '' ? v : DEFAULTS[k];
    }
    return out;
  }

  // Store exactly what the user typed.
  set(patch) {
    for (const k of FIELDS) {
      if (patch && typeof patch[k] === 'string') this.data[k] = patch[k].trim();
    }
    return this.write();
  }

  write() {
    try {
      fs.mkdirSync(this.dir, { recursive: true });
      const tmp = `${this.file}.tmp-${process.pid}`;
      fs.writeFileSync(tmp, JSON.stringify(this.data, null, 2), 'utf8');
      if (fs.existsSync(this.file)) {
        try { fs.copyFileSync(this.file, this.bak); } catch { /* backup is best effort */ }
      }
      fs.renameSync(tmp, this.file);
      this.problem = null;
      return { ok: true, savedAt: new Date().toISOString() };
    } catch (e) {
      // Memory still holds the values, so the app keeps working this session.
      return { ok: false, error: `Could not write ${this.file}: ${e.message}` };
    }
  }
}

module.exports = { SettingsStore, FIELDS };
