# Contributing to ChAIpi

Thanks for helping. Bug reports, hardware notes from your own build, and pull requests are all welcome.

## Before you start
- Read [docs/13-device-software.md](docs/13-device-software.md) for how the software fits together and [docs/12-revision-3.md](docs/12-revision-3.md) for the hardware.
- For anything bigger than a small fix, open an issue first so we can agree on the approach.

## How the code is laid out
- **The OS is `mockup/chaipi-os.html`.** It runs in a browser (the emulator) and, unchanged, on the device through `device/ui/host.js`. Device-only behaviour goes through a hook on `window.CHAIPI_HOST`, guarded by `if(HOST)`, so the page keeps working in a browser.
- A new device feature usually needs three changes: the hook in the mockup, its implementation in `host.js` (or `device/ui/lib/`), and a check in `device/ui/test/os-smoke.js`.
- Pins and tunables live in `config/chaipi.example.toml`. Never hard-code a pin.
- State is saved atomically (temp file, fsync, rename, fsync the folder). Use `lib/store.js` / `writeAtomic`.
- `src/chaipi` is the first prototype (OLED + voice). It isn't used on the device, so please don't build on it.

## Tests
Run these before sending a pull request. None of them needs a Pi.

```bash
python3 -m pytest tests/test_input.py tests/test_transfer.py -q
```
```bash
/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc device/ui/test/os-smoke.js -- mockup/chaipi-os.html device/ui/lib
```
```bash
/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc device/ui/test/lib-test.js -- device/ui/lib config/chaipi.example.toml
```

The JavaScript tests use JavaScriptCore, which every Mac has. On Linux, use the `jsc` from WebKitGTK, or let GitHub Actions run them on your pull request. After a UI change, also open the emulator (`python3 tools/build_emulator.py /tmp/emu.html --inline-fonts`) and click through the screens you touched.

## Pull requests
- Keep each pull request to one change, and say how you tested it: in the emulator, the tests, or on real hardware (which board and screen).
- Be exact about what ran on hardware. "Tested in the emulator only" is a perfectly good answer.
- By contributing you agree that your work is released under the project's licence (GPL-3.0-or-later).
