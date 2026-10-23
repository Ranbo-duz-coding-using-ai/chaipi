"""Draws docs/wiring/header-map.svg and docs/wiring/power.svg for ChAIpi revision 3."""
import os, sys
from xml.sax.saxutils import escape as esc

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)

C = {'5v': '#d7263d', '3v3': '#ee7d1a', 'gnd': '#222222', 'spi': '#2f6fe0', 'i2c': '#13a06f', 'i2s': '#8a4fe0',
     'btn': '#c79400', 'pwm': '#d6337a', 'uart': '#6b7785', 'free': '#c9ced6', 'sd': '#5aa3f0'}
GROUP_NAME = {'5v': '5 V', '3v3': '3.3 V', 'gnd': 'Ground', 'spi': 'Screen (SPI)', 'sd': 'Screen’s SD slot (optional)',
              'i2c': 'I2C: ADS1115 + DS3231', 'i2s': 'Sound (I2S amp, optional)', 'btn': 'Buttons (other leg to GND)',
              'pwm': 'Backlight / vibration', 'uart': 'Serial console (debug)', 'free': 'Not used'}

# physical pin -> (label, group, destination)
PINS = {
    1: ('3V3', '3v3', 'ADS1115 VDD, DS3231 VCC'), 2: ('5V', '5v', 'from MT3608 OUT+'),
    3: ('GPIO2 SDA', 'i2c', 'ADS1115 + DS3231 SDA'), 4: ('5V', '5v', 'vibration VCC, amp VIN'),
    5: ('GPIO3 SCL', 'i2c', 'ADS1115 + DS3231 SCL'), 6: ('GND', 'gnd', 'MT3608 OUT−'),
    7: ('GPIO4', 'free', 'spare'), 8: ('GPIO14 TX', 'uart', 'serial console'),
    9: ('GND', 'gnd', 'buttons'), 10: ('GPIO15 RX', 'uart', 'serial console'),
    11: ('GPIO17', 'btn', 'Fn'), 12: ('GPIO18', 'i2s', 'amp BCLK'),
    13: ('GPIO27', 'btn', 'joystick SW'), 14: ('GND', 'gnd', 'buttons'),
    15: ('GPIO22', 'free', 'spare'), 16: ('GPIO23', 'btn', 'Menu'),
    17: ('3V3', '3v3', 'TFT VCC, joystick +5V pin'), 18: ('GPIO24', 'spi', 'TFT RESET'),
    19: ('GPIO10 MOSI', 'spi', 'TFT SDI (MOSI)'), 20: ('GND', 'gnd', 'TFT GND'),
    21: ('GPIO9 MISO', 'sd', 'TFT SD_MISO'), 22: ('GPIO25', 'spi', 'TFT DC'),
    23: ('GPIO11 SCLK', 'spi', 'TFT SCK'), 24: ('GPIO8 CE0', 'spi', 'TFT CS'),
    25: ('GND', 'gnd', 'ADS1115 + DS3231 GND'), 26: ('GPIO7 CE1', 'sd', 'TFT SD_CS'),
    27: ('ID_SD', 'free', 'leave empty'), 28: ('ID_SC', 'free', 'leave empty'),
    29: ('GPIO5', 'btn', 'Confirm'), 30: ('GND', 'gnd', 'buttons'),
    31: ('GPIO6', 'btn', 'Backspace'), 32: ('GPIO12', 'pwm', 'vibration IN'),
    33: ('GPIO13', 'pwm', 'TFT LED (backlight)'), 34: ('GND', 'gnd', 'joystick GND'),
    35: ('GPIO19', 'i2s', 'amp LRC'), 36: ('GPIO16', 'btn', 'Esc'),
    37: ('GPIO26', 'btn', 'Tab'), 38: ('GPIO20', 'free', 'leave empty (I2S)'),
    39: ('GND', 'gnd', 'amp GND, vibration GND'), 40: ('GPIO21', 'i2s', 'amp DIN'),
}

FONT = "font-family:'Atkinson Hyperlegible','Segoe UI',Helvetica,Arial,sans-serif"
MONO = "font-family:'JetBrains Mono',Menlo,Consolas,monospace"


def header_map():
    W, H = 1240, 1050
    cx, top, pitch = 700, 150, 36       # header centre x, first row y, row pitch
    xl, xr = cx - 20, cx + 20           # odd column (left), even column (right)
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" style="{FONT}">',
         f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
         '<text x="40" y="46" style="font-size:27px;font-weight:700" fill="#1b1b1b">ChAIpi wiring: the Pi Zero 2 W header</text>',
         '<text x="40" y="74" style="font-size:15px" fill="#555">Hold the Pi as in the sketch: microSD card at the top, header on the right. Pin 1 (square pad) is top left.</text>']
    # orientation sketch
    ox, oy, ow, oh = 130, 140, 120, 260
    s.append(f'<rect x="{ox}" y="{oy}" width="{ow}" height="{oh}" rx="14" fill="#1f7a4d" stroke="#145234" stroke-width="3"/>')
    s.append(f'<rect x="{ox+38}" y="{oy-10}" width="44" height="26" rx="4" fill="#c9c9c9" stroke="#888"/>')
    s.append(f'<text x="{ox+60}" y="{oy-18}" text-anchor="middle" style="font-size:12px;font-weight:700" fill="#555">microSD</text>')
    s.append(f'<rect x="{ox+ow-26}" y="{oy+22}" width="18" height="{oh-44}" rx="3" fill="#111"/>')
    s.append(f'<rect x="{ox+ow-25}" y="{oy+24}" width="8" height="8" fill="{C["3v3"]}"/>')
    s.append(f'<text x="{ox+ow-32}" y="{oy+34}" text-anchor="end" style="font-size:12px;font-weight:700" fill="#fff">pin 1</text>')
    for i, lbl in enumerate(('mini-HDMI', 'USB', 'PWR')):
        yy = oy + 60 + i * 70
        s.append(f'<rect x="{ox-8}" y="{yy}" width="22" height="40" rx="4" fill="#c9c9c9" stroke="#888"/>')
        s.append(f'<text x="{ox-14}" y="{yy+25}" text-anchor="end" style="font-size:12px;font-weight:700" fill="#555">{lbl}</text>')
    s.append(f'<text x="{ox+ow/2}" y="{oy+oh+28}" text-anchor="middle" style="font-size:13px" fill="#555">top view</text>')
    s.append(f'<text x="{ox+ow/2}" y="{oy+oh+48}" text-anchor="middle" style="font-size:13px" fill="#555">(components up)</text>')
    s.append(f'<path d="M{ox+ow+16} {oy+40} C {ox+ow+90} {oy+40}, {cx-330} {top-10}, {cx-300} {top-10}" fill="none" stroke="#bbb" stroke-width="2" stroke-dasharray="5 5"/>')
    # header strip
    s.append(f'<rect x="{cx-46}" y="{top-26}" width="92" height="{pitch*19+52}" rx="8" fill="#141414"/>')
    s.append(f'<text x="{xl+6}" y="{top-36}" text-anchor="end" style="font-size:12px;font-weight:700" fill="#777">inner row</text>')
    s.append(f'<text x="{xr-6}" y="{top-36}" text-anchor="start" style="font-size:12px;font-weight:700" fill="#777">board edge</text>')
    for r in range(20):
        y = top + r * pitch
        for pin, x, side in ((2 * r + 1, xl, 'l'), (2 * r + 2, xr, 'r')):
            lbl, g, dest = PINS[pin]
            dim = g == 'free'
            if pin == 1:
                s.append(f'<rect x="{x-13}" y="{y-13}" width="26" height="26" rx="3" fill="{C[g]}" stroke="#fff" stroke-width="2"/>')
            else:
                s.append(f'<circle cx="{x}" cy="{y}" r="13" fill="{C[g]}" stroke="#fff" stroke-width="2"/>')
            s.append(f'<text x="{x}" y="{y+4.5}" text-anchor="middle" style="{MONO};font-size:12px;font-weight:700" fill="{"#222" if g in ("free", "btn", "3v3", "sd") else "#fff"}">{pin}</text>')
            tx = cx - 62 if side == 'l' else cx + 62
            anchor = 'end' if side == 'l' else 'start'
            name = f'<tspan style="font-weight:700" fill="{"#9aa0a8" if dim else C[g]}">{esc(lbl)}</tspan>'
            d = f'<tspan fill="{"#9aa0a8" if dim else "#1b1b1b"}">{esc(dest)}</tspan>'
            body = (d + '  ' + name) if side == 'l' else (name + '  ' + d)
            s.append(f'<text x="{tx}" y="{y+5}" text-anchor="{anchor}" style="font-size:15px">{body}</text>')
    # legend
    lx, ly = 60, top + pitch * 20 + 40
    s.append(f'<text x="{lx}" y="{ly}" style="font-size:15px;font-weight:700" fill="#1b1b1b">Colours (use matching wire colours if you can)</text>')
    groups = ['5v', '3v3', 'gnd', 'spi', 'i2c', 'btn', 'pwm', 'i2s', 'sd', 'uart', 'free']
    for i, g in enumerate(groups):
        gx = lx + (i % 4) * 290
        gy = ly + 22 + (i // 4) * 28
        s.append(f'<circle cx="{gx+8}" cy="{gy+6}" r="8" fill="{C[g]}"/><text x="{gx+24}" y="{gy+11}" style="font-size:14px" fill="#333">{esc(GROUP_NAME[g])}</text>')
    s.append(f'<text x="{W-40}" y="{H-18}" text-anchor="end" style="font-size:12px" fill="#888">docs/03-wiring.md \u00b7 same pins as config/chaipi.example.toml</text>')
    s.append('</svg>')
    return '\n'.join(s)


def power():
    W, H = 1240, 680
    yP, yN = 270, 350
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" style="{FONT}">',
         f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
         '<text x="40" y="44" style="font-size:27px;font-weight:700" fill="#1b1b1b">ChAIpi power: battery to Pi</text>',
         '<text x="40" y="72" style="font-size:15px" fill="#555">Red = positive, black = negative, dashed = thin sense wire. Keep the switch OFF while soldering. Set the MT3608 to 5.1 V before the Pi is connected.</text>']

    def box(x, y, w, h, title, sub, fill='#f4f1ec', stroke='#8a7f72'):
        s.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
        s.append(f'<text x="{x+w/2}" y="{y+27}" text-anchor="middle" style="font-size:16px;font-weight:700" fill="#1b1b1b">{esc(title)}</text>')
        for i, line in enumerate(sub):
            s.append(f'<text x="{x+w/2}" y="{y+50+i*19}" text-anchor="middle" style="font-size:13.5px" fill="#555">{esc(line)}</text>')

    def term(x, y, label, color, inside):
        """A terminal dot on a box edge, labelled inside the box so wires stay clear."""
        s.append(f'<circle cx="{x}" cy="{y}" r="6" fill="{color}" stroke="#fff" stroke-width="2"/>')
        if inside == 'r':
            s.append(f'<text x="{x+12}" y="{y+5}" style="{MONO};font-size:13px;font-weight:700" fill="{color}">{esc(label)}</text>')
        elif inside == 'l':
            s.append(f'<text x="{x-12}" y="{y+5}" text-anchor="end" style="{MONO};font-size:13px;font-weight:700" fill="{color}">{esc(label)}</text>')
        else:
            s.append(f'<text x="{x}" y="{y-12}" text-anchor="middle" style="{MONO};font-size:13px;font-weight:700" fill="{color}">{esc(label)}</text>')

    def wire(pts, color, width=4.5, dash=None, halo=False):
        d = 'M' + ' L'.join(f'{x} {y}' for x, y in pts)
        if halo:
            s.append(f'<path d="{d}" fill="none" stroke="#fff" stroke-width="{width+8}" stroke-linecap="butt"/>')
        extra = f' stroke-dasharray="{dash}"' if dash else ''
        s.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"{extra}/>')

    R, K = C['5v'], C['gnd']
    # battery (two cells in parallel, drawn as an inset)
    box(40, 200, 200, 230, 'Battery', ['2 \u00d7 2000 mAh in parallel', '(or one 6000 mAh)'])
    for i, cx_ in enumerate((80, 160)):
        s.append(f'<rect x="{cx_-24}" y="305" width="48" height="80" rx="6" fill="#fff" stroke="#8a7f72" stroke-width="1.5"/>')
        s.append(f'<text x="{cx_}" y="325" text-anchor="middle" style="font-size:13px;font-weight:700" fill="{R}">+</text>')
        s.append(f'<text x="{cx_}" y="377" text-anchor="middle" style="font-size:15px;font-weight:700" fill="{K}">\u2212</text>')
        s.append(f'<text x="{cx_}" y="352" text-anchor="middle" style="font-size:11px" fill="#777">{"AB"[i]}</text>')
    wire([(80, 305), (80, 295), (160, 295), (160, 305)], R, 2.5)
    wire([(80, 385), (80, 400), (160, 400), (160, 385)], K, 2.5)
    term(240, yP, '+', R, 'l'); term(240, yN, '\u2212', K, 'l')
    s.append('<text x="140" y="458" text-anchor="middle" style="font-size:13px;font-weight:700" fill="#b4232f">Charge or measure both cells to</text>')
    s.append('<text x="140" y="476" text-anchor="middle" style="font-size:13px;font-weight:700" fill="#b4232f">within 0.05 V before joining them</text>')
    # TP4056
    box(340, 200, 200, 210, 'TP4056', ['USB-C charger, 1 A'])
    term(340, yP, 'B+', R, 'r'); term(340, yN, 'B\u2212', K, 'r')
    term(540, yP, 'OUT+', R, 'l'); term(540, yN, 'OUT\u2212', K, 'l')
    term(400, 410, 'IN+', R, 't'); term(480, 410, 'IN\u2212', K, 't')
    wire([(246, yP), (334, yP)], R); wire([(246, yN), (334, yN)], K)
    # USB-C and charger sense
    box(340, 520, 200, 70, 'USB-C', ['charger cable'], fill='#eef3fb', stroke='#7d93b8')
    wire([(400, 520), (400, 416)], R); wire([(480, 520), (480, 416)], K)
    box(40, 520, 260, 110, 'Charger sense', ['IN+ \u2192 100 k \u2192 node \u2192 100 k \u2192 GND', 'node \u2192 ADS1115 A3', '(shows \u201ccharging\u201d)'], fill='#eefaf4', stroke='#13a06f')
    wire([(400, 470), (280, 470), (280, 520)], R, 2.5, '7 6')
    # switch
    box(620, 225, 130, 85, 'Rocker switch', ['ON / OFF'])
    wire([(546, yP), (620, yP)], R); wire([(750, yP), (854, yP)], R)
    wire([(546, yN), (854, yN)], K)
    # battery sense, above the chain
    box(640, 92, 300, 112, 'Battery sense', ['VIN+ \u2192 100 k \u2192 node \u2192 100 k \u2192 GND', 'node \u2192 ADS1115 A2', 'after the switch, so no drain when off'], fill='#eefaf4', stroke='#13a06f')
    wire([(800, yP), (800, 204)], R, 2.5, '7 6')
    # MT3608
    box(860, 200, 200, 210, 'MT3608 boost', ['set VOUT to 5.10 V'])
    term(860, yP, 'VIN+', R, 'r'); term(860, yN, 'VIN\u2212', K, 'r')
    term(1060, yP, 'VOUT+', R, 'l'); term(1060, yN, 'VOUT\u2212', K, 'l')
    # 5 V and GND buses with the loads between them
    wire([(1066, yP), (1180, yP), (1180, 460), (640, 460)], R, 5)
    wire([(1066, yN), (1210, yN), (1210, 630), (705, 630)], K, 5, halo=True)
    s.append('<text x="1168" y="452" text-anchor="end" style="font-size:13px;font-weight:700" fill="#d7263d">5 V bus</text>')
    s.append('<text x="1198" y="650" text-anchor="end" style="font-size:13px;font-weight:700" fill="#222">GND bus</text>')
    loads = [('Pi header', ['pin 2 = 5 V', 'pin 6 = GND']), ('Vibration', ['VCC, GND']), ('MAX98357A', ['VIN, GND', '(optional)']), ('Capacitor', ['470\u20131000 \u00b5F', 'stripe = GND'])]
    for i, (t, sub) in enumerate(loads):
        lx = 610 + i * 135
        box(lx, 490, 125, 110, t, sub, fill='#fbf1f2', stroke='#d7263d')
        wire([(lx + 30, 460), (lx + 30, 490)], R, 3.5)
        wire([(lx + 95, 630), (lx + 95, 600)], K, 3.5)
    s.append(f'<text x="{W-40}" y="{H-12}" text-anchor="end" style="font-size:12px" fill="#888">docs/03-wiring.md, steps 1 and 6</text>')
    s.append('</svg>')
    return '\n'.join(s)


open(os.path.join(OUT, 'header-map.svg'), 'w').write(header_map())
open(os.path.join(OUT, 'power.svg'), 'w').write(power())
print('wrote', OUT)
