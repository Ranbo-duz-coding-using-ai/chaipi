# 11 — Revision 2 (2026-10-22): new hardware and UI direction

**This replaces parts of docs 01–07.** Where they disagree, this file wins.

## What changed
| Before (docs 01–07) | Now |
|---|---|
| Waveshare 1.3" OLED HAT, 128×64 | **2.8" ILI9341 SPI TFT, 320×240, colour** (one display only) |
| Piece → file → rank entry | **On-screen board with a joystick cursor**. Pick up a piece, drop it on a legal square (snap-to-legal) |
| Voice input (Vosk + USB mic) | **Dropped.** The mic button becomes **Tab** (switches the side panel: Game / Analysis / System) |
| 5-way digital joystick | **PS2 analog thumbstick** read through an **ADS1115** ADC |
| PowerBoost 1000C + 5000 mAh | **TP4056 (USB-C, protected) + 5 V boost + 2× 2000 mAh LiPo in parallel** (4000 mAh) |
| MAX17048 gauge | **ADS1115 spare channel** measures battery voltage (MAX17048 optional if findable) |

## Controls (final)
Joystick (up/down/left/right + press), **Confirm, Backspace (undo), Esc, Tab, Menu, Fn** (programmable), plus the power switch. That's 6 buttons + joystick + switch.

## Modes (see the live mockup)
Play vs ChAIpi (Elo 1320–3190, random side pick), Helper (move both sides of a real game, best-move arrows), Two player (chess clock), Puzzles, History (PGN `.txt` per game), Game review (accuracy and move labels), Settings (themes, accent colours, 7 boards, 3 piece sets, Fn mapping, haptics, clock), quick panel (hold Menu).

**Mockup:** `mockup/chaipi-os.html` (the emulator). It is the UI spec. Build the real UI to match it.

## GPIO plan
| Function | BCM GPIO |
|---|---|
| TFT SPI0: SCK / MOSI / CS | 11 / 10 / 8 (CE0) |
| TFT DC / RESET / backlight (PWM) | 25 / 24 / 18 |
| I2C SDA / SCL: ADS1115 (0x48), DS3231 (0x68, EEPROM 0x57) | 2 / 3 |
| Confirm / Backspace / Esc / Tab / Menu / Fn | 5 / 6 / 13 / 19 / 26 / 16 |
| Joystick press | 20 |
| Vibration module IN | 12 |
| ADS1115 A0 / A1 / A2 / A3 | joystick X / joystick Y / battery V (100k:100k divider) / USB-in V (charging detect, 100k:100k) |
| Spare | 4, 17, 21, 22, 23, 27 |

Buttons pull to GND and use the internal pull-ups. Power the joystick and the ADS1115 from **3.3 V**, not 5 V.

## Power
- Both LiPos have their own BMS. **Charge or measure both to within ~0.05 V before connecting them in parallel.** Don't add the old Nokia 1000 mAh cells: mixed age, capacity and resistance in parallel is a bad idea.
- Chain: cells (parallel) → TP4056 B+/B− → TP4056 OUT+ → **power switch (≥ 2 A)** → 5 V boost → Pi 5 V + TFT VCC + vibration VCC.
- Runtime with the TFT backlight: about **3.6 h worst case** (CPU 100% the whole time), **about 8 h typical**. To reach 4 h+ in the worst case, dim the backlight or turn off "think on their time".
- TP4056 charges at 1 A, so a full charge takes about 4.5–5 h. Playing while charging works, but the charger may not report "done". An optional load-sharing circuit (P-MOSFET + Schottky) fixes that later.

## Software impact
- Display: kernel `fbtft`/`mipi-dbi` driver for the ILI9341 (or direct SPI). The UI is drawn at 320×240 (pygame or Pillow) and pushed to the framebuffer.
- The Phase 0 session (stopped partway) left `src/chaipi/config.py`, `engine/`, `game/` and fonts. The engine and game logic are reusable. The OLED/voice hardware layer and the piece→file→rank `entry.py` flow are obsolete under this revision.
