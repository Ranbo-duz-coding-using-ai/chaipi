"""Tests for the input daemon's pure logic (device/input/chaipi_input.py)."""
import asyncio
import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'device', 'input'))
import chaipi_input as ci  # noqa: E402


@pytest.mark.parametrize('ch,word', [(0, 0xC3E3), (1, 0xD3E3), (2, 0xE3E3), (3, 0xF3E3)])
def test_ads1115_config_words(ch, word):
    assert ci.ads1115_config(ch) == word


def test_ads1115_volts():
    assert ci.ads1115_volts(0x0000) == 0
    assert ci.ads1115_volts(0x7FFF) == pytest.approx(4.096, abs=0.001)
    assert ci.ads1115_volts(0x4000) == pytest.approx(2.048)
    assert ci.ads1115_volts(0xFFFF) == pytest.approx(-0.000125)


def test_joystick_press_release_hysteresis():
    j = ci.Joystick(press=0.55, release=0.35)
    j.calibrate([1.65] * 4, [1.65] * 4)
    assert j.update(1.65, 1.65) == []
    assert j.update(1.65 + 0.6 * 1.65, 1.65) == [('RIGHT', True)]
    assert j.update(1.65 + 0.45 * 1.65, 1.65) == []          # inside hysteresis: still held
    assert j.update(1.65 + 0.2 * 1.65, 1.65) == [('RIGHT', False)]
    assert j.update(1.65, 0.1) == [('UP', True)]
    assert j.update(1.65, 3.2) == [('UP', False), ('DOWN', True)]   # straight across: release then press


def test_joystick_dominant_axis_and_inversion():
    j = ci.Joystick(invert_x=True, swap_xy=False)
    j.calibrate([1.6], [1.7])
    assert j.update(3.3, 2.4) == [('LEFT', True)]


def test_lipo_percent_curve():
    assert ci.lipo_percent(4.25) == 100
    assert ci.lipo_percent(3.0) == 0
    assert ci.lipo_percent(3.84) == pytest.approx(50)
    assert 60 < ci.lipo_percent(3.89) < 65


def test_battery_never_rises_on_battery_and_detects_charging():
    b = ci.Battery()
    m, _ = b.update(3.90, 0.0, 0)
    p0 = m['bat']
    m, _ = b.update(3.95, 0.0, 2)       # load dropped, voltage bounced up
    assert m['bat'] <= p0 and not m['charging']
    m, _ = b.update(4.05, 5.0, 4)       # charger plugged in
    assert m['usb'] and m['charging']


def test_battery_full_and_low():
    b = ci.Battery(shutdown_v=3.35)
    for t in range(0, 200, 2):
        m, _ = b.update(4.19, 5.0, t)
    assert m['full'] and m['bat'] == 100 and not m['charging']
    b = ci.Battery(shutdown_v=3.35)
    fired = [b.update(3.30, 0.0, t)[1] for t in range(0, 40, 2)]
    assert fired.count(True) == 1


def test_daemon_rebroadcasts_injections_and_sends_sys():
    async def run():
        d = ci.Daemon(ci.load_config(None), mock=True)
        path = os.path.join(tempfile.mkdtemp(), 'in.sock')
        task = asyncio.create_task(d.run(path))
        for _ in range(50):
            if os.path.exists(path):
                break
            await asyncio.sleep(0.02)
        r1, w1 = await asyncio.open_unix_connection(path)
        r2, w2 = await asyncio.open_unix_connection(path)
        first = json.loads(await r1.readline())
        assert first['e'] == 'sys'
        await r2.readline()
        w2.write(b'{"inject":"down","b":"OK"}\n{"inject":"char","c":"xy"}\n{"inject":"down","b":"NOPE"}\n')
        await w2.drain()
        got = []
        while len(got) < 2:
            m = json.loads(await asyncio.wait_for(r1.readline(), 2))
            if m['e'] != 'sys':
                got.append(m)
        assert got == [{'e': 'down', 'b': 'OK'}, {'e': 'char', 'c': 'x'}]
        task.cancel()
    asyncio.run(run())
