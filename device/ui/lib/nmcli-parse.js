/* Pure parsers for `nmcli -t` (terse) output. Fields are split on ':' and '\:' is a literal colon. */
(function (root) {
  'use strict';

  function splitTerse(line) {
    const out = []; let cur = '';
    for (let i = 0; i < line.length; i++) {
      const c = line[i];
      if (c === '\\' && i + 1 < line.length) { cur += line[++i]; continue; }
      if (c === ':') { out.push(cur); cur = ''; continue; }
      cur += c;
    }
    out.push(cur);
    return out;
  }

  /* `nmcli -t -f IN-USE,SSID,SIGNAL,SECURITY,FREQ device wifi list` -> [{ssid, sig 0-4, sec, five, inUse}], strongest first.
     The same name on several access points becomes one row. Hidden (empty) names are dropped. */
  function parseWifiList(text) {
    const by = new Map();
    for (const raw of text.split('\n')) {
      if (!raw.trim()) continue;
      const [inUse, ssid, signal, security, freq] = splitTerse(raw);
      if (!ssid) continue;
      const pct = parseInt(signal, 10) || 0;
      const mhz = parseInt(freq, 10) || 0;
      const five = mhz >= 4900, sec = !!security && security !== '--';
      const prev = by.get(ssid);
      // The Pi Zero 2 W only does 2.4 GHz, so a name counts as 2.4 GHz if any of its access points is.
      if (!prev) by.set(ssid, { ssid, pct, five, sec, inUse: inUse === '*' });
      else {
        prev.inUse = prev.inUse || inUse === '*';
        if (prev.five && !five) { prev.five = false; prev.pct = pct; prev.sec = sec; }
        else if (prev.five === five && pct > prev.pct) prev.pct = pct;
      }
    }
    const rows = [...by.values()];
    rows.forEach(r => { r.sig = r.pct >= 75 ? 4 : r.pct >= 50 ? 3 : r.pct >= 25 ? 2 : 1; });
    return rows.sort((a, b) => (b.inUse - a.inUse) || (a.five - b.five) || (b.pct - a.pct));
  }

  /* `nmcli -t -f NAME,TYPE connection show` -> names of saved Wi-Fi connections. */
  function parseSaved(text, skip) {
    return text.split('\n').map(splitTerse).filter(f => f[1] === '802-11-wireless' && f[0] && !(skip || []).includes(f[0])).map(f => f[0]);
  }

  /* `nmcli -t -f ACTIVE,SSID device wifi` -> the SSID in use, or ''. */
  function parseActive(text) {
    for (const raw of text.split('\n')) { const f = splitTerse(raw); if (f[0] === 'yes' && f[1]) return f[1]; }
    return '';
  }

  /* `nmcli -t -f IP4.ADDRESS device show wlan0` -> "192.168.1.42" or ''. */
  function parseIp(text) {
    const m = text.match(/IP4\.ADDRESS\[\d+\]:(\d+\.\d+\.\d+\.\d+)/);
    return m ? m[1] : '';
  }

  const api = { splitTerse, parseWifiList, parseSaved, parseActive, parseIp };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.NmcliParse = api;
})(this);
