# 08 — OS Setup: what to flash, and how to hand over SSH

## What to flash
**Raspberry Pi OS Lite (64-bit)**, the latest release offered by Raspberry Pi Imager. That's "Lite": no desktop. The 512 MB of RAM is needed for Stockfish and Vosk.

- Not the 32-bit version: the Stockfish ARM64 build needs 64-bit.
- Not the Desktop version: it wastes RAM and boot time.

## Steps (about 10 minutes)
1. Install **Raspberry Pi Imager** on the Mac (`brew install --cask raspberry-pi-imager`, or download it from raspberrypi.com).
2. Put the microSD card in the Mac.
3. In Imager:
   - **Device:** Raspberry Pi Zero 2 W
   - **OS:** Raspberry Pi OS (other) → **Raspberry Pi OS Lite (64-bit)**
   - **Storage:** your microSD card (double-check it's the right disk)
4. When Imager offers **OS customisation**, fill in:

   | Setting | Value |
   |---|---|
   | Hostname | `chaipi` |
   | Username | `pi` |
   | Password | anything you like. You keep it; Claude never needs it |
   | WiFi SSID / password | your home WiFi. **It must be 2.4 GHz**: the Zero 2 W has no 5 GHz radio. A phone hotspot set to 2.4 GHz also works |
   | WiFi country | `IN` (or wherever you are) |
   | Time zone / keyboard | `Asia/Kolkata` / `us` (or yours) |
   | **SSH** | Enable SSH → **"Allow public-key authentication only"** → paste your Mac's public key (see below) |
   | Telemetry | your choice (off is fine) |

   **Your Mac's public key:** you already have one at `~/.ssh/id_ed25519.pub`. Copy it to the clipboard by running this in Terminal, then paste it into Imager:
   ```bash
   pbcopy < ~/.ssh/id_ed25519.pub
   ```
   (The `.pub` file is the *public* half and safe to paste. Never share the file without `.pub`.)
5. Write the card, eject it, and put it in the Pi.
6. Power the Pi from the **PWR IN** port (the micro-USB at the board's edge), with the HAT already plugged on. **The first boot takes 2–4 minutes**: it resizes the card and reboots once. The OLED stays blank until our software is installed; that's normal.

## Check it works (from the Mac)
```bash
ping -c 3 chaipi.local
```
```bash
ssh pi@chaipi.local 'uname -m; cat /etc/os-release | head -2; free -m'
```
You should see `aarch64`, the Raspberry Pi OS / Debian version, and about 420–450 MB of total memory.

If `chaipi.local` doesn't resolve, find the Pi's IP in your router's device list (or your phone hotspot's connected devices) and use `ssh pi@<ip>`.

**That's the handover.** Then open a Claude session in this folder and say *"ChAIpi: start Phase 1"*.

## What Claude does next over SSH (`tools/provision.sh`, safe to re-run)
1. `apt update && apt full-upgrade`, then install: `python3-venv python3-gpiozero python3-lgpio python3-rpi-lgpio python3-pil python3-numpy python3-smbus2 libportaudio2 alsa-utils i2c-tools fonts-dejavu-core git stress-ng`
2. Add the `system/config.txt.snippet` lines to `/boot/firmware/config.txt`:
   ```
   dtparam=spi=on
   dtparam=i2c_arm=on
   dtoverlay=i2c-rtc,ds3231          # Phase 5, once the RTC is wired
   dtoverlay=disable-bt
   gpu_mem=16
   camera_auto_detect=0
   display_auto_detect=0
   gpio=5,6,13,16,19,20,21,26=ip,pu  # HAT button pull-ups from boot
   # and comment out dtoverlay=vc4-kms-v3d (frees RAM; there's no HDMI screen)
   ```
3. Set up zram swap. Disable `bluetooth`, `hciuart`, `ModemManager`, `triggerhappy`, `NetworkManager-wait-online`.
4. Download **Stockfish 19** (`stockfish-linux-arm64-universal.tar.gz`) to `/opt/chaipi/engine/` and run `bench`.
5. Download the **Vosk** models (`vosk-model-small-en-in-0.4`, `vosk-model-small-en-us-0.15`) to `/opt/chaipi/models/`.
6. Create the venv (`--system-site-packages`) and `pip install chess luma.oled vosk sounddevice tomli-w`.
7. Install `system/asound.conf` (USB mic as the default capture device), `system/chaipi.service`, and the sudoers rule for poweroff/reboot.
8. Create `/data/chaipi/{games,logs}`, then deploy `src/` and start the service.

## Later (Phase 6): hardening for the hard-cut power switch
- Turn on the **read-only root (overlayfs)** and move `/data` to its **own ext4 partition**. This most likely means one re-flash so the card can be partitioned before the root filesystem expands. The exact method depends on the Pi OS version at that point, and Claude will check it then.
- Because `provision.sh` rebuilds everything, a re-flash costs about 20 minutes. Copy your games off first (`scp`, or the WiFi export page).
- The alternative, if you'd rather never re-flash: keep root read-write and rely on atomic saves + ext4 journaling + a good card (SanDisk High Endurance) + clean auto-shutdown on low battery.
