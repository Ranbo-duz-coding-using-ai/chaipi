'use strict';
/* Runs a UCI engine (Stockfish 19 by default) and answers the OS's think() calls.
   Stockfish 19 exits on any command it doesn't understand, so we only send options the engine
   declared, and we restart it if it dies. */
const { spawn } = require('child_process');
const os = require('os');
const readline = require('readline');
const { parseInfo, parseOption, parseBestmove, LineBook } = require('./uci-parse');

class UciEngine {
  constructor(spec, opts) {
    this.spec = spec; this.opts = opts || {}; this.log = this.opts.log || console.log;
    this.proc = null; this.options = new Map(); this.sent = new Map(); this.waiters = []; this.onLine = null;
    this.name = spec.name; this.ready = null; this.deaths = [];
  }
  start() {
    if (this.ready) return this.ready;
    this.ready = new Promise((resolve, reject) => {
      const p = spawn(this.spec.exe, this.spec.args || [], { cwd: this.spec.dir, stdio: ['pipe', 'pipe', 'pipe'] });
      this.proc = p; this.options.clear(); this.sent.clear();
      try { os.setPriority(p.pid, this.opts.nice || 0); } catch (e) { /* not allowed: keep normal priority */ }
      const rl = readline.createInterface({ input: p.stdout });
      rl.on('line', line => this.handle(line));
      p.stderr.on('data', d => this.log('[engine]', String(d).trim()));
      p.on('error', err => { this.log('engine failed to start:', err.message); this.dead(); reject(err); });
      p.on('exit', (code, sig) => { this.log('engine exited', code, sig || ''); this.dead(); });
      const t = setTimeout(() => reject(new Error(this.spec.name + ' did not answer "uci"')), 15000);
      this.expect(l => l === 'uciok').then(() => {
        clearTimeout(t);
        const th = this.options.get('Threads');
        this.set('Threads', Math.min(this.opts.threads || os.cpus().length, th && th.max || 512));
        if (this.opts.hash) this.set('Hash', this.opts.hash);
        return this.isready();
      }).then(resolve, reject);
      this.send('uci');
    });
    this.ready.catch(() => { this.ready = null; });
    return this.ready;
  }
  dead() {
    if (!this.proc) return;
    this.proc = null; this.ready = null;
    this.deaths.push(Date.now());
    const w = this.waiters; this.waiters = [];
    w.forEach(x => x.reject(new Error('engine stopped')));
    if (this.onDeath) this.onDeath();
  }
  restartsLastMinute() { const t = Date.now() - 60000; this.deaths = this.deaths.filter(d => d > t); return this.deaths.length; }
  handle(line) {
    if (line.startsWith('option name ')) { const o = parseOption(line); if (o) this.options.set(o.name, o); }
    if (line.startsWith('id name ')) this.name = line.slice(8).trim();
    if (this.onLine) this.onLine(line);
    for (let i = 0; i < this.waiters.length; i++) {
      const w = this.waiters[i];
      if (w.test(line)) { this.waiters.splice(i, 1); w.resolve(line); break; }
    }
  }
  expect(test) { return new Promise((resolve, reject) => this.waiters.push({ test, resolve, reject })); }
  send(cmd) { if (this.proc && this.proc.stdin.writable) this.proc.stdin.write(cmd + '\n'); }
  isready() { const p = this.expect(l => l === 'readyok'); this.send('isready'); return p; }
  has(name) { return this.options.has(name); }
  /* Sends setoption only for declared options, clamped to the engine's range, and only when the value changes. */
  set(name, value) {
    const o = this.options.get(name);
    if (!o) return false;
    let v = value;
    if (o.type === 'spin') { v = Math.round(Number(v)); if (o.min != null) v = Math.max(o.min, v); if (o.max != null) v = Math.min(o.max, v); }
    if (o.type === 'check') v = v ? 'true' : 'false';
    if (o.type === 'combo' && !o.vars.includes(String(v))) return false;
    if (o.type === 'button') { this.send('setoption name ' + name); return true; }
    if (this.sent.get(name) === String(v)) return true;
    this.sent.set(name, String(v));
    this.send('setoption name ' + name + ' value ' + v);
    return true;
  }
  quit() {
    if (!this.proc) return;
    const p = this.proc;
    this.send('quit');
    setTimeout(() => { try { p.kill('SIGKILL'); } catch (e) { /* already gone */ } }, 1500);
  }
}

/* Turns the OS's think(fen, depth, opt) into engine searches.
   - 'move' (the engine's turn): Elo-limited when the engine supports UCI_Elo, else MultiPV for the OS's own weakening.
   - 'analyse' (arrows, hints, helper): MultiPV 3, short first passes then the full think time.
   - 'review': one quick line per position.
   - pondering: an infinite search on the player's time, stopped by any real request.
   A new request stops a running analysis or ponder; an engine move is never interrupted. */
class Thinker {
  constructor(opts) {
    this.opts = opts; this.log = opts.log || console.log;
    this.engine = null; this.queue = []; this.cur = null; this.suspended = false;
  }
  use(spec) {
    if (this.engine && this.engine.spec.exe === spec.exe && JSON.stringify(this.engine.spec.args) === JSON.stringify(spec.args)) return;
    if (this.engine) this.engine.quit();
    this.engine = new UciEngine(spec, { threads: this.opts.threads, hash: this.opts.hash(), nice: this.opts.nice, log: this.log });
    this.engine.start().catch(e => this.log('engine start:', e.message));
  }
  suspend() { this.suspended = true; this.stopPonder(); if (this.engine) { this.engine.quit(); } }
  resume() { if (!this.suspended) return; this.suspended = false; if (this.engine) this.engine.start().catch(e => this.log('engine start:', e.message)); }
  setHash(mb) { if (this.engine && this.engine.proc && !this.cur) this.engine.set('Hash', mb); }
  setThreads(n) { if (this.engine && this.engine.proc && !this.cur) this.engine.set('Threads', n); }
  busy() { return !!this.cur && this.cur.purpose !== 'ponder'; }

  think(fen, depth, opt) {
    return new Promise(resolve => {
      const req = { fen, depth, opt: opt || {}, purpose: (opt && opt.purpose) || 'analyse', resolve };
      // Drop stale analyses still waiting; their results would be ignored anyway.
      this.queue = this.queue.filter(q => { if (q.purpose === 'move') return true; q.resolve({ lines: [], nodes: 0 }); return false; });
      this.queue.push(req);
      if (this.cur && this.cur.purpose !== 'move') this.stopCurrent();
      this.pump();
    });
  }
  ponder(fen) {
    if (this.cur || this.queue.length || this.suspended) return;
    this.queue.push({ fen, purpose: 'ponder', opt: {}, resolve: () => {} });
    this.pump();
  }
  stopPonder() { if (this.cur && this.cur.purpose === 'ponder') this.stopCurrent(); }
  stopCurrent() { if (this.cur && !this.cur.stopping && this.engine) { this.cur.stopping = true; this.engine.send('stop'); } }

  async pump() {
    if (this.cur || !this.queue.length) return;
    const req = this.queue.shift();
    this.cur = req;
    let result = { lines: [], nodes: 0 };
    // An engine move is retried once after a crash, so the game never stalls waiting for a reply.
    for (let attempt = 0; attempt < (req.purpose === 'move' ? 2 : 1); attempt++) {
      try {
        if (this.suspended) throw new Error('engine paused');
        if (!this.engine) throw new Error('no engine');
        if (!this.engine.proc && this.engine.restartsLastMinute() > (this.opts.restartMax || 5)) throw new Error('engine keeps crashing');
        await this.engine.start();
        result = await this.search(req);
        break;
      } catch (e) {
        if (req.purpose !== 'ponder') this.log('think failed:', e.message);
        if (this.onError && req.purpose === 'move' && attempt === 1) this.onError(e);
      }
    }
    this.cur = null;
    req.resolve(result);
    this.pump();
  }

  plan(req) {
    const e = this.engine, o = req.opt, c = this.opts;
    const thinkMs = { fast: c.thinkMs.fast, medium: c.thinkMs.medium, deep: c.thinkMs.deep }[o.think] || c.thinkMs.medium;
    if (req.purpose === 'move') {
      const eloOpt = e.options.get('UCI_Elo');
      const max = eloOpt && eloOpt.max || 3190, min = eloOpt && eloOpt.min || 1320;
      const elo = o.elo || max;
      if (elo >= max) return { limit: false, multipv: 1, go: 'go movetime ' + thinkMs, single: true };
      if (eloOpt && e.has('UCI_LimitStrength') && elo >= min) return { limit: true, elo, multipv: 1, go: 'go movetime ' + thinkMs, single: true };
      return { limit: false, multipv: c.weakMultipv, go: 'go depth ' + (elo <= 800 ? 4 : 6) + ' movetime ' + Math.min(thinkMs, 1500) };
    }
    if (req.purpose === 'review') return { limit: false, multipv: 1, go: 'go movetime ' + c.reviewMs };
    if (req.purpose === 'ponder') return { limit: false, multipv: 1, go: 'go infinite' };
    const steps = c.analyseSteps;
    const ms = o.last || !steps[req.depth - 1] ? thinkMs : steps[req.depth - 1];
    return { limit: false, multipv: 3, go: 'go movetime ' + ms };
  }

  search(req) {
    const e = this.engine, p = this.plan(req);
    e.set('UCI_LimitStrength', p.limit);
    if (p.limit) e.set('UCI_Elo', p.elo);
    e.set('MultiPV', p.multipv);
    const book = new LineBook();
    return new Promise((resolve, reject) => {
      const done = e.expect(l => l.startsWith('bestmove'));
      e.onLine = line => { if (line.startsWith('info')) book.add(parseInfo(line)); };
      e.send('position fen ' + req.fen);
      e.send(p.go);
      if (req.stopping) e.send('stop');
      done.then(line => {
        e.onLine = null;
        const bm = parseBestmove(line);
        let lines = book.lines(bm && bm.best);
        if (p.single) lines = lines.slice(0, 1);
        resolve({ lines, nodes: book.nodes, depth: book.depth });
      }, err => { e.onLine = null; reject(err); });
    });
  }
}

module.exports = { UciEngine, Thinker };
