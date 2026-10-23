'use strict';
/* Real numbers for the System panel: per-core CPU load, SoC temperature, RAM in use, free space. */
const fs = require('fs');

let lastCpu = null;
function cpuLoads() {
  let text; try { text = fs.readFileSync('/proc/stat', 'utf8'); } catch (e) { return null; }
  const cores = text.split('\n').filter(l => /^cpu\d+ /.test(l)).map(l => {
    const v = l.trim().split(/\s+/).slice(1).map(Number);
    const idle = v[3] + (v[4] || 0), total = v.reduce((a, b) => a + b, 0);
    return { idle, total };
  });
  const prev = lastCpu; lastCpu = cores;
  if (!prev || prev.length !== cores.length) return cores.map(() => 0);
  return cores.map((c, i) => {
    const dt = c.total - prev[i].total, di = c.idle - prev[i].idle;
    return dt > 0 ? Math.round(100 * (1 - di / dt)) : 0;
  });
}

function tempC() {
  try { return Number(fs.readFileSync('/sys/class/thermal/thermal_zone0/temp', 'utf8')) / 1000; } catch (e) { return null; }
}

/* MB in use the way `free` counts it: total minus available. */
function ramUsedMb() {
  try {
    const t = fs.readFileSync('/proc/meminfo', 'utf8');
    const get = k => Number((t.match(new RegExp('^' + k + ':\\s+(\\d+)', 'm')) || [])[1] || 0);
    return { used: Math.round((get('MemTotal') - get('MemAvailable')) / 1024), total: Math.round(get('MemTotal') / 1024) };
  } catch (e) { return null; }
}

function freeSpace(dir) {
  try {
    const s = fs.statfsSync(dir);
    const b = s.bavail * s.bsize;
    return b > 1e9 ? (b / 1e9).toFixed(1) + ' GB' : Math.round(b / 1e6) + ' MB';
  } catch (e) { return '?'; }
}

/* Under-voltage and throttling flags from the firmware (bit 0 = under-voltage now, bit 16 = since boot). */
function throttled() {
  try { return parseInt(fs.readFileSync('/sys/devices/platform/soc/soc:firmware/get_throttled', 'utf8'), 16); } catch (e) { return null; }
}

module.exports = { cpuLoads, tempC, ramUsedMb, freeSpace, throttled };
