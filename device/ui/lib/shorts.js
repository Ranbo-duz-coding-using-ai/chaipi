'use strict';
/* YouTube Shorts for the Extras tab: yt-dlp finds videos and their stream, ffmpeg decodes (hardware H.264 when
   it can), plays the sound through ALSA and hands small RGBA frames to the OS, which draws them like any image.
   YouTube changes often, so this breaks from time to time until yt-dlp is updated (Settings -> System). */
const { spawn, execFile } = require('child_process');
const https = require('https');

const FRAME_W = 136, FRAME_H = 240, FPS = 24;

function fmtCount(n) {
  if (!n && n !== 0) return '';
  if (n >= 1e6) return (n / 1e6).toFixed(n >= 1e7 ? 0 : 1).replace(/\.0$/, '') + 'M';
  if (n >= 1e3) return Math.round(n / 1e3) + 'K';
  return String(n);
}

function fetchBuffer(url, depth) {
  return new Promise((resolve, reject) => {
    https.get(url, { timeout: 8000 }, res => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location && (depth || 0) < 4) {
        res.resume(); fetchBuffer(res.headers.location, (depth || 0) + 1).then(resolve, reject); return;
      }
      if (res.statusCode !== 200) { res.resume(); reject(new Error('HTTP ' + res.statusCode)); return; }
      const chunks = []; res.on('data', c => chunks.push(c)); res.on('end', () => resolve(Buffer.concat(chunks)));
    }).on('error', reject).on('timeout', function () { this.destroy(new Error('timeout')); });
  });
}

class Shorts {
  constructor(opts) {
    this.opts = opts; this.log = opts.log || console.log; this.canvas = opts.canvasLib;
    this.thumbs = new Map(); this.frameCanvas = this.canvas.createCanvas(FRAME_W, FRAME_H);
    this.fctx = this.frameCanvas.getContext('2d'); this.ff = null; this.cur = null; this.lastError = '';
    this.state = { frames: 0, offset: 0, paused: false, ended: false, gotFrame: false };
    this.extra = (opts.ytdlpArgs || ['--js-runtimes', 'node']).slice();
  }
  ytdlp(args, timeoutMs) {
    const run = extra => new Promise((resolve, reject) => {
      execFile(this.opts.ytdlp, extra.concat(['--no-warnings']).concat(args), { timeout: timeoutMs || 45000, maxBuffer: 8 << 20 }, (err, out, errOut) => {
        if (err) { err.message = (errOut || err.message).trim().split('\n').pop(); reject(err); } else resolve(out);
      });
    });
    return run(this.extra).catch(e => {
      if (this.extra.length && /no such option|unrecognized/i.test(e.message)) { this.extra = []; return run([]); }
      throw e;
    });
  }
  async find(query) {
    const out = await this.ytdlp(['--flat-playlist', '-J', '--playlist-end', '15', 'ytsearch15:' + query]);
    const data = JSON.parse(out);
    return (data.entries || []).filter(e => e && e.id && (!e.duration || e.duration <= 180)).map((e, i) => ({
      id: e.id, t: e.title || 'Untitled', c: '@' + String(e.channel || e.uploader || 'youtube').replace(/^@/, ''),
      l: fmtCount(e.view_count), views: true, dur: Math.round(e.duration || 60), hue: (i * 47 + 20) % 360, m: 'ball'
    }));
  }
  feed() { return this.find(this.opts.feedQuery).catch(e => { this.lastError = e.message; this.log('shorts feed:', e.message); return []; }); }
  /* Returns an array right away and fills it when the search finishes; the OS shows "Searching…" meanwhile. */
  search(q) {
    const out = []; out.loading = true;
    this.find(q + ' #shorts').then(r => { out.push(...r); }, e => { this.lastError = e.message; this.log('shorts search:', e.message); })
      .finally(() => { out.loading = false; });
    return out;
  }
  image(v) {
    if (this.cur && this.cur.id === v.id && this.state.gotFrame) return { img: this.frameCanvas, cover: false };
    const t = this.thumbs.get(v.id);
    if (t === undefined) {
      this.thumbs.set(v.id, null);
      if (this.thumbs.size > 60) this.thumbs.delete(this.thumbs.keys().next().value);
      fetchBuffer('https://i.ytimg.com/vi/' + v.id + '/mqdefault.jpg').then(b => this.canvas.loadImage(b))
        .then(img => this.thumbs.set(v.id, img), () => {});
      return null;
    }
    return t ? { img: t, cover: true } : null;
  }
  time() { return this.state.offset + this.state.frames / FPS; }
  ended() { return this.state.ended; }
  async play(v, seek) {
    this.stopFfmpeg();
    if (!v || !v.id) return;
    const same = this.cur && this.cur.id === v.id && this.urls;
    this.cur = v; const token = this.token = (this.token || 0) + 1;
    this.state = { frames: 0, offset: seek || 0, paused: false, ended: false, gotFrame: !!same && this.state.gotFrame };
    let urls = same ? this.urls : null;
    if (!urls) {
      this.urls = null;
      try {
        urls = (await this.ytdlp(['-f', '18/b[height<=' + this.opts.maxHeight + '][ext=mp4]/b[height<=480]/b', '-g', 'https://www.youtube.com/shorts/' + v.id])).trim().split('\n');
      } catch (e) { this.lastError = e.message; this.log('shorts stream:', e.message); if (this.onError) this.onError('Couldn’t play this Short'); return; }
      if (token !== this.token) return;
      this.urls = urls;
    }
    this.startFfmpeg(urls, seek || 0, true, token);
  }
  startFfmpeg(urls, seek, hw, token) {
    const args = ['-nostdin', '-hide_banner', '-loglevel', 'error', '-re'];
    if (seek) args.push('-ss', String(seek));
    if (hw) args.push('-c:v', 'h264_v4l2m2m');
    args.push('-i', urls[0]);
    if (urls[1]) args.push('-i', urls[1]);
    args.push('-map', '0:v:0', '-vf', 'scale=' + FRAME_W + ':' + FRAME_H + ':force_original_aspect_ratio=decrease,pad=' + FRAME_W + ':' + FRAME_H + ':(ow-iw)/2:(oh-ih)/2,fps=' + FPS,
      '-pix_fmt', 'rgba', '-f', 'rawvideo', 'pipe:1');
    args.push('-map', urls[1] ? '1:a:0?' : '0:a:0?', '-f', 'alsa', 'default');
    const p = spawn('ffmpeg', args, { stdio: ['ignore', 'pipe', 'pipe'] });
    this.ff = p; const size = FRAME_W * FRAME_H * 4; let buf = Buffer.alloc(0), errText = '';
    p.stdout.on('data', chunk => {
      buf = buf.length ? Buffer.concat([buf, chunk]) : chunk;
      let last = null;
      while (buf.length >= size) { last = buf.subarray(0, size); buf = buf.subarray(size); this.state.frames++; }
      if (last) {
        const img = this.fctx.createImageData(FRAME_W, FRAME_H); img.data.set(last);
        this.fctx.putImageData(img, 0, 0); this.state.gotFrame = true;
      }
    });
    p.stderr.on('data', d => { errText += d; });
    p.on('exit', code => {
      if (this.ff !== p) return;
      this.ff = null;
      if (code !== 0 && hw && this.state.frames === 0 && token === this.token) { this.log('hardware decode failed, using software:', errText.trim()); this.startFfmpeg(urls, seek, false, token); return; }
      if (code !== 0 && code !== null) this.log('ffmpeg:', errText.trim());
      this.state.ended = true;
    });
  }
  pause(on) {
    this.state.paused = on;
    if (this.ff) { try { this.ff.kill(on ? 'SIGSTOP' : 'SIGCONT'); } catch (e) { /* gone */ } }
  }
  seek(t) { if (this.cur) this.play(this.cur, Math.max(0, t)); }
  stopFfmpeg() { const p = this.ff; this.ff = null; if (p) { try { p.kill('SIGCONT'); p.kill('SIGTERM'); } catch (e) { /* gone */ } } }
  stop() { this.token = (this.token || 0) + 1; this.stopFfmpeg(); this.cur = null; this.urls = null; this.state.gotFrame = false; }
  playing() { return !!this.cur; }
}

module.exports = { Shorts, fmtCount };
