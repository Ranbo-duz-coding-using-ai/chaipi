#!/usr/bin/env python3
"""Turns mockup/chaipi-os.html (the device OS) into a web page anyone can open: the ChAIpi emulator.

    python3 tools/build_emulator.py _site/index.html --fonts-dir fonts   # the website: fonts copied next to the page
    python3 tools/build_emulator.py chaipi-emulator.html --inline-fonts  # one file that works offline
    python3 tools/build_emulator.py page.html                            # fonts from Google Fonts, like the mockup

The mockup is kept as a fragment (no <!doctype>, <html> or <head>) because that is how it is published as a
claude.ai artifact and how device/ui/host.js reads it. This adds the document skeleton around it.
--inline-fonts and --fonts-dir swap the Google Fonts link for the device's own font files (device/fonts),
embedded as base64 or copied into a folder next to the page.
"""
import argparse
import base64
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'mockup' / 'chaipi-os.html'
FONTS = ROOT / 'device' / 'fonts'

# family, weight (a range lets one file cover the weights the page asks for), file
FACES = [
    ('Atkinson Hyperlegible', '400', 'AtkinsonHyperlegible-Regular.ttf'),
    ('Atkinson Hyperlegible', '700', 'AtkinsonHyperlegible-Bold.ttf'),
    ('JetBrains Mono', '400', 'JetBrainsMono-Regular.ttf'),
    ('JetBrains Mono', '600', 'JetBrainsMono-SemiBold.ttf'),
    ('Unbounded', '500 700', 'Unbounded-SemiBold.ttf'),
    ('Noto Sans Symbols 2', '400', 'NotoSansSymbols2-Regular.ttf'),
]

HEAD = '''<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="ChAIpi OS emulator: the software of a pocket chess computer that runs Stockfish 19 on a Raspberry Pi Zero 2 W.">
'''


def build(inline_fonts=False, fonts_dir=None):
    html = SRC.read_text(encoding='utf-8')
    if html.lstrip().lower().startswith('<!doctype'):
        sys.exit('mockup/chaipi-os.html already has a <!doctype>; nothing to wrap')
    html = re.sub(r'<meta (?:charset="utf-8"|name="claude:[^>]*)>\n?', '', html)
    if inline_fonts or fonts_dir:
        html, n = re.subn(r'<link rel="(?:preconnect|stylesheet)" href="https://fonts\.(?:googleapis|gstatic)\.com[^>]*>\n?', '', html)
        if n != 3:
            sys.exit(f'expected 3 Google Fonts <link> tags, found {n}: update build_emulator.py')
        faces = []
        for family, weight, name in FACES:
            if fonts_dir:
                url = f'{fonts_dir}/{name}'
            else:
                url = 'data:font/ttf;base64,' + base64.b64encode((FONTS / name).read_bytes()).decode('ascii')
            faces.append(f'@font-face{{font-family:"{family}";font-weight:{weight};font-style:normal;font-display:swap;'
                         f'src:url({url}) format("truetype")}}')
        html = html.replace('<style>', '<style>\n' + '\n'.join(faces) + '\n', 1)
    return HEAD + html + ('' if html.endswith('\n') else '\n') + '</html>\n'


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('out', type=Path)
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--inline-fonts', action='store_true', help='embed the fonts so the page works offline')
    g.add_argument('--fonts-dir', metavar='DIR', help='copy the fonts and their licences to DIR next to the page')
    a = ap.parse_args()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(build(a.inline_fonts, a.fonts_dir), encoding='utf-8')
    if a.fonts_dir:
        dest = a.out.parent / a.fonts_dir
        dest.mkdir(parents=True, exist_ok=True)
        for f in [name for _, _, name in FACES] + [f.name for f in FONTS.glob('OFL-*.txt')]:
            shutil.copy2(FONTS / f, dest / f)
    print(f'{a.out}  {a.out.stat().st_size / 1e6:.1f} MB')


if __name__ == '__main__':
    main()
