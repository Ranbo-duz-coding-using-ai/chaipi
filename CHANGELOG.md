# Changelog

## 1.0.0 (revision 3), first public pre-release
Not yet tested on real hardware.

- The ChAIpi OS for a 2.8" ILI9341 screen, a joystick and six buttons: Play (400–3190 Elo), Helper, Two player, History with one PGN file per game, and game review.
- Extras: eight games, six tools, puzzles, coordinate training, YouTube Shorts, and your own Python apps through the `chaipi` SDK.
- Transfer over ChAIpi's own Wi-Fi with a phone page and a PIN, plus USB drive mode and the microSD slot. Backup and restore.
- The device host: Node.js + Skia on the framebuffer, Stockfish 19 over UCI, GPIO and ADC input, NetworkManager, the USB gadget.
- An SD-card image built by GitHub Actions (Raspberry Pi OS Lite 64-bit, Debian 13), with no SSH key inside. Wi-Fi, time zone and SSH keys can be set from files on the boot partition.
- The emulator: the same OS in any browser, as a single offline file and (once the repository is public) a website.
- A step-by-step wiring guide with diagrams, and a 3D-printable logo badge.
