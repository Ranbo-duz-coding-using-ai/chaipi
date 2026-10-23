#!/usr/bin/env bash
# Builds the ChAIpi SD-card image: Raspberry Pi OS Lite 64-bit (pi-gen, arm64 branch) + stage-chaipi.
#
#   ./image/build.sh                                        # the image as published: no SSH key inside
#   CHAIPI_SSH_KEY="$(cat ~/.ssh/id_ed25519.pub)" ./image/build.sh   # a private image that already trusts your key
#
# Without a key built in, SSH logins need chaipi-ssh.txt on the boot partition (see image/README.md).
# Needs Docker (pi-gen's build-docker.sh), about 25 GB of free disk and a network connection.
# On an x86 machine Docker also needs ARM emulation (qemu-user-static + binfmt-support).
# The result lands in image/deploy/: chaipi.img.xz, its SHA-256, and pi-password.txt.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(dirname "$HERE")
WORK=${CHAIPI_WORK:-$HERE/work}
PIGEN_REF=${PIGEN_REF:-arm64}
P=$WORK/pi-gen
case "$WORK" in *' '*) echo "pi-gen can't build in a folder with spaces ($WORK). Set CHAIPI_WORK=/some/path/without/spaces"; exit 1 ;; esac

KEY=${CHAIPI_SSH_KEY:-}
free_gb=$(df -Pk "$HERE" | awk 'NR==2 {print int($4/1048576)}')
[ "$free_gb" -ge 20 ] || echo "Warning: only ${free_gb} GB free here; pi-gen needs about 25 GB."

mkdir -p "$WORK"
rm -rf "$P"
git clone --depth 1 --branch "$PIGEN_REF" https://github.com/RPi-Distro/pi-gen.git "$P"
cp -r "$HERE/stage-chaipi" "$P/"
SRC=$P/stage-chaipi/01-chaipi/files/src
mkdir -p "$SRC"
tar -C "$ROOT" --exclude node_modules --exclude __pycache__ --exclude 'device/ui/test' -cf - \
  device mockup/chaipi-os.html config/chaipi.example.toml image/install.sh image/files VERSION | tar -C "$SRC" -xf -
# Only the ChAIpi image, not the plain Lite one from stage2.
touch "$P/stage2/SKIP_IMAGES"
rm -f "$P/stage2/EXPORT_NOOBS"

# (not tr | head: under pipefail the broken pipe would stop the build)
PASS=$(python3 -c 'import secrets; print(secrets.token_urlsafe(12))')
cp "$HERE/pigen.config" "$P/config"
echo "FIRST_USER_PASS='$PASS'" >> "$P/config"
[ -n "$KEY" ] && echo "PUBKEY_SSH_FIRST_USER='$KEY'" >> "$P/config"

cd "$P"
if [ "${CHAIPI_NATIVE:-0}" = 1 ]; then sudo ./build.sh; else ./build-docker.sh; fi

mkdir -p "$HERE/deploy"
cp "$P"/deploy/*.img* "$HERE/deploy/" 2>/dev/null || cp "$P"/deploy/* "$HERE/deploy/"
echo "$PASS" > "$HERE/deploy/pi-password.txt"
(cd "$HERE/deploy" && sha256sum ./*.img* > SHA256SUMS 2>/dev/null || shasum -a 256 ./*.img* > SHA256SUMS)
echo
echo "Image ready in $HERE/deploy. Flash it with Raspberry Pi Imager (Use custom)."
if [ -n "$KEY" ]; then echo "SSH: ssh pi@chaipi.local (your key is built in)."; else echo "SSH: put your public key in chaipi-ssh.txt on the boot partition first."; fi
echo "Console password for user pi is in pi-password.txt (keep it private; SSH itself only takes keys)."
