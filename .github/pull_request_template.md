## What this changes


## How it was tested
<!-- Tick what applies. "Emulator only" is a fine answer: just say so. -->
- [ ] Python tests (`python3 -m pytest tests/test_input.py tests/test_transfer.py -q`)
- [ ] OS smoke test and library tests (JavaScriptCore, see CONTRIBUTING.md)
- [ ] Clicked through the changed screens in the emulator
- [ ] On real hardware (Pi, screen, and anything wired differently from docs/03):

## Checklist
- [ ] No pins hard-coded (they belong in `config/chaipi.example.toml`)
- [ ] Device-only code goes through a `CHAIPI_HOST` hook, so the emulator still works
- [ ] Docs updated if behaviour or wiring changed
