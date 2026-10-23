#!/bin/bash -e
# Copies the ChAIpi sources into the image and runs the same installer used over SSH.
# Not /tmp: pi-gen bind-mounts the build's own /tmp over the image's /tmp while a chroot command runs.
rm -rf "${ROOTFS_DIR}/usr/src/chaipi"
mkdir -p "${ROOTFS_DIR}/usr/src"
cp -a files/src "${ROOTFS_DIR}/usr/src/chaipi"
on_chroot << 'CHROOT'
bash /usr/src/chaipi/image/install.sh --chroot
rm -rf /usr/src/chaipi
CHROOT
