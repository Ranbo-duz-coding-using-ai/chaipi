# 12 — Revision 3 (2026-10-23): parts check, audio, final pin map, transfer, image

**This replaces the GPIO plan and the power numbers in `history/11-revision-2.md`.** Everything else in doc 11 still stands. The device software and the SD-card image are described in `13-device-software.md`.

## What changed since revision 2
| Revision 2 | Revision 3 |
|---|---|
| No audio | **I2S amplifier (MAX98357A) + small speaker**, for YouTube Shorts, game sound and move clicks |
| Backlight on GPIO 18, Tab on 19, joystick press on 20 | I2S needs GPIO 18/19/20/21, so **backlight moves to 13, buttons move** (table below) |
| 2× 2000 mAh | 2× 2000 mAh now, **maybe one 6000 mAh** later. Both work, see Power |
| Extras = puzzles | **Extras tab**: games (Dhoom, Rickshaw Rush, Blocks, …), tools (scientific calculator, graphing, equation solver), chess extras, YouTube Shorts, your own Python apps |
| Phone/Mac clients for transfer | **Transfer over ChAIpi's own Wi-Fi**: a hotspot and a web page any phone or laptop opens. USB drive mode and the display's microSD slot are the backups |
| Flash stock Pi OS | **Custom ChAIpi image** (pi-gen). See doc 13 |

## Core parts
The parts ChAIpi is designed around, and what to watch out for with each.

| Part | Verdict | Notes |
|---|---|---|
| 2.8" ILI9341 SPI TFT (320×240) | ✅ Main display | Runs on 3.3 V logic. Its microSD slot is optional (SD card mode). Ignore the touch pins |
| 1.8" ST7735 | Spare | Not used. The UI also runs at 160×128 if you ever swap |
| TP4056 USB-C ×4 | ✅ | Use one. The 1 A charge rate stays as is; don't change Rprog |
| DS3231 RTC | ✅ | Power it from **3.3 V**. If it is the ZS-042 board, remove its 200 Ω charging resistor before fitting a CR2032 |
| PS2 joysticks ×6 | ✅ | Through the ADS1115. Power from **3.3 V** |
| ADS1115 | ✅ | Address 0x48 (ADDR to GND). Also measures battery and USB voltage |
| MT3608 boost ×2 | ✅ with care | **Set 5.1 V with a multimeter before connecting the Pi.** Good for about 1 A. Add a 470–1000 µF capacitor on its output. If `vcgencmd get_throttled` ever reports under-voltage, swap it for a 2 A+ synchronous boost |
| MOTVCM 5 V vibration ×2 | ✅ | It has its own driver transistor. VCC 5 V, IN from GPIO 12 |
| Mini rocker switch | ✅ | On the battery side. Peak is about 1.3 A, well inside its rating |
| PiBOX heatsink | ✅ | Needed: Stockfish runs all four cores at 100% |
| Resistor kit | ✅ | 100 k pairs for the two voltage dividers |
| 2× 2000 mAh LiPo with BMS | ✅ | Match voltages within 0.05 V before joining them in parallel. Don't mix in older or different cells |

## Also needed
Small parts the core list doesn't cover, plus the optional extras.

| # | Part | Why | Needed? |
|---|---|---|---|
| 1 | **6 tactile buttons** (6×6 mm or 12×12 mm, with caps) | Confirm, Backspace, Esc, Tab, Menu, Fn | **Yes** |
| 2 | **CR2032 coin cell** | Keeps the RTC clock running when the power is off | **Yes** |
| 3 | **Wiring kit**: perfboard, 26–28 AWG silicone wire, JST-PH 2.0 connectors, a 2×20 male header (if your Pi has none) | Hooking everything up | **Yes** |
| 4 | **470–1000 µF 10 V electrolytic capacitor** | Steadies the 5 V rail for the Pi | **Yes** (a few rupees) |
| 5 | **MAX98357A I2S amplifier board** + **8 Ω 1–2 W speaker** (28 mm round or 2030 box) | Sound for Shorts and games | Only if you want sound |
| 6 | **USB-C female breakout with D+/D− pins** (16-pin, with 5.1 k CC resistors) + a spare micro-USB cable to cut | One USB-C port for charging **and** USB drive mode | Only for USB drive mode |
| 7 | **Female–female Dupont jumper wires** (a pack of 40) | Wire and test everything before soldering (docs/03) | Recommended, cheap |
| 8 | **S8550 PNP transistor + 1 kΩ resistor** | Only if the backlight test in docs/03 step 2 says the LED pin draws 20 mA or more | Only if needed |

You do **not** need a MAX17048 gauge. The ADS1115 already measures the battery.

## Final pin map (BCM numbering)
| Function | GPIO | Header pin |
|---|---|---|
| TFT SCK / MOSI / CS | 11 / 10 / 8 (CE0) | 23 / 19 / 24 |
| TFT DC / RESET | 25 / 24 | 22 / 18 |
| TFT backlight (LED), hardware PWM1 | 13 | 33 |
| TFT microSD: CS / MISO (optional) | 7 (CE1) / 9 | 26 / 21 |
| I2C SDA / SCL: ADS1115 0x48, DS3231 0x68 (EEPROM 0x57) | 2 / 3 | 3 / 5 |
| I2S to MAX98357A: BCLK / LRC / DIN | 18 / 19 / 21 | 12 / 35 / 40 |
| Confirm | 5 | 29 |
| Backspace | 6 | 31 |
| Esc | 16 | 36 |
| Tab | 26 | 37 |
| Menu | 23 | 16 |
| Fn | 17 | 11 |
| Joystick press (SW) | 27 | 13 |
| Vibration IN | 12 | 32 |
| Serial console TX / RX (keep free for debugging) | 14 / 15 | 8 / 10 |
| Spare | 4, 22 | 7, 15 |

GPIO 20 stays empty. The I2S block claims it as audio input even though the MAX98357A doesn't use it.

| ADS1115 input | Signal |
|---|---|
| A0 | Joystick VRx |
| A1 | Joystick VRy |
| A2 | Battery + through 100 k : 100 k (4.2 V → 2.1 V) |
| A3 | USB VBUS through 100 k : 100 k (5 V → 2.5 V). Shows the charger is plugged in |

- Buttons go between the GPIO and GND. The Pi's internal pull-ups are enough.
- The joystick, ADS1115, RTC and the TFT's VCC run on **3.3 V**. Use pin 1 or 17. The vibration module and the amplifier run on **5 V**.
- The MAX98357A's SD pin stays unconnected. The board's own pull-up selects mono (L+R)/2. Leave GAIN unconnected (9 dB), or tie it to VIN for 6 dB if the speaker is too loud.

## Power
```
LiPo (2× 2000 mAh in parallel, or 1× 6000 mAh)
  └─ TP4056 B+ / B−
        TP4056 OUT+ ── rocker switch ── MT3608 IN+   (MT3608 set to 5.1 V)
                                          MT3608 OUT+ ──┬─ Pi 5V (pin 2) + 470 µF cap
                                                        ├─ vibration VCC
                                                        └─ MAX98357A VIN
        Battery + ── 100k ──┬── 100k ── GND        (to ADS1115 A2)
USB-C VBUS ─ TP4056 IN+ and 100k ──┬── 100k ── GND (to ADS1115 A3)
```
| Battery | Worst case (engine at 100%, bright screen) | Typical play | Full charge at 1 A |
|---|---|---|---|
| 2× 2000 mAh | ~3.6 h | ~8 h | ~4.5–5 h |
| 1× 6000 mAh | ~5.4 h | ~11.8 h | ~6.5–7 h |

- Sound costs extra: about 0.3–0.6 W while a Short plays at a sensible volume. The software caps volume at 70% by default to keep peaks inside the MT3608's limit.
- **Low battery:** a warning shows at 20% and 10%. At about 3.35 V under load, ChAIpi saves everything and shuts down cleanly. That happens before the BMS cuts out.
- **Before flipping the switch off**, use Menu → Power off when you can. Games are saved after every move anyway, so a sudden cut costs at most the current move.

## USB-C for charging and data (optional, needs part 6)
Without part 6, the TP4056's own USB-C port charges and that's all.

With part 6:
- Wire the breakout's **VBUS** to TP4056 IN+ and **GND** to GND. Leave the TP4056's own port empty.
- Cut a micro-USB cable and plug it into the Pi's **USB** port (the inner one, not PWR). Wire **D+ (green)** and **D− (white)** to the breakout's D+ and D−, and **GND (black)** to GND.
- **Leave the red VBUS wire unconnected.** The Pi's data port VBUS is joined to its 5 V rail, so a computer would fight the boost converter.
- The Pi then acts as a USB device (`dwc2` in peripheral mode). In Settings → Transfer → USB drive mode, ChAIpi appears on a computer as a drive with `games`, `engines`, `apps` and `puzzles` folders.

## Transfer: how it works
1. Settings → Transfer → **Activate**. ChAIpi starts its own Wi-Fi network (`ChAIpi-XXXX`, a WPA2 password made at first boot, 2.4 GHz channel 6) at 192.168.4.1. In "home Wi-Fi" mode it uses your router instead.
2. A small web server starts. Every website name points to ChAIpi on its network, so most phones pop up the page on their own. If not, scan the second QR code or open **http://192.168.4.1** (or http://chaipi.local).
3. The page asks for the **4-digit PIN** shown on the screen. Five wrong tries locks it for a minute.
4. On the page you can download games (one `.txt` or all as one PGN), upload engines, Python apps and puzzle packs, back up and restore settings, and stop sharing.
5. Uploads land in `/data/chaipi/inbox` first. ChAIpi checks them before installing: an engine must be an ARM64 Linux program that answers `uci`, an app must be valid Python, and a puzzle pack must parse.
6. Transfer stops when you press Esc, leave the screen, or after the idle timeout (10 min by default). The hotspot and the web server are separate processes that exit, so the memory comes back.

## Sound and YouTube Shorts
- The amplifier shows up as an ALSA card. ChAIpi adds a software volume control because the MAX98357A has none.
- Shorts uses `yt-dlp` to search and get the stream, and `ffmpeg` with the Pi's hardware H.264 decoder. Video is 360p, scaled to fit, at up to 30 fps. ffmpeg plays the sound and hands frames to the UI.
- **Honest caveats:** YouTube's terms don't allow third-party players. YouTube also changes things often, so `yt-dlp` needs updating (Settings → System → Update yt-dlp) and may stop working for a while. Shorts needs a home Wi-Fi connection. While it plays, Stockfish is stopped to free memory.

## Open checks for bring-up (Phase 1)
- [ ] MT3608 at 5.1 V and no under-voltage (`vcgencmd get_throttled` = `0x0`) with Stockfish at 100% plus a Short playing
- [ ] TFT colours correct (if red and blue are swapped, toggle `bgr` in `config.txt`) and rotation correct (`rotate=90` or `270`)
- [ ] Joystick centre and direction (calibration runs at boot; swap axes in `chaipi.toml` if needed)
- [ ] Battery reading matches a multimeter within 0.03 V (tune `battery.divider` in `chaipi.toml`)
- [ ] RTC keeps time across a power cut
- [ ] Hotspot visible from an Android phone and an iPhone, and the page pops up
- [ ] Thermal: 10 minutes of analysis, CPU stays under 80 °C with the heatsink
