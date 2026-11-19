// Over-the-air update from GitHub (Zhihong0321/sld-generator, branch main).
//
// The app runs from the repo folder, so an update = bring that folder up to date:
//   - git checkout  -> `git fetch` + `git pull --ff-only` (never resets or discards local changes)
//   - zip install   -> download the branch zip and copy it over, keeping projects/, output/
//                      and the user's library entries (new library entries are merged in)
// Every function returns a result object; an update problem is reported, never fatal.

const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn } = require('child_process');

const OWNER = 'Zhihong0321', REPO = 'sld-generator', BRANCH = 'main';
const API = `https://api.github.com/repos/${OWNER}/${REPO}`;
const KEEP_DIRS = new Set(['.git', 'projects', 'output', 'graft', 'node_modules']);

function run(cmd, args, cwd) {
  return new Promise((resolve) => {
    let out = '', err = '';
    let child;
    try { child = spawn(cmd, args, { cwd, windowsHide: true, shell: process.platform === 'win32' && cmd === 'npm' }); }
    catch (e) { return resolve({ code: -1, out: '', err: String(e) }); }
    child.stdout.on('data', (d) => (out += d));
    child.stderr.on('data', (d) => (err += d));
    child.on('error', (e) => resolve({ code: -1, out, err: e.message }));
    child.on('close', (code) => resolve({ code, out: out.trim(), err: err.trim() }));
  });
}

async function gh(url) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 20000);
  try {
    const r = await fetch(url, { signal: ctrl.signal, headers: { 'User-Agent': 'sld-studio', Accept: 'application/vnd.github+json' } });
    if (!r.ok) throw new Error(`GitHub ${r.status} ${(await r.text()).slice(0, 120)}`);
    return await r.json();
  } finally { clearTimeout(t); }
}

class Updater {
  constructor(root) {
    this.root = root;
    this.versionFile = path.join(root, '.sld-version');
    this.last = null;
  }

  async mode() {
    if (!fs.existsSync(path.join(this.root, '.git'))) return 'zip';
    const r = await run('git', ['--version'], this.root);
    return r.code === 0 ? 'git' : 'zip';
  }

  async localVersion() {
    const mode = await this.mode();
    if (mode === 'git') {
      const r = await run('git', ['rev-parse', 'HEAD'], this.root);
      return { mode, sha: r.code === 0 ? r.out : null };
    }
    let sha = null;
    try { sha = fs.readFileSync(this.versionFile, 'utf8').trim() || null; } catch { /* unknown */ }
    return { mode, sha };
  }

  // -> { ok, available, behind, mode, local, remote, changes:[{sha,msg,date}], dirty, error }
  async check() {
    const res = { ok: true, available: false, behind: 0, changes: [], checkedAt: new Date().toISOString() };
    try {
      const { mode, sha } = await this.localVersion();
      Object.assign(res, { mode, local: sha });
      if (mode === 'git') {
        const f = await run('git', ['fetch', '--quiet', 'origin', BRANCH], this.root);
        if (f.code !== 0) throw new Error(`git fetch failed: ${f.err || f.out}`);
        const remote = await run('git', ['rev-parse', `origin/${BRANCH}`], this.root);
        res.remote = remote.out;
        const n = await run('git', ['rev-list', '--count', `HEAD..origin/${BRANCH}`], this.root);
        res.behind = parseInt(n.out, 10) || 0;
        if (res.behind) {
          const log = await run('git', ['log', '--format=%h%x09%cI%x09%s', `HEAD..origin/${BRANCH}`], this.root);
          res.changes = log.out.split('\n').filter(Boolean).map((l) => { const [s, date, ...m] = l.split('\t'); return { sha: s, date, msg: m.join('\t') }; });
        }
        const st = await run('git', ['status', '--porcelain', '--untracked-files=no'], this.root);
        res.dirty = st.out ? st.out.split('\n').length : 0;
      } else {
        const head = await gh(`${API}/commits/${BRANCH}`);
        res.remote = head.sha;
        if (!res.local) {
          res.behind = 1;
          res.changes = [{ sha: head.sha.slice(0, 7), date: head.commit?.committer?.date, msg: head.commit?.message?.split('\n')[0] || '' }];
          res.unknownLocal = true;
        } else if (res.local !== head.sha) {
          try {
            const cmp = await gh(`${API}/compare/${res.local}...${head.sha}`);
            res.behind = cmp.ahead_by || 1;
            res.changes = (cmp.commits || []).reverse().map((c) => ({ sha: c.sha.slice(0, 7), date: c.commit?.committer?.date, msg: c.commit?.message?.split('\n')[0] || '' }));
          } catch {
            res.behind = 1;
            res.changes = [{ sha: head.sha.slice(0, 7), date: head.commit?.committer?.date, msg: head.commit?.message?.split('\n')[0] || '' }];
          }
        }
      }
      res.available = res.behind > 0;
    } catch (e) {
      Object.assign(res, { ok: false, error: e.name === 'AbortError' ? 'GitHub did not answer (timed out)' : String(e.message || e) });
    }
    this.last = res;
    return res;
  }

  // -> { ok, mode, from, to, log:[...], npmInstalled, error }
  async apply(progress = () => {}) {
    const log = [];
    const say = (m) => { log.push(m); progress(m); };
    try {
      const { mode, sha: from } = await this.localVersion();
      const pkgBefore = this.readPkg();
      let to = null;
      if (mode === 'git') {
        say('Downloading changes (git pull)…');
        const p = await run('git', ['pull', '--ff-only', 'origin', BRANCH], this.root);
        if (p.code !== 0) {
          return { ok: false, mode, from, log, error: `git pull could not finish: ${p.err || p.out}. Your files were not changed. ` +
            'Usually this means a file you edited here was also changed on GitHub; commit or move your edit, then update again.' };
        }
        to = (await run('git', ['rev-parse', 'HEAD'], this.root)).out;
      } else {
        to = await this.applyZip(say);
      }
      let npmInstalled = false;
      if (JSON.stringify(pkgBefore) !== JSON.stringify(this.readPkg())) {
        say('App dependencies changed: running npm install…');
        const n = await run('npm', ['install', '--no-audit', '--no-fund'], path.join(this.root, 'app'));
        npmInstalled = n.code === 0;
        if (!npmInstalled) say(`npm install problem (the app may still run): ${n.err.slice(0, 300)}`);
      }
      try { fs.writeFileSync(this.versionFile, `${to}\n`); } catch { /* version file is only a hint */ }
      say('Update installed. Restart to use it.');
      return { ok: true, mode, from, to, log, npmInstalled };
    } catch (e) {
      return { ok: false, log, error: String(e.message || e) };
    }
  }

  readPkg() {
    try { const p = JSON.parse(fs.readFileSync(path.join(this.root, 'app', 'package.json'), 'utf8')); return { d: p.dependencies, dd: p.devDependencies }; }
    catch { return null; }
  }

  async applyZip(say) {
    const head = await gh(`${API}/commits/${BRANCH}`);
    const sha = head.sha;
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'sld-update-'));
    try {
      say('Downloading update from GitHub…');
      const r = await fetch(`https://codeload.github.com/${OWNER}/${REPO}/zip/${sha}`, { headers: { 'User-Agent': 'sld-studio' } });
      if (!r.ok) throw new Error(`download failed: HTTP ${r.status}`);
      const zip = path.join(tmp, 'src.zip');
      fs.writeFileSync(zip, Buffer.from(await r.arrayBuffer()));
      say('Unpacking…');
      const x = process.platform === 'win32'
        ? await run('powershell', ['-NoProfile', '-Command', `Expand-Archive -LiteralPath '${zip}' -DestinationPath '${tmp}' -Force`], tmp)
        : await run('unzip', ['-q', '-o', zip, '-d', tmp], tmp);
      if (x.code !== 0) throw new Error(`unpack failed: ${x.err}`);
      const src = fs.readdirSync(tmp, { withFileTypes: true }).find((d) => d.isDirectory());
      if (!src) throw new Error('downloaded zip was empty');
      say('Installing files…');
      this.copyOver(path.join(tmp, src.name), this.root, '');
      return sha;
    } finally {
      try { fs.rmSync(tmp, { recursive: true, force: true }); } catch { /* temp cleanup only */ }
    }
  }

  copyOver(srcDir, dstDir, rel) {
    for (const e of fs.readdirSync(srcDir, { withFileTypes: true })) {
      const r = rel ? `${rel}/${e.name}` : e.name;
      if (KEEP_DIRS.has(e.name) && e.isDirectory()) continue;
      const s = path.join(srcDir, e.name), d = path.join(dstDir, e.name);
      if (e.isDirectory()) { fs.mkdirSync(d, { recursive: true }); this.copyOver(s, d, r); }
      else if (r === 'library/modules.json' || r === 'library/inverters.json') this.mergeLibrary(s, d);
      else fs.copyFileSync(s, d);
    }
  }

  // Add library entries that are new on GitHub; never overwrite an entry the user already has.
  mergeLibrary(src, dst) {
    if (!fs.existsSync(dst)) { fs.copyFileSync(src, dst); return; }
    try {
      const mine = JSON.parse(fs.readFileSync(dst, 'utf8'));
      const theirs = JSON.parse(fs.readFileSync(src, 'utf8'));
      let added = 0;
      for (const [k, v] of Object.entries(theirs)) if (!(k in mine)) { mine[k] = v; added++; }
      if (added) fs.writeFileSync(dst, JSON.stringify(mine, null, 2) + '\n', 'utf8');
    } catch { /* keep the user's file as it is */ }
  }
}

module.exports = { Updater, REPO_URL: `https://github.com/${OWNER}/${REPO}` };
