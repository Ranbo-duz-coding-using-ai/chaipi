/* Reads PGN files (uploaded from a phone, or from the SD card / USB drive) into the OS's game records.
   Moves are checked with the OS's own chess rules (core), so an illegal move ends that game's import there. */
(function (root) {
  'use strict';

  function splitGames(text) {
    const games = []; let cur = null;
    for (const line of text.replace(/\r/g, '').split('\n')) {
      const tag = line.match(/^\s*\[(\w+)\s+"((?:[^"\\]|\\.)*)"\]\s*$/);
      if (tag) {
        if (!cur || cur.moves.trim()) { cur = { tags: {}, moves: '' }; games.push(cur); }
        cur.tags[tag[1]] = tag[2].replace(/\\(.)/g, '$1');
      } else if (line.trim()) {
        if (!cur) { cur = { tags: {}, moves: '' }; games.push(cur); }
        cur.moves += ' ' + line;
      }
    }
    return games;
  }

  /* Movetext -> SAN tokens: drops comments, variations, NAGs, move numbers and the result. */
  function sanTokens(moves) {
    let s = moves.replace(/\{[^}]*\}/g, ' ').replace(/;[^\n]*/g, ' ');
    let depth = 0, out = '';
    for (const c of s) { if (c === '(') depth++; else if (c === ')') depth = Math.max(0, depth - 1); else if (!depth) out += c; }
    return out.split(/\s+/).map(t => t.replace(/^\d+\.(\.\.)?/, '').replace(/[!?]+$/, '')).filter(t =>
      t && !/^\$\d+$/.test(t) && !/^(1-0|0-1|1\/2-1\/2|\*)$/.test(t) && !/^\d+\.+$/.test(t));
  }

  function parseDate(d) {
    const m = String(d || '').match(/^(\d{4})\.(\d{2})\.(\d{2})/);
    if (!m) return null;
    const t = Date.UTC(+m[1], +m[2] - 1, +m[3], 12);
    return isNaN(t) ? null : t;
  }

  /* -> [{id, date, mode, white, black, result, reason, ucis, side, fen}] */
  function importPgn(text, core, now) {
    const t0 = now || Date.now();
    return splitGames(text).map((g, i) => {
      const fen = g.tags.FEN || null;
      let ch; try { ch = new core.Chess(fen || core.START); } catch (e) { return null; }
      const ucis = [];
      for (const san of sanTokens(g.moves)) { const m = ch.fromSan(san); if (!m) break; ucis.push(core.uci(m)); ch.play(m); }
      if (!ucis.length) return null;
      return {
        id: 'imp' + t0.toString(36) + i, date: parseDate(g.tags.Date) || t0 - i, mode: 'duo',
        white: g.tags.White || 'White', black: g.tags.Black || 'Black', result: g.tags.Result || '*',
        reason: 'Imported', ucis, side: 'w', fen
      };
    }).filter(Boolean);
  }

  const api = { splitGames, sanTokens, importPgn };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.PGN = api;
})(this);
