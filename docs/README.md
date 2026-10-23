# ChAIpi docs

Start here:

| Doc | What's in it |
|---|---|
| [12 — Hardware](12-revision-3.md) | Parts list with the pitfalls of each part, the final pin map, power, audio, how Transfer works |
| [03 — Wiring](03-wiring.md) | Step-by-step wiring with a test after each step, every wire in one table, troubleshooting |
| [13 — Device software](13-device-software.md) | How the OS runs on the Pi, processes, hooks, folders, what's been tested, the bring-up plan |
| [../image/README.md](../image/README.md) | Getting the SD card: download, build it yourself, or install over SSH |
| [../device/README.md](../device/README.md) | Code map and the tests |
| [../enclosure/logo-badge/README.md](../enclosure/logo-badge/README.md) | The 3D-printable logo badge |

Diagrams: [wiring/header-map.svg](wiring/header-map.svg) (which pin goes where) and [wiring/power.svg](wiring/power.svg) (battery to 5 V). [wiring/tools/make_diagrams.py](wiring/tools/make_diagrams.py) draws both.

## Design history
[history/](history/README.md) has the original plan (an OLED, a 5-way joystick and voice input) and revision 2. They're kept to show how the design got here. Where they disagree with the docs above, the docs above win.
