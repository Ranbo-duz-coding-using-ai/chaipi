# 05 — Stockfish 19 Engine

## Getting Stockfish 19 onto the Pi (no compiling)
Stockfish 19 (released **5 Sep 2026**) ships an official **`stockfish-linux-arm64-universal.tar.gz`** (~80 MB) build. "Universal" means it detects the CPU's features at runtime, so it picks the plain ARMv8/NEON code path on the Zero 2 W's Cortex-A53.

```bash
sudo mkdir -p /opt/chaipi/engine && sudo chown pi: /opt/chaipi/engine && cd /opt/chaipi/engine
curl -LO https://github.com/official-stockfish/Stockfish/releases/download/sf_19/stockfish-linux-arm64-universal.tar.gz
tar xzf stockfish-linux-arm64-universal.tar.gz
# the binary embeds its NNUE net (nn-1a298aa575a0.nnue); no separate net file is needed
./stockfish/stockfish-* <<< $'uci\nquit' | head -3     # expect "id name Stockfish 19"
./stockfish/stockfish-* bench 16 4 13                   # 16 MB hash, 4 threads, depth 13 → nodes/second
```

Check the exact folder and file name inside the tarball when it's extracted, then symlink it to `/opt/chaipi/engine/stockfish`. The provisioning script (`tools/provision.sh`) does all of this automatically.

**Fallback** (only if the official binary won't run, e.g. a glibc mismatch): build from source on the Pi with `make -j2 build ARCH=armv8 COMP=gcc`, after adding 1 GB of swap (expect 20–40 min).

### Stockfish 19 changes that matter to us
- **Single network.** SF19 retired the small secondary net, so memory use is simpler.
- **Strict input validation.** An invalid FEN, position, or UCI command now prints `info string CRITICAL ERROR …` and **the engine exits**. Every move we send comes from python-chess's legal-move list, and the engine wrapper auto-restarts Stockfish (re-applying options and position) if it ever dies.
- UCI options are unchanged: `Threads`, `Hash`, `MultiPV`, `Skill Level` (0–20), `UCI_LimitStrength`, **`UCI_Elo` (1320–3190)**, `UCI_ShowWDL`, `Ponder`, `SyzygyPath`, `Move Overhead`.

## Engine options we set
| Option | Value | Why |
|---|---|---|
| Threads | 4 (bench 3 vs 4 in Phase 1) | All cores. Stockfish runs at `nice 5`, so the UI and voice stay responsive |
| Hash | 64 MB (32 if RAM is tight) | The 512 MB of RAM is shared with Vosk; see the memory budget |
| UCI_ShowWDL | true | Win/draw/loss % on screen |
| MultiPV | 1 (2–3 if "Show alternatives" is on) | Each extra line costs some depth |
| UCI_LimitStrength / UCI_Elo | per preset | Elo-limited play |
| SyzygyPath | `/data/syzygy` if present | Optional perfect endgames (later) |

## Expected speed on the Zero 2 W (to be measured in Phase 1)
Rough guess: **~150–350 thousand nodes/sec** on 4 threads at 1 GHz. At that speed:

| Think time | Nodes | Typical middlegame depth | Strength (rough) |
|---|---|---|---|
| 1 s | ~0.25 M | ~14 | Already beyond any human (2800+) |
| 4 s | ~1 M | ~17 | ~3000 |
| 12 s | ~3 M | ~19–20 | ~3100+ |
| 30 s | ~7.5 M | ~21–22 | Close to full strength |

These are estimates. Phase 1 replaces them with real `bench` numbers, and the About screen shows the measured nodes/sec. Even "Fast" will crush any human; Deep is for when you want the truly best move.

### Optional overclock (you said max speed)
Only after the heatsink is fitted, and only if it passes a 30-minute `stress-ng` + Stockfish bench with `vcgencmd get_throttled` = `0x0`:
```
# /boot/firmware/config.txt
arm_freq=1200
over_voltage=4      # raise to 6 only if it's unstable at 4
```
That's about +20% nodes/sec. If it's unstable or throttles in the closed case, revert. Stock 1 GHz is the default.

## Presets
| Preset | Strength | Think time | Use |
|---|---|---|---|
| ⚡ **Fast** | Full (3190) | 1 s | Blitz-speed help |
| ⚖ **Medium** | Full | 4 s | Default casual |
| 🧠 **Deep** | Full | 12 s, **hold OK to play earlier** | When it matters |
| ∞ **Manual** | Full | Until you press OK (live best move shown) | Analysis / long games |
| 🎯 **Elo N** | `UCI_LimitStrength=true`, `UCI_Elo=N` | 1 s | Playing *against* ChAIpi, or human-like advice |

**Why Elo presets get short think times:** Stockfish's Elo limiter makes it *choose weaker moves* (it picks among the top 4 lines with deliberate randomness). It does **not** think less on its own. A weak move found in 12 s is still a weak move, so we save the time and the battery.

**Note on the Elo numbers:** `UCI_Elo` was calibrated by Stockfish at a fixed time control on desktop hardware. On the Pi with 1 s per move, the real strength is probably a little *below* the label. It's still a good relative scale.

## Thinking on the opponent's time ("pondering")
1. You press OK ("played it"), so the board now has the opponent to move.
2. ChAIpi immediately starts an **infinite analysis of that position** in the background.
   - Its main line gives the **predicted opponent move**, which is where the entry cursor starts and what long-press OK accepts.
   - Every position it searches is stored in the hash table.
3. When you enter the opponent's actual move, ChAIpi stops the background search and starts the real search. Because the hash table already holds most of the likely positions, the real search reaches **several plies deeper in the same time** (or the same depth much faster).
4. When MIC is pressed, the background search is **paused** so voice recognition gets the CPU, then resumed.

This is the generic "analyse while waiting" technique, not UCI `ponder` on a single guessed move. It's simpler and helps even when the guess is wrong. The cost is battery (scenario A in [02-power.md](02-power.md)). Setting: On / Off / Auto (off below 20%).

## Evaluation display
- Stockfish reports scores from the side to move. ChAIpi converts them to **your perspective**: + means you're better.
- Format: `+0.42` (pawns), `M4` (you mate in 4), `-M3` (you get mated in 3).
- WDL: `W58 D35 L7` (per mille → %).
- Eval bar in board view: logistic squash of centipawns, ±4.0 = full bar.
- **"Only move!"** when MultiPV 2 shows the best move is ≥ 150 cp better than the second (needs alternatives ≥ 2, or a cheap MultiPV-2 re-check at the end of the search).
- **"Opponent blundered"** when the eval jumps ≥ 200 cp in your favour after their move.

## Mode logic
| Mode | Engine searches for | You enter |
|---|---|---|
| Advisor | **Your** side (shows suggestion) | Opponent's moves, plus your own if you deviated |
| Opponent | **ChAIpi's** side (shows "ChAIpi plays Nf3 — make it on the board") | Your moves |
| Analysis | Nobody by default; continuous eval of the current position | Both sides' moves. MENU → "Best move here?" |

## Later (v1.x) engine extras
- **Opening book** (Polyglot `.bin`) for instant, varied openings. python-chess reads Polyglot. A small book (~1–5 MB) is fine.
- **Syzygy 3-4-5-piece tablebases** (~1 GB on the SD card) for perfect endgames. Download over WiFi to `/data/syzygy`.
- **Guardian mode:** enter the move you're *planning* before you play it, and ChAIpi only warns you if it drops ≥ 1.5 pawns. A training tool where you still do the thinking.
