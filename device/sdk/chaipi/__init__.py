"""chaipi: write your own games and tools for ChAIpi in Python.

    from chaipi import app

    @app.loop(fps=15)
    def frame(screen, keys):
        screen.clear()
        screen.text("Hello", 10, 20)
        if keys.pressed("ok"):
            app.buzz()

Put main.py (and an app.toml with name = "My game") in a folder and send it with Transfer, USB drive
mode or the SD card. It appears in Extras -> Games. ChAIpi runs it as its own process, so it gets the
whole screen and all its memory is freed when it ends. Esc quits (hold Esc for 1 s if the app is stuck).

screen   320 x 240 (or the size of your display). clear, text, rect, circle, line, pixel, image;
         .img and .draw give you the Pillow Image and ImageDraw for anything else.
keys     keys.down("left") while held, keys.pressed("ok") once per press, keys.released(...).
         Names: up down left right ok back esc tab menu fn stick.
app      app.buzz(ms), app.quit(), app.width, app.height, app.data_dir (save high scores here), app.t (seconds).
Colours  any Pillow colour, or the theme names: bg surface fg muted accent berry good warn bad blue.
"""
import json
import os
import socket
import threading
import time

from PIL import Image, ImageDraw, ImageFont

try:
    import numpy as np
except ImportError:  # slower fallback below
    np = None

THEME = {'bg': '#121013', 'surface': '#1d1a1e', 'surface2': '#2a262b', 'line': '#39343a', 'fg': '#f3ede6', 'muted': '#a49b94',
         'faint': '#6d655f', 'accent': '#e7a54d', 'berry': '#f2557f', 'good': '#4cb37c', 'warn': '#e3b23c', 'bad': '#e5534b', 'blue': '#7fa7ff'}
KEYNAMES = {'UP': 'up', 'DOWN': 'down', 'LEFT': 'left', 'RIGHT': 'right', 'OK': 'ok', 'BKSP': 'back', 'ESC': 'esc',
            'TAB': 'tab', 'MENU': 'menu', 'FN': 'fn', 'STICK': 'stick'}
FONT_DIR = os.environ.get('CHAIPI_FONTS', '/opt/chaipi/fonts')


def colour(c):
    return THEME.get(c, c) if isinstance(c, str) else c


def _find_fb():
    want = os.environ.get('CHAIPI_FB')
    if want:
        return want
    try:
        fbs = sorted(n for n in os.listdir('/sys/class/graphics') if n.startswith('fb'))
    except OSError:
        return None
    for fb in fbs:
        try:
            name = open('/sys/class/graphics/%s/name' % fb).read()
        except OSError:
            continue
        if any(k in name.lower() for k in ('ili9341', 'ili9340', 'mipi', 'ili9486', 'st7735', 'st7789', 'fb_')):
            return '/dev/' + fb
    return '/dev/' + fbs[-1] if fbs else None


def _fb_size(dev):
    try:
        w, h = open('/sys/class/graphics/%s/virtual_size' % os.path.basename(dev)).read().strip().split(',')
        return int(w), int(h)
    except (OSError, ValueError):
        return 320, 240


class Screen:
    """Draw here; ChAIpi sends it to the display after each frame."""

    def __init__(self, w, h):
        self.width, self.height = w, h
        self.img = Image.new('RGB', (w, h), THEME['bg'])
        self.draw = ImageDraw.Draw(self.img)
        self._fonts = {}

    def font(self, size=12, bold=False, mono=False):
        key = (size, bold, mono)
        if key not in self._fonts:
            names = (['JetBrainsMono-SemiBold.ttf' if bold else 'JetBrainsMono-Regular.ttf'] if mono else
                     ['AtkinsonHyperlegible-Bold.ttf' if bold else 'AtkinsonHyperlegible-Regular.ttf']) + ['DejaVuSans.ttf']
            f = None
            for n in names:
                for d in (FONT_DIR, '/usr/share/fonts/truetype/dejavu'):
                    try:
                        f = ImageFont.truetype(os.path.join(d, n), size)
                        break
                    except OSError:
                        continue
                if f:
                    break
            self._fonts[key] = f or ImageFont.load_default(size)
        return self._fonts[key]

    def clear(self, c='bg'):
        self.draw.rectangle((0, 0, self.width, self.height), fill=colour(c))

    def text(self, s, x, y, c='fg', size=12, bold=False, mono=False, align='left'):
        f = self.font(size, bold, mono)
        anchor = {'left': 'ls', 'center': 'ms', 'right': 'rs'}[align]
        self.draw.text((x, y), str(s), fill=colour(c), font=f, anchor=anchor)

    def text_width(self, s, size=12, bold=False, mono=False):
        return self.draw.textlength(str(s), font=self.font(size, bold, mono))

    def rect(self, x, y, w, h, c='fg', fill=True, radius=0, width=1):
        box = (x, y, x + w - 1, y + h - 1)
        if radius:
            self.draw.rounded_rectangle(box, radius, fill=colour(c) if fill else None, outline=None if fill else colour(c), width=width)
        else:
            self.draw.rectangle(box, fill=colour(c) if fill else None, outline=None if fill else colour(c), width=width)

    def circle(self, x, y, r, c='fg', fill=True, width=1):
        box = (x - r, y - r, x + r, y + r)
        self.draw.ellipse(box, fill=colour(c) if fill else None, outline=None if fill else colour(c), width=width)

    def line(self, x1, y1, x2, y2, c='fg', width=1):
        self.draw.line((x1, y1, x2, y2), fill=colour(c), width=width)

    def pixel(self, x, y, c='fg'):
        self.draw.point((x, y), fill=colour(c))

    def image(self, img, x, y):
        if isinstance(img, str):
            img = Image.open(img)
        self.img.paste(img.convert('RGB'), (int(x), int(y)), img if img.mode == 'RGBA' else None)

    def rgb565(self):
        if np is not None:
            a = np.asarray(self.img, dtype=np.uint16)
            v = ((a[..., 0] >> 3) << 11) | ((a[..., 1] >> 2) << 5) | (a[..., 2] >> 3)
            return v.astype('<u2').tobytes()
        raw = self.img.tobytes()
        out = bytearray(len(raw) // 3 * 2)
        j = 0
        for i in range(0, len(raw), 3):
            v = ((raw[i] & 0xF8) << 8) | ((raw[i + 1] & 0xFC) << 3) | (raw[i + 2] >> 3)
            out[j] = v & 0xFF
            out[j + 1] = v >> 8
            j += 2
        return bytes(out)


class Keys:
    def __init__(self):
        self._down = set()
        self._pressed = set()
        self._released = set()
        self._pending = []
        self._lock = threading.Lock()

    def _event(self, name, is_down):
        with self._lock:
            self._pending.append((name, is_down))

    def _frame(self):
        with self._lock:
            ev, self._pending = self._pending, []
        self._pressed, self._released = set(), set()
        for name, is_down in ev:
            if is_down:
                self._down.add(name)
                self._pressed.add(name)
            else:
                self._down.discard(name)
                self._released.add(name)

    def down(self, name):
        return name in self._down

    def pressed(self, name):
        return name in self._pressed

    def released(self, name):
        return name in self._released

    def any_pressed(self):
        return bool(self._pressed)


class App:
    def __init__(self):
        self.fn = None
        self.setup_fn = None
        self.fps = 15
        self.esc_quits = True
        self.running = False
        self.t = 0.0
        self.keys = Keys()
        self._sock = None
        self.data_dir = os.environ.get('CHAIPI_DATA') or os.path.join(os.path.expanduser('~'), '.chaipi-app')
        dev = _find_fb()
        self.fb_path = dev
        self.width, self.height = _fb_size(dev) if dev and dev.startswith('/dev/') else (320, 240)
        self.screen = Screen(self.width, self.height)

    def loop(self, fps=15, esc_quits=True):
        def deco(fn):
            self.fn, self.fps, self.esc_quits = fn, fps, esc_quits
            return fn
        return deco

    def setup(self, fn):
        self.setup_fn = fn
        return fn

    def quit(self):
        self.running = False

    def buzz(self, ms=20):
        self._send({'cmd': 'buzz', 'ms': int(ms)})

    # --- plumbing ------------------------------------------------------------------------------
    def _send(self, msg):
        if self._sock:
            try:
                self._sock.sendall((json.dumps(msg) + '\n').encode())
            except OSError:
                pass

    def _input_thread(self, path):
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(path)
        except OSError:
            return
        self._sock = s
        buf = b''
        while self.running:
            try:
                chunk = s.recv(4096)
            except OSError:
                break
            if not chunk:
                break
            buf += chunk
            while b'\n' in buf:
                line, buf = buf.split(b'\n', 1)
                try:
                    m = json.loads(line)
                except ValueError:
                    continue
                name = KEYNAMES.get(m.get('b'))
                if name and m.get('e') in ('down', 'up'):
                    self.keys._event(name, m['e'] == 'down')

    def _flush(self, fb):
        if fb is None:
            return
        if isinstance(fb, str):  # "png:/path" for trying apps on a computer
            if time.monotonic() - getattr(self, '_last_png', 0) > 0.5:
                self.screen.img.save(fb)
                self._last_png = time.monotonic()
            return
        fb.seek(0)
        fb.write(self.screen.rgb565())
        fb.flush()

    def run(self):
        if not self.fn:
            raise SystemExit('No @app.loop function in this app')
        os.makedirs(self.data_dir, exist_ok=True)
        self.running = True
        threading.Thread(target=self._input_thread, args=(os.environ.get('CHAIPI_INPUT', '/run/chaipi/input.sock'),), daemon=True).start()
        fb = None
        if self.fb_path and self.fb_path.startswith('png:'):
            fb = self.fb_path[4:]
        elif self.fb_path:
            try:
                fb = open(self.fb_path, 'r+b', buffering=0)
            except OSError as e:
                print('chaipi: no display (%s); running without one' % e)
        if self.setup_fn:
            self.setup_fn(self.screen)
        t0 = time.monotonic()
        period = 1.0 / max(1, self.fps)
        try:
            while self.running:
                start = time.monotonic()
                self.t = start - t0
                self.keys._frame()
                if self.esc_quits and self.keys.pressed('esc'):
                    break
                self.fn(self.screen, self.keys)
                self._flush(fb)
                time.sleep(max(0.0, period - (time.monotonic() - start)))
        finally:
            self.running = False
            if fb is not None and not isinstance(fb, str):
                fb.close()


app = App()
