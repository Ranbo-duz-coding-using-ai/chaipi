/* Unit tests for the device UI's pure helpers and the engine request logic (with a fake Stockfish).
     jsc device/ui/test/lib-test.js -- device/ui/lib config/chaipi.example.toml */
'use strict';
const ARGS = typeof arguments !== 'undefined' ? arguments : scriptArgs;
const LIB = ARGS[0], CONF = ARGS[1];
const G = globalThis;
let failures = 0;
const ok = (c, what) => { if (c) print('  ok  ' + what); else { failures++; print('  FAIL ' + what); } };
const eq = (a, b, what) => ok(JSON.stringify(a) === JSON.stringify(b), what + (JSON.stringify(a) === JSON.stringify(b) ? '' : ' -> got ' + JSON.stringify(a) + ', want ' + JSON.stringify(b)));

['toml.js', 'uci-parse.js', 'pixels.js', 'nmcli-parse.js'].forEach(f => load(LIB + '/' + f));

print('toml');
const conf = TOML.parse(read(CONF));
eq([conf.buttons.OK, conf.buttons.MENU, conf.buttons.STICK], [5, 23, 27], 'button pins from the example config');
eq(conf.adc.address, 0x48, 'hex values');
eq(conf.engine.analyse_steps_ms, [250, 900], 'arrays');
eq(conf.paths.data, '/data/chaipi', 'strings with trailing comments');
eq(TOML.parse('a = "x # not a comment" # real one\n[t.u]\nb = true\nc = -1.5e2\n'), { a: 'x # not a comment', t: { u: { b: true, c: -150 } } }, 'quoted hash, dotted tables, floats');

print('uci-parse');
const i1 = UCIParse.parseInfo('info depth 22 seldepth 30 multipv 2 score cp -34 upperbound nodes 1234567 nps 900000 hashfull 120 tbhits 0 time 1371 pv e2e4 e7e5 g1f3');
eq([i1.depth, i1.multipv, i1.score, i1.bound, i1.nodes, i1.pv.length], [22, 2, { cp: -34 }, 'upperbound', 1234567, 3], 'info line');
eq(UCIParse.parseInfo('info depth 5 currmove e2e4 currmovenumber 1'), null, 'currmove lines carry no line');
eq(UCIParse.parseInfo('info string NNUE evaluation using nn-1a298aa575a0.nnue'), null, 'info string ignored');
eq(UCIParse.parseInfo('info depth 30 score mate 3 wdl 1000 0 0 pv d8h4').score, { mate: 3 }, 'mate score with wdl');
eq([UCIParse.toScore({ mate: 1 }), UCIParse.toScore({ mate: 3 }), UCIParse.toScore({ mate: -2 }), UCIParse.toScore({ mate: 0 }), UCIParse.toScore({ cp: 41 })], [99999, 99995, -99996, -100000, 41], 'score scale matches the OS (mate = 100000 - plies)');
const o = UCIParse.parseOption('option name UCI_Elo type spin default 1320 min 1320 max 3190');
eq([o.name, o.type, o.min, o.max], ['UCI_Elo', 'spin', 1320, 3190], 'spin option');
eq(UCIParse.parseOption('option name Analysis Contempt type combo default Both var Off var White var Black var Both').vars, ['Off', 'White', 'Black', 'Both'], 'combo option');
eq(UCIParse.parseOption('option name EvalFile type string default nn-1a298aa575a0.nnue').default, 'nn-1a298aa575a0.nnue', 'string option default');
const book = new UCIParse.LineBook();
['info depth 10 multipv 1 score cp 50 pv e2e4 e7e5', 'info depth 10 multipv 2 score cp 20 pv d2d4', 'info depth 11 multipv 1 score cp 45 lowerbound pv e2e4', 'info depth 11 multipv 1 score cp 48 pv e2e4 c7c5', 'info depth 11 multipv 2 score cp 60 pv d2d4 d7d5'].forEach(l => book.add(UCIParse.parseInfo(l)));
eq(book.lines('e2e4').map(l => [l.uci, l.score, l.exact]), [['e2e4', 48, true], ['d2d4', 60, true]], 'bestmove first, then by score');
eq(book.lines('(none)'), [], 'no move in a finished position');
eq(UCIParse.parseBestmove('bestmove g1f3 ponder d7d5'), { best: 'g1f3', ponder: 'd7d5' }, 'bestmove with ponder');

print('pixels');
const rgba = new Uint8ClampedArray([255, 0, 0, 255, 0, 255, 0, 255, 0, 0, 255, 255, 255, 255, 255, 255]);
const px = Pixels.toRgb565(rgba, new Uint16Array(4), 2, 2, false);
eq([...px], [0xf800, 0x07e0, 0x001f, 0xffff], 'RGB565 packing');
eq([...Pixels.toRgb565(rgba, new Uint16Array(4), 2, 2, true)], [0xffff, 0x001f, 0x07e0, 0xf800], '180 degree flip');
eq([...Pixels.rotate90(new Uint16Array([1, 2, 3, 4, 5, 6]), new Uint16Array(6), 3, 2)], [4, 1, 5, 2, 6, 3], '90 degree rotation');
const a = new Uint16Array(4 * 5), b = a.slice(); b[1 * 4 + 2] = 9; b[3 * 4] = 1;
eq(Pixels.dirtyRows(a, b, 4, 5), [1, 3], 'dirty row range');
eq(Pixels.dirtyRows(a, a.slice(), 4, 5), null, 'identical frames send nothing');

print('nmcli-parse');
eq(NmcliParse.splitTerse('*:My\\:Net:80:WPA2:2437 MHz'), ['*', 'My:Net', '80', 'WPA2', '2437 MHz'], 'escaped colons');
const nets = NmcliParse.parseWifiList([':Home WiFi:62:WPA2:5180 MHz', '*:Home WiFi:70:WPA2:2437 MHz', ':Chai Point Guest:30::2412 MHz', '::90:WPA2:2462 MHz', ':Office 5G:95:WPA3:5745 MHz'].join('\n'));
eq(nets.map(n => [n.ssid, n.sig, n.sec, n.five, n.inUse]), [['Home WiFi', 3, true, false, true], ['Chai Point Guest', 2, false, false, false], ['Office 5G', 4, true, true, false]], 'one row per name, 2.4 GHz preferred, hidden dropped');
eq(NmcliParse.parseSaved('Home WiFi:802-11-wireless\nchaipi-hotspot:802-11-wireless\nWired:802-3-ethernet\nlo:loopback', ['chaipi-hotspot']), ['Home WiFi'], 'saved networks without the hotspot');
eq(NmcliParse.parseActive('no:Cafe\nyes:Home WiFi'), 'Home WiFi', 'active network');
eq(NmcliParse.parseIp('IP4.ADDRESS[1]:192.168.1.42/24'), '192.168.1.42', 'IP address');

print('engine requests (fake Stockfish)');
/* minimal CommonJS so engine.js loads under jsc */
let now = 0; const timers = []; G.setTimeout = (f, ms) => { timers.push({ f, at: now + (ms || 0) }); return timers.length; };
G.clearTimeout = () => {};
const runTimers = async ms => { const end = now + ms; while (now < end) { now += 5; for (const t of timers.splice(0)) { if (t.at <= now) t.f(); else timers.push(t); } await null; await null; } };
G.module = { exports: {} };
G.require = n => n === './uci-parse' ? UCIParse : n === 'os' ? { cpus: () => [1, 2, 3, 4], setPriority() {} } : n === 'readline' ? {} : n === 'child_process' ? { spawn() { throw new Error('no spawn in tests'); } } : {};
load(LIB + '/engine.js');
const ThinkerC = module.exports.Thinker;

function fakeEngine(opts) {
  const sent = [];
  const e = {
    spec: { exe: 'fake' }, sent, proc: {}, deaths: [], options: new Map(), waiters: [], onLine: null, crashOnGo: opts && opts.crashOnGo || 0,
    start: () => Promise.resolve(), restartsLastMinute: () => 0, has: n => e.options.has(n),
    set(name, v) { if (!e.options.has(name)) return false; sent.push('setoption ' + name + ' ' + v); return true; },
    expect(test) { return new Promise((resolve, reject) => e.waiters.push({ test, resolve, reject })); },
    emit(line) { if (e.onLine) e.onLine(line); const w = e.waiters.findIndex(x => x.test(line)); if (w >= 0) e.waiters.splice(w, 1)[0].resolve(line); },
    send(cmd) {
      sent.push(cmd);
      if (cmd.startsWith('go')) {
        if (e.crashOnGo > 0) { e.crashOnGo--; setTimeout(() => { const ws = e.waiters.splice(0); ws.forEach(x => x.reject(new Error('engine stopped'))); }, 10); return; }
        const ms = /movetime (\d+)/.test(cmd) ? +RegExp.$1 : /infinite/.test(cmd) ? 1e9 : 50;
        const mpv = +((sent.filter(s => s.startsWith('setoption MultiPV')).pop() || 'x 1').split(' ').pop());
        e.goTimer = { done: false };
        const g = e.goTimer;
        setTimeout(() => { for (let k = 1; k <= mpv; k++) e.emit('info depth 12 multipv ' + k + ' score cp ' + (60 - k * 10) + ' nodes 5000 pv ' + ['e2e4', 'd2d4', 'g1f3', 'c2c4', 'b1c3', 'e2e3', 'g2g3', 'f2f4'][k - 1]); }, 5);
        setTimeout(() => { if (!g.done) { g.done = true; e.emit('bestmove e2e4'); } }, Math.min(ms, 1e8));
      }
      if (cmd === 'stop' && e.goTimer && !e.goTimer.done) { e.goTimer.done = true; setTimeout(() => e.emit('bestmove e2e4'), 1); }
    }
  };
  ['Threads', 'Hash', 'MultiPV', 'UCI_LimitStrength'].forEach(n => e.options.set(n, { name: n, type: n === 'UCI_LimitStrength' ? 'check' : 'spin' }));
  if (!(opts && opts.noElo)) e.options.set('UCI_Elo', { name: 'UCI_Elo', type: 'spin', min: 1320, max: 3190 });
  return e;
}
const cfg = { log: () => {}, thinkMs: { fast: 1000, medium: 4000, deep: 12000 }, analyseSteps: [250, 900], reviewMs: 250, weakMultipv: 8, restartMax: 5 };

(async () => {
  let t = new ThinkerC(cfg); t.engine = fakeEngine();
  const FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';
  let r = null; t.think(FEN, 2, { purpose: 'move', elo: 1800, think: 'fast' }).then(x => { r = x; });
  await runTimers(1100);
  ok(r && r.lines.length === 1 && r.lines[0].uci === 'e2e4', 'Elo 1800 move returns one line');
  ok(t.engine.sent.includes('setoption UCI_LimitStrength true') && t.engine.sent.includes('setoption UCI_Elo 1800') && t.engine.sent.includes('go movetime 1000'), 'Elo 1800 uses UCI_LimitStrength + UCI_Elo and the Fast think time');

  t = new ThinkerC(cfg); t.engine = fakeEngine(); r = null;
  t.think(FEN, 1, { purpose: 'move', elo: 600, think: 'medium' }).then(x => { r = x; });
  await runTimers(1600);
  ok(r && r.lines.length === 8, 'Elo 600 gets 8 candidate moves for the OS to choose from (' + (r && r.lines.length) + ')');
  ok(t.engine.sent.some(s => /^go depth 4 movetime 1500/.test(s)) && t.engine.sent.includes('setoption UCI_LimitStrength false'), 'Elo 600 searches shallow, unlimited');

  t = new ThinkerC(cfg); t.engine = fakeEngine(); r = null;
  t.think(FEN, 3, { purpose: 'move', elo: 3190, think: 'deep' }).then(x => { r = x; });
  await runTimers(50);
  ok(t.engine.sent.includes('go movetime 12000') && !t.engine.sent.includes('setoption UCI_LimitStrength true'), 'Max strength: full power, Deep = 12 s');

  t = new ThinkerC(cfg); t.engine = fakeEngine({ noElo: true }); r = null;
  t.think(FEN, 2, { purpose: 'move', elo: 2000, think: 'fast' }).then(x => { r = x; });
  await runTimers(1600);
  ok(r && r.lines.length === 8, 'engine without UCI_Elo falls back to MultiPV weakening');

  t = new ThinkerC(cfg); t.engine = fakeEngine(); let a1 = null, a2 = null;
  t.think(FEN, 3, { purpose: 'analyse', think: 'deep', last: true }).then(x => { a1 = x; });
  await runTimers(100);
  t.think(FEN, 1, { purpose: 'analyse', think: 'deep' }).then(x => { a2 = x; });
  await runTimers(400);
  ok(a1 && a1.lines.length === 3, 'a new analysis stops the old one, which still returns its lines');
  ok(a2 && a2.lines.length === 3 && t.engine.sent.includes('go movetime 250'), 'first analysis pass is 250 ms with 3 lines');

  t = new ThinkerC(cfg); t.engine = fakeEngine(); let mvR = null, anR = null;
  t.think(FEN, 2, { purpose: 'move', elo: 1500, think: 'fast' }).then(x => { mvR = x; });
  await runTimers(100);
  t.think(FEN, 1, { purpose: 'analyse', think: 'fast' }).then(x => { anR = x; });
  await runTimers(200);
  ok(!mvR && !t.engine.sent.slice(-3).includes('stop'), 'an engine move is never interrupted by analysis');
  await runTimers(1500);
  ok(mvR && mvR.lines.length === 1 && anR && anR.lines.length === 3, 'the analysis runs after the move');

  t = new ThinkerC(cfg); t.engine = fakeEngine(); r = null;
  t.ponder(FEN); await runTimers(100);
  ok(t.engine.sent.includes('go infinite'), 'pondering runs an infinite search');
  t.think(FEN, 2, { purpose: 'move', elo: 2500, think: 'fast' }).then(x => { r = x; });
  await runTimers(1200);
  ok(t.engine.sent.includes('stop') && r && r.lines.length === 1, 'a real request stops the ponder search');

  t = new ThinkerC(cfg); t.engine = fakeEngine({ crashOnGo: 1 }); r = null;
  t.think(FEN, 2, { purpose: 'move', elo: 2000, think: 'fast' }).then(x => { r = x; });
  await runTimers(1300);
  ok(r && r.lines.length === 1, 'an engine crash during a move is retried, so the game does not stall');

  t = new ThinkerC(cfg); t.engine = fakeEngine(); r = null;
  t.think(FEN, 2, { purpose: 'review' }).then(x => { r = x; });
  await runTimers(300);
  ok(r && r.lines.length === 1 && t.engine.sent.includes('go movetime 250') && t.engine.sent.includes('setoption MultiPV 1'), 'review: one line, 250 ms');

  print(failures ? '\n' + failures + ' FAILED' : '\nAll library tests passed.');
})();
