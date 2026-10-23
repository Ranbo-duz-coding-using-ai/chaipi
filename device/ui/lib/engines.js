'use strict';
/* Installed engines. Each lives in its own folder with an engine.json:
     {"id":"berserk","name":"Berserk 13","short":"Berserk","exe":"berserk","args":[],"by":"…","tier":"…","type":"NNUE","desc":"…"}
   Built-in engines are in /opt/chaipi/engines (read-only); downloaded and uploaded ones in /data/chaipi/engines. */
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const https = require('https');
const { execFile } = require('child_process');

function readJson(f) { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch (e) { return null; } }

function scan(dirs) {
  const out = new Map();
  for (const dir of dirs) {
    let names = []; try { names = fs.readdirSync(dir); } catch (e) { continue; }
    for (const n of names) {
      const d = path.join(dir, n), meta = readJson(path.join(d, 'engine.json'));
      if (!meta || !meta.id || !meta.exe) continue;
      const exe = path.resolve(d, meta.exe);
      if (!fs.existsSync(exe)) continue;
      out.set(meta.id, Object.assign({}, meta, { dir: d, exe, builtin: dir === dirs[0] }));
    }
  }
  return out;
}

function download(url, file, onProgress, depth) {
  return new Promise((resolve, reject) => {
    https.get(url, { timeout: 20000, headers: { 'User-Agent': 'ChAIpi' } }, res => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location && (depth || 0) < 5) {
        res.resume(); download(new URL(res.headers.location, url).href, file, onProgress, (depth || 0) + 1).then(resolve, reject); return;
      }
      if (res.statusCode !== 200) { res.resume(); reject(new Error('Download failed (HTTP ' + res.statusCode + ')')); return; }
      const total = Number(res.headers['content-length']) || 0, hash = crypto.createHash('sha256'), out = fs.createWriteStream(file);
      let got = 0;
      res.on('data', c => { got += c.length; hash.update(c); if (total && onProgress) onProgress(got / total); });
      res.pipe(out);
      out.on('finish', () => resolve(hash.digest('hex')));
      out.on('error', reject); res.on('error', reject);
    }).on('error', reject).on('timeout', function () { this.destroy(new Error('Download timed out')); });
  });
}

class Engines {
  constructor(opts) { this.opts = opts; this.log = opts.log || console.log; this.map = new Map(); this.catalog = null; this.refresh(); }
  refresh() { this.map = scan([this.opts.builtinDir, this.opts.dataDir]); return this.map; }
  get(id) { return this.map.get(id) || null; }
  ids() { return [...this.map.keys()]; }
  async loadCatalog() {
    if (this.catalog || !this.opts.catalogUrl) return this.catalog;
    const tmp = path.join(this.opts.tmpDir, 'catalog.json');
    await download(this.opts.catalogUrl, tmp);
    this.catalog = JSON.parse(fs.readFileSync(tmp, 'utf8'));
    return this.catalog;
  }
  /* Catalog entries: {"id":"berserk","url":"https://…/berserk-linux-arm64.tar.gz","sha256":"…"}; the archive holds engine.json. */
  async install(id, onProgress) {
    if (!this.opts.catalogUrl) throw new Error('No download for this engine yet. Upload it from your phone with Transfer.');
    const cat = await this.loadCatalog();
    const entry = cat && (cat.engines || []).find(e => e.id === id);
    if (!entry) throw new Error('No ARM64 build of this engine yet. You can upload one with Transfer.');
    fs.mkdirSync(this.opts.tmpDir, { recursive: true });
    const tmp = path.join(this.opts.tmpDir, id + '.tar.gz');
    const sha = await download(entry.url, tmp, onProgress);
    if (entry.sha256 && entry.sha256.toLowerCase() !== sha) { fs.rmSync(tmp, { force: true }); throw new Error('Download was damaged. Try again.'); }
    // The same checker the transfer page uses: it unpacks, checks the program is ARM64 and speaks UCI, then installs.
    await new Promise((resolve, reject) => execFile('python3', ['-m', 'chaipi_xfer.install', 'engine', tmp, '--data', this.opts.data, '--id', id],
      { env: Object.assign({}, process.env, { PYTHONPATH: this.opts.pythonPath }), timeout: 120000 },
      (err, out, errOut) => { fs.rmSync(tmp, { force: true }); if (err) reject(new Error((errOut || err.message).trim().split('\n').pop())); else resolve(out); }));
    this.refresh();
    return !!this.get(id);
  }
  remove(id) {
    const e = this.map.get(id);
    if (!e || e.builtin) return false;
    fs.rmSync(e.dir, { recursive: true, force: true });
    this.refresh();
    return true;
  }
}

module.exports = { Engines, download };
