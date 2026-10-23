#!/usr/bin/env python3
"""Renders the README pictures from the emulator with headless Google Chrome:

    .venv/bin/python tools/capture_screens.py      # needs Chrome and Pillow; writes docs/media/

  docs/media/hero.png          the handheld on the home screen (transparent background)
  docs/media/tour.gif          a short screen recording at the device's real 320x240 pixels, scaled 2x
  docs/media/screens/*.png     single screens at real pixels, scaled 2x
  docs/media/phone.png         the Transfer page a phone sees

Chrome is driven over --remote-debugging-pipe (the DevTools protocol on fds 3 and 4), so nothing beyond the
standard library and Pillow is needed. Each run starts with a fresh browser profile, so the emulator is on its
default settings.
"""
import base64
import fcntl
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'docs' / 'media'
CHROME = os.environ.get('CHROME', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
sys.path.insert(0, str(ROOT / 'tools'))
import build_emulator  # noqa: E402

# name, jump-chip label, keys to press after the jump, seconds to wait before the capture
SCREENS = [
    ('home', 'Home', [], 1.0),
    ('play', 'Play (in game)', [], 1.0),
    ('helper', 'Helper', [], 3.0),
    ('review', 'Game review', ['ArrowRight'] * 6, 1.5),
    ('settings', 'Settings', [], 1.0),
    ('extras', 'Extras', [], 1.0),
    ('rickshaw', 'Rickshaw Rush', [], 2.5),
    ('graphing', 'Graphing', [], 1.5),
]
# The tour: (jump label or None, keys, seconds to record afterwards)
TOUR = [
    ('Boot', [], 4.2),
    (None, ['ArrowDown', 'ArrowDown', 'ArrowUp'], 1.6),
    ('Play (in game)', ['ArrowUp', 'ArrowRight'], 2.2),
    ('Helper', [], 3.0),
    ('Game review', ['ArrowRight', 'ArrowRight', 'ArrowRight'], 2.2),
    ('Extras', ['ArrowRight', 'ArrowRight'], 1.8),
    ('Rickshaw Rush', [], 3.2),
    ('Graphing', [], 2.0),
]
FPS = 12


class Chrome:
    """Minimal DevTools client over Chrome's pipe transport (JSON messages ending in a NUL byte)."""

    def __init__(self, profile):
        to_chrome_r, self.to_chrome = os.pipe()
        self.from_chrome, from_chrome_w = os.pipe()

        def child():  # Chrome reads commands on fd 3 and writes replies on fd 4
            a = fcntl.fcntl(to_chrome_r, fcntl.F_DUPFD, 10)
            b = fcntl.fcntl(from_chrome_w, fcntl.F_DUPFD, 10)
            os.dup2(a, 3)
            os.dup2(b, 4)

        self.proc = subprocess.Popen(
            [CHROME, '--headless=new', '--remote-debugging-pipe', '--user-data-dir=' + profile, '--no-first-run',
             '--no-default-browser-check', '--hide-scrollbars', '--mute-audio', '--allow-file-access-from-files',
             'about:blank'],
            pass_fds=(3, 4), preexec_fn=child, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.close(to_chrome_r)
        os.close(from_chrome_w)
        self.buf, self.next_id = b'', 0

    def send(self, method, params=None, session=None):
        self.next_id += 1
        msg = {'id': self.next_id, 'method': method, 'params': params or {}}
        if session:
            msg['sessionId'] = session
        os.write(self.to_chrome, json.dumps(msg).encode() + b'\0')
        while True:
            while b'\0' not in self.buf:
                chunk = os.read(self.from_chrome, 1 << 20)
                if not chunk:
                    raise RuntimeError('Chrome closed the pipe')
                self.buf += chunk
            raw, self.buf = self.buf.split(b'\0', 1)
            reply = json.loads(raw)
            if reply.get('id') == self.next_id:
                if 'error' in reply:
                    raise RuntimeError(f"{method}: {reply['error']}")
                return reply.get('result', {})

    def close(self):
        try:
            self.send('Browser.close')
        except RuntimeError:
            pass
        self.proc.wait(timeout=20)


class Page:
    def __init__(self, chrome):
        self.c = chrome
        target = chrome.send('Target.createTarget', {'url': 'about:blank'})['targetId']
        self.sid = chrome.send('Target.attachToTarget', {'targetId': target, 'flatten': True})['sessionId']

    def cmd(self, method, params=None):
        return self.c.send(method, params, self.sid)

    def js(self, expr):
        r = self.cmd('Runtime.evaluate', {'expression': expr, 'returnByValue': True, 'awaitPromise': True})
        if 'exceptionDetails' in r:
            raise RuntimeError(f"JS error in {expr[:80]!r}: {r['exceptionDetails'].get('exception', {}).get('description')}")
        return r['result'].get('value')

    def jump(self, label):
        ok = self.js(f"(()=>{{const b=[...document.querySelectorAll('#jump .chip')].find(b=>b.textContent==={json.dumps(label)});"
                     f"if(b) b.click(); return !!b; }})()")
        if not ok:
            raise RuntimeError(f'no "{label}" button under Jump to a screen')

    def press(self, key, hold=0.09):
        # the emulator listens on the #device element and maps keys there (see KEYMAP in the mockup)
        k = json.dumps(key)
        self.js(f"document.getElementById('device').dispatchEvent(new KeyboardEvent('keydown',{{key:{k},bubbles:true}}))")
        time.sleep(hold)
        self.js(f"document.getElementById('device').dispatchEvent(new KeyboardEvent('keyup',{{key:{k},bubbles:true}}))")
        time.sleep(0.12)

    def screen(self):
        """The device screen's own canvas: 320x240 when 'Show real pixels' is on."""
        url = self.js("document.getElementById('screen').toDataURL('image/png')")
        return Image.open(io.BytesIO(base64.b64decode(url.split(',', 1)[1]))).convert('RGB')

    def element_png(self, selector, scale=1):
        box = self.js(f"(()=>{{const r=document.querySelector({json.dumps(selector)}).getBoundingClientRect();"
                      f"return {{x:r.left+scrollX,y:r.top+scrollY,width:r.width,height:r.height}};}})()")
        pad = 24  # room for the shadow
        clip = {'x': box['x'] - pad, 'y': box['y'] - pad, 'width': box['width'] + 2 * pad,
                'height': box['height'] + 2 * pad, 'scale': scale}
        data = self.cmd('Page.captureScreenshot', {'format': 'png', 'clip': clip, 'captureBeyondViewport': True})['data']
        return Image.open(io.BytesIO(base64.b64decode(data)))


def x2(img):
    return img.resize((img.width * 2, img.height * 2), Image.NEAREST)


def save_gif(frames, durations, path):
    pal = [f.quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for f in frames]
    pal[0].save(path, save_all=True, append_images=pal[1:], duration=durations, loop=0, optimize=True, disposal=1)


def main():
    if not Path(CHROME).exists():
        sys.exit(f'Google Chrome not found at {CHROME} (set CHROME=/path/to/chrome)')
    (OUT / 'screens').mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='chaipi-cap-'))
    page_file = work / 'emulator.html'
    page_file.write_text(build_emulator.build(inline_fonts=True), encoding='utf-8')
    chrome = Chrome(str(work / 'profile'))
    try:
        p = Page(chrome)
        p.cmd('Page.enable')
        p.cmd('Runtime.enable')
        p.cmd('Emulation.setDeviceMetricsOverride', {'width': 1200, 'height': 1500, 'deviceScaleFactor': 2, 'mobile': False})
        p.cmd('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-color-scheme', 'value': 'light'}]})
        p.cmd('Page.navigate', {'url': page_file.as_uri()})
        for _ in range(100):
            time.sleep(0.1)
            if p.js("document.readyState==='complete' && !!document.querySelector('#jump .chip')"):
                break
        p.js('document.fonts.ready.then(()=>true)')
        time.sleep(4)  # the boot animation that starts on load

        # hero: the whole handheld, smooth screen, transparent page, no focus ring or key legend
        p.jump('Home')
        time.sleep(1.2)
        p.js("(()=>{const s=document.createElement('style');s.id='cap';s.textContent='html,body,.stage{background:transparent!important}"
             ".legend{visibility:hidden} .phone-wrap .section{visibility:hidden}';document.head.appendChild(s);document.activeElement.blur();return true;})()")
        p.cmd('Emulation.setDefaultBackgroundColorOverride', {'color': {'r': 0, 'g': 0, 'b': 0, 'a': 0}})
        p.element_png('#device', scale=1).save(OUT / 'hero.png', optimize=True)

        # phone (page still transparent): activate Transfer (with Math.random pinned for a moment, the PIN is 5500), join, type the PIN
        p.jump('Transfer')
        time.sleep(0.8)
        p.js('window.__r=Math.random; Math.random=()=>0.5')
        p.press('Enter')
        p.js('Math.random=window.__r')
        time.sleep(2.5)
        p.js("document.querySelector('#phone [data-act=join]').click()")
        time.sleep(2.5)
        p.js("(()=>{const i=document.getElementById('phPin'); i.value='5500'; i.dispatchEvent(new Event('input',{bubbles:true}));})()")
        time.sleep(1.5)
        p.element_png('.phone', scale=1).save(OUT / 'phone.png', optimize=True)
        p.cmd('Emulation.setDefaultBackgroundColorOverride', {})
        p.js("document.getElementById('cap').remove()")
        p.press('Escape')
        print('phone.png')

        # single screens at real pixels
        p.js("(()=>{const c=document.getElementById('pix'); if(!c.checked) c.click(); return c.checked;})()")
        for name, label, keys, wait in SCREENS:
            p.jump('Home')  # closes any running Extra; its toast fades before the shot
            time.sleep(3)
            p.jump(label)
            time.sleep(0.4)
            for k in keys:
                p.press(k)
            time.sleep(wait)
            x2(p.screen()).save(OUT / 'screens' / f'{name}.png', optimize=True)
            print(f'screens/{name}.png')

        # tour
        p.jump('Home')
        time.sleep(3)
        frames, stamps = [], []
        for label, keys, seconds in TOUR:
            if label:
                p.jump(label)
            t_end = time.time() + seconds
            pending = list(keys)
            next_key = time.time() + 0.5
            while time.time() < t_end:
                t0 = time.time()
                if pending and t0 >= next_key:
                    p.press(pending.pop(0))
                    next_key = time.time() + 0.35
                frames.append(x2(p.screen()))
                stamps.append(time.time())
                time.sleep(max(0.0, 1 / FPS - (time.time() - t0)))
        save_gif(frames, [round((b - a) * 1000) for a, b in zip(stamps, stamps[1:] + [stamps[-1] + 1 / FPS])], OUT / 'tour.gif')
        print(f'tour.gif  {len(frames)} frames, {(OUT / "tour.gif").stat().st_size / 1e6:.1f} MB')
    finally:
        chrome.close()
        shutil.rmtree(work, ignore_errors=True)


if __name__ == '__main__':
    main()
