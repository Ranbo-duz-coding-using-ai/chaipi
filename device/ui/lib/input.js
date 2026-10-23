'use strict';
/* Client for chaipi-input (device/input/chaipi_input.py): buttons, joystick, battery in; vibration and backlight out.
   One JSON object per line over a Unix socket. Reconnects by itself if the daemon restarts. */
const net = require('net');
const readline = require('readline');
const { EventEmitter } = require('events');

class InputClient extends EventEmitter {
  constructor(sockPath, log) {
    super(); this.path = sockPath; this.log = log || console.log; this.sock = null; this.connected = false; this.queue = [];
    this.connect();
  }
  connect() {
    const s = net.createConnection(this.path);
    this.sock = s;
    s.on('connect', () => {
      this.connected = true; this.emit('connected');
      const q = this.queue; this.queue = []; q.forEach(m => this.send(m));
    });
    readline.createInterface({ input: s }).on('line', line => {
      let m; try { m = JSON.parse(line); } catch (e) { return; }
      this.emit('event', m);
    });
    s.on('error', () => {});
    s.on('close', () => {
      if (this.connected) this.log('input daemon disconnected');
      this.connected = false; this.sock = null;
      setTimeout(() => this.connect(), 1000);
    });
  }
  send(msg) {
    if (!this.connected) { if (this.queue.length < 20) this.queue.push(msg); return; }
    this.sock.write(JSON.stringify(msg) + '\n');
  }
}

module.exports = { InputClient };
