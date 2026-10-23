'use strict';
/* Custom Python apps from /data/chaipi/apps/<id>/ (main.py + app.toml). Each runs as its own process that draws
   to the framebuffer through the chaipi SDK (device/sdk). The UI stops drawing while it runs, and when the
   process exits all its memory is returned. Holding Esc for 1 s ends an app that won't quit. */
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const TOML = require('./toml');

function listApps(dir) {
  let names = []; try { names = fs.readdirSync(dir); } catch (e) { return []; }
  return names.map(id => {
    const d = path.join(dir, id);
    if (!fs.existsSync(path.join(d, 'main.py'))) return null;
    let meta = {}; try { meta = TOML.parse(fs.readFileSync(path.join(d, 'app.toml'), 'utf8')); } catch (e) { /* defaults */ }
    return { id, name: String(meta.name || id).slice(0, 24), ram: Number(meta.ram) || 40, dir: d };
  }).filter(Boolean);
}

class Apps {
  constructor(opts) { this.opts = opts; this.log = opts.log || console.log; this.proc = null; }
  running() { return !!this.proc; }
  run(app, fbDev) {
    return new Promise((resolve, reject) => {
      if (this.proc) { reject(new Error('Another app is running')); return; }
      const logDir = path.join(this.opts.data, 'logs', 'apps');
      fs.mkdirSync(logDir, { recursive: true });
      const logFile = path.join(logDir, app.id + '.log');
      const out = fs.openSync(logFile, 'w');
      const env = Object.assign({}, process.env, {
        PYTHONPATH: this.opts.sdk, CHAIPI_FB: fbDev || '', CHAIPI_INPUT: this.opts.inputSock, CHAIPI_APP_DIR: app.dir,
        CHAIPI_DATA: path.join(this.opts.data, 'appdata', app.id)
      });
      const p = spawn('python3', ['-m', 'chaipi.run', path.join(app.dir, 'main.py')], { cwd: app.dir, env, stdio: ['ignore', out, out] });
      this.proc = p;
      // The kernel's out-of-memory killer should pick the app before the UI or the engine.
      try { fs.writeFileSync('/proc/' + p.pid + '/oom_score_adj', '800'); } catch (e) { /* not on Linux */ }
      p.on('error', e => { this.proc = null; fs.closeSync(out); reject(e); });
      p.on('exit', (code, sig) => {
        this.proc = null; fs.closeSync(out);
        if (code === 0 || sig === 'SIGTERM') resolve('');
        else resolve(app.name + ' stopped with an error · log in logs/apps');
      });
    });
  }
  kill() { if (this.proc) { this.proc.kill('SIGTERM'); const p = this.proc; setTimeout(() => { try { p.kill('SIGKILL'); } catch (e) { /* gone */ } }, 1500); } }
}

module.exports = { Apps, listApps };
