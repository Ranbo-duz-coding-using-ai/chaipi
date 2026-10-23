'use strict';
/* Starts and stops the transfer web server (device/transfer, Python). It brings up the hotspot itself and
   reports what phones do as JSON lines on stdout. When it exits, its memory and the hotspot are gone. */
const { spawn } = require('child_process');
const readline = require('readline');
const { EventEmitter } = require('events');

class Transfer extends EventEmitter {
  constructor(opts) { super(); this.opts = opts; this.log = opts.log || console.log; this.proc = null; }
  running() { return !!this.proc; }
  start({ mode, pin, timeout, tab }) {
    if (this.proc) this.stop();
    const args = ['-m', 'chaipi_xfer.server', '--mode', mode, '--data', this.opts.data, '--port', String(this.opts.port),
      '--portal', this.opts.portal, '--fonts', this.opts.fonts, '--config', this.opts.config];
    if (pin) args.push('--pin', pin);
    if (timeout) args.push('--idle-min', String(timeout));
    if (tab) args.push('--start-tab', tab);
    const p = spawn('python3', args, { cwd: this.opts.cwd, env: Object.assign({}, process.env, { PYTHONPATH: this.opts.pythonPath }), stdio: ['pipe', 'pipe', 'pipe'] });
    this.proc = p;
    readline.createInterface({ input: p.stdout }).on('line', line => {
      let ev; try { ev = JSON.parse(line); } catch (e) { return; }
      this.emit('event', ev);
    });
    p.stderr.on('data', d => this.log('[transfer]', String(d).trim()));
    p.on('error', e => { this.emit('event', { ev: 'error', msg: 'Transfer could not start: ' + e.message }); });
    p.on('exit', code => {
      if (this.proc === p) { this.proc = null; this.emit('event', { ev: 'exit', code }); }
    });
  }
  setPin(pin) { this.cmd({ cmd: 'pin', pin }); }
  status(st) { this.cmd(Object.assign({ cmd: 'status' }, st)); }
  cmd(m) { if (this.proc && this.proc.stdin.writable) this.proc.stdin.write(JSON.stringify(m) + '\n'); }
  stop() {
    const p = this.proc; if (!p) return;
    this.proc = null;
    p.kill('SIGTERM');
    setTimeout(() => { try { p.kill('SIGKILL'); } catch (e) { /* gone */ } }, 8000);
  }
}

module.exports = { Transfer };
