"""Tests for the transfer server and installer (device/transfer). The server runs with --no-network."""
import io
import json
import os
import socket
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
import zipfile

import pytest

ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(ROOT, 'device', 'transfer'))
from chaipi_xfer import install as inst  # noqa: E402


def fake_elf(path, machine):
    head = bytearray(64)
    head[:4] = b'\x7fELF'
    head[4], head[5] = 2, 1
    head[18:20] = machine.to_bytes(2, 'little')
    with open(path, 'wb') as f:
        f.write(head)


@pytest.fixture
def data(tmp_path):
    d = tmp_path / 'data'
    for sub in ('games', 'tmp', 'engines', 'apps', 'puzzles'):
        (d / sub).mkdir(parents=True)
    return str(d)


def test_engine_for_pc_is_rejected_with_a_helpful_reason(data, tmp_path):
    p = tmp_path / 'stockfish-ubuntu-x86-64-avx2'
    fake_elf(p, 0x3E)
    with pytest.raises(inst.Rejected, match='x86-64 PCs'):
        inst.install('engine', str(p), data)


def test_engine_zip_without_program(data, tmp_path):
    z = tmp_path / 'net.zip'
    with zipfile.ZipFile(z, 'w') as zf:
        zf.writestr('nn-123.nnue', b'net')
    with pytest.raises(inst.Rejected, match='No Linux ARM64 program'):
        inst.install('engine', str(z), data)


def test_unsafe_archive_paths_are_refused(data, tmp_path):
    t = tmp_path / 'evil.tar.gz'
    with tarfile.open(t, 'w:gz') as tf:
        info = tarfile.TarInfo('../../escape.txt')
        info.size = 3
        tf.addfile(info, io.BytesIO(b'bad'))
    with pytest.raises(inst.Rejected, match='unsafe'):
        inst.install('engine', str(t), data)
    assert not os.path.exists(os.path.join(os.path.dirname(data), 'escape.txt'))


def test_arm64_engine_is_found_and_probed(data, tmp_path, monkeypatch):
    z = tmp_path / 'berserk-13-linux-arm64.zip'
    with zipfile.ZipFile(z, 'w') as zf:
        buf = tmp_path / 'b'
        fake_elf(buf, 0xB7)
        zf.write(buf, 'berserk-13/berserk')
        zf.writestr('berserk-13/README.md', 'hi')
    monkeypatch.setattr(inst, 'probe_uci', lambda exe, cwd: ('Berserk 13', 'Jay Honnold'))
    item = inst.install('engine', str(z), data)
    assert item == {'kind': 'engine', 'id': 'berserk-13', 'name': 'Berserk 13'}
    meta = json.load(open(os.path.join(data, 'engines', 'berserk-13', 'engine.json')))
    assert meta['exe'] == 'berserk' and meta['by'] == 'Jay Honnold'


def test_app_zip_with_folder_and_toml(data, tmp_path):
    z = tmp_path / 'snake.zip'
    with zipfile.ZipFile(z, 'w') as zf:
        zf.writestr('snake/main.py', 'from chaipi import app\n')
        zf.writestr('snake/app.toml', 'name = "Snake 2"\nram = 30\n')
    assert inst.install('app', str(z), data)['name'] == 'Snake 2'
    assert os.path.exists(os.path.join(data, 'apps', 'snake-2', 'main.py'))


def test_puzzle_lines_and_lichess_csv(data, tmp_path):
    p = tmp_path / 'p.txt'
    p.write_text('6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1\nnonsense\n')
    assert inst.install('puzzles', str(p), data)['count'] == 1
    chess = pytest.importorskip('chess')
    csvp = tmp_path / 'lichess_db_puzzle.csv'
    csvp.write_text('PuzzleId,FEN,Moves,Rating,RatingDeviation,Popularity,NbPlays,Themes,GameUrl,OpeningTags\n'
                    '00x1,6k1/5ppp/8/8/8/8/5PPP/3R2K1 b - - 0 1,g8h8 d1d8,800,80,90,100,mate mateIn1 short,u,\n'
                    '00x2,6k1/5ppp/8/8/8/8/5PPP/3R2K1 b - - 0 1,g8h8 d1d8 h7h6 d8e8,1500,80,90,100,mateIn2,u,\n')
    items = inst.puzzles_from_text(csvp.read_text(), chess)
    assert len(items) == 1 and items[0]['fen'].startswith('6k1/5ppp') is False and ' w ' in items[0]['fen']


def test_backup_round_trip(data):
    with open(os.path.join(data, 'state.json'), 'w') as f:
        json.dump({'chaipi.settings': '{"theme":"light"}'}, f)
    open(os.path.join(data, 'games', 'a.txt'), 'w').write('[Event "x"]\n')
    blob = inst.make_backup(data)
    os.remove(os.path.join(data, 'games', 'a.txt'))
    p = os.path.join(data, 'tmp', 'b.tgz')
    open(p, 'wb').write(blob)
    inst.install('backup', p, data)
    assert os.path.exists(os.path.join(data, 'games', 'a.txt'))


def free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture
def server(data):
    port = free_port()
    env = dict(os.environ, PYTHONPATH=os.path.join(ROOT, 'device', 'transfer'))
    p = subprocess.Popen([sys.executable, '-m', 'chaipi_xfer.server', '--mode', 'hotspot', '--no-network', '--data', data,
                          '--port', str(port), '--portal', os.path.join(ROOT, 'device', 'transfer', 'portal'), '--fonts', data,
                          '--builtin-engines', data, '--pin', '2468', '--config', '/nonexistent'],
                         env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    ready = json.loads(p.stdout.readline())
    assert ready['ev'] == 'ready'
    yield 'http://127.0.0.1:%d' % port, p
    p.terminate()
    p.wait(5)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def req(url, data=None, cookie=None, method=None, headers=None):
    h = dict(headers or {})
    if cookie:
        h['Cookie'] = cookie
    r = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        resp = OPENER.open(r, timeout=5)
        return resp.status, resp.read(), resp.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e.headers


def test_server_pin_lockout_and_events(server):
    base, proc = server
    assert req(base + '/api/state')[0] == 401
    for i in range(4):
        assert req(base + '/api/login', b'{"pin":"0000"}', method='POST')[0] == 403
    code, body, _ = req(base + '/api/login', b'{"pin":"0000"}', method='POST')
    assert code == 429 and json.loads(body)['locked'] > 0
    assert req(base + '/api/login', b'{"pin":"2468"}', method='POST')[0] == 429   # locked even with the right PIN
    evs = [json.loads(proc.stdout.readline()) for _ in range(5)]
    assert [e['ev'] for e in evs] == ['pinfail'] * 5


def test_server_login_upload_and_new_pin(server):
    base, proc = server
    code, _, h = req(base + '/api/login', b'{"pin":"2468"}', method='POST')
    assert code == 200
    cookie = h['Set-Cookie'].split(';')[0]
    assert json.loads(proc.stdout.readline())['ev'] == 'login'
    code, body, _ = req(base + '/api/upload?kind=app&name=hello.py', b'print("hi")\n', cookie, 'POST')
    assert code == 200 and json.loads(body)['item']['id'] == 'hello'
    assert json.loads(proc.stdout.readline())['ev'] == 'installed'
    state = json.loads(req(base + '/api/state', cookie=cookie)[1])
    assert [a['id'] for a in state['apps']] == ['hello']
    proc.stdin.write('{"cmd":"pin","pin":"1357"}\n')
    proc.stdin.flush()
    time.sleep(0.3)
    assert req(base + '/api/state', cookie=cookie)[0] == 401      # a new PIN signs everyone out
    assert req(base + '/api/login', b'{"pin":"1357"}', method='POST')[0] == 200


def test_server_captive_probe_redirects(server):
    base, _ = server
    code, _, h = req(base + '/generate_204')
    assert code == 302 and h['Location'].startswith('http://127.0.0.1')
    assert req(base + '/', headers={'Host': 'captive.apple.com'})[0] == 302
    assert req(base + '/')[0] == 200


def test_backup_start_opens_device_tab(data):
    port = free_port()
    env = dict(os.environ, PYTHONPATH=os.path.join(ROOT, 'device', 'transfer'))
    p = subprocess.Popen([sys.executable, '-m', 'chaipi_xfer.server', '--mode', 'hotspot', '--no-network', '--data', data,
                          '--port', str(port), '--portal', os.path.join(ROOT, 'device', 'transfer', 'portal'), '--fonts', data,
                          '--builtin-engines', data, '--pin', '1111', '--config', '/nonexistent', '--start-tab', 'device'],
                         env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert json.loads(p.stdout.readline())['ev'] == 'ready'
        hello = json.loads(req('http://127.0.0.1:%d/api/hello' % port)[1])
        assert hello['tab'] == 'device' and hello['pin'] is True
    finally:
        p.terminate()
        p.wait(5)
