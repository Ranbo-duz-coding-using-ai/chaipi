/* The small part of TOML that config/chaipi.example.toml uses: [tables], [dotted.tables],
   key = "string" | 'literal' | number | 0xHEX | true/false | [arrays of those], # comments. */
(function (root) {
  'use strict';

  function stripComment(line) {
    let q = null;
    for (let i = 0; i < line.length; i++) {
      const c = line[i];
      if (q) {
        if (c === '\\' && q === '"') { i++; continue; }
        if (c === q) q = null;
      } else if (c === '"' || c === "'") q = c;
      else if (c === '#') return line.slice(0, i);
    }
    return line;
  }

  function parseValue(src, where) {
    const v = src.trim();
    if (v.startsWith('"')) {
      if (!v.endsWith('"') || v.length < 2) throw new Error('unterminated string at ' + where);
      return v.slice(1, -1).replace(/\\(["\\nt]|u[0-9a-fA-F]{4})/g, (m, e) =>
        e === 'n' ? '\n' : e === 't' ? '\t' : e[0] === 'u' ? String.fromCharCode(parseInt(e.slice(1), 16)) : e);
    }
    if (v.startsWith("'")) {
      if (!v.endsWith("'") || v.length < 2) throw new Error('unterminated string at ' + where);
      return v.slice(1, -1);
    }
    if (v === 'true') return true;
    if (v === 'false') return false;
    if (v.startsWith('[')) {
      if (!v.endsWith(']')) throw new Error('unterminated array at ' + where);
      const inner = v.slice(1, -1).trim();
      if (!inner) return [];
      const parts = []; let depth = 0, q = null, cur = '';
      for (let i = 0; i < inner.length; i++) {
        const c = inner[i];
        if (q) { cur += c; if (c === q) q = null; continue; }
        if (c === '"' || c === "'") { q = c; cur += c; continue; }
        if (c === '[') depth++;
        if (c === ']') depth--;
        if (c === ',' && depth === 0) { parts.push(cur); cur = ''; continue; }
        cur += c;
      }
      if (cur.trim()) parts.push(cur);
      return parts.map(p => parseValue(p, where));
    }
    const n = v.replace(/_/g, '');
    if (/^[+-]?0x[0-9a-fA-F]+$/.test(n)) return parseInt(n, 16);
    if (/^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/.test(n)) return Number(n);
    throw new Error('cannot read value "' + v + '" at ' + where);
  }

  function parse(text) {
    const out = {}; let table = out;
    text.split(/\r?\n/).forEach((raw, i) => {
      const line = stripComment(raw).trim();
      if (!line) return;
      const where = 'line ' + (i + 1);
      const t = line.match(/^\[([A-Za-z0-9_.-]+)\]$/);
      if (t) {
        table = out;
        for (const k of t[1].split('.')) { if (typeof table[k] !== 'object' || table[k] === null) table[k] = {}; table = table[k]; }
        return;
      }
      const eq = line.indexOf('=');
      if (eq < 1) throw new Error('expected key = value at ' + where);
      const key = line.slice(0, eq).trim().replace(/^"(.*)"$/, '$1');
      table[key] = parseValue(line.slice(eq + 1), where);
    });
    return out;
  }

  const api = { parse };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.TOML = api;
})(this);
