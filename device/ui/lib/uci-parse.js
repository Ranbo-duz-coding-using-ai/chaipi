/* Pure helpers for the UCI protocol: no Node APIs, so they can be tested anywhere. */
(function (root) {
  'use strict';

  const MATE = 100000;

  /* "info depth 18 multipv 2 score cp -34 upperbound nodes 1234 pv e2e4 e7e5" -> object, or null if it carries no line. */
  function parseInfo(line) {
    const t = line.trim().split(/\s+/);
    if (t[0] !== 'info') return null;
    const o = { depth: 0, multipv: 1, score: null, bound: null, nodes: 0, pv: [] };
    for (let i = 1; i < t.length; i++) {
      const k = t[i];
      if (k === 'string') break;
      if (k === 'depth') o.depth = +t[++i];
      else if (k === 'seldepth') o.seldepth = +t[++i];
      else if (k === 'multipv') o.multipv = +t[++i];
      else if (k === 'nodes') o.nodes = +t[++i];
      else if (k === 'nps') o.nps = +t[++i];
      else if (k === 'time') o.time = +t[++i];
      else if (k === 'hashfull') o.hashfull = +t[++i];
      else if (k === 'tbhits') o.tbhits = +t[++i];
      else if (k === 'currmove' || k === 'currmovenumber' || k === 'refutation' || k === 'currline' || k === 'cpuload') { i++; }
      else if (k === 'wdl') { i += 3; }
      else if (k === 'score') {
        const kind = t[++i], val = +t[++i];
        o.score = kind === 'mate' ? { mate: val } : { cp: val };
        if (t[i + 1] === 'lowerbound' || t[i + 1] === 'upperbound') o.bound = t[++i];
      } else if (k === 'pv') { o.pv = t.slice(i + 1); break; }
    }
    return o.score && o.pv.length ? o : null;
  }

  /* UCI score (side to move) -> the OS's scale: centipawns, mate as +-(100000 - plies). */
  function toScore(s) {
    if (!s) return 0;
    if (s.mate != null) {
      if (s.mate > 0) return MATE - (2 * s.mate - 1);
      if (s.mate < 0) return -(MATE + 2 * s.mate);
      return -MATE;
    }
    return s.cp;
  }

  /* "option name UCI_Elo type spin default 1320 min 1320 max 3190" -> {name, type, default, min, max, vars} */
  function parseOption(line) {
    const m = line.match(/^option name (.+?) type (\w+)(.*)$/);
    if (!m) return null;
    const o = { name: m[1], type: m[2], vars: [] };
    const rest = m[3].trim().split(/\s+/);
    for (let i = 0; i < rest.length; i++) {
      if (rest[i] === 'default') {
        const vals = []; while (i + 1 < rest.length && !['min', 'max', 'var'].includes(rest[i + 1])) vals.push(rest[++i]);
        o.default = vals.join(' ');
      } else if (rest[i] === 'min') o.min = +rest[++i];
      else if (rest[i] === 'max') o.max = +rest[++i];
      else if (rest[i] === 'var') o.vars.push(rest[++i]);
    }
    return o;
  }

  /* Keeps the newest line per multipv index; turns them into the OS's {uci, score, exact} list, best first. */
  class LineBook {
    constructor() { this.by = new Map(); this.nodes = 0; this.depth = 0; }
    add(info) {
      if (!info) return;
      const prev = this.by.get(info.multipv);
      if (!prev || info.depth >= prev.depth || prev.bound) this.by.set(info.multipv, info);
      if (info.nodes > this.nodes) this.nodes = info.nodes;
      if (info.multipv === 1 && info.depth > this.depth) this.depth = info.depth;
    }
    lines(bestmove) {
      const ls = [...this.by.entries()].sort((a, b) => a[0] - b[0]).map(([, i]) =>
        ({ uci: i.pv[0], score: toScore(i.score), exact: !i.bound, depth: i.depth, pv: i.pv.slice(0, 8) }));
      const seen = new Set(), out = [];
      for (const l of ls) if (!seen.has(l.uci)) { seen.add(l.uci); out.push(l); }
      out.sort((a, b) => b.score - a.score);
      if (bestmove && bestmove !== '(none)' && bestmove !== '0000') {
        const i = out.findIndex(l => l.uci === bestmove);
        if (i > 0) out.unshift(out.splice(i, 1)[0]);
        if (i < 0) out.unshift({ uci: bestmove, score: out.length ? out[0].score : 0, exact: true, depth: 0, pv: [bestmove] });
      }
      if (bestmove === '(none)' || bestmove === '0000') return [];
      return out;
    }
  }

  /* "bestmove e2e4 ponder e7e5" -> {best, ponder} */
  function parseBestmove(line) {
    const t = line.trim().split(/\s+/);
    if (t[0] !== 'bestmove') return null;
    return { best: t[1] || '(none)', ponder: t[2] === 'ponder' ? t[3] : null };
  }

  const api = { MATE, parseInfo, toScore, parseOption, parseBestmove, LineBook };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.UCIParse = api;
})(this);
