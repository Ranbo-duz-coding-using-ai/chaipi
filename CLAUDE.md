# CLAUDE.md: notes for AI coding agents

ChAIpi is a pocket chess computer: **Stockfish 19 on a Raspberry Pi Zero 2 W** with a 2.8" ILI9341 TFT (320×240), an on-screen board moved with a PS2 joystick (via ADS1115), 6 buttons and a battery. It also has an Extras tab (games, scientific/graphing calculator, solver, YouTube Shorts, your own Python apps) and Transfer: its own Wi-Fi hotspot plus a phone web page. Created by Ranbir Dhall. GPL-3.0-or-later.

## Status
- Revision 3. **Read `docs/12-revision-3.md` (hardware, final pin map) and `docs/13-device-software.md` (device software, what's tested) first.** `docs/history/` is the superseded original plan.
- The UI spec **is** the device OS: `mockup/chaipi-os.html`. On the Pi, `device/ui/host.js` runs its `<script>` in Node.js + @napi-rs/canvas and provides `window.CHAIPI_HOST`. The mockup's hooks are no-ops when HOST is absent. `tools/build_emulator.py` wraps the mockup (a fragment with no doctype) into the emulator page. **Re-run `device/ui/test/os-smoke.js` and click through the emulator after any mockup edit.**
- Device software is tested off-device only (os-smoke, lib-test, pytest). **The image builds on GitHub Actions, but nothing has booted on a Pi yet.** Next: Phase 1 bring-up in docs/13, with wiring in docs/03.
- `src/chaipi` + `pyproject.toml` are the abandoned Phase 0 prototype (OLED + voice). Not used on the device. Don't extend them.

## Key decisions (don't re-litigate without the maintainer)
- Pi Zero 2 W at stock speed, no underclocking. Stockfish gets 4 threads at nice 5. The UI keeps priority instead of the engine losing a core.
- Stockfish 19 official ARM64 build, release tag `sf_19` (`install.sh` falls back to the GitHub API, then to compiling `sf_19`). SF19 exits on invalid UCI, so only send declared options and valid FENs; `lib/engine.js` restarts it and retries an engine move once.
- Elo: `UCI_LimitStrength` + `UCI_Elo` for 1320–3189. Below 1320: MultiPV 8 and the OS's `pickByElo` blunders. Think times are Fast 1 s, Medium 4 s, Deep 12 s.
- Pins (BCM): TFT SPI0 CE0, DC 25, RST 24, backlight PWM 13; I2C 2/3 (ADS1115 0x48, DS3231 0x68); I2S 18/19/21; Confirm 5, Backspace 6, Esc 16, Tab 26, **Menu 23**, Fn 17, joystick press 27; vibration 12; UART 14/15 kept for the console; GPIO 20 is left empty (I2S claims it). All pins live in `config/chaipi.example.toml` → `/etc/chaipi/chaipi.toml`. Never hard-code them.
- Transfer = NetworkManager hotspot `chaipi-hotspot` (192.168.4.1, made by `chaipi-boot`) + captive DNS + `chaipi_xfer.server` with a 4-digit PIN. Uploads are checked by `chaipi_xfer.install` (engines must be ARM64 ELF and answer `uci`).
- Shorts = yt-dlp + ffmpeg (hardware H.264), with the engine suspended. YouTube's terms don't allow third-party players, and it breaks when YouTube changes.
- Puzzle mode stays mate-in-one, so packs are filtered to that.
- **The published image contains no SSH key and no known password.** Keys come from `chaipi-ssh.txt` on the boot partition (`chaipi-boot`). Never bake a personal key into a CI build.

## Build and test
- Image: `.github/workflows/chaipi-image.yml` (workflow_dispatch) builds with pi-gen in Docker and publishes a GitHub Release `v<VERSION>` with the `.img.xz`, `SHA256SUMS` and `chaipi-emulator.html`. pi-gen bind-mounts the host's /tmp over the image's /tmp inside `on_chroot`, so stage files go to `/usr/src`. The pi-gen work path must not contain spaces.
- Emulator website: `.github/workflows/emulator.yml` deploys to GitHub Pages, only when the repository is public.
- Tests (no Pi): `device/README.md` lists the three commands. The JS tests run in JavaScriptCore (`/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc` on macOS). README pictures: `tools/capture_screens.py` (headless Chrome + Pillow).
- On the Pi: `ssh pi@chaipi.local`. Services `chaipi-boot`, `chaipi-input`, `chaipi-ui`. Logs: `journalctl -u chaipi-ui -f`. Drive the UI without buttons with `chaipi-keys`. Screenshot: `sudo systemctl kill -s USR2 chaipi-ui` → `/run/chaipi/screen.png`.
- Device paths: code `/opt/chaipi/device`, OS `/opt/chaipi/ui/chaipi-os.html`, engines `/opt/chaipi/engines` + `/data/chaipi/engines`, state `/data/chaipi/state.json`, games `/data/chaipi/games/*.txt`.

## Conventions
- Save state atomically (temp → fsync → rename → fsync dir): `lib/store.js`, `writeAtomic`.
- New device features: add a HOST hook in the mockup guarded by `if(HOST)`, implement it in `host.js`, then add a check to `os-smoke.js`.
- Be exact about what was tested on hardware and what wasn't.
- No personal data in the repository: no real names other than the creator credit, no emails, home paths, network names or keys.

## Docs map
`docs/README.md` (index) · `docs/12-revision-3.md` (parts, pins, power, transfer, sound) · `docs/03-wiring.md` (wiring) · `docs/13-device-software.md` (architecture, hooks, tests, bring-up) · `image/README.md` (SD card) · `device/README.md` (code map, tests) · `docs/history/` (original plan) · `enclosure/logo-badge/README.md`
