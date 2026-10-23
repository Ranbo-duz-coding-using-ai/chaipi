# 01 — Hardware & Shopping List

Prices are rough Oct-2026 estimates. ₹ prices are for Indian shops (Robu.in, Robocraze, Evelta, ThinkRobotics, Amazon.in). $ prices are for US shops (Adafruit, PiShop, Amazon). Check stock before ordering.

## Phase 1 kit (start software work with no soldering)

| # | Part | Qty | ≈ ₹ | ≈ $ | Notes |
|---|---|---|---|---|---|
| 1 | **Raspberry Pi Zero 2 WH** (the "H" means the GPIO header comes pre-soldered) | 1 | 2,000–2,500 | 18 | If you can only find the Zero 2 W (no H), add a 2×20 male header (₹30) and solder 40 pins |
| 2 | **Waveshare 1.3inch OLED HAT** (SKU 13890): SH1106 128×64, 5-way joystick, 3 keys | 1 | 1,200–1,700 | 15 | Plugs straight onto the header. This is the screen *and* all 8 buttons |
| 3 | **Mini USB microphone** (the tiny stub type, e.g. Adafruit #3367 or any "USB mini mic for Raspberry Pi") | 1 | 300–600 | 6 | Plug-and-play on Linux, no drivers |
| 4 | **Micro-USB OTG adapter** (micro-USB male → USB-A female), the shortest you can find | 1 | 80–150 | 3 | The Pi's data port is micro-USB |
| 5 | **microSD card, 32 GB, A1 or A2** (SanDisk Extreme / High Endurance, Samsung EVO Plus) | 1 | 350–550 | 8 | 16 GB works, 32 GB leaves room for endgame tablebases later |
| 6 | **Low-profile heatsink** for the Zero 2 W, ≤ 6 mm tall, with thermal tape | 1 | 60–150 | 2 | **Required.** Stockfish runs all 4 cores at 100%, and the HAT sits on top of the chip |
| 7 | Any phone **power bank** + micro-USB cable | – | (you have one) | – | Temporary power for Phase 1–4 |
| 8 | 5 V / 2.5 A micro-USB power supply (optional, for the desk) | 1 | 400 | 8 | The official Pi supply is ideal |

**Phase 1 subtotal: about ₹4,000–5,500 / $50.**

## Phase 5 kit (internal battery, switch, extras)

| # | Part | Qty | ≈ ₹ | ≈ $ | Notes |
|---|---|---|---|---|---|
| 9 | **Adafruit PowerBoost 1000C** (#2465) | 1 | 1,800–2,600 | 20 | LiPo charger and 5 V boost in one. **Load-sharing**, so it can charge while running without rebooting the Pi. Has an EN pin for the power switch |
| 10 | **3.7 V LiPo, 5000 mAh**, with protection circuit (PCM), **JST-PH 2.0 mm** connector, red wire = + | 1 | 700–1,400 | 15 | Typical size about 10 × 50 × 90 mm. **Check the JST polarity matches Adafruit's** (many cheap packs are reversed, which can destroy the board). Alternative: Adafruit #353 (6600 mAh, 3× 18650) or #354 (4400 mAh) |
| 11 | **Adafruit MAX17048 LiPo fuel gauge** (#5580) | 1 | 500–900 | 6 | Accurate battery % over I2C (address 0x36). Sits in-line on the battery JST |
| 12 | **DS3231 RTC mini module** (the small Pi-sized one) with CR1220 / LIR2032 cell | 1 | 150–350 | 4 | The Pi has no clock. Without this, game dates are wrong when there's no WiFi. I2C address 0x68 |
| 13 | **Coin vibration motor module** (3-pin: VCC / GND / IN, transistor on board) | 1 | 60–150 | 2 | Silent buzz when the move is ready, so you don't have to keep looking at the screen |
| 14 | **SPDT slide switch** (SS12D00 or a panel-mount mini slide switch) | 1 | 10–40 | 1 | Power on/off (wired to the PowerBoost EN pin) |
| 15 | **Short USB-A → micro-USB cable**, 10–15 cm (or a right-angle one) | 1 | 100–200 | 3 | PowerBoost USB-A output → Pi PWR IN. No soldering on the Pi side |
| 16 | 2× JST-PH 2-pin extension leads, 28–30 AWG silicone wire, heat-shrink, Kapton tape | – | 200 | 5 | For tidy internal wiring |
| 17 | Enclosure: 3D print (PLA/PETG) or a ~100 × 65 × 35 mm ABS project box | 1 | 300–800 | 5–10 | See [10-enclosure.md](10-enclosure.md) |

**Phase 5 subtotal: about ₹3,800–7,200 / $65–75.**

**Grand total: about ₹8,000–12,500 / $110–125.**

## Tools you'll need
- Soldering iron + solder (about 15 joints in total: the PowerBoost USB-A jack, the switch, and the extras to the Pi header's underside)
- Small Phillips screwdriver, side cutters, tweezers
- A multimeter (useful for checking battery polarity and the 5 V rail)
- Your Mac with an SD-card reader (or a ₹200 USB reader)

## Why these parts

**Pi Zero 2 W.** This is the smallest Pi that runs 64-bit Linux, which Stockfish's ARM64 build needs. It has 4 cores, and Stockfish uses all of them. The original Pi Zero (single-core ARMv6) can't do this.

**Waveshare 1.3" OLED HAT.** It has the display, joystick, and 3 keys on one board with zero wiring. Pin map:

| Function | BCM GPIO |
|---|---|
| KEY1 (→ MIC) | 21 |
| KEY2 (→ BACK) | 20 |
| KEY3 (→ MENU) | 16 |
| Joystick UP / DOWN / LEFT / RIGHT / PRESS | 6 / 19 / 5 / 26 / 13 |
| OLED SPI: SCLK / MOSI / CS / DC / RST | 11 / 10 / 8 / 24 / 25 |

The buttons pull to GND, and software turns on the internal pull-ups.

**USB mic instead of an I2S MEMS mic.** An I2S mic (INMP441) needs GPIO 18/19/20, but the HAT already uses 19 and 20. A USB mic also needs no kernel overlay hacking and records clean 16 kHz audio.

**PowerBoost 1000C instead of a cheap TP4056 + MT3608 / IP5306 board.**
- Cheap IP5306 boards briefly cut the output when you plug the charger in, which reboots the Pi and risks SD corruption.
- TP4056 + MT3608 can't charge and run at the same time properly, and the MT3608 is noisy, which the mic picks up.
- The PowerBoost gives clean 5.2 V at 1 A continuous (the Pi peaks around 0.6 A), with proper load sharing.

**Why not a PiSugar 3?** It's elegant (pogo pins, built-in RTC), but its 1200 mAh cell gives only about 1.3 h at full Stockfish load. A PiSugar with a bigger cell is an acceptable alternative if it ships to you; see [02-power.md](02-power.md) for the runtime math.

## Alternatives

| Want | Swap |
|---|---|
| Bigger, easier-to-read screen | 2.42" SSD1309 128×64 OLED module (SPI). Same resolution, same code, about 60 × 37 mm. You then need discrete buttons (build B below) |
| Cheaper | Skip the fuel gauge (use a voltage estimate), RTC, and motor: saves about ₹1,000. Use a generic 5000 mAh power-bank board (accept the reboot-on-plug-in quirk) |
| USB-C charging | A USB-C (female) → micro-USB (male) adapter into the PowerBoost, or a panel-mount USB-C breakout wired to the PowerBoost's USB pads |
| Clean push-button power (no slide switch) | Pimoroni OnOff SHIM-style soft power: press to boot, long-press for a clean shutdown and power cut. More complex; v2 |

## Build B (v2 option): custom buttons, I2S mic, any layout

Skip the HAT and use a 1.3" SH1106 **I2C** module plus 8 separate 12 × 12 mm tactile buttons (with caps), laid out however you want in a custom case. The I2S mic then becomes possible.

| Function | BCM GPIO | | Function | BCM GPIO |
|---|---|---|---|---|
| UP | 17 | | OK | 24 |
| DOWN | 27 | | BACK | 25 |
| LEFT | 22 | | MIC | 5 |
| RIGHT | 23 | | MENU | 6 |
| I2S BCLK | 18 | | I2S LRCLK | 19 |
| I2S DIN (from INMP441 SD) | 20 | | Haptic | 12 |
| OLED / RTC / gauge (I2C) | 2 (SDA), 3 (SCL) | | | |

All pins live in `config/chaipi.toml`, so switching from build A to build B is a config change, not a rewrite.
