'use strict';
/* localStorage for the OS, kept in one JSON file. Writes are atomic (temp file, fsync, rename, fsync dir)
   so a power cut leaves either the old or the new state, never half of each. */
const fs = require('fs');
const path = require('path');

function writeAtomic(file, data) {
  const dir = path.dirname(file), tmp = file + '.tmp';
  const fd = fs.openSync(tmp, 'w', 0o644);
  try { fs.writeSync(fd, data); fs.fsyncSync(fd); } finally { fs.closeSync(fd); }
  fs.renameSync(tmp, file);
  try { const d = fs.openSync(dir, 'r'); try { fs.fsyncSync(d); } finally { fs.closeSync(d); } } catch (e) { /* some filesystems refuse fsync on a directory */ }
}

class FileStorage {
  constructor(file, log) {
    this.file = file; this.log = log || console.log; this.map = new Map(); this.timer = null;
    try {
      const obj = JSON.parse(fs.readFileSync(file, 'utf8'));
      for (const [k, v] of Object.entries(obj)) this.map.set(k, String(v));
    } catch (e) {
      if (e.code !== 'ENOENT') this.log('state file unreadable, starting fresh:', e.message);
    }
  }
  get length() { return this.map.size; }
  key(i) { return [...this.map.keys()][i] ?? null; }
  getItem(k) { return this.map.has(k) ? this.map.get(k) : null; }
  setItem(k, v) { this.map.set(String(k), String(v)); this.schedule(k); }
  removeItem(k) { this.map.delete(String(k)); this.schedule(k); }
  clear() { this.map.clear(); this.schedule(); }
  /* The current game is saved after every move, so it goes to disk at once; everything else is batched. */
  schedule(k) {
    if (k === 'chaipi.current') { this.flush(); return; }
    if (!this.timer) this.timer = setTimeout(() => this.flush(), 400);
  }
  flush() {
    clearTimeout(this.timer); this.timer = null;
    if (this.frozen) return;
    try { writeAtomic(this.file, JSON.stringify(Object.fromEntries(this.map))); }
    catch (e) { this.log('could not save state:', e.message); }
  }
}

module.exports = { FileStorage, writeAtomic };
