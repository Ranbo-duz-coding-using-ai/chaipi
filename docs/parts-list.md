# Parts list

Everything for one ChAIpi, grouped by job. **Required** parts are needed for a working device, **Recommended** ones make the build safer or easier, and **Optional** ones add features. The pitfalls of each part are in [12-revision-3.md](12-revision-3.md), and how it all connects is in [03-wiring.md](03-wiring.md).

## Brain and screen
| Qty | Part | Look for | Used for | |
|---|---|---|---|---|
| 1 | Raspberry Pi Zero 2 W | The **WH** version has the 40-pin header already soldered | Everything | Required |
| 1 | Heatsink for the Pi Zero 2 W | Stick-on or clip-on | Stockfish runs all four cores at 100% | Required |
| 1 | microSD card | 16–32 GB, A1 or A2, a known brand | The system and your games | Required |
| 1 | 2.8" ILI9341 SPI TFT, 320×240 | The common red-board module with a 14-pin header. Touch pins stay unused | The screen | Required |

## Controls
| Qty | Part | Look for | Used for | |
|---|---|---|---|---|
| 1 | PS2-style analog joystick module | X, Y and a press switch (KY-023 type) | Moving the cursor | Required |
| 1 | ADS1115 16-bit ADC module | I2C | Reads the joystick, the battery and USB voltage | Required |
| 6 | Tactile push buttons + caps | 6×6 mm or 12×12 mm | Confirm, Undo, Esc, Tab, Menu, Fn | Required |

## Power
| Qty | Part | Look for | Used for | |
|---|---|---|---|---|
| 2 | 3.7 V 2000 mAh LiPo with BMS | Same make and age. Or one 6000 mAh cell instead | The battery | Required |
| 1 | TP4056 USB-C charger board | The version **with protection** (OUT+ / OUT− pads) | Charging | Required |
| 1 | MT3608 boost converter | Adjustable. **Set it to 5.1 V before connecting the Pi** | 3.7 V → 5 V | Required |
| 1 | 470–1000 µF 10 V electrolytic capacitor | | Steadies the Pi's 5 V | Required |
| 1 | Mini rocker switch | 2 A or more | Power on/off | Required |
| 4 | 100 kΩ resistors | 1% if you have them | Battery and USB voltage dividers | Required |
| 1 | Resettable fuse (PTC), about 2 A hold | Through-hole or inline | In the battery + lead, in case a wire shorts | Recommended |

## Clock and feedback
| Qty | Part | Look for | Used for | |
|---|---|---|---|---|
| 1 | DS3231 RTC module | On a ZS-042 board, remove its 200 Ω charging resistor before fitting the coin cell | Correct dates on saved games | Required |
| 1 | CR2032 coin cell | | Keeps the clock running when off | Required |
| 1 | 5 V vibration motor module | With its own driver transistor (VCC, GND, IN) | Buzzes when a move is ready | Optional |

## Sound and USB (optional)
| Qty | Part | Look for | Used for | |
|---|---|---|---|---|
| 1 | MAX98357A I2S amplifier board | | Sound for Shorts and games | Optional |
| 1 | 8 Ω 1–2 W speaker | 28 mm round, or a 2030 box speaker | | Optional |
| 1 | USB-C female breakout with D+/D− pads | 16-pin, with 5.1 kΩ CC resistors | One port for charging **and** USB drive mode | Optional |
| 1 | Spare micro-USB cable to cut up | | Data lines to the Pi's USB port | Optional |
| 1 | S8550 PNP transistor + 1 kΩ resistor | | Only if the backlight test in docs/03 step 2 reads 20 mA or more | If needed |

## Wiring and assembly
| Qty | Part | Used for | |
|---|---|---|---|
| 1 | Perfboard (about 5×7 cm) | Mounting the small boards | Required |
| 1 | 26–28 AWG silicone wire, a few colours | Wiring | Required |
| a few | JST-PH 2.0 connectors | Unplugging the battery and screen | Required |
| 1 | 2×20 male pin header | Only if your Pi has none (not a WH) | If needed |
| 40 | Female–female Dupont jumper wires | Testing each step before soldering | Recommended |
| 1 | Heat-shrink tubing assortment | Insulating joints, especially on the battery side | Recommended |
| 1 | Kapton tape and double-sided foam tape | Insulating and holding the battery and boards | Recommended |
| 4 | M2.5 nylon standoffs and screws | Mounting the Pi in the case | Recommended |

## Tools
| Tool | Why | |
|---|---|---|
| Multimeter | Setting the MT3608 to 5.1 V, and every test in docs/03 | Required |
| Temperature-controlled soldering iron, rosin-core solder (0.6–0.8 mm), flux, desoldering wick | Header, perfboard, battery leads | Required |
| Wire stripper and flush cutters | | Required |
| microSD card reader | Flashing the image, if your computer has no card slot | If needed |
| 5 V USB-C charger and cable | Charging | Required |
| 3.3 V USB-to-serial adapter (CP2102 or CH340) | The serial console on GPIO 14/15, if the Pi won't show up on Wi-Fi | Optional |

## Case
The case isn't designed yet. The 3D-printable logo badge for it is in [enclosure/logo-badge](../enclosure/logo-badge).

You do **not** need a battery fuel-gauge board (MAX17048): the ADS1115 measures the battery.
