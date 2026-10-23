#!/usr/bin/env python3
"""chaipi-input: buttons, joystick, battery, vibration and backlight for ChAIpi (revision 3 wiring, docs/12).

Serves one JSON object per line on a Unix socket (default /run/chaipi/input.sock).
Out:  {"e":"down","b":"OK"}  {"e":"up","b":"OK"}  {"e":"sys","bat":84.2,"volts":3.95,"usb":true,"charging":true,"full":false}
      {"e":"lowbatt"}  {"e":"char","c":"a"}  {"e":"submit"}
In:   {"cmd":"buzz","ms":25}  {"cmd":"backlight","level":0.8}
      {"inject":"down","b":"OK"} / {"inject":"up","b":"OK"} / {"inject":"char","c":"a"} / {"inject":"submit"}
        (injections are re-sent to every client, so `chaipi-keys` can drive the UI over SSH)

Run with --mock on a computer without the hardware.
"""
import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
import time

try:
    import tomllib
except ImportError:  # Python < 3.11
    tomllib = None

log = logging.getLogger('chaipi-input')
BUTTONS = ('OK', 'BKSP', 'ESC', 'TAB', 'MENU', 'FN', 'STICK')
DIRS = ('UP', 'DOWN', 'LEFT', 'RIGHT')

DEFAULTS = {
    'buttons': {'OK': 5, 'BKSP': 6, 'ESC': 16, 'TAB': 26, 'MENU': 23, 'FN': 17, 'STICK': 27, 'bounce_ms': 15},
    'joystick': {'adc_x': 0, 'adc_y': 1, 'invert_x': False, 'invert_y': False, 'swap_xy': False, 'press': 0.55, 'release': 0.35, 'rate_hz': 100},
    'adc': {'i2c_bus': 1, 'address': 0x48},
    'battery': {'adc_channel': 2, 'divider': 2.0, 'usb_channel': 3, 'usb_divider': 2.0, 'usb_present_v': 4.4, 'warn_v': 3.5, 'shutdown_v': 3.35},
    'vibration': {'gpio': 12},
    'backlight': {'pwm_chip': 0, 'pwm_channel': 1, 'gpio': 13, 'frequency_hz': 1000, 'invert': False},
    'paths': {'run': '/run/chaipi'},
}


def load_config(path):
    cfg = {k: dict(v) for k, v in DEFAULTS.items()}
    if path and tomllib and os.path.exists(path):
        with open(path, 'rb') as f:
            user = tomllib.load(f)
        for k, v in user.items():
            if isinstance(v, dict):
                cfg.setdefault(k, {}).update(v)
    return cfg


# --------------------------------------------------------------------------------------------
# Pure logic (unit-tested in tests/test_input.py)
# --------------------------------------------------------------------------------------------

def ads1115_config(channel):
    """Config register for one single-shot conversion: AINx vs GND, +-4.096 V, 860 samples/s, comparator off."""
    if not 0 <= channel <= 3:
        raise ValueError('ADS1115 channel 0-3')
    return 0x8000 | ((4 + channel) << 12) | (0b001 << 9) | (1 << 8) | (0b111 << 5) | 0b11


def ads1115_volts(raw):
    """Signed 16-bit conversion result to volts at the +-4.096 V range."""
    if raw >= 0x8000:
        raw -= 0x10000
    return raw * 4.096 / 32768


class Joystick:
    """Analog stick -> UP/DOWN/LEFT/RIGHT edges, with a dead zone and hysteresis so it never chatters."""

    def __init__(self, press=0.55, release=0.35, invert_x=False, invert_y=False, swap_xy=False, vref=3.3):
        self.press, self.release = press, release
        self.inv_x, self.inv_y, self.swap = invert_x, invert_y, swap_xy
        self.vref = vref
        self.cx = self.cy = vref / 2
        self.held = None

    def calibrate(self, xs, ys):
        self.cx = sum(xs) / len(xs)
        self.cy = sum(ys) / len(ys)

    def _norm(self, v, c):
        span = max(c, self.vref - c, 0.1)
        return max(-1.0, min(1.0, (v - c) / span))

    def update(self, vx, vy):
        """Returns a list of (direction, is_down) edges."""
        x, y = self._norm(vx, self.cx), self._norm(vy, self.cy)
        if self.swap:
            x, y = y, x
        if self.inv_x:
            x = -x
        if self.inv_y:
            y = -y
        mag_x, mag_y = abs(x), abs(y)
        want = self.held
        if self.held is None:
            if max(mag_x, mag_y) >= self.press:
                want = ('RIGHT' if x > 0 else 'LEFT') if mag_x >= mag_y else ('DOWN' if y > 0 else 'UP')
        else:
            axis = x if self.held in ('LEFT', 'RIGHT') else y
            same_way = (axis > 0) == (self.held in ('RIGHT', 'DOWN'))
            if abs(axis) < self.release or not same_way:
                want = None
                if max(mag_x, mag_y) >= self.press:
                    want = ('RIGHT' if x > 0 else 'LEFT') if mag_x >= mag_y else ('DOWN' if y > 0 else 'UP')
        edges = []
        if want != self.held:
            if self.held:
                edges.append((self.held, False))
            if want:
                edges.append((want, True))
            self.held = want
        return edges


# Resting LiPo voltage -> charge, from common discharge curves (single cell or cells in parallel).
LIPO_CURVE = [(3.27, 0), (3.61, 5), (3.69, 10), (3.71, 15), (3.73, 20), (3.75, 25), (3.77, 30), (3.79, 35), (3.80, 40),
              (3.82, 45), (3.84, 50), (3.85, 55), (3.87, 60), (3.91, 65), (3.95, 70), (3.98, 75), (4.02, 80), (4.08, 85),
              (4.11, 90), (4.15, 95), (4.20, 100)]


def lipo_percent(v):
    if v <= LIPO_CURVE[0][0]:
        return 0.0
    if v >= LIPO_CURVE[-1][0]:
        return 100.0
    for (v0, p0), (v1, p1) in zip(LIPO_CURVE, LIPO_CURVE[1:]):
        if v <= v1:
            return p0 + (p1 - p0) * (v - v0) / (v1 - v0)
    return 100.0


class Battery:
    """Smooths the divider reading into a steady percentage.
    While charging, the TP4056 lifts the cell voltage, so ~0.08 V is taken off; when not charging the
    percentage only goes down, so it doesn't jump up and down with the engine's load."""

    def __init__(self, warn_v=3.5, shutdown_v=3.35, usb_present_v=4.4):
        self.warn_v, self.shutdown_v, self.usb_present_v = warn_v, shutdown_v, usb_present_v
        self.v = None
        self.pct = None
        self.usb = False
        self.full_since = None
        self.low_since = None
        self.lowbatt_sent = False

    def update(self, vbat, vusb, now):
        self.v = vbat if self.v is None else self.v + (vbat - self.v) * 0.15
        was_usb, self.usb = self.usb, vusb >= self.usb_present_v
        est = lipo_percent(self.v - (0.08 if self.usb else 0.0))
        if self.pct is None or self.usb != was_usb:
            self.pct = est
        elif self.usb:
            self.pct += (est - self.pct) * 0.1
        else:
            self.pct = min(self.pct, self.pct + (est - self.pct) * 0.1)
        if self.usb and self.v >= 4.17:
            self.full_since = self.full_since or now
        else:
            self.full_since = None
        full = self.full_since is not None and now - self.full_since > 120
        if full:
            self.pct = 100.0
        lowbatt = False
        if not self.usb and self.v < self.shutdown_v:
            self.low_since = self.low_since or now
            if now - self.low_since > 30 and not self.lowbatt_sent:
                self.lowbatt_sent = lowbatt = True
        else:
            self.low_since = None
            if self.usb:
                self.lowbatt_sent = False
        return {'e': 'sys', 'bat': round(self.pct, 1), 'volts': round(self.v, 3), 'usb': self.usb,
                'charging': self.usb and not full, 'full': full}, lowbatt


# --------------------------------------------------------------------------------------------
# Hardware
# --------------------------------------------------------------------------------------------

class ADS1115:
    def __init__(self, bus, address):
        try:
            from smbus2 import SMBus
        except ImportError:  # Debian's python3-smbus has the same calls
            from smbus import SMBus
        self.bus = SMBus(bus)
        self.addr = address

    def read(self, channel):
        word = ads1115_config(channel)
        self.bus.write_i2c_block_data(self.addr, 0x01, [word >> 8, word & 0xFF])
        time.sleep(0.0013)
        for _ in range(5):
            hi, lo = self.bus.read_i2c_block_data(self.addr, 0x01, 2)
            if hi & 0x80:
                break
            time.sleep(0.0003)
        hi, lo = self.bus.read_i2c_block_data(self.addr, 0x00, 2)
        return ads1115_volts((hi << 8) | lo)


class Backlight:
    """Hardware PWM through sysfs (dtoverlay=pwm,pin=13,func=4), or gpiozero's PWM on the same pin."""

    def __init__(self, chip, channel, gpio, freq, invert=False):
        self.invert = invert
        self.base = f'/sys/class/pwm/pwmchip{chip}'
        self.pwm = f'{self.base}/pwm{channel}'
        self.period = int(1e9 / freq)
        self.soft = None
        try:
            if not os.path.exists(self.pwm):
                with open(f'{self.base}/export', 'w') as f:
                    f.write(str(channel))
            for _ in range(20):  # udev fixes the permissions a moment after export
                try:
                    self._w('period', self.period)
                    break
                except PermissionError:
                    time.sleep(0.05)
            self._w('duty_cycle', self.period)
            self._w('enable', 1)
            log.info('backlight: hardware PWM %s', self.pwm)
        except OSError as e:
            from gpiozero import PWMOutputDevice
            log.info('backlight: software PWM on GPIO%s (%s)', gpio, e)
            self.soft = PWMOutputDevice(gpio, frequency=freq, initial_value=1.0)

    def _w(self, name, value):
        with open(f'{self.pwm}/{name}', 'w') as f:
            f.write(str(value))

    def set(self, level):
        level = max(0.0, min(1.0, float(level)))
        if self.invert:  # PNP high-side switch: low = on
            level = 1.0 - level
        if self.soft:
            self.soft.value = level
        else:
            self._w('duty_cycle', int(self.period * level))


# --------------------------------------------------------------------------------------------
# Daemon
# --------------------------------------------------------------------------------------------

class Daemon:
    def __init__(self, cfg, mock=False):
        self.cfg, self.mock = cfg, mock
        self.clients = set()
        self.loop = None
        self.adc = self.backlight = self.vib = None
        self.buttons = []
        j = cfg['joystick']
        self.stick = Joystick(j['press'], j['release'], j['invert_x'], j['invert_y'], j['swap_xy'])
        b = cfg['battery']
        self.battery = Battery(b['warn_v'], b['shutdown_v'], b.get('usb_present_v', 4.4))
        self.last_sys = {'e': 'sys', 'bat': 80.0, 'volts': 3.9, 'usb': False, 'charging': False, 'full': False}

    def broadcast(self, msg):
        line = (json.dumps(msg) + '\n').encode()
        for w in list(self.clients):
            try:
                w.write(line)
            except Exception:
                self.clients.discard(w)

    def from_thread(self, msg):
        self.loop.call_soon_threadsafe(self.broadcast, msg)

    def setup_hardware(self):
        if self.mock:
            log.info('mock mode: no GPIO, no ADC')
            return
        from gpiozero import Button, DigitalOutputDevice
        bounce = self.cfg['buttons'].get('bounce_ms', 15) / 1000
        for name in BUTTONS:
            pin = self.cfg['buttons'].get(name)
            if pin is None:
                continue
            btn = Button(pin, pull_up=True, bounce_time=bounce)
            btn.when_pressed = lambda n=name: self.from_thread({'e': 'down', 'b': n})
            btn.when_released = lambda n=name: self.from_thread({'e': 'up', 'b': n})
            self.buttons.append(btn)
        try:
            self.vib = DigitalOutputDevice(self.cfg['vibration']['gpio'])
        except Exception as e:
            log.warning('vibration: %s', e)
        bl = self.cfg['backlight']
        try:
            self.backlight = Backlight(bl['pwm_chip'], bl['pwm_channel'], bl['gpio'], bl['frequency_hz'], bl.get('invert', False))
        except Exception as e:
            log.warning('backlight: %s', e)
        try:
            a = self.cfg['adc']
            self.adc = ADS1115(a['i2c_bus'], a['address'])
            j = self.cfg['joystick']
            xs = [self.adc.read(j['adc_x']) for _ in range(16)]
            ys = [self.adc.read(j['adc_y']) for _ in range(16)]
            self.stick.calibrate(xs, ys)
            log.info('joystick centre %.3f V / %.3f V', self.stick.cx, self.stick.cy)
        except Exception as e:
            log.warning('ADS1115 not answering (joystick and battery off): %s', e)
            self.adc = None

    async def joystick_task(self):
        j = self.cfg['joystick']
        period = 1 / j.get('rate_hz', 100)
        while True:
            if self.adc:
                try:
                    vx, vy = await asyncio.to_thread(lambda: (self.adc.read(j['adc_x']), self.adc.read(j['adc_y'])))
                    for d, down in self.stick.update(vx, vy):
                        self.broadcast({'e': 'down' if down else 'up', 'b': d})
                except OSError as e:
                    log.warning('joystick read: %s', e)
                    await asyncio.sleep(1)
            await asyncio.sleep(period)

    async def battery_task(self):
        b = self.cfg['battery']
        while True:
            if self.adc:
                try:
                    vb, vu = await asyncio.to_thread(lambda: (self.adc.read(b['adc_channel']) * b['divider'],
                                                                self.adc.read(b['usb_channel']) * b['usb_divider']))
                    msg, low = self.battery.update(vb, vu, time.monotonic())
                    self.last_sys = msg
                    if low:
                        log.warning('battery at %.2f V for 30 s: asking the UI to shut down', self.battery.v)
                        self.broadcast({'e': 'lowbatt'})
                        self.loop.call_later(60, self.failsafe_poweroff)
                except OSError as e:
                    log.warning('battery read: %s', e)
            self.broadcast(self.last_sys)
            await asyncio.sleep(2)

    def failsafe_poweroff(self):
        if self.battery.usb:
            return
        log.warning('UI did not power off; doing it now')
        subprocess.run(['systemctl', 'poweroff'], check=False)

    def command(self, m):
        if 'inject' in m:
            kind = m['inject']
            if kind in ('down', 'up') and m.get('b') in BUTTONS + DIRS:
                self.broadcast({'e': kind, 'b': m['b']})
            elif kind == 'char' and isinstance(m.get('c'), str) and m['c']:
                self.broadcast({'e': 'char', 'c': m['c'][:1]})
            elif kind == 'submit':
                self.broadcast({'e': 'submit'})
            return
        cmd = m.get('cmd')
        if cmd == 'buzz' and self.vib:
            ms = max(5, min(400, int(m.get('ms', 20))))
            self.vib.on()
            self.loop.call_later(ms / 1000, self.vib.off)
        elif cmd == 'backlight' and self.backlight:
            try:
                self.backlight.set(m.get('level', 1.0))
            except OSError as e:
                log.warning('backlight: %s', e)

    async def client(self, reader, writer):
        self.clients.add(writer)
        writer.write((json.dumps(self.last_sys) + '\n').encode())
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                try:
                    self.command(json.loads(line))
                except (ValueError, TypeError, AttributeError):
                    pass
        finally:
            self.clients.discard(writer)
            writer.close()

    async def run(self, sock_path):
        self.loop = asyncio.get_running_loop()
        self.setup_hardware()
        os.makedirs(os.path.dirname(sock_path), exist_ok=True)
        if os.path.exists(sock_path):
            os.unlink(sock_path)
        server = await asyncio.start_unix_server(self.client, path=sock_path)
        os.chmod(sock_path, 0o660)
        log.info('listening on %s', sock_path)
        async with server:
            await asyncio.gather(server.serve_forever(), self.joystick_task(), self.battery_task())


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--config', default='/etc/chaipi/chaipi.toml')
    ap.add_argument('--socket')
    ap.add_argument('--mock', action='store_true', help='run without GPIO/I2C (for testing on a computer)')
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', stream=sys.stdout)
    cfg = load_config(args.config)
    sock = args.socket or os.path.join(cfg['paths'].get('run', '/run/chaipi'), 'input.sock')
    try:
        asyncio.run(Daemon(cfg, mock=args.mock).run(sock))
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
