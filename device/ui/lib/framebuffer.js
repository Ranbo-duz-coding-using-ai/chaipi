'use strict';
/* Writes canvas frames to the SPI display's framebuffer (fbtft or panel-mipi-dbi), 16-bit RGB565.
   Only the rows that changed since the last frame are written, so a still screen costs almost nothing. */
const fs = require('fs');
const path = require('path');
const { toRgb565, rotate90, dirtyRows } = require('./pixels');

const SYS = '/sys/class/graphics';

function readSys(fb, name) { try { return fs.readFileSync(path.join(SYS, fb, name), 'utf8').trim(); } catch (e) { return ''; } }

/* "auto" picks the framebuffer whose driver name mentions an SPI panel, else the last one. */
function findFramebuffer(want) {
  if (want && want !== 'auto') return want;
  let fbs = [];
  try { fbs = fs.readdirSync(SYS).filter(n => /^fb\d+$/.test(n)).sort(); } catch (e) { return null; }
  const spi = fbs.find(fb => /ili9341|ili9340|mipi|ili9486|st7735|st7789|fb_/i.test(readSys(fb, 'name')));
  const pick = spi || fbs[fbs.length - 1];
  return pick ? '/dev/' + pick : null;
}

class Framebuffer {
  constructor(opts) {
    this.dev = findFramebuffer(opts.fb);
    if (!this.dev) throw new Error('no framebuffer found (is the display overlay in config.txt?)');
    const fb = path.basename(this.dev);
    const [vw, vh] = (readSys(fb, 'virtual_size') || '320,240').split(',').map(Number);
    this.bpp = Number(readSys(fb, 'bits_per_pixel') || 16);
    if (this.bpp !== 16) throw new Error(this.dev + ' is ' + this.bpp + '-bit; ChAIpi expects 16-bit RGB565');
    this.fbW = vw; this.fbH = vh;
    this.stride = Number(readSys(fb, 'stride')) || vw * 2;
    this.name = readSys(fb, 'name');
    this.rot180 = opts.rotate === 180;
    this.fd = fs.openSync(this.dev, 'r+');
    this.prev = null;
  }
  /* The OS draws landscape or portrait; if the panel is the other way round we rotate in software. */
  setSource(w, h) {
    this.w = w; this.h = h;
    this.rotate = (w !== this.fbW || h !== this.fbH) && w === this.fbH && h === this.fbW;
    this.cur = new Uint16Array(w * h);
    this.out = this.rotate ? new Uint16Array(w * h) : this.cur;
    this.prev = null;
  }
  invalidate() { this.prev = null; }
  /* rgba: Uint8ClampedArray from getImageData. Returns how many rows were sent. */
  push(rgba) {
    toRgb565(rgba, this.cur, this.w, this.h, this.rot180);
    let img = this.cur, W = this.w, H = this.h;
    if (this.rotate) { rotate90(this.cur, this.out, this.w, this.h); img = this.out; W = this.h; H = this.w; }
    let range = [0, H - 1];
    if (this.prev) { range = dirtyRows(this.prev, img, W, H); if (!range) return 0; }
    else this.prev = new Uint16Array(W * H);
    const [y0, y1] = range;
    const rows = y1 - y0 + 1;
    if (this.stride === W * 2) {
      const buf = Buffer.from(img.buffer, img.byteOffset + y0 * W * 2, rows * W * 2);
      fs.writeSync(this.fd, buf, 0, buf.length, y0 * this.stride);
    } else {
      for (let y = y0; y <= y1; y++) {
        const buf = Buffer.from(img.buffer, img.byteOffset + y * W * 2, W * 2);
        fs.writeSync(this.fd, buf, 0, buf.length, y * this.stride);
      }
    }
    this.prev.set(img.subarray(y0 * W, (y1 + 1) * W), y0 * W);
    return rows;
  }
  clear() {
    const blank = Buffer.alloc(this.stride * this.fbH);
    fs.writeSync(this.fd, blank, 0, blank.length, 0);
    this.prev = null;
  }
}

module.exports = { Framebuffer, findFramebuffer };
