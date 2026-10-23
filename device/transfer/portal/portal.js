/* ChAIpi transfer page: PIN, then Games / Engines / Apps / Puzzles / Device. Talks to chaipi_xfer/server.py. */
(function () {
  'use strict';
  const $ = id => document.getElementById(id);
  const main = $('main'), nav = $('nav');
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const fmtSize = b => b >= 1e9 ? (b / 1e9).toFixed(1) + ' GB' : b >= 1e6 ? (b / 1e6).toFixed(1) + ' MB' : Math.max(1, Math.round(b / 1e3)) + ' KB';
  const fmtDate = ms => new Date(ms).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
  const MODE = { play: 'Play', helper: 'Helper', duo: 'Two player' };

  const ICON = {
    games: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="3.5" width="17" height="17" rx="3" fill="none" stroke="currentColor" stroke-width="1.9"/><path d="M3.5 12h17M12 3.5v17" stroke="currentColor" stroke-width="1.9"/><rect x="3.5" y="3.5" width="8.5" height="8.5" fill="currentColor" opacity=".35"/><rect x="12" y="12" width="8.5" height="8.5" fill="currentColor" opacity=".35"/></svg>',
    engines: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="6" width="12" height="12" rx="2" fill="none" stroke="currentColor" stroke-width="1.9"/><path d="M9 2.5v3.5M15 2.5v3.5M9 18v3.5M15 18v3.5M2.5 9H6M2.5 15H6M18 9h3.5M18 15h3.5" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/><circle cx="12" cy="12" r="2.4" fill="currentColor"/></svg>',
    apps: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 8h10a4 4 0 0 1 4 4v1a4 4 0 0 1-7 2.6h-4A4 4 0 0 1 3 13v-1a4 4 0 0 1 4-4Z" fill="none" stroke="currentColor" stroke-width="1.9"/><path d="M8 10.5v3M6.5 12h3" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/><circle cx="15.5" cy="11" r="1.1" fill="currentColor"/><circle cx="17.5" cy="13.2" r="1.1" fill="currentColor"/></svg>',
    puzzles: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 8.5h4.6c-.2-3.9 5-3.9 4.8 0H19v3.9c3.6 0 3.6 5.2 0 5.2V20H5Z" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round"/></svg>',
    device: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="6" width="18" height="12" rx="3" fill="none" stroke="currentColor" stroke-width="1.9"/><rect x="7" y="9" width="7" height="6" rx="1" fill="currentColor" opacity=".35"/><circle cx="17" cy="12" r="1.5" fill="currentColor"/></svg>',
    up: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 16V4m0 0-5 5m5-5 5 5M4 17v2a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-2" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>'
  };
  const LOGO = document.querySelector('.logo').innerHTML;
  const TABS = [['games', 'Games'], ['engines', 'Engines'], ['apps', 'Apps'], ['puzzles', 'Puzzles'], ['device', 'Device']];

  const ui = { tab: 'games', filter: 'all', q: '', data: null, busy: null, hello: null };

  /* ---------- helpers ---------- */
  let toastT = 0;
  function toast(msg) { const t = $('toast'); t.textContent = msg; t.hidden = false; clearTimeout(toastT); toastT = setTimeout(() => { t.hidden = true; }, 2600); }
  async function api(path, opt) {
    const r = await fetch(path, Object.assign({ credentials: 'same-origin', cache: 'no-store' }, opt || {}));
    let body = null; try { body = await r.json(); } catch (e) { /* not JSON */ }
    if (r.status === 401) { showPin(); throw new Error((body && body.error) || 'PIN needed'); }
    if (!r.ok) { const e = new Error((body && body.error) || 'ChAIpi said no (' + r.status + ')'); e.body = body; e.status = r.status; throw e; }
    return body;
  }
  function download(url) { const a = document.createElement('a'); a.href = url; a.download = ''; document.body.appendChild(a); a.click(); a.remove(); }
  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(text);
    const ta = document.createElement('textarea'); ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0'; document.body.appendChild(ta);
    ta.select(); let ok = false; try { ok = document.execCommand('copy'); } catch (e) { /* old browser */ } ta.remove();
    return ok ? Promise.resolve() : Promise.reject(new Error('copy blocked'));
  }

  /* ---------- PIN ---------- */
  function showPin(err, locked) {
    nav.hidden = true; $('pill').hidden = true;
    main.innerHTML = '<div class="center" style="margin-top:18px"><span class="logo" style="display:inline-block">' + LOGO.replace('<svg', '<svg style="width:64px;height:64px"') + '</span></div>' +
      '<h1 class="h center">Welcome to Ch<span style="color:var(--accent)">AI</span>pi</h1>' +
      '<p class="sub center">Type the 4-digit PIN shown on ChAIpi’s screen.</p>' +
      '<form id="pinForm" class="list" autocomplete="off"><input id="pinIn" class="pin-in' + (err ? ' bad' : '') + '" inputmode="numeric" pattern="[0-9]*" maxlength="4" autocomplete="one-time-code" placeholder="\u2022\u2022\u2022\u2022" aria-label="4-digit PIN">' +
      (err ? '<p class="sub center" style="color:var(--berry)">' + esc(err) + '</p>' : '') +
      '<button class="btn" id="pinGo"' + (locked ? ' disabled' : '') + '>Connect</button></form>' +
      '<p class="sub center">Only someone who can see ChAIpi\u2019s screen can get in.</p>';
    const pinIn = $('pinIn');
    pinIn.focus();
    pinIn.addEventListener('input', () => { pinIn.value = pinIn.value.replace(/\D/g, '').slice(0, 4); if (pinIn.value.length === 4) submitPin(); });
    $('pinForm').addEventListener('submit', e => { e.preventDefault(); submitPin(); });
    if (locked) { let s = locked; const t = setInterval(() => { s--; if (s <= 0) { clearInterval(t); showPin(); } }, 1000); }
    async function submitPin() {
      const pin = pinIn.value;
      if (pin.length < 4) return;
      try { await api('/api/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pin }) }); load(); }
      catch (e) {
        if (e.status === 429) showPin(e.message, (e.body && e.body.locked) || 30);
        else showPin((e.body && e.body.left != null) ? e.message + ' · ' + e.body.left + ' tries left' : e.message);
      }
    }
  }

  /* ---------- pages ---------- */
  function hotspotHint() {
    if (!ui.hello || ui.hello.mode !== 'hotspot') return '';
    return '<div class="hint"><span>ℹ️</span><span>Downloads not starting? This may be the phone’s sign-in window. Open <b>http://' + esc(ui.data.device.ip) + '</b> in Safari or Chrome instead.</span></div>';
  }
  function gameRows() {
    const q = ui.q.trim().toLowerCase();
    const list = ui.data.games.filter(g => (ui.filter === 'all' || g.mode === ui.filter) &&
      (!q || (g.white + ' ' + g.black + ' ' + g.result + ' ' + g.reason + ' ' + (MODE[g.mode] || '')).toLowerCase().includes(q)));
    if (!list.length) return '<p class="empty">' + (ui.data.games.length ? 'No games match.' : 'No games yet. Finished games appear here.') + '</p>';
    return list.map(g => {
      const you = g.mode && g.mode !== 'duo' ? g.side : null;
      const won = you && ((g.result === '1-0' && you === 'w') || (g.result === '0-1' && you === 'b'));
      const lost = you && g.result !== '1/2-1/2' && g.result !== '*' && !won;
      return '<div class="card game"><div class="between"><span class="t">' + esc(g.white) + ' vs ' + esc(g.black) + '</span><span class="res' + (won ? ' w' : lost ? ' l' : '') + '">' + (g.result === '1/2-1/2' ? '½–½' : esc(g.result)) + '</span></div>' +
        '<div class="meta">' + fmtDate(g.date) + (g.mode ? ' · ' + MODE[g.mode] : '') + ' · ' + g.moves + ' moves' + (g.reason ? ' · ' + esc(g.reason) : '') + '</div>' +
        '<div class="row"><button class="btn small ghost" data-act="dl" data-file="' + esc(g.file) + '">Download .txt</button><button class="btn small ghost" data-act="pgn" data-file="' + esc(g.file) + '">View PGN</button></div></div>';
    }).join('');
  }
  function pageGames() {
    let w = 0, d = 0, l = 0;
    ui.data.games.forEach(g => { if (!g.mode || g.mode === 'duo') return; if (g.result === '1/2-1/2') d++; else if (g.result === '*') return; else if ((g.result === '1-0') === (g.side === 'w')) w++; else l++; });
    const n = ui.data.games.length;
    return '<div class="hero">' + LOGO + '<h2>Your games, ready to take</h2><p>' + n + ' game' + (n === 1 ? '' : 's') + ', each saved as a PGN .txt file.</p></div>' +
      '<div class="stats"><div><b>' + w + '</b><span>won</span></div><div><b>' + d + '</b><span>drawn</span></div><div><b>' + l + '</b><span>lost</span></div></div>' +
      (n ? '<div class="two"><button class="btn" data-act="zip">All as .zip</button><button class="btn ghost" data-act="allpgn">One .pgn file</button></div>' : '') +
      hotspotHint() +
      (n ? '<input class="search" id="q" type="search" placeholder="Search players or results" value="' + esc(ui.q) + '" aria-label="Search games">' +
        '<div class="chips" role="group" aria-label="Filter">' + [['all', 'All'], ['play', 'Play'], ['helper', 'Helper'], ['duo', 'Two player']].map(([k, t]) => '<button class="chip" data-filter="' + k + '" aria-pressed="' + (ui.filter === k) + '">' + t + '</button>').join('') + '</div>' : '') +
      '<div class="list" id="gameList">' + gameRows() + '</div>' + uploadBox('games', 'Add games from a .pgn file', 'They appear in History on ChAIpi.', '.pgn,.txt');
  }
  function uploadBox(kind, title, sub, accept) {
    const b = ui.busy && ui.busy.kind === kind ? ui.busy : null;
    return '<label class="drop" data-drop="' + kind + '">' + ICON.up + '<b>' + title + '</b><span class="sub">' + sub + '</span>' +
      '<input type="file" data-up="' + kind + '"' + (accept ? ' accept="' + accept + '"' : '') + ' aria-label="' + esc(title) + '"' + (ui.busy ? ' disabled' : '') + '></label>' +
      (b ? '<div class="card"><div class="between"><b style="min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + esc(b.name) + '</b><span class="meta">' + fmtSize(b.size) + '</span></div>' +
        '<div class="prog" style="margin-top:9px"><i id="prog-' + kind + '" style="width:' + Math.round(b.p * 100) + '%"></i></div><p class="sub" id="step-' + kind + '" style="margin-top:7px">' + esc(b.step) + '</p></div>' : '');
  }
  function pageEngines() {
    const E = ui.data.engines;
    return '<h1 class="h">Engines</h1><p class="sub">Profile <b>' + esc(E.profile) + '</b> plays with the one marked In use.</p>' +
      '<div class="list">' + E.engines.map(e => '<div class="card between"><div style="min-width:0"><b>' + esc(e.name) + '</b><div class="meta">' + esc([e.tier, e.type, e.builtin ? 'built in' : 'added'].filter(Boolean).join(' · ')) + '</div></div>' +
        (e.inUse ? '<span class="badge on">In use</span>' : '<button class="btn small ghost" data-act="use" data-id="' + esc(e.id) + '">Use</button>') + '</div>').join('') + '</div>' +
      uploadBox('engine', 'Upload an engine', 'A Linux ARM64 (aarch64) UCI engine: the program, or a .zip / .tar.gz with its network file.') +
      '<div class="card"><b>Where to find one</b><p class="sub">Pick the <b>Linux ARM64</b> or <b>aarch64</b> download on the engine’s release page. Builds for Windows, Mac or Android won’t run, and ChAIpi tells you so.</p></div>';
  }
  function pageApps() {
    const A = ui.data.apps;
    return '<h1 class="h">Python apps</h1><p class="sub">They appear in Extras → Games. Each runs on its own and is cleared from memory when you leave Extras.</p>' +
      '<div class="list">' + (A.length ? A.map(a => '<div class="card between"><div><b>' + esc(a.name) + '</b><div class="meta">up to ' + esc(a.ram) + ' MB</div></div><span class="badge on">py</span></div>').join('') : '<p class="empty">No apps added yet.</p>') + '</div>' +
      uploadBox('app', 'Upload a Python app', 'main.py on its own, or a .zip with main.py and app.toml.', '.py,.zip') +
      '<pre class="code">from chaipi import app\n\n@app.loop(fps=15)\ndef frame(screen, keys):\n    screen.clear()\n    screen.text("Hello", 10, 20)\n    if keys.pressed("ok"):\n        app.buzz()</pre>';
  }
  function pagePuzzles() {
    const P = ui.data.puzzles;
    return '<h1 class="h">Puzzles</h1><p class="sub">ChAIpi’s puzzle mode is mate in one. Packs are filtered to those.</p>' +
      '<div class="list">' + P.map(p => '<div class="card between"><div><b>' + esc(p.name) + '</b><div class="meta">' + p.count + ' puzzle' + (p.count === 1 ? '' : 's') + '</div></div><span class="badge' + (p.builtin ? '' : ' on') + '">' + (p.builtin ? 'built in' : 'added') + '</span></div>').join('') + '</div>' +
      uploadBox('puzzles', 'Upload a puzzle pack', 'The Lichess puzzle CSV, or a text file with one FEN per line.', '.csv,.txt,.epd,.fen,.pgn');
  }
  function pageDevice() {
    const D = ui.data.device, used = D.totalBytes ? 1 - D.freeBytes / D.totalBytes : 0;
    return '<h1 class="h">This ChAIpi</h1>' +
      '<div class="card"><dl class="kv">' +
      (D.bat != null ? '<dt>Battery</dt><dd>' + Math.round(D.bat) + '%' + (D.charging ? ' · charging' : '') + '</dd>' : '') +
      '<dt>Storage</dt><dd>' + fmtSize(D.freeBytes) + ' free</dd>' +
      '<dt>Games</dt><dd>' + D.games + '</dd><dt>Engines</dt><dd>' + D.engines + '</dd><dt>Apps</dt><dd>' + D.apps + '</dd>' +
      '<dt>Network</dt><dd>' + (D.mode === 'hotspot' ? esc(D.ssid || 'ChAIpi hotspot') : 'home Wi-Fi') + '</dd>' +
      '<dt>Software</dt><dd>' + esc(D.version || 'ChAIpi OS') + '</dd></dl>' +
      '<div class="bar" aria-label="Storage used"><i style="width:' + Math.round(used * 100) + '%"></i></div></div>' +
      '<div class="card list' + (ui.goal === 'backup' ? ' goal' : '') + '"><b>' + (ui.goal === 'backup' ? 'Save your backup' : 'Back up') + '</b><p class="sub">Settings, games, apps and puzzle packs in one file' + (ui.goal === 'backup' ? ', saved to this phone\u2019s Downloads (Files app on iPhone)' : '') + '. Engines aren\u2019t included; upload them again after a restore.</p><button class="btn' + (ui.goal === 'backup' ? '' : ' ghost') + '" data-act="backup">Download backup</button></div>' +
      uploadBox('backup', 'Restore a backup', 'Replaces settings and adds the games, apps and puzzles from the file. ChAIpi restarts when you stop sharing.', '.gz,.tgz') +
      '<button class="btn danger" data-act="stop">Stop sharing</button>';
  }

  function render() {
    const page = { games: pageGames, engines: pageEngines, apps: pageApps, puzzles: pagePuzzles, device: pageDevice }[ui.tab];
    const focus = document.activeElement && document.activeElement.id === 'q';
    main.innerHTML = page();
    if (focus) { const q = $('q'); q.focus(); q.setSelectionRange(q.value.length, q.value.length); }
    nav.innerHTML = TABS.map(([k, t]) => '<button data-tab="' + k + '"' + (ui.tab === k ? ' aria-current="page"' : '') + '>' + ICON[k] + t + '</button>').join('');
    nav.hidden = false;
    const D = ui.data.device; $('pill').hidden = false;
    $('pillText').textContent = D.bat != null ? Math.round(D.bat) + '%' + (D.charging ? ' ⚡' : '') : 'connected';
  }

  /* ---------- uploads with progress ---------- */
  function upload(kind, file) {
    if (ui.busy) return;
    ui.busy = { kind, name: file.name, size: file.size, p: 0, step: 'Sending to ChAIpi…' };
    render();
    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/upload?kind=' + encodeURIComponent(kind) + '&name=' + encodeURIComponent(file.name));
    xhr.upload.onprogress = e => {
      if (!e.lengthComputable) return;
      ui.busy.p = e.loaded / e.total;
      ui.busy.step = e.loaded < e.total ? 'Sending to ChAIpi… ' + Math.round(ui.busy.p * 100) + '%' : 'Checking it on ChAIpi…';
      const bar = $('prog-' + kind), st = $('step-' + kind);
      if (bar) bar.style.width = Math.round(ui.busy.p * 100) + '%';
      if (st) st.textContent = ui.busy.step;
    };
    xhr.onload = () => {
      let body = null; try { body = JSON.parse(xhr.responseText); } catch (e) { /* no body */ }
      ui.busy = null;
      if (xhr.status === 200) {
        const it = body && body.item;
        toast(kind === 'backup' ? 'Backup restored. ChAIpi restarts when you stop sharing.' : (it ? it.name : file.name) + ' added to ChAIpi');
        load();
      } else if (xhr.status === 401) showPin();
      else { toast((body && body.error) || 'Upload failed'); render(); }
    };
    xhr.onerror = () => { ui.busy = null; toast('Lost the connection to ChAIpi'); render(); };
    xhr.send(file);
  }

  /* ---------- events ---------- */
  document.addEventListener('click', async e => {
    const t = e.target.closest('[data-act],[data-tab],[data-filter]');
    if (!t) return;
    if (t.dataset.tab) { ui.tab = t.dataset.tab; render(); window.scrollTo(0, 0); return; }
    if (t.dataset.filter) { ui.filter = t.dataset.filter; render(); return; }
    const act = t.dataset.act;
    try {
      if (act === 'dl') download('/api/games/' + encodeURIComponent(t.dataset.file));
      else if (act === 'zip') download('/api/games.zip');
      else if (act === 'allpgn') download('/api/games.pgn');
      else if (act === 'backup') { download('/api/backup'); if (ui.goal === 'backup') { ui.goal = null; toast('Backup saved. You can stop sharing on ChAIpi now.'); } }
      else if (act === 'pgn') {
        const r = await fetch('/api/games/' + encodeURIComponent(t.dataset.file) + '?view=1', { credentials: 'same-origin' });
        openSheet(t.dataset.file, await r.text());
      } else if (act === 'use') {
        await api('/api/use-engine', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: t.dataset.id }) });
        toast('ChAIpi will play with it'); setTimeout(load, 900);
      } else if (act === 'stop') {
        if (!confirm('Stop sharing? ChAIpi turns its hotspot off.')) return;
        await api('/api/stop', { method: 'POST' });
        nav.hidden = true; $('pill').hidden = true;
        main.innerHTML = '<div class="card list" style="margin-top:30px"><b>ChAIpi stopped sharing</b><p class="sub">Start Transfer on the device again whenever you need it: Settings → Transfer → Activate.</p></div>';
      }
    } catch (err) { toast(err.message); }
  });
  document.addEventListener('input', e => {
    if (e.target.id === 'q') { ui.q = e.target.value; const l = $('gameList'); if (l) l.innerHTML = gameRows(); }
  });
  document.addEventListener('change', e => {
    const inp = e.target.closest && e.target.closest('input[type=file][data-up]');
    if (inp && inp.files && inp.files[0]) { upload(inp.dataset.up, inp.files[0]); inp.value = ''; }
  });
  document.addEventListener('dragover', e => { const z = e.target.closest && e.target.closest('[data-drop]'); if (z) { e.preventDefault(); z.classList.add('over'); } });
  document.addEventListener('dragleave', e => { const z = e.target.closest && e.target.closest('[data-drop]'); if (z) z.classList.remove('over'); });
  document.addEventListener('drop', e => {
    const z = e.target.closest && e.target.closest('[data-drop]'); if (!z) return;
    e.preventDefault(); z.classList.remove('over');
    const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]; if (f) upload(z.dataset.drop, f);
  });

  function openSheet(title, text) {
    const sh = $('sheet');
    sh.innerHTML = '<div class="between"><b id="sheetTitle" style="min-width:0;overflow:hidden;text-overflow:ellipsis">' + esc(title) + '</b><button class="btn small ghost" id="shClose">Close</button></div>' +
      '<textarea id="shText" readonly aria-label="PGN">' + esc(text) + '</textarea><div class="two"><button class="btn" id="shCopy">Copy PGN</button><button class="btn ghost" id="shDl">Download</button></div>';
    sh.hidden = false; $('sheetBg').hidden = false;
    const close = () => { sh.hidden = true; $('sheetBg').hidden = true; };
    $('shClose').onclick = close; $('sheetBg').onclick = close;
    $('shDl').onclick = () => download('/api/games/' + encodeURIComponent(title));
    $('shCopy').onclick = () => copyText(text).then(() => toast('PGN copied'), () => { const ta = $('shText'); ta.focus(); ta.select(); toast('Press and hold to copy'); });
  }
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && !$('sheet').hidden) { $('sheet').hidden = true; $('sheetBg').hidden = true; } });

  /* ---------- start ---------- */
  async function load() {
    try {
      ui.data = await api('/api/state');
      if (!ui.busy) render();
    } catch (e) { if (!/PIN/.test(e.message)) { main.innerHTML = '<div class="card" style="margin-top:30px"><b>Can’t reach ChAIpi</b><p class="sub">' + esc(e.message) + '. Is Transfer still on?</p></div>'; } }
  }
  (async () => {
    try {
      ui.hello = await api('/api/hello');
      if (ui.hello.tab) { ui.tab = ui.hello.tab; ui.goal = ui.hello.tab === 'device' ? 'backup' : null; }
      if (ui.hello.locked) showPin('Too many tries', ui.hello.locked);
      else if (!ui.hello.authed) showPin();
      else load();
    } catch (e) { main.innerHTML = '<div class="card" style="margin-top:30px"><b>Can’t reach ChAIpi</b><p class="sub">Is Transfer still on? Settings → Transfer → Activate.</p></div>'; }
  })();
  setInterval(() => { if (ui.data && !ui.busy && !document.hidden && $('sheet').hidden && document.activeElement && document.activeElement.id !== 'q') load(); }, 15000);
})();
