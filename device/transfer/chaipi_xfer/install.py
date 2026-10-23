"""Checks and installs files that arrive by Transfer, USB drive mode or the SD card.

  engine   one ARM64 Linux program, or an archive with one (plus its network files). It must answer "uci".
  app      main.py, or a .zip with main.py and app.toml. It must be valid Python.
  puzzles  Lichess puzzle CSV, or FEN/EPD lines. ChAIpi's puzzle mode plays mates in one, so only those are kept.
  games    PGN. Lands in inbox/games; the UI adds the games to History.
  backup   a backup made by the transfer page (settings, games, apps, puzzles).

Command line (used by chaipi-media and the engine catalog):
  python3 -m chaipi_xfer.install engine FILE --data /data/chaipi [--id ID]
  python3 -m chaipi_xfer.install inbox DIR --data /data/chaipi     (DIR has engines/ apps/ puzzles/ games/)
Prints one JSON line: {"ok": true, "msg": "...", "items": [...]}.
"""
import argparse
import csv
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile

try:
    import tomllib
except ImportError:
    tomllib = None

MAX_UNPACKED = 600 * 1024 * 1024
ELF_MACHINES = {0xB7: 'ARM64', 0x3E: 'x86-64 PCs', 0x28: '32-bit ARM', 0x03: 'x86 PCs', 0xF3: 'RISC-V'}


class Rejected(Exception):
    """A file that can't be installed; the message is shown on the phone and the device."""


def slug(s, fallback='item'):
    s = re.sub(r'[^a-z0-9]+', '-', str(s).lower()).strip('-')
    return s[:32] or fallback


def pretty(name):
    base = re.sub(r'\.(tar\.gz|tar\.xz|tgz|tar|zip|py|csv|pgn|epd|txt)$', '', os.path.basename(name), flags=re.I)
    base = re.sub(r'[-_.]+', ' ', base)
    base = re.sub(r'\b(arm64|aarch64|armv8|linux|android|bmi2|avx2|x86|x86 64|v?\d+(\.\d+)*)\b', ' ', base, flags=re.I)
    return re.sub(r'\s+', ' ', base).strip().title() or 'Upload'


def elf_machine(path):
    try:
        with open(path, 'rb') as f:
            head = f.read(20)
    except OSError:
        return None
    if len(head) < 20 or head[:4] != b'\x7fELF':
        return None
    return int.from_bytes(head[18:20], 'little' if head[5] == 1 else 'big')


def safe_extract(archive, dest):
    """Unpacks zip/tar without letting paths escape dest, and with a size cap."""
    total = 0
    dest = os.path.realpath(dest)

    def check(name, size):
        nonlocal total
        total += size
        if total > MAX_UNPACKED:
            raise Rejected('Archive is too big when unpacked')
        target = os.path.realpath(os.path.join(dest, name))
        if not (target == dest or target.startswith(dest + os.sep)):
            raise Rejected('Archive has unsafe paths')
        return target

    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as z:
            for info in z.infolist():
                target = check(info.filename, info.file_size)
                if info.is_dir():
                    os.makedirs(target, exist_ok=True)
                    continue
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with z.open(info) as src, open(target, 'wb') as out:
                    shutil.copyfileobj(src, out)
                mode = (info.external_attr >> 16) & 0o777
                if mode & 0o111:
                    os.chmod(target, 0o755)
        return True
    try:
        tf = tarfile.open(archive)
    except tarfile.TarError:
        return False
    with tf:
        for m in tf.getmembers():
            if m.issym() or m.islnk() or m.isdev():
                continue
            target = check(m.name, m.size)
            if m.isdir():
                os.makedirs(target, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            src = tf.extractfile(m)
            if src is None:
                continue
            with src, open(target, 'wb') as out:
                shutil.copyfileobj(src, out)
            if m.mode & 0o111:
                os.chmod(target, 0o755)
    return True


def probe_uci(exe, cwd, timeout=12):
    """Starts the engine, sends uci, and returns (name, author) if it answers uciok."""
    try:
        os.chmod(exe, os.stat(exe).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        p = subprocess.run([exe], input='uci\nquit\n', capture_output=True, text=True, timeout=timeout, cwd=cwd)
    except subprocess.TimeoutExpired:
        raise Rejected("The engine didn't answer in time")
    except OSError as e:
        raise Rejected("The engine wouldn't start (%s)" % e.strerror)
    out = p.stdout.splitlines()
    if 'uciok' not in [l.strip() for l in out]:
        raise Rejected("This program doesn't speak UCI")
    name = next((l[8:].strip() for l in out if l.startswith('id name ')), None)
    author = next((l[10:].strip() for l in out if l.startswith('id author ')), None)
    return name, author


def install_engine(src, data, want_id=None, display_name=None):
    work = tempfile.mkdtemp(prefix='engine-', dir=os.path.join(data, 'tmp'))
    try:
        unpack = os.path.join(work, 'x')
        os.makedirs(unpack)
        if not safe_extract(src, unpack):
            shutil.copy(src, os.path.join(unpack, os.path.basename(display_name or src)))
        elves, wrong = [], set()
        for root, _, files in os.walk(unpack):
            for f in files:
                p = os.path.join(root, f)
                m = elf_machine(p)
                if m == 0xB7:
                    elves.append(p)
                elif m is not None:
                    wrong.add(ELF_MACHINES.get(m, 'another computer'))
        if not elves:
            if wrong:
                raise Rejected('Built for %s, not the Pi. Look for a Linux ARM64 (aarch64) build' % ', '.join(sorted(wrong)))
            raise Rejected("No Linux ARM64 program in this file")
        elves.sort(key=lambda p: (not re.search(r'stockfish|engine|chess|lc0|berserk|ethereal|koivisto|rubi|weiss|arasan|fruit|fairy', os.path.basename(p), re.I), len(p)))
        exe = elves[0]
        name, author = probe_uci(exe, os.path.dirname(exe))
        name = name or pretty(display_name or src)
        eid = slug(want_id or name, 'engine')
        root = os.path.dirname(exe)
        dest = os.path.join(data, 'engines', eid)
        if os.path.exists(dest):
            shutil.rmtree(dest)
        shutil.copytree(root, dest)
        has_net = any(f.lower().endswith(('.nnue', '.pb', '.pb.gz', '.bin')) for f in os.listdir(dest))
        meta = {'id': eid, 'name': name[:40], 'short': name.split()[0][:12], 'exe': os.path.basename(exe), 'args': [],
                'by': (author or 'Uploaded')[:40], 'tier': 'Custom', 'type': 'NNUE' if has_net else 'UCI',
                'desc': 'Added %s. Plays through the same ChAIpi interface.' % time.strftime('%d %b %Y')}
        with open(os.path.join(dest, 'engine.json'), 'w') as f:
            json.dump(meta, f, indent=1)
        return {'kind': 'engine', 'id': eid, 'name': meta['name']}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def install_app(src, data, display_name=None):
    work = tempfile.mkdtemp(prefix='app-', dir=os.path.join(data, 'tmp'))
    try:
        unpack = os.path.join(work, 'x')
        os.makedirs(unpack)
        base = os.path.basename(display_name or src)
        if not safe_extract(src, unpack):
            if not base.lower().endswith('.py'):
                raise Rejected('Send main.py, or a .zip with main.py and app.toml')
            shutil.copy(src, os.path.join(unpack, 'main.py'))
        mains = [os.path.join(r, 'main.py') for r, _, fs in os.walk(unpack) if 'main.py' in fs]
        if not mains:
            raise Rejected('No main.py in this file')
        root = os.path.dirname(sorted(mains, key=len)[0])
        with open(os.path.join(root, 'main.py'), encoding='utf-8', errors='replace') as f:
            code = f.read()
        try:
            compile(code, 'main.py', 'exec')
        except SyntaxError as e:
            raise Rejected('main.py has a syntax error on line %s' % e.lineno)
        meta = {}
        tpath = os.path.join(root, 'app.toml')
        if os.path.exists(tpath) and tomllib:
            try:
                with open(tpath, 'rb') as f:
                    meta = tomllib.load(f)
            except Exception:
                raise Rejected("app.toml can't be read")
        name = str(meta.get('name') or (os.path.basename(root) if root != unpack else pretty(base)))[:24]
        aid = slug(name, 'app')
        if not os.path.exists(tpath):
            with open(tpath, 'w') as f:
                f.write('name = %s\nram = 40\n' % json.dumps(name))
        dest = os.path.join(data, 'apps', aid)
        if os.path.exists(dest):
            shutil.rmtree(dest)
        shutil.copytree(root, dest)
        return {'kind': 'app', 'id': aid, 'name': name}
    finally:
        shutil.rmtree(work, ignore_errors=True)


FEN_RE = re.compile(r'^([pnbrqkPNBRQK1-8]+/){7}[pnbrqkPNBRQK1-8]+ [wb] (-|[KQkq]+) (-|[a-h][36])( \d+ \d+)?')


def puzzles_from_text(text, chess=None):
    """Returns [{id, name, rating, fen}] for mate-in-one candidates (the UI double-checks each)."""
    out = []
    head = text.lstrip()[:200]
    if head.startswith('PuzzleId') or head.count(',') >= 4:
        for row in csv.DictReader(io.StringIO(text)):
            fen, moves = row.get('FEN', ''), (row.get('Moves') or '').split()
            themes = row.get('Themes') or ''
            if not fen or len(moves) != 2 or 'mateIn1' not in themes or chess is None:
                continue
            try:
                b = chess.Board(fen)
                b.push_uci(moves[0])
            except ValueError:
                continue
            out.append({'id': 'li-' + row.get('PuzzleId', str(len(out))), 'name': 'Lichess ' + row.get('PuzzleId', ''),
                        'rating': int(row.get('Rating') or 1000), 'fen': b.fen()})
            if len(out) >= 5000:
                break
        return out
    for i, line in enumerate(text.splitlines()):
        m = FEN_RE.match(line.strip())
        if not m:
            continue
        parts = line.strip().split()
        fen = ' '.join(parts[:6]) if len(parts) >= 6 and parts[4].isdigit() else ' '.join(parts[:4]) + ' 0 1'
        out.append({'id': 'p%d' % i, 'name': 'Puzzle %d' % (len(out) + 1), 'rating': 1000, 'fen': fen})
        if len(out) >= 5000:
            break
    return out


def install_puzzles(src, data, display_name=None):
    try:
        import chess  # python3-chess, optional
    except ImportError:
        import glob
        # install.sh puts python-chess in ChAIpi's venv when the OS has no python3-chess package
        for sp in glob.glob('/opt/chaipi/venv/lib/python3*/site-packages'):
            if sp not in sys.path:
                sys.path.append(sp)
        try:
            import chess
        except ImportError:
            chess = None
    with open(src, encoding='utf-8', errors='replace') as f:
        text = f.read(50 * 1024 * 1024)
    puzzles = puzzles_from_text(text, chess)
    if not puzzles:
        raise Rejected('No mate-in-one puzzles found (Lichess CSV or FEN lines)')
    name = pretty(display_name or src)[:24]
    pid = slug(name, 'pack')
    for p in puzzles:
        p['id'] = pid + ':' + p['id']
    dest = os.path.join(data, 'puzzles', pid + '.json')
    with open(dest + '.tmp', 'w') as f:
        json.dump({'name': name, 'puzzles': puzzles}, f)
    os.replace(dest + '.tmp', dest)
    return {'kind': 'puzzles', 'id': pid, 'name': name, 'count': len(puzzles)}


def install_games(src, data, display_name=None):
    with open(src, encoding='utf-8', errors='replace') as f:
        text = f.read(20 * 1024 * 1024)
    n = len(re.findall(r'^\s*\[Event\s', text, re.M)) or (1 if re.search(r'\b1\.\s*\S', text) else 0)
    if not n:
        raise Rejected('No PGN games in this file')
    inbox = os.path.join(data, 'inbox', 'games')
    os.makedirs(inbox, exist_ok=True)
    dest = os.path.join(inbox, '%d-%s.pgn' % (time.time() * 1000, slug(pretty(display_name or src), 'games')))
    shutil.copy(src, dest)
    return {'kind': 'games', 'id': os.path.basename(dest), 'name': '%d game%s' % (n, '' if n == 1 else 's'), 'path': dest, 'count': n}


BACKUP_PARTS = ('state.json', 'games', 'apps', 'puzzles')


def make_backup(data):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w:gz') as tf:
        for part in BACKUP_PARTS:
            p = os.path.join(data, part)
            if os.path.exists(p):
                tf.add(p, arcname=part)
    return buf.getvalue()


def restore_backup(src, data):
    work = tempfile.mkdtemp(prefix='restore-', dir=os.path.join(data, 'tmp'))
    try:
        if not safe_extract(src, work):
            raise Rejected('Not a ChAIpi backup')
        state = os.path.join(work, 'state.json')
        if not os.path.exists(state):
            raise Rejected('Not a ChAIpi backup (no state.json)')
        try:
            with open(state) as f:
                json.load(f)
        except ValueError:
            raise Rejected('The backup is damaged')
        for part in BACKUP_PARTS:
            s, d = os.path.join(work, part), os.path.join(data, part)
            if not os.path.exists(s):
                continue
            if os.path.isdir(s):
                os.makedirs(d, exist_ok=True)
                for name in os.listdir(s):
                    t = os.path.join(d, name)
                    if os.path.isdir(t):
                        shutil.rmtree(t)
                    (shutil.copytree if os.path.isdir(os.path.join(s, name)) else shutil.copy2)(os.path.join(s, name), t)
            else:
                shutil.copy2(s, d + '.restore')
                os.replace(d + '.restore', d)
        return {'kind': 'backup', 'id': 'backup', 'name': 'Backup'}
    finally:
        shutil.rmtree(work, ignore_errors=True)


INSTALLERS = {'engine': install_engine, 'app': install_app, 'puzzles': install_puzzles, 'games': install_games}


def install(kind, src, data, display_name=None, want_id=None):
    os.makedirs(os.path.join(data, 'tmp'), exist_ok=True)
    for d in ('engines', 'apps', 'puzzles', 'games'):
        os.makedirs(os.path.join(data, d), exist_ok=True)
    if kind == 'backup':
        return restore_backup(src, data)
    if kind == 'engine':
        return install_engine(src, data, want_id, display_name)
    if kind not in INSTALLERS:
        raise Rejected('Unknown kind of file')
    return INSTALLERS[kind](src, data, display_name)


def install_inbox(folder, data):
    """For USB drive mode and the SD card: every file under engines/, apps/, puzzles/ and games/."""
    items, problems = [], []
    for sub, kind in (('engines', 'engine'), ('apps', 'app'), ('puzzles', 'puzzles'), ('games', 'games')):
        d = os.path.join(folder, sub)
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            p = os.path.join(d, name)
            if name.startswith('.'):
                continue
            if os.path.isdir(p):
                if kind != 'app':
                    continue
                z = shutil.make_archive(os.path.join(data, 'tmp', 'app-' + slug(name)), 'zip', p)
                p = z
            try:
                items.append(install(kind, p, data, display_name=name))
            except Rejected as e:
                problems.append('%s: %s' % (name, e))
    return items, problems


def summary(items, problems):
    counts = {}
    for it in items:
        counts[it['kind']] = counts.get(it['kind'], 0) + (it.get('count', 1) if it['kind'] == 'games' else 1)
    words = {'engine': ('engine', 'engines'), 'app': ('app', 'apps'), 'puzzles': ('puzzle pack', 'puzzle packs'), 'games': ('game', 'games')}
    parts = ['%d %s' % (n, words[k][0] if n == 1 else words[k][1]) for k, n in counts.items()]
    msg = ('Imported ' + ', '.join(parts)) if parts else 'Nothing new to import'
    if problems:
        msg += ' · %d skipped' % len(problems)
    return msg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('kind', choices=['engine', 'app', 'puzzles', 'games', 'backup', 'inbox'])
    ap.add_argument('path')
    ap.add_argument('--data', default='/data/chaipi')
    ap.add_argument('--id')
    ap.add_argument('--name')
    a = ap.parse_args()
    try:
        if a.kind == 'inbox':
            items, problems = install_inbox(a.path, a.data)
            print(json.dumps({'ok': True, 'msg': summary(items, problems), 'items': items, 'problems': problems}))
        else:
            it = install(a.kind, a.path, a.data, a.name or os.path.basename(a.path), a.id)
            print(json.dumps({'ok': True, 'msg': it['name'] + ' installed', 'items': [it]}))
    except Rejected as e:
        print(json.dumps({'ok': False, 'msg': str(e)}))
        print(str(e), file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    main()
