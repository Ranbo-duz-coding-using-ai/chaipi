#!/bin/bash
# Installs ChAIpi onto Raspberry Pi OS Lite (64-bit, Bookworm or Trixie). The same script is used two ways:
#
#   1. Inside the image build (image/build.sh -> pi-gen stage-chaipi):   bash install.sh --chroot
#   2. On a Pi you flashed with plain Raspberry Pi OS Lite, over SSH:
#        rsync -a --exclude node_modules --exclude .venv "Project ChAIpi/" pi@chaipi.local:chaipi-src/
#        ssh pi@chaipi.local 'sudo bash chaipi-src/image/install.sh && sudo reboot'
#
# It is safe to run again: it updates the code and leaves your games and settings (/data/chaipi) alone.
set -euo pipefail

CHROOT=0
[ "${1:-}" = "--chroot" ] && CHROOT=1
SRC=$(cd "$(dirname "$0")/.." && pwd)
OPT=/opt/chaipi
BOOT=/boot/firmware
[ -d "$BOOT" ] || BOOT=/boot
log() { printf '\n== %s\n' "$*"; }
[ "$(id -u)" = 0 ] || { echo "Run as root (sudo)."; exit 1; }
[ "$(uname -m)" = aarch64 ] || { echo "This needs 64-bit Raspberry Pi OS (aarch64); found $(uname -m)."; exit 1; }
export DEBIAN_FRONTEND=noninteractive

# --------------------------------------------------------------------------------------------------
log "Packages"
apt-get update
apt-get install -y --no-install-recommends \
  nodejs npm python3 python3-venv python3-pip python3-pil python3-numpy python3-gpiozero \
  ffmpeg alsa-utils i2c-tools iw network-manager avahi-daemon mtools dosfstools \
  curl ca-certificates git xz-utils unzip fonts-dejavu-core fontconfig polkitd sudo
# Package names that differ between releases: install each one that exists.
for p in python3-lgpio python3-smbus2 python3-smbus python3-chess util-linux-extra exfatprogs; do
  apt-get install -y --no-install-recommends "$p" 2>/dev/null || echo "   (skipped $p: not in this release)"
done
NODE_MAJOR=$(node -p 'process.versions.node.split(".")[0]')
[ "$NODE_MAJOR" -ge 18 ] || { echo "Node.js $NODE_MAJOR is too old (need 18+)."; exit 1; }

# --------------------------------------------------------------------------------------------------
log "User and folders"
id chaipi >/dev/null 2>&1 || useradd --system --create-home --home-dir /var/lib/chaipi --shell /usr/sbin/nologin chaipi
for g in video input gpio i2c spi audio netdev render plugdev; do getent group "$g" >/dev/null && usermod -aG "$g" chaipi; done
install -d -m 755 "$OPT" "$OPT/bin" "$OPT/ui" "$OPT/engines" "$OPT/fonts" /etc/chaipi
install -d -o chaipi -g chaipi -m 755 /data /data/chaipi
for d in games engines apps puzzles inbox logs tmp usb appdata; do install -d -o chaipi -g chaipi -m 755 "/data/chaipi/$d"; done

# --------------------------------------------------------------------------------------------------
log "ChAIpi code"
rm -rf "$OPT/device.new"
mkdir -p "$OPT/device.new"
tar -C "$SRC/device" --exclude node_modules --exclude __pycache__ --exclude test -cf - . | tar -C "$OPT/device.new" -xf -
# keep already-installed npm packages if package.json didn't change
if [ -d "$OPT/device/ui/node_modules" ] && cmp -s "$OPT/device/ui/package.json" "$OPT/device.new/ui/package.json"; then
  mv "$OPT/device/ui/node_modules" "$OPT/device.new/ui/"
fi
rm -rf "$OPT/device"
mv "$OPT/device.new" "$OPT/device"
install -m 644 "$SRC/mockup/chaipi-os.html" "$OPT/ui/chaipi-os.html"
cp "$OPT"/device/fonts/* "$OPT/fonts/"
install -m 755 "$OPT/device/bin/chaipi-media" "$OPT/device/bin/chaipi-boot" "$OPT/bin/"
[ -f "$SRC/VERSION" ] && install -m 644 "$SRC/VERSION" "$OPT/VERSION"
[ -f /etc/chaipi/chaipi.toml ] || install -m 644 "$SRC/config/chaipi.example.toml" /etc/chaipi/chaipi.toml
install -m 644 "$SRC/config/chaipi.example.toml" /etc/chaipi/chaipi.example.toml

log "Node packages (canvas, QR codes)"
if [ ! -d "$OPT/device/ui/node_modules/@napi-rs" ]; then
  (cd "$OPT/device/ui" && npm install --omit=dev --no-audit --no-fund --loglevel=error)
fi
node -e "require('$OPT/device/ui/node_modules/@napi-rs/canvas'); require('$OPT/device/ui/node_modules/qrcode'); console.log('   canvas and qrcode load')"

# --------------------------------------------------------------------------------------------------
log "Stockfish 19"
SF=$OPT/engines/sf19
sf_ok() {  # (output captured first: grep -q in a pipe would trip pipefail)
  [ -x "$SF/stockfish" ] || return 1
  local out; out=$(printf 'uci\nisready\nquit\n' | timeout 60 "$SF/stockfish" 2>/dev/null || true)
  grep -q '^readyok' <<<"$out"
}
is_arm64_elf() { python3 -c 'import sys; h=open(sys.argv[1],"rb").read(20); sys.exit(0 if h[:4]==b"\x7fELF" and int.from_bytes(h[18:20],"little")==0xB7 else 1)' "$1" 2>/dev/null; }
if ! sf_ok; then
  mkdir -p "$SF"
  tmp=$(mktemp -d)
  url=https://github.com/official-stockfish/Stockfish/releases/download/sf_19/stockfish-linux-arm64-universal.tar.gz
  if ! curl -fsSL -o "$tmp/sf.tar.gz" "$url"; then
    echo "   $url not found; asking GitHub which files sf_19 has"
    url=$(curl -fsSL https://api.github.com/repos/official-stockfish/Stockfish/releases/tags/sf_19 | python3 -c '
import json, re, sys
assets = [a["browser_download_url"] for a in json.load(sys.stdin).get("assets", [])]
good = [u for u in assets if re.search(r"(linux|ubuntu).*(arm64|aarch64|armv8)", u, re.I)]
print(good[0] if good else "")' || true)
    [ -n "$url" ] && curl -fsSL -o "$tmp/sf.tar.gz" "$url" || rm -f "$tmp/sf.tar.gz"
  fi
  exe=""
  if [ -s "$tmp/sf.tar.gz" ]; then
    mkdir -p "$tmp/x" && (tar -xf "$tmp/sf.tar.gz" -C "$tmp/x" 2>/dev/null || unzip -q "$tmp/sf.tar.gz" -d "$tmp/x")
    while IFS= read -r f; do is_arm64_elf "$f" && { exe=$f; break; }; done < <(find "$tmp/x" -type f -iname 'stockfish*')
  fi
  if [ -n "$exe" ]; then
    install -m 755 "$exe" "$SF/stockfish"
  else
    echo "   no ready-made ARM64 build: compiling Stockfish 19 from source (takes a while)"
    apt-get install -y --no-install-recommends build-essential
    git clone --depth 1 --branch sf_19 https://github.com/official-stockfish/Stockfish.git "$tmp/src"
    make -C "$tmp/src/src" -j"$(nproc)" build ARCH=armv8
    install -m 755 "$tmp/src/src/stockfish" "$SF/stockfish"
  fi
  rm -rf "$tmp"
fi
cat > "$SF/engine.json" <<'EOF'
{"id": "sf19", "name": "Stockfish 19", "short": "ChAIpi", "exe": "stockfish", "args": [],
 "by": "The Stockfish developers", "tier": "Strongest", "type": "NNUE",
 "desc": "The built-in engine. Open source and the strongest available. Elo limiting from 1320 to 3190."}
EOF
sf_ok && echo "   $(printf 'uci\nquit\n' | "$SF/stockfish" | grep '^id name')" || { echo "Stockfish does not answer."; exit 1; }

# --------------------------------------------------------------------------------------------------
log "yt-dlp for Shorts"
[ -x "$OPT/venv/bin/python" ] || python3 -m venv "$OPT/venv"
"$OPT/venv/bin/pip" install --no-cache-dir --upgrade --quiet "yt-dlp[default]"
"$OPT/venv/bin/yt-dlp" --version | sed 's/^/   yt-dlp /'
# Lichess puzzle CSVs need python-chess; Debian trixie has no python3-chess, so keep a copy in the venv.
python3 -c "import chess" 2>/dev/null || "$OPT/venv/bin/pip" install --no-cache-dir --quiet chess

# --------------------------------------------------------------------------------------------------
log "System files"
cp -r "$SRC/image/files/etc/." /etc/
install -m 755 "$SRC/image/files/usr/local/bin/chaipi-keys" /usr/local/bin/chaipi-keys
chmod 440 /etc/sudoers.d/chaipi
visudo -cf /etc/sudoers.d/chaipi >/dev/null
chmod 644 /etc/polkit-1/rules.d/50-chaipi.rules
if [ "$CHROOT" = 1 ]; then
  # The image ships with no known password, so SSH takes keys only (from chaipi-ssh.txt or a private build).
  # Not done over SSH: a Pi set up with password logins would lock its owner out.
  install -d /etc/ssh/sshd_config.d
  printf 'PasswordAuthentication no\nKbdInteractiveAuthentication no\n' > /etc/ssh/sshd_config.d/10-chaipi-keys-only.conf
fi
chown -R root:root "$OPT"
chown -R chaipi:chaipi /data/chaipi

log "Boot settings (config.txt, cmdline.txt)"
CFG=$BOOT/config.txt
if [ -f "$CFG" ]; then
  sed -i '/^# --- ChAIpi hardware/,/^# --- end ChAIpi ---/d' "$CFG"
  # HDMI sound is not wanted: the I2S amplifier is the only sound card
  sed -i 's/^dtoverlay=vc4-kms-v3d$/dtoverlay=vc4-kms-v3d,noaudio/' "$CFG"
  printf '\n' >> "$CFG"
  cat "$SRC/image/files/config-chaipi.txt" >> "$CFG"
fi
CMD=$BOOT/cmdline.txt
if [ -f "$CMD" ]; then
  # Boot messages go to the serial port only, so the screen stays clean until the UI draws.
  line=$(head -1 "$CMD" | sed -e 's/console=tty1//g' -e 's/ quiet//g' -e 's/ loglevel=[0-9]//g' -e 's/ logo.nologo//g' \
    -e 's/ vt.global_cursor_default=0//g' -e 's/ consoleblank=0//g' -e 's/  */ /g' -e 's/ *$//')
  echo "$line quiet loglevel=3 logo.nologo vt.global_cursor_default=0 consoleblank=0" > "$CMD"
fi

log "Services"
systemctl enable chaipi-boot.service chaipi-input.service chaipi-ui.service chaipi-rtc-sync.timer
systemctl mask getty@tty1.service
for s in hciuart.service bluetooth.service fake-hwclock.service; do systemctl disable "$s" 2>/dev/null || true; done
systemctl enable NetworkManager.service avahi-daemon.service 2>/dev/null || true

# npm is only needed to install; dropping it saves about 60 MB
apt-get purge -y npm >/dev/null 2>&1 || true
apt-get autoremove -y >/dev/null 2>&1 || true
apt-get clean

if [ "$CHROOT" = 0 ]; then
  sysctl -q --system || true
  systemd-tmpfiles --create /etc/tmpfiles.d/chaipi.conf || true
  udevadm control --reload || true
  systemctl daemon-reload
  echo
  echo "ChAIpi is installed. Reboot to load the display, I2C, RTC and audio overlays:  sudo reboot"
else
  echo
  echo "ChAIpi is installed in the image."
fi
