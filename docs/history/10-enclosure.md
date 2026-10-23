# 10 — Enclosure

## Part sizes (approximate; measure the real parts before designing)
| Part | Size (mm) |
|---|---|
| Pi Zero 2 W | 65 × 30 × 1.4 board; about 5 tall with components |
| Pi + Waveshare HAT stack (incl. joystick cap) | about 65 × 30 × 22 |
| 5000 mAh LiPo pouch | about 10 × 50 × 90 (varies by brand) |
| PowerBoost 1000C | 36 × 23, about 8 tall with the USB-A jack |
| MAX17048 breakout | 23 × 18 |
| DS3231 mini | about 15 × 13 |
| Mini USB mic + OTG adapter | about 35 long × 12 |

## Recommended layout: "sandwich"
```
side view
 ┌────────────────────────────────────────────┐  ← top shell: OLED window, joystick + key holes, mic holes
 │   [ HAT: OLED · joystick · KEY1-3 ]        │
 │   [ Pi Zero 2 W + heatsink ]   [PowerBoost]│  ← vent slots above and beside the chip
 │ ────────── foam / Kapton layer ─────────── │
 │   [ 5000 mAh LiPo pouch ]                  │
 └────────────────────────────────────────────┘  ← bottom shell: rubber feet, vents
```
**Outside size: about 100 × 60 × 36 mm** (deck-of-cards-and-a-half). The Pi stack sits off-centre so the PowerBoost, gauge, and RTC fit beside it.

## Faces
- **Top:**
  - OLED window (active area about 29.4 × 14.7 mm) with a 1 mm bezel
  - Joystick hole with an extended printed cap
  - 3 printed plungers for KEY1–3, labelled 🎤 / ↩ / ☰ (embossed)
  - A 3 × 3 grid of 1.5 mm mic holes near KEY1
  - Light-pipe hole for the charge LEDs
- **Left side:** slide power switch slot.
- **Bottom edge:** micro-USB charging port (PowerBoost).
- **Back:** vent slots, 4 rubber feet, optional lanyard loop.

## Build notes
- **PETG** rather than PLA. The chip area can sit at 60–70 °C, and PLA softens near 60 °C.
- Two halves joined with M2 screws into heat-set inserts. Standoffs for the Pi's 4 M2.5 holes.
- The mic is held behind its holes with a foam gasket, so it hears your voice and not internal noise.
- Keep the battery away from the heat. The foam layer and the battery's position under the *non-chip* end help.
- No 3D printer? Use an online printing service (e.g. JLC3DP, or a local maker space). Alternatively, use a 100 × 60 × 40 mm ABS project box and cut the openings by hand.

## When we get there (Phase 6)
1. You measure the parts with calipers. Claude provides a measurement checklist.
2. Claude writes a parametric OpenSCAD model (`case/chaipi_case.scad`) → STL for the top and bottom shells.
3. Print → test fit → adjust parameters → final print.
