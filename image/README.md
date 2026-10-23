# The ChAIpi SD card

ChAIpi runs on Raspberry Pi OS Lite 64-bit (Debian 13 "trixie") with the ChAIpi software on top (docs/13). There are three ways to get there, and each ends with the same system.

## A. Download the image (easiest)
1. From the repository's **Releases** page, download `<date>-chaipi.img.xz`. It's about 850 MB. Don't unzip it: Imager reads it as it is. `SHA256SUMS` is there if you want to check the download.
2. Open [Raspberry Pi Imager](https://www.raspberrypi.com/software/):
   - **Choose Device** → Raspberry Pi Zero 2 W
   - **Choose OS** → scroll to the bottom → **Use Custom** → pick the `.img.xz` file
   - **Choose Storage** → your microSD card (8 GB or more)
   - **Next** → **No** when it asks about OS customisation (the image ignores it) → **Yes** to erase and write
3. Add the optional files below, then boot.

The published image has **no SSH key and no known password** in it, so it's the same for everyone. You add your own key with `chaipi-ssh.txt`.

## B. Plain Raspberry Pi OS + the installer over SSH
1. Raspberry Pi Imager → Raspberry Pi Zero 2 W → **Raspberry Pi OS Lite (64-bit)**. In OS customisation: hostname `chaipi`, user `pi`, your Wi-Fi, and SSH with your public key.
2. Boot the Pi. Then, from a clone of this repository:
   ```bash
   rsync -a --exclude node_modules --exclude .venv --exclude image/work ./ pi@chaipi.local:chaipi-src/
   ```
   ```bash
   ssh pi@chaipi.local 'sudo bash chaipi-src/image/install.sh && sudo reboot'
   ```
   Running the same two commands again later updates the software. Games and settings in `/data/chaipi` stay.

## C. Build the image yourself
- **On GitHub:** fork the repository, then Actions tab → **ChAIpi image** → Run workflow. It takes about an hour, runs the tests first, and publishes a release with the image and the emulator. A release is used because build artifacts are capped at 500 MB on free private repositories.
- **On a computer with Docker:** `./image/build.sh` needs Docker, about 25 GB free and a good connection. The result is in `image/deploy/`. To make a private image that already trusts your key: `CHAIPI_SSH_KEY="$(cat ~/.ssh/id_ed25519.pub)" ./image/build.sh`. The folder path can't contain spaces (set `CHAIPI_WORK=/some/path` if yours does).

## Files on the boot partition
After writing the card, take it out and put it back in. A drive called `bootfs` appears. Put these plain-text files on it before the first boot (on a Mac, TextEdit → Format → Make Plain Text):

| File | What it does |
|---|---|
| `chaipi-wifi.txt` | Joins your Wi-Fi without using the buttons. Lines: `ssid = …`, `password = …` (leave it out for an open network), `country = IN` (your two-letter country code), `timezone = Asia/Kolkata` (your [time zone name](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)) |
| `chaipi-ssh.txt` | Your SSH public key, one per line (for example the contents of `~/.ssh/id_ed25519.pub`). Lets you `ssh pi@chaipi.local` |

ChAIpi reads them at boot, applies them, and deletes them. You can add them again later to change Wi-Fi or add another key. After the first boot you can also use Settings → Wi-Fi on the device.

## First boot
- The first boot takes a minute or two longer: it grows the system to fill the card and makes the Transfer hotspot `ChAIpi-XXXX` with its own password.
- SSH: `ssh pi@chaipi.local`. Only keys work, and `sudo` needs no password.
- No buttons wired yet? `chaipi-keys` over SSH drives the UI from your keyboard.
- Logs: `journalctl -u chaipi-ui -u chaipi-input -u chaipi-boot -b`.
- Time zone later: `sudo timedatectl set-timezone Area/City`.

## What the image changes (all in `install.sh`)
- Packages: Node.js, ffmpeg, NetworkManager, avahi, Python GPIO/I2C/Pillow/numpy, mtools.
- `config.txt`: SPI, I2C at 400 kHz, the ILI9341 (`fbtft`, DC 25, RESET 24, landscape), backlight PWM on GPIO13, DS3231 RTC, MAX98357A, USB device mode, Bluetooth off, serial console on GPIO14/15. See `files/config-chaipi.txt`.
- `cmdline.txt`: boot messages go to the serial port only, so the screen stays clean.
- User `chaipi` runs the UI and the input daemon. polkit lets it manage Wi-Fi and power off. sudo lets it run exactly one script, `chaipi-media`, for USB and the SD slot. Port 80 opens without root for the transfer page.
- Services: `chaipi-boot`, `chaipi-input`, `chaipi-ui`, and an hourly RTC sync.
- SSH: keys only, in the image build (`/etc/ssh/sshd_config.d/10-chaipi-keys-only.conf`). Installing over SSH (B) leaves your SSH settings alone.
- Stockfish 19: the official ARM64 build. If that file isn't on the release, it's compiled from the `sf_19` source.
- Defaults: hostname `chaipi`, user `pi`, locale `en_GB` (day-first dates), time zone Asia/Kolkata and Wi-Fi country IN until you set your own, SSH with keys only.

## Files here
| File | |
|---|---|
| `install.sh` | the installer (used by the image build and over SSH) |
| `build.sh` | pi-gen image build (Docker) |
| `pigen.config` | pi-gen settings: hostname, user, locale, time zone, Wi-Fi country, SSH on |
| `stage-chaipi/` | the pi-gen stage that runs `install.sh` inside the image |
| `files/` | systemd units, polkit, sudoers, sysctl, captive DNS, udev, the `config.txt` block |
| `../.github/workflows/chaipi-image.yml` | the GitHub Actions build and release |

**Status:** the image builds, and its log shows every install step completing. It hasn't booted on real hardware yet. That first boot is Phase 1 in docs/13.
