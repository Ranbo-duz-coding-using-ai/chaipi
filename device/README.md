# device/ — the software that runs on ChAIpi

The architecture is in `docs/13-device-software.md`, the hardware in `docs/12-revision-3.md`, and how it gets onto the SD card in `image/README.md`.

| Folder | What | Language |
|---|---|---|
| `ui/` | `host.js` runs the OS from `mockup/chaipi-os.html` on the SPI screen and connects it to the hardware. `lib/` holds the pieces (engine, framebuffer, Wi-Fi, Transfer, Shorts, USB/SD, apps) | Node.js |
| `input/` | `chaipi_input.py`: buttons, joystick, battery, vibration, backlight. `chaipi_keys.py`: drive the UI from an SSH terminal | Python |
| `transfer/` | the transfer web server, the upload checker and the phone page (`portal/`) | Python, HTML/JS |
| `sdk/` | `chaipi`, the module for your own Python apps, plus an example (`examples/chai-catch`) | Python |
| `bin/` | `chaipi-boot` (every boot) and `chaipi-media` (USB drive mode, SD card), both root | bash |
| `fonts/` | the four OFL fonts the OS and the phone page use | |

## Tests (run on the Mac, no Pi needed)
```bash
/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc device/ui/test/os-smoke.js -- mockup/chaipi-os.html device/ui/lib
```
```bash
/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc device/ui/test/lib-test.js -- device/ui/lib config/chaipi.example.toml
```
```bash
.venv/bin/python -m pytest tests/test_input.py tests/test_transfer.py -q
```

## Try the transfer page on the Mac
```bash
PYTHONPATH=device/transfer python3 -m chaipi_xfer.server --mode hotspot --no-network --data /tmp/chaipi-data --port 8780 --portal device/transfer/portal --fonts device/fonts --pin 1234
```
Then open http://127.0.0.1:8780 and type 1234.
