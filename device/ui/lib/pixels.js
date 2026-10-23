/* RGBA canvas pixels -> RGB565 for the ILI9341 framebuffer, plus a row diff so only changed rows are sent over SPI. */
(function (root) {
  'use strict';

  /* src: RGBA bytes (w*h*4). dst: Uint16Array (w*h). rot180 flips for an upside-down panel. */
  function toRgb565(src, dst, w, h, rot180) {
    const n = w * h;
    if (!rot180) {
      for (let i = 0, j = 0; i < n; i++, j += 4) dst[i] = ((src[j] & 0xf8) << 8) | ((src[j + 1] & 0xfc) << 3) | (src[j + 2] >> 3);
    } else {
      for (let i = 0, j = 0; i < n; i++, j += 4) dst[n - 1 - i] = ((src[j] & 0xf8) << 8) | ((src[j + 1] & 0xfc) << 3) | (src[j + 2] >> 3);
    }
    return dst;
  }

  /* Rotates a w*h RGB565 image 90 degrees clockwise into an h*w buffer (for a panel left in portrait). */
  function rotate90(src, dst, w, h) {
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) dst[x * h + (h - 1 - y)] = src[y * w + x];
    return dst;
  }

  /* First and last differing row between two w*h Uint16Arrays, or null if they match. */
  function dirtyRows(prev, cur, w, h) {
    let y0 = -1, y1 = -1;
    for (let y = 0; y < h; y++) {
      const o = y * w;
      for (let x = 0; x < w; x++) if (prev[o + x] !== cur[o + x]) { y0 = y; break; }
      if (y0 >= 0) break;
    }
    if (y0 < 0) return null;
    for (let y = h - 1; y >= y0; y--) {
      const o = y * w;
      for (let x = 0; x < w; x++) if (prev[o + x] !== cur[o + x]) { y1 = y; break; }
      if (y1 >= 0) break;
    }
    return [y0, y1];
  }

  const api = { toRgb565, rotate90, dirtyRows };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.Pixels = api;
})(this);
