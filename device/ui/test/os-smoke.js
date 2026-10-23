/* Runs the real OS (the <script> in mockup/chaipi-os.html) with a fake canvas and a fake HOST, the way
   device/ui/host.js runs it on the Pi, and walks through the device features. Needs no browser and no Node:
     jsc device/ui/test/os-smoke.js -- mockup/chaipi-os.html device/ui/lib
   (jsc = /System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc on a Mac).
   Any exception inside a frame, a timer or a hook fails the run. */
'use strict';
const ARGS = typeof arguments !== 'undefined' ? arguments : scriptArgs;
const HTML = ARGS[0], LIB = ARGS[1];
const G = globalThis;
if (typeof console === 'undefined') G.console = { log: print, warn: print, error: print };
G.window = G;

/* ---------- virtual time ---------- */
let clock = 0, timerId = 0; const timers = new Map();
G.performance = { now: () => clock };
G.setTimeout = (f, ms) => { const id = ++timerId; timers.set(id, { f, at: clock + (ms || 0) }); return id; };
G.clearTimeout = id => timers.delete(id);
G.setInterval = (f, ms) => { const id = ++timerId; const t = { f, at: clock + ms, every: ms }; timers.set(id, t); return id; };
G.clearInterval = id => timers.delete(id);
const errors = [];
function fail(where, e) { errors.push(where + ': ' + (e && e.stack ? e.message + '\n' + e.stack.split('\n').slice(0, 4).join('\n') : e)); }

/* ---------- fake canvas ---------- */
const drawn = { text: [], images: 0, rects: 0 };
function fakeCtx() {
  const state = { font: '10px sans-serif', fillStyle: '#000', strokeStyle: '#000', globalAlpha: 1, lineWidth: 1, textAlign: 'left', textBaseline: 'alphabetic', lineDashOffset: 0, lineCap: 'butt', lineJoin: 'miter' };
  const grad = () => ({ addColorStop() {} });
  const methods = {
    measureText(s) { const px = parseFloat((String(state.font).match(/([\d.]+)px/) || [0, 10])[1]); return { width: String(s).length * px * 0.56, actualBoundingBoxAscent: px * 0.72, actualBoundingBoxDescent: px * 0.2 }; },
    fillText(s) { drawn.text.push(String(s)); if (drawn.text.length > 4000) drawn.text.splice(0, 2000); },
    createLinearGradient: grad, createRadialGradient: grad, createPattern: () => ({}),
    getImageData: (x, y, w, h) => ({ data: new Uint8ClampedArray(w * h * 4), width: w, height: h }),
    createImageData: (w, h) => ({ data: new Uint8ClampedArray(w * h * 4), width: w, height: h }),
    drawImage(img) { if (!img || !(img.width > 0)) throw new Error('drawImage without a real image'); drawn.images++; },
    fillRect() { drawn.rects++; },
    getLineDash: () => [], isPointInPath: () => false, getTransform: () => ({ a: 1, b: 0, c: 0, d: 1, e: 0, f: 0 })
  };
  return new Proxy(state, {
    get(t, k) { if (k in methods) return methods[k]; if (k in t) return t[k]; return typeof k === 'string' ? () => {} : undefined; },
    set(t, k, v) { t[k] = v; return true; }
  });
}
const ctx = fakeCtx();
const canvas = { width: 320, height: 240, getContext: () => ctx };
G.Path2D = function Path2D(d) { this.d = d; ['arc', 'moveTo', 'lineTo', 'closePath', 'rect', 'bezierCurveTo', 'quadraticCurveTo', 'ellipse', 'roundRect', 'addPath'].forEach(m => { this[m] = () => {}; }); };

/* ---------- storage ---------- */
const mem = new Map();
G.localStorage = { getItem: k => mem.has(k) ? mem.get(k) : null, setItem: (k, v) => mem.set(k, String(v)), removeItem: k => mem.delete(k) };

/* ---------- fake HOST ---------- */
const calls = []; const call = (name, ...a) => calls.push([name].concat(a));
const called = name => calls.filter(c => c[0] === name);
let api = null;
const FOOL = ['f2f3', 'e7e5', 'g2g4', 'd8h4'];
const HW = { usbHost: false, sd: false };
const FAKE_SHORTS = [0, 1, 2, 3, 4].map(i => ({ id: 'vid' + i, t: 'Short ' + i, c: '@chan' + i, l: '12K', views: true, dur: 20, hue: i * 40, m: 'ball' }));
let shortTime = 0;
const thumb = { width: 320, height: 180 };
G.CHAIPI_HOST = {
  canvas, profile: 'ili9341', version: 'ChAIpi OS test',
  attach(a) { api = a; call('attach'); },
  think(fen, depth, opt) {
    call('think', opt.purpose, depth);
    const f = fen.split(' '), ply = (Number(f[5]) - 1) * 2 + (f[1] === 'b' ? 1 : 0);
    const uci = FOOL[ply] || null;
    const lines = uci ? [{ uci, score: 30, exact: true }] : [];
    return new Promise(r => setTimeout(() => r({ lines, nodes: 1000 }), 5));
  },
  sysTick(SYS) { SYS.bat = 77; SYS.volts = 3.91; SYS.charging = false; SYS.usbHost = HW.usbHost; SYS.sd = HW.sd; SYS.ram = 210; SYS.wh = 14.8; SYS.load = [10, 20, 30, 40]; SYS.temp = 52; },
  haptic(l) { call('haptic', l); },
  display(o) { if (o.sleeping) call('display-sleep'); },
  power(m) { call('power', m); },
  saveGame(rec, pgn, name) { call('saveGame', pgn, name); },
  deleteGame(rec, name) { call('deleteGame', name); },
  freeSpace: () => '28.1 GB',
  qr(text) { call('qr', text); return { size: 25, get: (r, c) => (r * 7 + c * 3) % 5 === 0 }; },
  transfer: {
    start(o) { call('transfer.start', o); setTimeout(() => { api.XFER.ip = '192.168.4.1'; api.XFER.ssid = 'ChAIpi-TEST'; api.XFER.pass = 'brew-test-11'; api.XFER.ready = true; }, 300); },
    stop() { call('transfer.stop'); }, setPin(p) { call('transfer.setPin', p); }
  },
  wifi: {
    list: () => [{ ssid: 'Home 2.4', sec: true, sig: 4, five: false }, { ssid: 'Cafe', sec: false, sig: 2, five: false }, { ssid: '', hidden: true }],
    scanning: () => false, scan() { call('wifi.scan'); }, radio(on) { call('wifi.radio', on); },
    connect(ssid, pwd) { call('wifi.connect', ssid, pwd); return new Promise(r => setTimeout(() => r(pwd.length >= 8), 200)); },
    disconnect() { call('wifi.disconnect'); }, forget(s) { call('wifi.forget', s); }, ip: () => '192.168.1.77'
  },
  engines: {
    install(id, onP) { call('engines.install', id); return new Promise(r => { let p = 0; const tick = () => { p += .25; onP(p); if (p >= 1) r(true); else setTimeout(tick, 100); }; setTimeout(tick, 100); }); },
    remove(id) { call('engines.remove', id); }
  },
  shorts: {
    feed() { call('shorts.feed'); return new Promise(r => setTimeout(() => r(FAKE_SHORTS.slice()), 100)); },
    search(q) { call('shorts.search', q); const out = []; out.loading = true; setTimeout(() => { out.push(...FAKE_SHORTS.slice(0, 3)); out.loading = false; }, 300); return out; },
    image(v) { return { img: thumb, cover: true }; },
    time: () => shortTime, ended: () => false,
    play(v) { call('shorts.play', v && v.id); shortTime = 0; }, pause(on) { call('shorts.pause', on); }, seek(t) { call('shorts.seek', t); }, stop() { call('shorts.stop'); }
  },
  usb: { start() { call('usb.start'); return Promise.resolve(); }, stop() { call('usb.stop'); return Promise.resolve('Imported 2 games'); } },
  sd: {
    importAll() { call('sd.import'); return Promise.resolve('Imported 1 app'); }, exportGames() { call('sd.export'); return Promise.resolve('1 game copied'); },
    eject() { call('sd.eject'); return Promise.resolve('Safe to remove the card'); }, backup() { call('sd.backup'); return Promise.resolve('Backed up'); },
    summary: () => 'SD:/chaipi · engines 0 · apps 1 · games 3'
  },
  apps: { run(id) { call('apps.run', id); return new Promise(r => setTimeout(() => r(''), 500)); } }
};

/* ---------- frame loop driven by virtual time ---------- */
let rafQ = [];
G.requestAnimationFrame = cb => { rafQ.push(cb); return rafQ.length; };
async function step(ms) {
  const end = clock + ms;
  while (clock < end) {
    clock += 16;
    for (const [id, t] of [...timers.entries()].sort((a, b) => a[1].at - b[1].at)) {
      if (t.at > clock) continue;
      if (t.every) t.at += t.every; else timers.delete(id);
      try { t.f(); } catch (e) { fail('timer', e); }
    }
    const q = rafQ; rafQ = [];
    for (const cb of q) { try { cb(clock); } catch (e) { fail('frame', e); rafQ.push(cb); } }
    await null; await null;
  }
}
async function press(b, n) { for (let i = 0; i < (n || 1); i++) { api.btnDown(b); await step(40); api.btnUp(b); await step(60); } }
async function typeText(s) { for (const c of s) { const t = api.topTarget(); if (!t || !t.onChar) throw new Error('no text field on top'); t.onChar(c); await step(20); } }
const expect = (cond, what) => { if (!cond) fail('expect', what); else print('  ok  ' + what); };
const screenText = () => drawn.text.join(' | ');
function clearText() { drawn.text.length = 0; }

/* ---------- load the OS ---------- */
const html = read(HTML);
const s0 = html.lastIndexOf('<script>'), s1 = html.indexOf('</script>', s0);
try { (0, eval)(html.slice(s0 + 8, s1)); } catch (e) { fail('load', e); }
load(LIB + '/pgn.js');

async function main() {
  expect(api && called('attach').length === 1, 'OS loaded and called HOST.attach');
  api.S.timeout = 0;
  await step(5200);
  expect(api.OS.screen && !api.OS.screen.noQuick, 'boot animation finished, Home is showing');

  print('Helper game, played with Fn (play best), ends in mate');
  await press('RIGHT'); await press('OK'); await step(200); await press('OK'); await step(400);
  expect(api.OS.game && api.OS.game.cfg.mode === 'helper', 'helper game started');
  for (let i = 0; i < 4; i++) { await step(900); await press('FN'); }
  await step(1500);
  expect(called('think').some(c => c[1] === 'analyse'), 'analysis requests carry purpose "analyse"');
  const saved = called('saveGame');
  expect(saved.length === 1 && /Qh4#/.test(saved[0][1]) && /0-1/.test(saved[0][1]), 'finished game saved as PGN with Qh4# 0-1');
  expect(saved.length === 1 && /^chaipi-\d{4}-\d\d-\d\d-\w+\.txt$/.test(saved[0][2]), 'game file name ' + (saved[0] && saved[0][2]));

  print('Play vs ChAIpi: the engine move request');
  api.goHome(); await step(200);
  api.S.play.side = 'b';
  await press('OK'); await step(200);
  for (let i = 0; i < 12 && !(api.OS.game && api.OS.game.cfg.mode === 'play'); i++) { await press('OK'); await step(200); }
  await step(2500);
  const mv = called('think').filter(c => c[1] === 'move');
  expect(mv.length >= 1, 'engine asked for a move with purpose "move" (' + mv.length + ')');

  print('Transfer');
  api.goHome(); await step(200);
  await press('RIGHT', 5); await press('OK'); await step(200);
  await press('DOWN', 6); await press('OK'); await press('OK'); await step(200);
  await press('OK'); await step(1200);
  expect(called('transfer.start').length === 1, 'Activate starts the transfer server');
  expect(api.XFER.active, 'Transfer is live once the server reports ready');
  clearText(); await step(300);
  expect(called('qr').length > 0 && /WIFI:T:WPA;S:ChAIpi-TEST;P:brew-test-11;;/.test(called('qr')[0][1]), 'real QR code requested for the hotspot');
  expect(/192\.168\.4\.1/.test(screenText()), 'screen shows the hotspot address');
  api.PHN.stage = 'portal'; api.xferEvent('Phone opened the transfer page'); await step(300);
  await press('FN'); await step(100);
  expect(called('transfer.setPin').length === 1, 'Fn makes a new PIN and tells the server');
  api.stopTransfer(); await step(200);
  expect(called('transfer.stop').length >= 1 && !api.XFER.active, 'stopping Transfer stops the server');

  print('Wi-Fi');
  api.goHome(); await step(200);
  await press('RIGHT', 5); await press('OK'); await step(200);
  await press('DOWN', 5); await press('OK'); await press('OK'); await step(300);
  if (!api.S.wifi) { await press('OK'); await step(300); }
  expect(called('wifi.scan').length >= 1 || called('wifi.radio').length >= 1, 'Wi-Fi screen asks for a scan');
  await press('DOWN'); await press('OK'); await step(200);
  await typeText('chai-pass-123'); api.topTarget().submit(); await step(600);
  const cn = called('wifi.connect');
  expect(cn.length === 1 && cn[0][1] === 'Home 2.4' && cn[0][2] === 'chai-pass-123', 'connect sends the typed password');
  expect(api.S.wifiNet === 'Home 2.4', 'connected network shown');

  print('Shorts');
  api.goHome(); await step(200);
  await press('RIGHT', 3); await press('OK'); await step(200);
  await press('TAB', 3); await press('OK'); await step(600);
  expect(called('shorts.feed').length === 1, 'Shorts loads the real feed');
  clearText(); await step(200);
  expect(/Short 0/.test(screenText()), 'feed titles come from the host');
  expect(drawn.images > 0, 'thumbnails drawn');
  await press('DOWN'); await press('OK'); await step(300);
  expect(called('shorts.play').length >= 1, 'Watch Shorts starts playback');
  await press('DOWN'); await step(300); await press('OK'); await step(100);
  expect(called('shorts.pause').some(c => c[1] === true), 'Confirm pauses');
  await press('ESC'); await step(200);
  expect(called('shorts.stop').length >= 1, 'Esc stops the video');
  await press('UP'); await press('OK'); await step(200);
  await typeText('king'); api.topTarget().submit(); await step(100);
  clearText(); await step(100);
  expect(/Searching/.test(screenText()), 'search shows Searching… while it loads');
  await step(500); clearText(); await step(100);
  expect(/Short 1/.test(screenText()), 'search results shown');
  await press('OK'); await step(200); await press('RIGHT'); await step(100); await press('ESC'); await step(200);
  expect(called('shorts.seek').length === 1, 'right seeks while watching');

  print('Engine catalog');
  api.goHome(); await step(200);
  await press('RIGHT', 5); await press('OK'); await step(200);
  await press('DOWN', 2); await press('OK'); await press('DOWN', 3); await press('OK'); await step(200);
  await press('DOWN'); await press('OK'); await step(200); await press('OK'); await step(800);
  expect(called('engines.install').length === 1 && api.S.installed.includes(called('engines.install')[0][1]), 'download installs through the host');

  print('Custom Python app');
  api.addCustomApp({ id: 'myapp', name: 'My App', ram: 20 });
  api.goHome(); await step(200);
  await press('RIGHT', 3); await press('OK'); await step(200);
  await press('RIGHT', 8); await press('OK'); await step(200);
  expect(called('apps.run').length === 1 && called('apps.run')[0][1] === 'myapp', 'opening the app runs it as a process');
  await step(800);

  print('USB drive and SD card');
  api.goHome(); await step(200);
  await press('RIGHT', 5); await press('OK'); await step(200);
  await press('DOWN', 6); await press('OK'); await press('DOWN', 4); await press('OK'); await step(300);
  expect(called('usb.start').length === 1, 'USB drive mode starts the gadget');
  HW.usbHost = true; await step(300); await press('ESC'); await step(400);
  expect(called('usb.stop').length === 1, 'Esc ejects and imports');
  HW.sd = true; await step(100);
  await press('DOWN'); await press('OK'); await step(200);
  clearText(); await step(100);
  expect(/apps 1/.test(screenText()), 'SD summary from the host');
  await press('OK'); await step(200);
  expect(called('sd.import').length === 1, 'Import all goes to the host');

  print('History delete, sleep and shut down');
  api.goHome(); await step(200);
  await press('RIGHT', 4); await press('OK'); await step(200);
  await press('FN'); await step(200); await press('OK'); await step(300);
  expect(called('deleteGame').length === 1 && called('deleteGame')[0][1] === saved[0][2], 'deleting a game removes its .txt file');
  api.goHome(); await step(200);
  api.S.timeout = 5; await step(6000);
  expect(called('display-sleep').length > 0, 'screen sleeps and the host dims the backlight');
  await press('OK'); api.S.timeout = 0; await step(200);
  await press('MENU'); await step(200); await press('DOWN', 4); await press('OK'); await step(2500);
  expect(called('power').length === 1 && called('power')[0][1] === 'off', 'Shut down asks the host to power off, once');

  print('PGN import with the OS chess rules');
  const recs = PGN.importPgn('[White "A"]\n[Black "B"]\n[Result "1-0"]\n\n1. e4 {best} e5 2. Qh5 Nc6 (2... g6) 3. Bc4 Nf6?? 4. Qxf7# 1-0\n', api.core, 1);
  expect(recs.length === 1 && recs[0].ucis.length === 7 && recs[0].ucis[6] === 'h5f7', 'PGN with comments and variations imports 7 moves');

  print(errors.length ? '\nFAILED: ' + errors.length + ' problem(s)\n' + errors.join('\n\n') : '\nAll smoke checks passed.');
}
main().catch(e => { fail('main', e); print('\nFAILED\n' + errors.join('\n\n')); });
