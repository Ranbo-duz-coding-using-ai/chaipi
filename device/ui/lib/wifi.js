'use strict';
/* Wi-Fi through NetworkManager's nmcli. Arguments are passed as a list (no shell), so network
   names and passwords with spaces or quotes are safe. */
const { execFile } = require('child_process');
const P = require('./nmcli-parse');

function nmcli(args, timeoutMs) {
  return new Promise((resolve, reject) => {
    execFile('nmcli', args, { timeout: timeoutMs || 15000 }, (err, stdout, stderr) => {
      if (err) { err.message = (stderr || err.message).trim(); reject(err); } else resolve(stdout);
    });
  });
}

class Wifi {
  constructor(opts) {
    this.log = opts.log || console.log; this.skip = [opts.hotspotName || 'chaipi-hotspot'];
    this.nets = []; this.scanUntil = 0; this.ipAddr = ''; this.active = ''; this.saved = []; this.radioOn = true;
  }
  /* The OS's list: 2.4 GHz networks first, plus the "hidden network" row. */
  list() { return this.nets.map(n => ({ ssid: n.ssid, sec: n.sec, sig: n.sig, five: n.five })).concat([{ ssid: '', hidden: true }]); }
  scanning() { return Date.now() < this.scanUntil; }
  async scan() {
    if (this.scanning()) return;
    this.scanUntil = Date.now() + 8000;
    try {
      const out = await nmcli(['-t', '-f', 'IN-USE,SSID,SIGNAL,SECURITY,FREQ', 'device', 'wifi', 'list', '--rescan', 'yes'], 20000);
      this.nets = P.parseWifiList(out);
    } catch (e) { this.log('wifi scan:', e.message); }
    this.scanUntil = 0;
  }
  async radio(on) {
    try { await nmcli(['radio', 'wifi', on ? 'on' : 'off']); this.radioOn = on; if (on) setTimeout(() => this.scan(), 1500); }
    catch (e) { this.log('wifi radio:', e.message); }
  }
  async connect(ssid, password, opt) {
    const args = ['--wait', '30', 'device', 'wifi', 'connect', ssid];
    if (password) args.push('password', password);
    if (opt && opt.hidden) args.push('hidden', 'yes');
    args.push('ifname', 'wlan0');
    try { await nmcli(args, 40000); await this.sync(); return true; }
    catch (e) {
      this.log('wifi connect:', e.message);
      // A failed first attempt leaves a half-made profile behind; remove it so a retry asks for the password again.
      if (!this.saved.includes(ssid)) nmcli(['connection', 'delete', 'id', ssid]).catch(() => {});
      return false;
    }
  }
  async disconnect() { try { await nmcli(['device', 'disconnect', 'wlan0']); } catch (e) { this.log('wifi disconnect:', e.message); } await this.sync(); }
  async forget(ssid) { try { await nmcli(['connection', 'delete', 'id', ssid]); } catch (e) { this.log('wifi forget:', e.message); } await this.sync(); }
  ip() { return this.ipAddr || '–'; }
  /* Reads the real state back so the OS shows what NetworkManager is actually doing. */
  async sync() {
    try {
      const [radio, active, saved, ip] = await Promise.all([
        nmcli(['radio', 'wifi']),
        nmcli(['-t', '-f', 'ACTIVE,SSID', 'device', 'wifi']),
        nmcli(['-t', '-f', 'NAME,TYPE', 'connection', 'show']),
        nmcli(['-t', '-f', 'IP4.ADDRESS', 'device', 'show', 'wlan0']).catch(() => '')
      ]);
      this.radioOn = radio.trim() === 'enabled';
      this.active = P.parseActive(active);
      this.saved = P.parseSaved(saved, this.skip);
      this.ipAddr = P.parseIp(ip);
    } catch (e) { this.log('wifi sync:', e.message); }
  }
  /* Copies the real state into the OS settings (S.wifi, S.wifiNet, S.wifiSaved). */
  apply(S) {
    let changed = false;
    const set = (k, v) => { if (JSON.stringify(S[k]) !== JSON.stringify(v)) { S[k] = v; changed = true; } };
    set('wifi', this.radioOn);
    set('wifiNet', this.active);
    set('wifiSaved', this.saved);
    return changed;
  }
}

module.exports = { Wifi, nmcli };
