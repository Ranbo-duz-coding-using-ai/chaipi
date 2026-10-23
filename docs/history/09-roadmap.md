# 09 — Build Roadmap

Each phase ends with something that works and can be tested. Phases 0–4 need only the "Phase 1 kit" (no soldering).

## Phase 0: Mac prototype (optional; can start today, before parts arrive)
- [ ] Scaffold `src/chaipi/` per [07-software.md](07-software.md), with a pytest setup and a Python 3.12/3.13 venv
- [ ] Desktop hardware layer: `luma.emulator` window + keyboard buttons
- [ ] `game/session.py`, `game/entry.py`, `game/storage.py` + unit tests
- [ ] Engine worker using the Mac's Homebrew Stockfish 19
- [ ] Screens: boot, home, setup, thinking, suggest, entry, gameover
- [ ] Voice parser + ~200 text test cases (no audio needed yet)

**Done when:** a full Advisor game can be played in the emulator, the `.txt` file is saved, and it resumes after killing the app.

## Phase 1: Pi bring-up and go/no-go measurements
- [ ] You: buy the Phase 1 kit, flash the card ([08-os-setup.md](08-os-setup.md)), confirm `ssh pi@chaipi.local`
- [ ] `tools/provision.sh` written and run
- [ ] **Engine bench:** nodes/sec at Threads = 1/2/3/4. Record it in [05-engine.md](05-engine.md)
- [ ] **Thermal soak:** 30 min of continuous search with the HAT on. Log `vcgencmd measure_temp` / `get_throttled`
- [ ] **RAM test:** Stockfish (Hash 64) + Vosk model loaded + Python UI at the same time. Record `free -m`. **This is the go/no-go check**; apply the mitigations if it's tight
- [ ] Display hello-world on the SH1106; **button-test screen** (shows each press, confirms the pin map)
- [ ] Mic capture test: record 5 s at 16 kHz, play it back on the Mac
- [ ] Optional: 1.2 GHz overclock stability test

**Done when:** the numbers table is filled in, and the screen, all 8 buttons, and the mic are confirmed working.

## Phase 2: Core game loop on the device
- [ ] Pi hardware layer (luma SH1106 SPI, gpiozero with long-press and repeat, GPIO-safe shutdown)
- [ ] All game screens + in-game MENU, Undo, "I played something else"
- [ ] Presets (Fast / Medium / Deep / Manual / Elo) + "play now"
- [ ] Pondering + predicted-move pre-select + long-press-OK accept
- [ ] Atomic save after every move, resume on boot, game counter
- [ ] `chaipi.service` autostart; boot to ready ≤ 20 s
- [ ] Engine auto-restart

**Done when:** you can play a real game on a real board, from power-on to checkmate, with buttons only.

## Phase 3: Voice
- [ ] Audio stream + pre-roll + level meter; push-to-talk and tap-to-talk
- [ ] Vosk grammar; log any dropped words
- [ ] Parser wired to the UI: confirm / choices / failure states
- [ ] **Accent tuning:** record the 60-move script, run `tools/voice_eval.py` on both models, pick the winner, tune the confusion costs

**Done when:** ≥ 90% of moves are right first time in your voice, ≥ 98% after the confirm step, and latency is ≤ 1 s.

## Phase 4: Polish
- [ ] Board view (sprites, arrow, last-move highlight, eval bar)
- [ ] Alternatives list, "Only move!", "Opponent blundered", mate alerts
- [ ] Opponent and Analysis modes; switching mode / side mid-game
- [ ] Hint style "Piece first"
- [ ] Saved-games browser + move-by-move viewer
- [ ] Full Settings menu; About screen (versions, nodes/sec, temperature, RAM, IP)
- [ ] Screen dim / sleep, burn-in shift; vibration patterns (after Phase 5 wiring)

## Phase 5: Battery and power hardware
- [ ] You: buy the Phase 5 kit
- [ ] Assemble per [03-wiring.md](../03-wiring.md): PowerBoost + switch + LiPo + MAX17048 + RTC + motor
- [ ] Battery %, charging indicator, low-battery warnings, auto-save + shutdown at 3%
- [ ] RTC overlay, time sync from NTP when WiFi is on
- [ ] **Rundown test:** fully charged, pondering ON, continuous; log the % every minute. **Target ≥ 4 h**

## Phase 6: Enclosure and hardening
- [ ] Measure the real parts with calipers → OpenSCAD case ([10-enclosure.md](10-enclosure.md)) → print → fit
- [ ] Thermal soak *in the closed case*. If it throttles: more vents, Threads = 3, or no overclock
- [ ] Read-only root (overlayfs) + `/data` partition, per the decision in [08-os-setup.md](08-os-setup.md)
- [ ] WiFi game export: tiny read-only web page at `http://chaipi.local:8080` listing games for download

## Phase 7: Extras (v1.x, pick what you like)
- Polyglot opening book (instant, varied openings)
- Syzygy 5-piece tablebases (~1 GB)
- Guardian mode (warns only if your planned move is a blunder)
- WiFi hotspot mode, so you can grab games anywhere from your phone
- From→to entry style
- Hindi number words / custom voice synonyms
- Eval graph on the game-over screen

## Definition of done: v1.0
| Requirement | Target |
|---|---|
| Power-on to ready | ≤ 20 s |
| Button → screen response | < 50 ms |
| Presses per typical move | 2–3 (1 for the predicted move) |
| Voice | ≥ 90% first try, ≤ 1 s latency |
| Battery, worst case (100% CPU) | ≥ 4 h |
| Power cut mid-game | no game lost; resumes at the same position |
| Thermal (closed case, 30 min of search) | no hard throttling |
| Game files | one `.txt` per game, valid PGN, imports into lichess |

## Risk register
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| RAM: Stockfish + Vosk + UI > 512 MB | Medium | High | Phase 1 test first; zram, Hash 32, KMS off, PocketSphinx fallback |
| Thermal throttling in the case | Medium | Medium | Heatsink (required), vents, PETG case, Threads = 3, overclock off |
| Voice accuracy (accent, noisy room) | Medium | Medium | Small grammar, legal-move filter, confusion fallback, NATO letters; buttons always work |
| SD corruption from the hard switch | Low–Med | High | Atomic saves, overlayfs, low-battery auto-shutdown, a quality card |
| Official Stockfish arm64 binary won't run | Low | Low | Compile from source on the Pi (20–40 min) |
| HAT pin map differs | Low | Low | All pins in config + button-test screen |
| Reversed LiPo JST polarity | Medium (cheap packs) | High | Multimeter check before plugging in |
| Runtime below estimate | Low | Medium | Rundown test; ponder Auto-off at 20%; 6600 mAh option |
