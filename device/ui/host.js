#!/usr/bin/env node
'use strict';
/* ChAIpi device host.
   Runs the very same OS as mockup/chaipi-os.html (its <script> block) inside Node.js, with a Skia canvas
   (@napi-rs/canvas) instead of a browser. It gives the OS a HOST object (window.CHAIPI_HOST) that answers
   with the real hardware: Stockfish over UCI, buttons and battery from chaipi-input, NetworkManager for
   Wi-Fi, the transfer server, yt-dlp/ffmpeg for Shorts, the USB gadget and the SD slot.
   docs/13-device-software.md describes every hook. */
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { execFile } = require('child_process');

const TOML = require('./lib/toml');
const { FileStorage, writeAtomic } = require('./lib/store');
const { Framebuffer } = require('./lib/framebuffer');
const { Thinker } = require('./lib/engine');
const { InputClient } = require('./lib/input');
const sysinfo = require('./lib/sysinfo');
const { Wifi } = require('./lib/wifi');
const { Transfer } = require('./lib/transfer');
const { Shorts } = require('./lib/shorts');
const { Engines } = require('./lib/engines');
const { Media, usbConfigured, sdPresent } = require('./lib/media');
const { Apps, listApps } = require('./lib/apps');
const { importPgn } = require('./lib/pgn');

/* ---------- configuration ---------- */
const argv = process.argv.slice(2);
const arg = (k, d) => { const i = argv.indexOf(k); return i >= 0 ? argv[i + 1] : d; };
const CONFIG = arg('--config', '/etc/chaipi/chaipi.toml');
const HEADLESS = argv.includes('--headless');
const ROOT = path.resolve(__dirname, '..', '..');

const DEFAULTS = {
  paths: { data: '/data/chaipi', engines: '/opt/chaipi/engines', fonts: '/opt/chaipi/fonts', os: '/opt/chaipi/ui/chaipi-os.html', run: '/run/chaipi', sdk: '/opt/chaipi/device/sdk' },
  display: { fb: 'auto', rotate: 0, fps: 30, idle_fps: 12 },
  backlight: { sleep_level: 0.04, off_after_sleep_s: 600 },
  vibration: { light_ms: 18, strong_ms: 45 },
  battery: { capacity_mah: 4000 },
  engine: { threads: 4, nice: 5, hash_mb: 64, think_fast_ms: 1000, think_medium_ms: 4000, think_deep_ms: 12000, analyse_steps_ms: [250, 900], review_ms: 250, weak_multipv: 8, restart_max: 5 },
  audio: { volume: 70, max_volume: 85 },
  transfer: { port: 80 },
  shorts: { feed_query: 'chess #shorts', max_height: 360, yt_dlp: '/opt/chaipi/venv/bin/yt-dlp' },
  catalog: { url: '' }
};
function loadConfig(file) {
  let user = {};
  try { user = TOML.parse(fs.readFileSync(file, 'utf8')); } catch (e) { console.log('config:', e.message, '(using defaults)'); }
  const out = JSON.parse(JSON.stringify(DEFAULTS));
  for (const [k, v] of Object.entries(user)) out[k] = Object.assign(out[k] || {}, v);
  return out;
}
const cfg = loadConfig(CONFIG);
const P = cfg.paths;
const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a);
['games', 'engines', 'apps', 'puzzles', 'inbox', 'logs', 'tmp'].forEach(d => fs.mkdirSync(path.join(P.data, d), { recursive: true }));

/* ---------- canvas and fonts ---------- */
const canvasLib = require('@napi-rs/canvas');
const QRCode = (() => { try { return require('qrcode'); } catch (e) { return null; } })();
const FONT_FAMILIES = [
  [/^AtkinsonHyperlegible/i, 'Atkinson Hyperlegible'], [/^JetBrainsMono/i, 'JetBrains Mono'],
  [/^Unbounded/i, 'Unbounded'], [/^NotoSansSymbols2/i, 'Noto Sans Symbols 2']
];
try {
  for (const f of fs.readdirSync(P.fonts)) {
    if (!/\.(ttf|otf)$/i.test(f)) continue;
    const fam = FONT_FAMILIES.find(([re]) => re.test(f));
    canvasLib.GlobalFonts.registerFromPath(path.join(P.fonts, f), fam ? fam[1] : undefined);
  }
} catch (e) { log('fonts:', e.message); }

let fb = null;
if (!HEADLESS) {
  try { fb = new Framebuffer({ fb: cfg.display.fb, rotate: cfg.display.rotate }); log('display', fb.dev, fb.name, fb.fbW + 'x' + fb.fbH); }
  catch (e) { log('display:', e.message, '- running without a screen'); }
}
const PROFILE_BY_SIZE = { '320x240': 'ili9341', '480x320': 'ili9486', '800x480': 'hdmi5', '160x128': 'st7735', '240x320': 'port28', '320x480': 'port35' };
const profile = fb ? (PROFILE_BY_SIZE[fb.fbW + 'x' + fb.fbH] || 'ili9341') : 'ili9341';
const canvas = canvasLib.createCanvas(fb ? fb.fbW : 320, fb ? fb.fbH : 240);
const ctx = canvas.getContext('2d');
const CtxProto = Object.getPrototypeOf(ctx);
if (typeof CtxProto.roundRect !== 'function') {
  CtxProto.roundRect = function (x, y, w, h, r) {
    r = Math.max(0, Math.min(typeof r === 'number' ? r : (r && r[0]) || 0, w / 2, h / 2));
    this.moveTo(x + r, y); this.arcTo(x + w, y, x + w, y + h, r); this.arcTo(x + w, y + h, x, y + h, r);
    this.arcTo(x, y + h, x, y, r); this.arcTo(x, y, x + w, y, r); this.closePath();
  };
}

/* ---------- services ---------- */
const store = new FileStorage(path.join(P.data, 'state.json'), log);
const input = new InputClient(path.join(P.run, 'input.sock'), log);
const S_ = () => api && api.S;
const thinker = new Thinker({
  log, threads: cfg.engine.threads, nice: cfg.engine.nice, restartMax: cfg.engine.restart_max,
  hash: () => (S_() && S_().hash) || cfg.engine.hash_mb,
  thinkMs: { fast: cfg.engine.think_fast_ms, medium: cfg.engine.think_medium_ms, deep: cfg.engine.think_deep_ms },
  analyseSteps: cfg.engine.analyse_steps_ms, reviewMs: cfg.engine.review_ms, weakMultipv: cfg.engine.weak_multipv
});
thinker.onError = () => api && api.toast('The engine stopped. Restarting it…');
const PYPATH = [path.join(ROOT, 'device', 'transfer'), P.sdk].join(':');
const engines = new Engines({ builtinDir: P.engines, dataDir: path.join(P.data, 'engines'), catalogUrl: cfg.catalog.url, tmpDir: path.join(P.data, 'tmp'), data: P.data, pythonPath: PYPATH, log });
const wifi = new Wifi({ log, hotspotName: cfg.transfer.hotspot_connection });
const transfer = new Transfer({ log, data: P.data, port: cfg.transfer.port, portal: path.join(ROOT, 'device', 'transfer', 'portal'), fonts: P.fonts, config: CONFIG, cwd: ROOT, pythonPath: PYPATH });
const shorts = new Shorts({ log, canvasLib, ytdlp: cfg.shorts.yt_dlp, feedQuery: cfg.shorts.feed_query, maxHeight: cfg.shorts.max_height });
const media = new Media({ log, helper: '/opt/chaipi/bin/chaipi-media' });
const apps = new Apps({ log, data: P.data, sdk: P.sdk, inputSock: path.join(P.run, 'input.sock') });
let VERSION = 'ChAIpi OS'; try { VERSION = 'ChAIpi OS ' + fs.readFileSync('/opt/chaipi/VERSION', 'utf8').trim(); } catch (e) { /* dev checkout */ }

/* ---------- live hardware state ---------- */
const HW = { bat: 80, volts: 0, usb: false, charging: false, loads: [0, 0, 0, 0], temp: 45, ram: 0, usbHost: false, sd: false };
let api = null, appMode = false, escTimer = null, shortsScreen = null, restartWhenIdle = false;
let backlight = -1, sleepSince = 0, deepSleep = false, lastSd = false;

input.on('event', m => {
  if (m.e === 'sys') { Object.assign(HW, { bat: m.bat, volts: m.volts, usb: m.usb, charging: m.charging }); return; }
  if (m.e === 'lowbatt') { lowBattery(); return; }
  if (!api) return;
  if (appMode) {
    // While a Python app owns the screen, only "hold Esc" reaches the OS.
    if (m.e === 'down' && m.b === 'ESC') escTimer = setTimeout(() => apps.kill(), 1000);
    if (m.e === 'up' && m.b === 'ESC') clearTimeout(escTimer);
    return;
  }
  if (m.e === 'down') api.btnDown(m.b);
  else if (m.e === 'up') api.btnUp(m.b);
  else if (m.e === 'char' || m.e === 'submit') {
    const t = api.topTarget(); api.OS.lastInput = performance.now();
    if (m.e === 'char' && t && t.onChar) t.onChar(String(m.c).slice(0, 1));
    if (m.e === 'submit' && t && t.submit) t.submit();
  }
});
input.on('connected', () => { backlight = -1; });

setInterval(() => {
  HW.loads = sysinfo.cpuLoads() || HW.loads;
  HW.temp = sysinfo.tempC() || HW.temp;
  const r = sysinfo.ramUsedMb(); if (r) HW.ram = r.used;
  HW.usbHost = usbConfigured();
  HW.sd = sdPresent();
}, 1000);

function lowBattery() {
  log('battery empty: saving and powering off');
  if (api) api.toast('Battery empty · saving and switching off');
  store.flush();
  setTimeout(() => execFile('systemctl', ['poweroff'], () => {}), 4000);
}

/* ---------- content: engines, apps, puzzle packs ---------- */
function registerEngines() {
  engines.refresh();
  const S = api.S;
  const ids = engines.ids();
  S.installed = ['sf19'].concat(ids.filter(id => id !== 'sf19'));
  for (const id of ids) {
    const e = engines.get(id);
    if (!api.ENGINES.some(x => x.id === id)) {
      const entry = { id, name: e.name || id, short: e.short || e.name || id, by: e.by || 'Uploaded', tier: e.tier || 'Custom', type: e.type || 'UCI', desc: e.desc || 'Added from your phone or the SD card.' };
      api.ENGINES.push(entry);
      if (!S.customEngines.some(x => x.id === id)) S.customEngines.push(entry);
    }
  }
  S.profiles.forEach(p => { if (!engines.get(p.engine)) p.engine = 'sf19'; });
}
function registerApps() {
  const S = api.S, list = listApps(path.join(P.data, 'apps'));
  S.customApps = list.map(a => ({ id: a.id, name: a.name, ram: a.ram }));
  list.forEach(a => api.addCustomApp({ id: a.id, name: a.name, ram: a.ram }));
}
function registerPuzzles() {
  const S = api.S, dir = path.join(P.data, 'puzzles'), packs = [];
  let files = []; try { files = fs.readdirSync(dir).filter(f => f.endsWith('.json')); } catch (e) { /* none */ }
  for (const f of files) {
    try {
      const pack = JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8'));
      let n = 0;
      for (const p of pack.puzzles || []) {
        if (!p.fen || api.PUZZLES.some(x => x.id === p.id)) continue;
        const c = new api.core.Chess(p.fen);
        if (!c.moves().some(m => { c.make(m); const mate = c.inCheck() && !c.moves().length; c.undo(); return mate; })) continue;
        api.PUZZLES.push({ id: p.id, name: p.name || pack.name, rating: p.rating || 1000, fen: p.fen }); n++;
      }
      packs.push({ name: String(pack.name || f).slice(0, 24), count: n });
    } catch (e) { log('puzzle pack', f, e.message); }
  }
  S.puzzlePacks = packs;
}
/* Games that arrived as PGN (phone, USB drive, SD card) wait in inbox/games. Each becomes a History entry
   and its own .txt file, exactly like a game played on ChAIpi. */
function importInboxGames() {
  const dir = path.join(P.data, 'inbox', 'games');
  let files = []; try { files = fs.readdirSync(dir).filter(f => /\.(pgn|txt)$/i.test(f)); } catch (e) { return 0; }
  let n = 0;
  for (const f of files) {
    const file = path.join(dir, f);
    try {
      const recs = importPgn(fs.readFileSync(file, 'utf8'), api.core);
      const list = store.getItem('chaipi.games') ? JSON.parse(store.getItem('chaipi.games')) : [];
      for (const r of recs) {
        list.unshift(r);
        try { writeAtomic(path.join(P.data, 'games', api.fileName(r)), api.pgnOf(r)); } catch (e) { log('save imported game:', e.message); }
      }
      store.setItem('chaipi.games', JSON.stringify(list.slice(0, 500)));
      n += recs.length;
    } catch (e) { log('import games', f, e.message); }
    fs.rmSync(file, { force: true });
  }
  return n;
}
function reloadContent() {
  registerEngines(); registerApps(); registerPuzzles();
  const n = importInboxGames();
  api.saveS();
  return n;
}

/* ---------- the HOST object the OS talks to ---------- */
const qrCache = new Map();
const HOST = {
  canvas, profile, version: VERSION,
  attach(a) {
    api = a;
    reloadContent();
    applyVolume(cfg.audio.volume);
    wifi.sync().then(() => { if (wifi.apply(api.S)) api.saveS(); });
    log('OS attached;', api.ENGINES.length, 'engines,', api.PUZZLES.length, 'puzzles');
  },
  think: (fen, depth, opt) => thinker.think(fen, depth, opt),
  sysTick(SYS) {
    SYS.load = HW.loads.length ? HW.loads : SYS.load; SYS.temp = HW.temp; SYS.bat = HW.bat; SYS.volts = HW.volts;
    SYS.charging = HW.charging; SYS.usbHost = HW.usbHost; SYS.sd = HW.sd; SYS.ram = HW.ram;
    SYS.wh = cfg.battery.capacity_mah * 3.7 / 1000;
  },
  haptic(level) { input.send({ cmd: 'buzz', ms: level === 'strong' ? cfg.vibration.strong_ms : cfg.vibration.light_ms }); },
  display({ bright, dim, sleeping }) {
    const now = Date.now();
    if (sleeping) { if (!sleepSince) sleepSince = now; } else { sleepSince = 0; deepSleep = false; }
    if (sleepSince && now - sleepSince > cfg.backlight.off_after_sleep_s * 1000) deepSleep = true;
    const level = deepSleep ? 0 : sleeping ? cfg.backlight.sleep_level : dim ? bright * 0.35 : bright;
    if (Math.abs(level - backlight) > 0.005) { backlight = level; input.send({ cmd: 'backlight', level }); }
  },
  power(mode) {
    store.flush(); transfer.stop(); shorts.stop();
    execFile('systemctl', [mode === 'restart' ? 'reboot' : 'poweroff'], err => { if (err) log('power:', err.message); });
  },
  saveGame(rec, pgn, name) { try { writeAtomic(path.join(P.data, 'games', name), pgn); } catch (e) { log('save game:', e.message); } },
  deleteGame(rec, name) { try { fs.rmSync(path.join(P.data, 'games', name), { force: true }); } catch (e) { log('delete game:', e.message); } },
  freeSpace: () => sysinfo.freeSpace(P.data),
  qr(text) {
    if (!qrCache.has(text)) {
      try { const m = QRCode.create(text, { errorCorrectionLevel: 'M' }).modules; qrCache.set(text, { size: m.size, get: (r, c) => !!m.get(r, c) }); }
      catch (e) { log('qr:', e.message); qrCache.set(text, null); }
    }
    return qrCache.get(text);
  },
  transfer: {
    start(o) { transfer.start(o); },
    stop() { transfer.stop(); if (restartWhenIdle) setTimeout(() => restartUi('restored backup'), 1500); },
    setPin(pin) { transfer.setPin(pin); }
  },
  wifi: {
    list: () => wifi.list(), scanning: () => wifi.scanning(), scan: () => { wifi.scan(); },
    radio: on => { wifi.radio(on).then(() => wifi.sync()).then(() => wifi.apply(api.S) && api.saveS()); },
    connect: (ssid, pwd, o) => wifi.connect(ssid, pwd, o).then(ok => { wifi.apply(api.S); api.saveS(); return ok; }),
    disconnect: () => { wifi.disconnect().then(() => wifi.apply(api.S)); },
    forget: ssid => { wifi.forget(ssid).then(() => wifi.apply(api.S)); },
    ip: () => wifi.ip()
  },
  engines: {
    install: (id, onProgress) => engines.install(id, onProgress).then(ok => { registerEngines(); api.saveS(); return ok; }),
    remove: id => { engines.remove(id); }
  },
  shorts: {
    feed: () => shorts.feed(), search: q => shorts.search(q), image: v => shorts.image(v),
    time: () => shorts.time(), ended: () => shorts.ended(),
    play: v => { shortsScreen = api.OS.screen; shorts.play(v); },
    pause: on => shorts.pause(on), seek: t => shorts.seek(t), stop: () => shorts.stop()
  },
  usb: {
    start: () => media.usbStart().catch(e => api.toast('USB drive mode: ' + e.message)),
    stop: () => media.usbStop().then(msg => { reloadContent(); return msg; })
  },
  sd: {
    importAll: () => media.sdImport().then(msg => { reloadContent(); return msg; }),
    exportGames: () => media.sdExport(), eject: () => media.sdEject(), backup: () => media.sdBackup(), summary: () => media.summary()
  },
  apps: {
    run(id) {
      const app = listApps(path.join(P.data, 'apps')).find(a => a.id === id);
      if (!app) return Promise.reject(new Error('App not found. Upload it again.'));
      appMode = true; thinker.stopPonder();
      return apps.run(app, fb && fb.dev).finally(() => { appMode = false; clearTimeout(escTimer); if (fb) fb.invalidate(); });
    }
  }
};
shorts.onError = msg => api && api.toast(msg);

/* ---------- transfer events from the web server ---------- */
transfer.on('event', ev => {
  if (!api) return;
  const X = api.XFER;
  switch (ev.ev) {
    case 'ready': X.ip = ev.ip || ''; if (ev.ssid) X.ssid = ev.ssid; if (ev.pass) X.pass = ev.pass; X.ready = true; break;
    case 'login': api.PHN.stage = 'portal'; api.xferEvent('Phone opened the transfer page'); break;
    case 'pinfail': api.xferEvent('Wrong PIN typed on the phone'); break;
    case 'download': api.xferEvent('Sent ' + ev.name); break;
    case 'installed':
      if (ev.kind === 'games') { const n = reloadContent(); api.xferEvent(n + ' game' + (n === 1 ? '' : 's') + ' added to History'); }
      else { reloadContent(); api.xferEvent(ev.name + ' added'); }
      break;
    case 'rejected': api.xferEvent(ev.name + ': ' + ev.why); break;
    case 'restore':
      // The restored state.json must not be overwritten by what's in memory now.
      store.frozen = true; restartWhenIdle = true;
      api.xferEvent('Backup restored · ChAIpi restarts when you stop sharing'); break;
    case 'use-engine': {
      const S = api.S, prof = S.profiles.find(p => p.id === S.profile) || S.profiles[0];
      if (prof && engines.get(ev.id)) { prof.engine = ev.id; api.saveS(); api.xferEvent('Now playing with ' + (engines.get(ev.id).name || ev.id)); }
      break;
    }
    case 'stop': api.stopTransfer(); break;
    case 'error': api.toast(ev.msg || 'Transfer failed'); api.stopTransfer(true); break;
    case 'exit': if (X.active || X.starting) { api.stopTransfer(true); if (ev.code) api.toast('Transfer stopped unexpectedly'); } break;
  }
});

function applyVolume(pct) {
  const v = Math.min(cfg.audio.max_volume, pct);
  execFile('amixer', ['-q', 'sset', 'Master', v + '%'], err => { if (err) log('volume: no "Master" control yet (it appears after the first sound)'); });
}
function restartUi(why) { log('restarting UI:', why); if (!store.frozen) store.flush(); process.exit(0); }

/* ---------- background upkeep: engine choice, pondering, settings, Wi-Fi ---------- */
let lastHash = 0, lastSaver = null, tickN = 0;
function upkeep() {
  if (!api) return;
  const S = api.S, OS = api.OS;
  // engine for the active profile
  const prof = S.profiles.find(p => p.id === S.profile) || S.profiles[0];
  const spec = engines.get(prof && prof.engine) || engines.get('sf19');
  if (spec) thinker.use(spec);
  // Shorts needs the memory: the engine stops while it's open and comes back when Extras closes.
  if (api.SYS.extras.shorts && !thinker.suspended) thinker.suspend();
  if (!api.SYS.extras.shorts && thinker.suspended) thinker.resume();
  if (shorts.playing() && OS.screen !== shortsScreen) shorts.stop();
  if (S.hash !== lastHash && !thinker.cur) { thinker.setHash(S.hash); lastHash = S.hash; }
  if (S.saver !== lastSaver && !thinker.cur) { thinker.setThreads(S.saver ? 2 : cfg.engine.threads); lastSaver = S.saver; }
  // Think on the player's time: fills the hash table so the reply comes faster and stronger.
  const g = OS.game;
  if (S.ponder && g && g.cfg.mode === 'play' && !g.over && g.ch.turn === g.cfg.side && !g.thinking && OS.screen && OS.screen.game === g && !appMode) thinker.ponder(g.ch.fen());
  else thinker.stopPonder();
  // SD card in/out
  if (HW.sd !== lastSd) { lastSd = HW.sd; api.toast(HW.sd ? 'SD card inserted' : 'SD card removed'); if (HW.sd) media.sdScan(); }
  // Wi-Fi state from NetworkManager every 10 s (not while the hotspot is up)
  if (++tickN % 20 === 0 && !transfer.running()) wifi.sync().then(() => { if (wifi.apply(S)) api.saveS(); });
  if (transfer.running() && tickN % 10 === 0) transfer.status({ bat: Math.round(HW.bat), charging: HW.charging, free: sysinfo.freeSpace(P.data), version: VERSION });
}
setInterval(upkeep, 500);

/* ---------- frame loop ---------- */
let rafQ = [], errors = 0;
global.window = globalThis;
global.CHAIPI_HOST = HOST;
global.localStorage = store;
global.Path2D = canvasLib.Path2D;
global.requestAnimationFrame = cb => { rafQ.push(cb); return rafQ.length; };
global.cancelAnimationFrame = () => {};

function animating() {
  const OS = api && api.OS; if (!OS || !OS.screen) return true;
  const g = OS.game, sc = OS.screen;
  return performance.now() - OS.lastInput < 2500 || sc.extras || sc.noQuick || sc.busy || OS.toast || OS.overlays.length ||
    (g && (g.anim || g.thinking || g.analysing)) || api.XFER.starting;
}
function loop() {
  const t0 = performance.now();
  const q = rafQ; rafQ = [];
  for (const cb of q) {
    try { cb(t0); errors = 0; }
    catch (e) {
      log('frame error:', e && e.stack || e);
      rafQ.push(cb);
      if (++errors > 30 && api) { errors = 0; try { api.goHome(); api.toast('Something went wrong · back to Home'); } catch (e2) { /* keep going */ } }
    }
  }
  if (fb && !appMode && !deepSleep) {
    try { fb.push(ctx.getImageData(0, 0, canvas.width, canvas.height).data); } catch (e) { log('display write:', e.message); }
  }
  const fps = deepSleep ? 1 : animating() ? cfg.display.fps : cfg.display.idle_fps;
  setTimeout(loop, Math.max(2, 1000 / fps - (performance.now() - t0)));
}

/* ---------- start the OS ---------- */
process.on('uncaughtException', e => log('uncaught:', e && e.stack || e));
process.on('unhandledRejection', e => log('unhandled promise:', e && e.stack || e));
process.on('SIGTERM', () => { store.flush(); transfer.stop(); shorts.stop(); if (thinker.engine) thinker.engine.quit(); setTimeout(() => process.exit(0), 300); });
process.on('SIGUSR2', () => {
  // `systemctl kill -s USR2 chaipi-ui` saves the current screen to /run/chaipi/screen.png (handy over SSH).
  canvas.encode('png').then(png => fs.writeFileSync(path.join(P.run, 'screen.png'), png)).catch(e => log('screenshot:', e.message));
});

const html = fs.readFileSync(P.os, 'utf8');
const start = html.lastIndexOf('<script>'), end = html.indexOf('</script>', start);
if (start < 0 || end < 0) { log('no <script> in', P.os); process.exit(1); }
if (fb) fb.setSource(canvas.width, canvas.height);
vm.runInThisContext(html.slice(start + 8, end), { filename: 'chaipi-os.js' });
if (fb) fb.setSource(canvas.width, canvas.height);
loop();
log('ChAIpi UI running', VERSION, profile, HEADLESS ? '(headless)' : '');
