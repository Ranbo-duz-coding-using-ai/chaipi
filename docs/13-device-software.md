# 13 — Device software and the SD-card image (2026-10-23)

This replaces the software plan in docs 05–08 for revision 3 hardware (docs/12). The Phase 0 Python code in `legacy/phase0-prototype` (OLED + voice) is superseded and not used on the device.

## The idea: one OS, two hosts
The OS you clicked through in `mockup/chaipi-os.html` **is** the device OS. Its `<script>` block runs unchanged in two places:

| | Browser (the mockup) | ChAIpi |
|---|---|---|
| Runs in | any browser | Node.js + `@napi-rs/canvas` (Skia), `device/ui/host.js` |
| Screen | `<canvas>` on the page | the ILI9341 framebuffer (RGB565, only changed rows are sent) |
| Engine | small demo engine in a Web Worker | Stockfish 19 over UCI |
| Buttons | keyboard and the drawn shell | `chaipi-input` (GPIO + ADS1115) |
| Wi-Fi, Transfer, Shorts, USB, SD | simulated | NetworkManager, the transfer server, yt-dlp + ffmpeg, USB gadget, SD slot |

The script checks for `window.CHAIPI_HOST`. When it's there (on the device), a few dozen small hooks call it instead of simulating. When it's absent (the browser), nothing changes. So a UI change made in the mockup shows up on the device with no porting.

## Processes
```
systemd
├── chaipi-boot      once per boot, root: Wi-Fi file, hotspot profile, RTC, sound card, /data folders
├── chaipi-input     Python, user chaipi: 7 buttons, joystick + battery via ADS1115, vibration, backlight PWM
│                     -> /run/chaipi/input.sock (JSON lines)
└── chaipi-ui        Node.js, user chaipi: the OS + host.js
     ├── stockfish             UCI, nice 5, 4 threads, restarted if it dies
     ├── chaipi_xfer.server    only while Transfer is on (brings the hotspot up and down)
     ├── yt-dlp / ffmpeg       only while a Short plays (the engine is stopped meanwhile)
     ├── python3 -m chaipi.run your Python app, while it runs (the UI stops drawing)
     └── sudo chaipi-media     USB drive mode and SD card, for a few seconds at a time
```

## Folders on the device
| Path | What |
|---|---|
| `/opt/chaipi/device/` | this repo's `device/` folder (UI host, input daemon, transfer server, SDK, scripts) |
| `/opt/chaipi/ui/chaipi-os.html` | the OS, a copy of `mockup/chaipi-os.html` |
| `/opt/chaipi/engines/sf19/` | Stockfish 19 + `engine.json` |
| `/opt/chaipi/fonts/` | Atkinson Hyperlegible, JetBrains Mono, Unbounded, Noto Sans Symbols 2 (all OFL) |
| `/opt/chaipi/venv/` | yt-dlp |
| `/etc/chaipi/chaipi.toml` | pins and tunables (from `config/chaipi.example.toml`) |
| `/etc/chaipi/hotspot.json` | the hotspot name and password made at first boot |
| `/data/chaipi/state.json` | everything the OS stores: settings, History, the game in progress (written atomically) |
| `/data/chaipi/games/*.txt` | one PGN file per finished game |
| `/data/chaipi/{engines,apps,puzzles}/` | what you added |
| `/data/chaipi/inbox/` | uploads waiting to be checked |

## HOST hooks (what the OS asks the device for)
| Hook | Used by | Device side |
|---|---|---|
| `think(fen, depth, opt)` | engine moves, arrows, hints, Helper, review | `lib/engine.js`: Elo 1320–3189 uses `UCI_LimitStrength`/`UCI_Elo`; below 1320, MultiPV 8 and the OS's own blunder picker; analysis is MultiPV 3 (250 ms, 900 ms, then the full think time); pondering on your time. An engine move is never interrupted, and is retried once if Stockfish crashes. |
| `sysTick(SYS)` | status bar, System panel, low-battery warnings | battery from `chaipi-input`; CPU, temperature, RAM from `/proc` and `/sys` |
| `display({bright, dim, sleeping})` | brightness, dimming, sleep clock | real backlight PWM; backlight off 10 min into sleep |
| `haptic(level)` | taps, checks, game end | vibration motor pulse |
| `power(mode)` | Shut down / Restart | `systemctl poweroff/reboot` (allowed by polkit) |
| `saveGame`, `deleteGame` | History | `/data/chaipi/games/*.txt` |
| `qr(text)` | Transfer screen | real QR codes (`qrcode` package): Wi-Fi join code and page address |
| `transfer.start/stop/setPin` | Settings → Transfer | `chaipi_xfer.server` (below) |
| `wifi.*` | Settings → Wi-Fi | `nmcli`: scan, connect (with the on-screen keyboard's password), hidden networks, forget |
| `engines.install/remove` | Settings → Engines → Add engine | catalog download (needs `[catalog] url`), checked by the same installer as uploads |
| `shorts.*` | Extras → Media → Shorts | `lib/shorts.js`: yt-dlp search and stream, ffmpeg decode (hardware H.264 first) |
| `usb.*`, `sd.*` | USB drive mode, SD card | `chaipi-media` |
| `apps.run(id)` | Extras → your Python apps | separate process with the `chaipi` SDK |

## Transfer server (`device/transfer`)
- `python3 -m chaipi_xfer.server --mode hotspot|home --pin NNNN`, started and stopped by the UI.
- Hotspot mode: `nmcli connection up chaipi-hotspot` (WPA2, 2.4 GHz channel 6, 192.168.4.1/24), and NetworkManager's dnsmasq answers every name with 192.168.4.1 (`/etc/NetworkManager/dnsmasq-shared.d/chaipi-captive.conf`). Phones' "is there internet?" checks get a redirect, so the page pops up as a sign-in page.
- PIN: 4 digits on the device's screen, 5 tries then a 60 s lock. A new PIN (Fn) signs everyone out. Session cookie is HttpOnly + SameSite=Strict.
- Uploads go to `inbox/`, then `chaipi_xfer.install` checks them: engines must be ARM64 ELF programs that answer `uci` (a PC build is refused and says why); apps must compile; puzzle packs are filtered to mate-in-one; archives can't write outside their folder.
- The page (`device/transfer/portal`) works with no internet: fonts come from the device. Tabs: Games (stats, search, filters, .txt / .zip / one .pgn, View PGN), Engines (Use, upload), Apps, Puzzles, Device (backup, restore, stop sharing).

## Your own Python apps (`device/sdk`)
```python
from chaipi import app

@app.loop(fps=15)
def frame(screen, keys):
    screen.clear()
    screen.text("Hello", 10, 20)
    if keys.pressed("ok"):
        app.buzz()
```
A folder with `main.py` and `app.toml` (`name = "…"`, `ram = 40`). Example: `device/sdk/examples/chai-catch`. Screen drawing is Pillow underneath (`screen.img`, `screen.draw`). Esc quits; holding Esc for 1 s ends an app that hangs.

## Getting the software onto the Pi
See `image/README.md`. In short:
1. **Download** the image from Releases. GitHub Actions builds it (`.github/workflows/chaipi-image.yml`), so nobody needs the 25 GB pi-gen wants.
2. **Or** flash plain Raspberry Pi OS Lite 64-bit and run `image/install.sh` over SSH. Same result, no image build.
3. **Or** build it yourself with Docker (`image/build.sh`).

Wi-Fi before the buttons are wired: put `chaipi-wifi.txt` on the SD card's boot partition (`ssid = …`, `password = …`, `country = IN`, optionally `timezone = …`). SSH keys go in `chaipi-ssh.txt` there, since the published image has none. `chaipi-boot` applies both and deletes them.

Driving it over SSH before the buttons arrive: `chaipi-keys` (arrows, Enter, Esc, Tab, m, f; backtick for typing). Screenshot: `sudo systemctl kill -s USR2 chaipi-ui`, then copy `/run/chaipi/screen.png`. Logs: `journalctl -u chaipi-ui -u chaipi-input -f`.

## What has been tested, and what hasn't
Tested off-device, on a computer (no Pi needed):
- The real OS script running with a fake HOST and fake canvas (`device/ui/test/os-smoke.js`, 35 checks). It boots, plays a Helper game to checkmate and saves the PGN. It also covers the engine move request, Transfer with a real QR code request, Wi-Fi connect with a typed password, Shorts feed/search/play/pause/seek/stop, engine download, a Python app, USB and SD, History delete, sleep and shutdown.
- Engine request rules against a fake Stockfish (`device/ui/test/lib-test.js`): Elo limiting, weak levels, cancelling stale analysis, never interrupting a move, pondering, crash retry. Also the TOML, UCI, pixel, nmcli and PGN helpers.
- Input daemon logic: ADS1115 config words, joystick hysteresis, battery estimate, low-battery trigger, socket injection (`tests/test_input.py`).
- Transfer server and installer: PIN and lockout, sessions, new PIN, captive redirects, uploads of every kind, rejected PC engines, unsafe archives, backup and restore (`tests/test_transfer.py`). The page was used in a phone-sized browser.
- The SDK example ran against the mock input daemon.
- The mockup still runs in the browser with all 24 screen shortcuts and no errors.

**Not tested yet, because it needs the Pi:** Node + Skia rendering speed, the framebuffer and the `fbtft` overlay, GPIO and the ADS1115, the hotspot and captive page on real phones, yt-dlp/ffmpeg playback and sound, USB gadget mode, the SD slot, `install.sh` itself, and a boot of the built image (it builds, and every install step completes in the build log). Phase 1 below is that bring-up.

## Phase 1 bring-up order
1. Flash, boot, SSH in. `journalctl -b` shows `chaipi-boot` made the hotspot.
2. Screen: the TFT shows the boot animation. If colours are wrong, toggle `bgr`; if it's upside down, `rotate=270`. Measure UI frame time (`journalctl -u chaipi-ui`).
3. Input: `chaipi-keys` first, then the joystick (calibration is in the log), then buttons as they're soldered.
4. Engine: play at 1800 and at Max; check `vcgencmd get_throttled` is `0x0` and the temperature stays under 80 °C.
5. Battery: compare the Settings voltage with a multimeter; set `battery.divider`.
6. Transfer with an Android phone and an iPhone.
7. Wi-Fi, then Shorts (and the amplifier once it's fitted).
8. Memory: `free -m` while analysing, while Transfer is on, and while a Short plays.

## Known limits
- Puzzle mode is mate-in-one only (the OS's puzzle checker), so other puzzles in a pack are skipped.
- The engine catalog has no download URLs until someone builds ARM64 engines and publishes them (`[catalog] url`). Until then, engines come in by Transfer, USB or SD.
- YouTube Shorts: see the caveats in docs/12.
- A hard power cut loses at most the move being saved; use Menu → Shut down when you can.
