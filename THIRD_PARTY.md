# Third-party software

ChAIpi's own code is under the GPL-3.0-or-later ([LICENSE](LICENSE)). It uses the following projects. The ones marked "image" are downloaded and installed when the SD-card image is built. They are not stored in this repository.

| Project | Used for | Licence | Where |
|---|---|---|---|
| [Stockfish 19](https://github.com/official-stockfish/Stockfish) | the chess engine, including its built-in NNUE network | GPL-3.0 | image: the official `stockfish-linux-arm64-universal` build of tag `sf_19`. Source: https://github.com/official-stockfish/Stockfish/tree/sf_19 |
| [Raspberry Pi OS Lite](https://www.raspberrypi.com/software/) (Debian 13) | the operating system | many, mostly GPL / LGPL / BSD / MIT (see `/usr/share/doc/*/copyright` on the device) | image |
| [pi-gen](https://github.com/RPi-Distro/pi-gen) | builds the image | BSD-3-Clause | build only |
| [Node.js](https://nodejs.org/) | runs the OS on the device | MIT | image (Debian package) |
| [@napi-rs/canvas](https://github.com/Brooooooklyn/canvas) | draws the screen (Skia) | MIT | image (npm) |
| [qrcode](https://github.com/soldair/node-qrcode) | QR codes on the Transfer screen | MIT | image (npm) |
| [python-chess](https://github.com/niklasf/python-chess) | reading Lichess puzzle files | GPL-3.0-or-later | image (Debian package or pip) |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | YouTube Shorts | Unlicense | image (pip) |
| [FFmpeg](https://ffmpeg.org/) | video and sound for Shorts | LGPL-2.1+ / GPL-2.0+ | image (Debian package) |
| [gpiozero](https://github.com/gpiozero/gpiozero), lgpio, smbus2 | buttons, joystick ADC, vibration, backlight | BSD-3-Clause, Unlicense, MIT | image (Debian packages) |
| [NetworkManager](https://networkmanager.dev/), dnsmasq, Avahi | Wi-Fi, the Transfer hotspot, `chaipi.local` | GPL-2.0+ / LGPL-2.1+ | image (Debian packages) |

## Fonts

All under the [SIL Open Font License 1.1](https://openfontlicense.org/). The licence texts are next to the fonts in [device/fonts](device/fonts).

| Font | By | Used for |
|---|---|---|
| [Atkinson Hyperlegible](https://www.brailleinstitute.org/freefont/) | Braille Institute of America | text |
| [JetBrains Mono](https://www.jetbrains.com/lp/mono/) | JetBrains | numbers, clocks, move lists |
| [Unbounded](https://github.com/googlefonts/unbounded) | The Unbounded Project Authors | headings and the logo |
| [Noto Sans Symbols 2](https://notofonts.github.io/) | Google | chess pieces |

## Data you can add

- [Lichess puzzle database](https://database.lichess.org/#puzzles): CC0. ChAIpi imports the mate-in-one puzzles from it if you upload the CSV.
- Engines and apps you upload keep their own licences.
