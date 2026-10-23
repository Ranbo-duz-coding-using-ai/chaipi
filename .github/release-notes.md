**ChAIpi {VERSION}**: the SD-card image for a Raspberry Pi Zero 2 W, and the emulator.

> **Pre-release: not yet tested on real hardware.** The image builds and its install steps all completed, but it hasn't booted on a ChAIpi yet. Please report what you find.

| File | What it is |
|---|---|
| `…-chaipi.img.xz` | The SD-card image: Raspberry Pi OS Lite 64-bit (Debian 13) + ChAIpi + Stockfish 19. No SSH key or known password inside |
| `chaipi-emulator.html` | The ChAIpi OS in your browser. Download it and double-click. Works offline |
| `SHA256SUMS` | Checksums for the image |

### Flash it
1. Open [Raspberry Pi Imager](https://www.raspberrypi.com/software/). **Choose Device** → Raspberry Pi Zero 2 W · **Choose OS** → Use Custom → the `.img.xz` (don't unzip it) · **Choose Storage** → your microSD card → **Next** → **No** to OS customisation → **Yes**.
2. Optional: on the card's `bootfs` drive, add `chaipi-wifi.txt` (`ssid = …`, `password = …`, `country = …`, `timezone = …`) and/or `chaipi-ssh.txt` (your SSH public key). ChAIpi applies them at the first boot and deletes them.
3. Boot. SSH, if you added a key: `ssh pi@chaipi.local`.

Full instructions: [image/README.md](https://github.com/Ranbo-duz-coding-using-ai/chaipi/blob/main/image/README.md). Hardware and wiring: [docs](https://github.com/Ranbo-duz-coding-using-ai/chaipi/tree/main/docs).

### Licences
ChAIpi is GPL-3.0-or-later. The image includes Stockfish 19 (GPL-3.0); its source is at https://github.com/official-stockfish/Stockfish/tree/sf_19. Everything else is listed in [THIRD_PARTY.md](https://github.com/Ranbo-duz-coding-using-ai/chaipi/blob/main/THIRD_PARTY.md).

Built from {SHA} by GitHub Actions run {RUN}. Created by Ranbir Dhall.
