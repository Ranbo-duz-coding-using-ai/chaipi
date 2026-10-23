# 02 — Power & Battery

## Short answer
**Get a 3.7 V, 5000 mAh LiPo (about 18.5 Wh).** It runs about **4.8 hours even if Stockfish keeps all 4 cores at 100% the entire time**, and about **9–12 hours** in normal use. That covers your 3–4 hour target with margin for battery ageing and cold rooms.

## Where the power goes (measured at 5 V)

| Load | Power | Source / note |
|---|---|---|
| Pi Zero 2 W idle (WiFi off, BT off, no HDMI) | ~0.5 W (100 mA) | Jeff Geerling ~100 mA; CNX ~120 mA |
| Pi Zero 2 W, 4 cores flat out (Stockfish search) | ~2.8 W (500–580 mA) | Geerling ~500 mA; Tom's Hardware 580 mA |
| 1.3" OLED (typical screen) | ~0.08 W | Mostly black screens draw very little |
| USB mini mic (plugged in) | ~0.15 W | 20–50 mA |
| WiFi connected and idle | +0.15–0.25 W | Off by default during games |
| Fuel gauge + RTC + vibration motor (average) | < 0.01 W | |
| Optional overclock to 1.2 GHz | +~20% under load | Only if it passes the Phase 1 tests |

Two losses between the battery and the Pi: the boost converter is about **87%** efficient, and you can only safely use about **90%** of a LiPo's rated capacity.

## Three usage scenarios

| Scenario | What's happening | Pi-side power | Battery-side power |
|---|---|---|---|
| **A — Worst case** | "Think on opponent's time" ON, so the engine searches nonstop | 3.03 W | **3.48 W** |
| **B — Typical** | Pondering off, Deep/Medium presets, engine busy ~25% of the time | 1.31 W | **1.51 W** |
| **C — Idle** | Sitting on a menu | 0.73 W | **0.84 W** |

## Runtime table

| Battery (3.7 V) | Usable energy | A — worst | B — typical | C — idle |
|---|---|---|---|---|
| 1200 mAh (PiSugar 3) | 4.0 Wh | 1.1 h | 2.6 h | 4.8 h |
| 2000 mAh | 6.7 Wh | 1.9 h | 4.4 h | 7.9 h |
| 3000 mAh | 10.0 Wh | 2.9 h | 6.6 h | 11.9 h |
| 4400 mAh (Adafruit #354) | 14.7 Wh | 4.2 h | 9.7 h | 17.4 h |
| **5000 mAh (recommended)** | **16.7 Wh** | **4.8 h** | **11.0 h** | **19.8 h** |
| 6600 mAh (Adafruit #353) | 22.0 Wh | 6.3 h | 14.6 h | 26 h |

Formula: `hours = mAh × 3.7 V × 0.9 ÷ 1000 ÷ battery-side W`.

**Minimum viable:** 3000 mAh is enough if you leave "think on opponent's time" off.

## Charging
- PowerBoost 1000C charges at up to **1 A**, so 5000 mAh takes about **5.5–6.5 h** from empty. Charge overnight, or play while charging (load sharing handles it).
- Use any 5 V / 2 A phone charger with a micro-USB cable. For USB-C, use a USB-C-to-micro-USB adapter.
- The PowerBoost's yellow (charging) and green (done) LEDs show through a light-pipe hole in the case. The software also shows ⚡ next to the battery % when the MAX17048 reports a positive charge rate.

## Power switch behaviour
The slide switch connects the PowerBoost **EN pin to GND** when OFF, which disables the 5 V boost. When ON, EN floats high and the Pi boots.
- Charging still works with the switch OFF.
- **The switch is a hard power cut.** Software protects against that in three ways:
  1. **Every move is saved immediately** with an atomic write + `fsync`. A power cut loses at most the move you were typing.
  2. **The read-only root filesystem** (overlayfs) is turned on once development is finished. The OS can't be corrupted, and games live on a separate `/data` ext4 partition.
  3. **MENU → Shut down** does a clean shutdown and shows *"Safe to switch off"*. That's the polite way, but not required.

## Low-battery behaviour
| Battery % | Action |
|---|---|
| ≤ 20% | Battery icon blinks; "think on opponent's time" switches off automatically (setting) |
| ≤ 10% | Banner "Low battery — 10%"; one vibration pulse |
| ≤ 3% (or < 3.35 V) | Save game → "Battery empty — game saved" → clean `poweroff` |

Without the fuel gauge (budget build), software estimates the percentage from a lookup table. Don't wire the PowerBoost's LBO pin directly to a GPIO: it's pulled up to battery voltage (up to 4.2 V), which is above the Pi's 3.3 V limit.

## Speed vs. battery: settings that matter
| Setting | Effect |
|---|---|
| Think on opponent's time ON | Faster, deeper answers, but scenario A power |
| Think time 12 s vs 4 s | About 3× the energy per move |
| Overclock 1.2 GHz | About 20% more nodes per second, about 20% more power under load, more heat |
| WiFi ON | +0.2 W. Only turn it on to copy games or update the software |
| Screen sleep after 2 min | Small saving; mainly prevents OLED burn-in |

The CPU governor stays on the default `ondemand`: it jumps to full speed the instant Stockfish starts and idles low otherwise. `performance` would waste idle power without making searches any faster.
