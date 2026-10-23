"""The transfer web server. The UI starts it on Activate and stops it on Esc (device/ui/lib/transfer.js).

  python3 -m chaipi_xfer.server --mode hotspot|home --data /data/chaipi --port 80 --portal DIR --fonts DIR [--pin 1234]

In hotspot mode it brings up NetworkManager's "chaipi-hotspot" connection first and takes it down on exit,
after which NetworkManager rejoins the home network by itself. Every web address answers with the page, so
phones show it as a sign-in page. Events for the device's screen go to stdout as JSON lines; the UI sends
{"cmd":"pin"} and {"cmd":"status"} on stdin. Use --no-network to try it on a computer.
"""
import argparse
import email.utils
import hmac
import http.server
import io
import json
import mimetypes
import os
import re
import secrets
import shutil
import signal
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import zipfile
from datetime import datetime

from . import install as inst

try:
    import tomllib
except ImportError:
    tomllib = None

PROBES = {'/generate_204', '/gen_204', '/hotspot-detect.html', '/library/test/success.html', '/ncsi.txt', '/connecttest.txt',
          '/redirect', '/canonical.html', '/success.txt', '/mobile/status.php', '/check_network_status.txt'}
FONT_RE = re.compile(r'^[A-Za-z0-9_\-\[\],.]+\.(ttf|otf|woff2?)$')


def emit(**ev):
    sys.stdout.write(json.dumps(ev) + '\n')
    sys.stdout.flush()


def nmcli(*args, timeout=30):
    return subprocess.run(['nmcli'] + list(args), capture_output=True, text=True, timeout=timeout)


class Network:
    def __init__(self, mode, conn, ip_hint, enabled):
        self.mode, self.conn, self.ip_hint, self.enabled = mode, conn, ip_hint, enabled
        self.ssid = self.psk = ''
        self.up = False

    def creds(self):
        try:
            with open('/etc/chaipi/hotspot.json') as f:
                j = json.load(f)
            return j.get('ssid', ''), j.get('psk', '')
        except (OSError, ValueError):
            r = nmcli('-s', '-g', '802-11-wireless.ssid,802-11-wireless-security.psk', 'connection', 'show', self.conn)
            lines = r.stdout.strip().split('\n')
            return (lines + ['', ''])[0], (lines + ['', ''])[1]

    def wlan_ip(self):
        r = nmcli('-g', 'IP4.ADDRESS', 'device', 'show', 'wlan0')
        m = re.search(r'(\d+\.\d+\.\d+\.\d+)', r.stdout)
        return m.group(1) if m else ''

    def start(self):
        if not self.enabled:
            return '127.0.0.1'
        if self.mode == 'home':
            ip = self.wlan_ip()
            if not ip:
                raise RuntimeError('ChAIpi is not on a Wi-Fi network')
            return ip
        self.ssid, self.psk = self.creds()
        r = nmcli('connection', 'up', self.conn, timeout=45)
        if r.returncode != 0:
            raise RuntimeError('Hotspot did not start: ' + (r.stderr.strip() or r.stdout.strip())[-120:])
        self.up = True
        for _ in range(30):
            ip = self.wlan_ip()
            if ip:
                return ip
            time.sleep(0.3)
        return self.ip_hint

    def stop(self):
        if self.up:
            nmcli('connection', 'down', self.conn, timeout=20)
            self.up = False


class State:
    def __init__(self, args):
        self.args = args
        self.data = args.data
        self.pin = args.pin
        self.sessions = {}
        self.fails = 0
        self.locked_until = 0
        self.lock = threading.Lock()
        self.status = {'bat': None, 'charging': False, 'free': None, 'version': 'ChAIpi OS'}
        self.ip = '127.0.0.1'
        self.net = None
        self.max_upload = args.max_upload_mb * 1024 * 1024

    # --- device data -------------------------------------------------------------------
    def store(self):
        try:
            with open(os.path.join(self.data, 'state.json')) as f:
                raw = json.load(f)
            return {k[7:]: json.loads(v) for k, v in raw.items() if k.startswith('chaipi.')}
        except (OSError, ValueError):
            return {}

    @staticmethod
    def file_name(rec):
        d = datetime.fromtimestamp(rec['date'] / 1000)
        return 'chaipi-%04d-%02d-%02d-%s.txt' % (d.year, d.month, d.day, re.sub(r'\W', '', str(rec['id']))[-4:])

    def games(self):
        gdir = os.path.join(self.data, 'games')
        try:
            files = {f for f in os.listdir(gdir) if f.endswith('.txt')}
        except OSError:
            files = set()
        out, seen = [], set()
        for r in self.store().get('games', []):
            try:
                name = self.file_name(r)
            except (KeyError, TypeError, ValueError):
                continue
            if name not in files or name in seen:
                continue
            seen.add(name)
            out.append({'file': name, 'white': r.get('white', '?'), 'black': r.get('black', '?'), 'result': r.get('result', '*'),
                        'reason': r.get('reason') or '', 'mode': r.get('mode', ''), 'side': r.get('side', 'w'),
                        'moves': (len(r.get('ucis', [])) + 1) // 2, 'date': r.get('date', 0)})
        for name in sorted(files - seen):
            tags = self.pgn_tags(os.path.join(gdir, name))
            out.append({'file': name, 'white': tags.get('White', '?'), 'black': tags.get('Black', '?'), 'result': tags.get('Result', '*'),
                        'reason': tags.get('Termination', ''), 'mode': '', 'side': 'w', 'moves': tags.get('_moves', 0),
                        'date': int(os.path.getmtime(os.path.join(gdir, name)) * 1000)})
        out.sort(key=lambda g: -g['date'])
        return out

    @staticmethod
    def pgn_tags(path):
        tags = {}
        try:
            with open(path, encoding='utf-8', errors='replace') as f:
                text = f.read(200000)
        except OSError:
            return tags
        for k, v in re.findall(r'^\[(\w+)\s+"([^"]*)"\]', text, re.M):
            tags[k] = v
        tags['_moves'] = len(re.findall(r'\b\d+\.(?!\.)', re.sub(r'\[.*?\]', '', text)))
        return tags

    def engines(self):
        settings = self.store().get('settings', {})
        profiles = settings.get('profiles') or [{'id': 'p1', 'name': 'Default', 'engine': 'sf19'}]
        prof = next((p for p in profiles if p.get('id') == settings.get('profile')), profiles[0])
        out = []
        for base, builtin in ((self.args.builtin_engines, True), (os.path.join(self.data, 'engines'), False)):
            try:
                names = sorted(os.listdir(base))
            except OSError:
                continue
            for n in names:
                try:
                    with open(os.path.join(base, n, 'engine.json')) as f:
                        m = json.load(f)
                except (OSError, ValueError):
                    continue
                out.append({'id': m.get('id', n), 'name': m.get('name', n), 'tier': m.get('tier', ''), 'type': m.get('type', ''),
                            'builtin': builtin, 'inUse': m.get('id', n) == prof.get('engine')})
        return {'profile': prof.get('name', 'Default'), 'engines': out}

    def apps(self):
        out = []
        adir = os.path.join(self.data, 'apps')
        try:
            names = sorted(os.listdir(adir))
        except OSError:
            names = []
        for n in names:
            meta = {}
            t = os.path.join(adir, n, 'app.toml')
            if tomllib and os.path.exists(t):
                try:
                    with open(t, 'rb') as f:
                        meta = tomllib.load(f)
                except Exception:
                    pass
            if os.path.exists(os.path.join(adir, n, 'main.py')):
                out.append({'id': n, 'name': str(meta.get('name', n)), 'ram': meta.get('ram', 40)})
        return out

    def puzzles(self):
        out = [{'name': 'Mates in one', 'count': 8, 'builtin': True}]
        pdir = os.path.join(self.data, 'puzzles')
        try:
            names = sorted(os.listdir(pdir))
        except OSError:
            names = []
        for n in names:
            if n.endswith('.json'):
                try:
                    with open(os.path.join(pdir, n)) as f:
                        j = json.load(f)
                    out.append({'name': j.get('name', n), 'count': len(j.get('puzzles', []))})
                except (OSError, ValueError):
                    pass
        return out

    def device(self):
        du = shutil.disk_usage(self.data)
        return dict(self.status, freeBytes=du.free, totalBytes=du.total, games=len(self.games()), engines=len(self.engines()['engines']),
                    apps=len(self.apps()), mode=self.args.mode, ssid=self.net.ssid if self.net else '', ip=self.ip)

    # --- sessions ------------------------------------------------------------------------
    def new_session(self):
        tok = secrets.token_urlsafe(24)
        self.sessions[tok] = time.time() + 6 * 3600
        return tok

    def valid(self, tok):
        exp = self.sessions.get(tok or '')
        return bool(exp and exp > time.time())


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = 'ChAIpi'
    sys_version = ''
    st = None  # State, set in main()

    def log_message(self, fmt, *args):
        sys.stderr.write('%s %s\n' % (self.address_string(), fmt % args))

    # --- helpers --------------------------------------------------------------------------
    def send(self, code, body=b'', ctype='application/json', headers=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-store')
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def cookie(self):
        m = re.search(r'(?:^|;\s*)chaipi=([\w-]+)', self.headers.get('Cookie', ''))
        return m.group(1) if m else None

    def authed(self):
        return self.st.pin is None or self.st.valid(self.cookie())

    def host_ok(self):
        host = (self.headers.get('Host') or '').split(':')[0].lower()
        return host in ('', self.st.ip, 'chaipi.local', 'chaipi', 'localhost', '127.0.0.1')

    def static(self, path, root):
        full = os.path.realpath(os.path.join(root, path.lstrip('/')))
        if not full.startswith(os.path.realpath(root) + os.sep) or not os.path.isfile(full):
            return self.send(404, {'error': 'not found'})
        with open(full, 'rb') as f:
            body = f.read()
        ctype = mimetypes.guess_type(full)[0] or 'application/octet-stream'
        if full.endswith('.woff2'):
            ctype = 'font/woff2'
        self.send_response(200)
        self.send_header('Content-Type', ctype + ('; charset=utf-8' if ctype.startswith('text/') or ctype.endswith('javascript') else ''))
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'max-age=3600' if '/fonts/' in full else 'no-cache')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

    def attachment(self, name, body, ctype):
        self.send(200, body, ctype, {'Content-Disposition': 'attachment; filename="%s"' % name})
        emit(ev='download', name=name)

    # --- routes ---------------------------------------------------------------------------
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        url = urllib.parse.urlsplit(self.path)
        path = url.path
        if self.st.args.mode == 'hotspot' and (path in PROBES or not self.host_ok()):
            # Phones check a known address to see if a network needs signing in; send them to the page.
            return self.send(302, b'', 'text/plain', {'Location': 'http://%s/' % self.st.ip})
        if path in ('/', '/index.html'):
            return self.static('index.html', self.st.args.portal)
        if path in ('/portal.css', '/portal.js', '/favicon.svg'):
            return self.static(path, self.st.args.portal)
        if path.startswith('/fonts/'):
            name = path[7:]
            if not FONT_RE.match(name):
                return self.send(404, {'error': 'not found'})
            return self.static(name, self.st.args.fonts)
        if path == '/api/hello':
            return self.send(200, {'pin': self.st.pin is not None, 'authed': self.authed(), 'mode': self.st.args.mode, 'tab': self.st.args.start_tab,
                                   'locked': max(0, int(self.st.locked_until - time.time()))})
        if not path.startswith('/api/'):
            return self.send(404, {'error': 'not found'})
        if not self.authed():
            return self.send(401, {'error': 'Type the PIN shown on ChAIpi first'})
        st = self.st
        if path == '/api/state':
            return self.send(200, {'device': st.device(), 'games': st.games(), 'engines': st.engines(), 'apps': st.apps(), 'puzzles': st.puzzles()})
        if path == '/api/games.zip':
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
                for g in st.games():
                    z.write(os.path.join(st.data, 'games', g['file']), g['file'])
            return self.attachment('chaipi-games-%s.zip' % time.strftime('%Y-%m-%d'), buf.getvalue(), 'application/zip')
        if path == '/api/games.pgn':
            parts = []
            for g in st.games():
                with open(os.path.join(st.data, 'games', g['file']), encoding='utf-8', errors='replace') as f:
                    parts.append(f.read().strip())
            return self.attachment('chaipi-games-%s.pgn' % time.strftime('%Y-%m-%d'), '\n\n'.join(parts) + '\n', 'application/x-chess-pgn')
        m = re.match(r'^/api/games/([\w.-]+\.txt)$', path)
        if m:
            p = os.path.join(st.data, 'games', m.group(1))
            if not os.path.isfile(p):
                return self.send(404, {'error': 'That game is gone'})
            with open(p, 'rb') as f:
                body = f.read()
            if urllib.parse.parse_qs(url.query).get('view'):
                return self.send(200, body, 'text/plain; charset=utf-8')
            return self.attachment(m.group(1), body, 'text/plain; charset=utf-8')
        if path == '/api/backup':
            return self.attachment('chaipi-backup-%s.tar.gz' % time.strftime('%Y-%m-%d'), inst.make_backup(st.data), 'application/gzip')
        return self.send(404, {'error': 'not found'})

    def read_json(self):
        n = int(self.headers.get('Content-Length') or 0)
        if n > 10000:
            return None
        try:
            return json.loads(self.rfile.read(n) or b'{}')
        except ValueError:
            return None

    def do_POST(self):
        path = urllib.parse.urlsplit(self.path).path
        st = self.st
        if path == '/api/login':
            body = self.read_json() or {}
            with st.lock:
                now = time.time()
                if now < st.locked_until:
                    return self.send(429, {'error': 'Too many tries. Wait %d s' % (st.locked_until - now), 'locked': int(st.locked_until - now)})
                if st.pin is None or hmac.compare_digest(str(body.get('pin', '')), st.pin):
                    st.fails = 0
                    tok = st.new_session()
                    emit(ev='login')
                    return self.send(200, {'ok': True}, headers={'Set-Cookie': 'chaipi=%s; HttpOnly; SameSite=Strict; Path=/; Max-Age=21600' % tok})
                st.fails += 1
                left = self.st.args.pin_tries - st.fails
                emit(ev='pinfail', left=max(0, left))
                if left <= 0:
                    st.fails = 0
                    st.locked_until = now + self.st.args.lockout_s
                    return self.send(429, {'error': 'Too many tries. Wait %d s' % self.st.args.lockout_s, 'locked': self.st.args.lockout_s})
                return self.send(403, {'error': 'That PIN doesn’t match', 'left': left})
        if not self.authed():
            return self.send(401, {'error': 'Type the PIN shown on ChAIpi first'})
        if path == '/api/upload':
            return self.upload()
        if path == '/api/use-engine':
            body = self.read_json() or {}
            if not re.match(r'^[\w-]{1,40}$', str(body.get('id', ''))):
                return self.send(400, {'error': 'bad id'})
            emit(ev='use-engine', id=body['id'])
            return self.send(200, {'ok': True})
        if path == '/api/stop':
            self.send(200, {'ok': True})
            emit(ev='stop')
            return
        return self.send(404, {'error': 'not found'})

    def upload(self):
        st = self.st
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        kind = (q.get('kind') or [''])[0]
        name = os.path.basename((q.get('name') or ['upload'])[0])[:120] or 'upload'
        if kind not in ('engine', 'app', 'puzzles', 'games', 'backup'):
            return self.send(400, {'error': 'Unknown kind of upload'})
        n = int(self.headers.get('Content-Length') or 0)
        if n <= 0:
            return self.send(411, {'error': 'Empty upload'})
        if n > st.max_upload:
            return self.send(413, {'error': 'Too big (limit %d MB)' % (st.max_upload // 1048576)})
        inbox = os.path.join(st.data, 'inbox')
        os.makedirs(inbox, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix='up-', dir=inbox)
        try:
            with os.fdopen(fd, 'wb') as out:
                left = n
                while left > 0:
                    chunk = self.rfile.read(min(left, 1 << 16))
                    if not chunk:
                        raise inst.Rejected('Upload was cut off')
                    out.write(chunk)
                    left -= len(chunk)
            item = inst.install(kind, tmp, st.data, display_name=name)
        except inst.Rejected as e:
            emit(ev='rejected', kind=kind, name=name, why=str(e))
            return self.send(422, {'error': str(e)})
        except Exception as e:  # keep the server up whatever an upload does
            emit(ev='rejected', kind=kind, name=name, why='Could not install')
            sys.stderr.write('upload failed: %r\n' % e)
            return self.send(500, {'error': 'Could not install this file'})
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        if kind == 'backup':
            emit(ev='restore')
        else:
            emit(ev='installed', **item)
        return self.send(200, {'ok': True, 'item': item})


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def stdin_loop(st):
    for line in sys.stdin:
        try:
            m = json.loads(line)
        except ValueError:
            continue
        if m.get('cmd') == 'pin' and re.match(r'^\d{4}$', str(m.get('pin', ''))):
            st.pin = str(m['pin'])
            st.sessions.clear()
        elif m.get('cmd') == 'status':
            st.status.update({k: m[k] for k in ('bat', 'charging', 'free', 'version') if k in m})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['hotspot', 'home'], default='hotspot')
    ap.add_argument('--data', default='/data/chaipi')
    ap.add_argument('--port', type=int, default=80)
    ap.add_argument('--portal', default=os.path.join(os.path.dirname(__file__), '..', 'portal'))
    ap.add_argument('--fonts', default='/opt/chaipi/fonts')
    ap.add_argument('--builtin-engines', default='/opt/chaipi/engines')
    ap.add_argument('--config', default='/etc/chaipi/chaipi.toml')
    ap.add_argument('--pin')
    ap.add_argument('--idle-min', type=int, default=0)
    ap.add_argument('--start-tab', choices=['games', 'engines', 'apps', 'puzzles', 'device'], help='tab to open first, e.g. device for a backup')
    ap.add_argument('--no-network', action='store_true', help="don't touch Wi-Fi (for trying it on a computer)")
    args = ap.parse_args()
    t = {}
    if tomllib and os.path.exists(args.config):
        with open(args.config, 'rb') as f:
            t = tomllib.load(f).get('transfer', {})
    args.max_upload_mb = int(t.get('max_upload_mb', 300))
    args.pin_tries = int(t.get('pin_tries', 5))
    args.lockout_s = int(t.get('lockout_s', 60))
    args.portal = os.path.realpath(args.portal)
    st = State(args)
    st.net = Network(args.mode, t.get('hotspot_connection', 'chaipi-hotspot'), t.get('hotspot_ip', '192.168.4.1'), not args.no_network)
    Handler.st = st
    try:
        st.ip = st.net.start()
    except Exception as e:
        emit(ev='error', msg=str(e))
        st.net.stop()
        sys.exit(1)
    try:
        httpd = Server(('0.0.0.0', args.port), Handler)
    except OSError as e:
        emit(ev='error', msg='Web server could not start: %s' % e.strerror)
        st.net.stop()
        sys.exit(1)

    def quit_(*_):
        threading.Thread(target=httpd.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, quit_)
    signal.signal(signal.SIGINT, quit_)
    threading.Thread(target=stdin_loop, args=(st,), daemon=True).start()
    url = 'http://%s%s/' % (st.ip, '' if args.port == 80 else ':%d' % args.port)
    emit(ev='ready', ip=st.ip, ssid=st.net.ssid, url=url, **({'pass': st.net.psk} if st.net.psk else {}))
    try:
        httpd.serve_forever(poll_interval=0.5)
    finally:
        httpd.server_close()
        st.net.stop()


if __name__ == '__main__':
    main()
