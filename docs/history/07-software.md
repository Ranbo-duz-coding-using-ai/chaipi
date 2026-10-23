# 07 — Software Architecture

## Stack
| Layer | Choice | Why |
|---|---|---|
| Language | Python 3 (the version that ships with Pi OS) | Fast to build; the CPU-heavy parts (Stockfish, Vosk) are native code anyway |
| Chess rules / PGN / UCI | `chess` (python-chess) | Legal moves, SAN, PGN, game-over detection, async UCI engine control |
| Display | `luma.oled` (SH1106 over SPI) + Pillow | Standard, supports SH1106 and SSD1306/1309, and has a **desktop emulator** (`luma.emulator`) |
| Buttons | `gpiozero` (lgpio backend) | Debounce, `when_held`, hold-repeat built in |
| Voice | `vosk` + `sounddevice` (PortAudio) | Offline ASR with a grammar |
| Battery / RTC | `smbus2` (MAX17048); kernel `i2c-rtc` overlay for the DS3231 | |
| Settings | TOML (`tomllib` read, `tomli-w` write) | Human-editable over SSH |
| Service | systemd unit `chaipi.service` | Starts at boot, restarts on crash |

On the Pi, use a **venv with `--system-site-packages`**. Take `python3-gpiozero python3-lgpio python3-rpi-lgpio python3-pil python3-numpy python3-smbus2` from apt (prebuilt for the Pi), and `chess luma.oled vosk sounddevice tomli-w` from pip. `rpi-lgpio` is the drop-in `RPi.GPIO` that luma uses for the DC/RST pins on modern kernels.

## Develop on the Mac first (before the hardware arrives)
The whole app runs on the Mac with **the same code**:
- **Display:** `luma.emulator` opens a 128×64 window scaled 4×.
- **Buttons:** keyboard. Arrows = joystick, Enter = OK, Backspace = BACK, M = MENU, hold Space = MIC.
- **Engine:** the Mac's Homebrew Stockfish 19 (`/opt/homebrew/bin/stockfish`, already installed).
- **Voice:** the Mac's microphone + the same Vosk model. Use a Python 3.12/3.13 venv, because vosk wheels may lag behind the Mac's Python 3.14.

`platform = "auto"` in the config picks the Pi or desktop hardware layer.

## Repository layout
```
Project ChAIpi/
├── README.md, CLAUDE.md, docs/, config/
├── src/chaipi/
│   ├── __main__.py          # entry: python -m chaipi
│   ├── app.py               # event loop + screen stack (state machine)
│   ├── config.py            # defaults, load/save settings.toml, pin maps
│   ├── events.py            # Button/Engine/Voice/Battery event dataclasses
│   ├── hw/
│   │   ├── base.py          # Display, Buttons, Haptics, Battery interfaces
│   │   ├── pi.py            # luma sh1106 SPI, gpiozero buttons, GPIO12 motor, MAX17048
│   │   └── desktop.py       # luma.emulator + keyboard + no-op motor + fake battery
│   ├── engine/
│   │   ├── worker.py        # owns Stockfish; SEARCH / PONDER / STOP / CONFIGURE; auto-restart
│   │   └── presets.py       # Fast/Medium/Deep/Manual/Elo → engine options + limits
│   ├── game/
│   │   ├── session.py       # board, side, mode, history, undo, deviations, result
│   │   ├── entry.py         # legal-move filtering for piece → file → rank, autocomplete
│   │   └── storage.py       # PGN .txt writer, atomic save, resume, counter, game list
│   ├── voice/
│   │   ├── audio.py         # mic stream, pre-roll ring buffer, level meter
│   │   ├── asr.py           # Vosk model/recognizer, grammar, alternatives
│   │   └── parser.py        # words → pattern → legal-move match + confusion fallback
│   └── ui/
│       ├── screens/         # boot, home, setup, thinking, suggest, entry, voice,
│       │                    # board, menu, alts, gameover, settings, games, viewer, shutdown
│       ├── widgets.py       # status bar, list/row picker, big move, eval bar, mini board
│       ├── sprites.py       # 7×7 piece bitmaps, icons (battery, mic, cup)
│       └── fonts/           # bundled fonts (DejaVu Sans Bold, a 5×7 pixel font)
├── tests/                   # pytest; all run on the Mac
├── tools/
│   ├── deploy.sh            # rsync src → pi, restart service
│   ├── bench.sh             # engine nodes/sec + temperature log
│   ├── soak.sh              # thermal / battery rundown logger
│   └── voice_eval.py        # score recorded WAVs against both models
└── system/
    ├── chaipi.service
    ├── config.txt.snippet   # lines to add to /boot/firmware/config.txt
    ├── asound.conf          # default ALSA capture = USB mic via plughw
    └── sudoers.d-chaipi     # NOPASSWD for poweroff/reboot only
```

## Runtime model (threads + one queue)
```
 gpiozero callbacks ─┐
 engine worker ──────┼──▶  event queue  ──▶  MAIN THREAD: app loop
 voice worker ───────┤                        • pops events (timeout 66 ms ≈ 15 fps)
 battery poller (5s) ┘                        • current screen handles the event
                                              • redraw only if the screen is dirty
```
- **Main thread**: UI only. It never blocks. Button → screen-change latency target < 50 ms.
- **Engine worker**: owns `chess.engine.SimpleEngine.popen_uci(["nice","-n","5", STOCKFISH])`. It takes commands from its own queue and streams `EngineInfo` (depth, score, wdl, pv, nodes, nps, time) at ≤ 5 Hz, then `EngineDone(best, info)`. Searches run through `engine.analysis(board, limit, multipv=n)` so they can be **stopped at any time** ("play now", MIC pause, undo). Each command has a `tag`, and stale results from a cancelled search are ignored.
- **Voice worker**: opens the audio stream on move-entry screens, keeps the pre-roll buffer, and runs Vosk on MIC press. It emits `VoiceLevel` and `VoiceResult(alternatives)`.
- **Auto-restart**: if Stockfish exits (`EngineTerminatedError`, e.g. SF19's strict-validation exit), the worker relaunches it, re-applies options, and re-issues the last command. The UI shows "engine restarted".

## Game state machine (Advisor mode shown)
```
SETUP ─▶ (engine side to move?) ─yes─▶ THINKING ─done─▶ SUGGEST ─OK─▶ push move ─┐
              │no                                          │◄ "other"            │
              ▼                                            ▼                     │
        ENTRY (opponent) ◀────────────── PONDER starts ◀─── ENTRY(you) ──────────┘
              │ move entered (buttons/voice)
              ▼
         push move ─▶ game over? ─yes─▶ GAME_OVER
              │no
              ▼
          THINKING …
```
Undo is allowed from any state. It pops moves until it's back at the last position where the user had to enter something, cancels any search, and restarts pondering if needed.

## Move-entry logic (`game/entry.py`)
```python
ORDER = [PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING]

def piece_options(board):
    kinds = {board.piece_type_at(m.from_square) for m in board.legal_moves if not board.is_castling(m)}
    opts = [k for k in ORDER if k in kinds]
    opts += [c for c in ("O-O", "O-O-O") if castling_move(board, c) in board.legal_moves]
    return opts

def file_options(board, kind):    # files of destination squares, sorted a→h
def rank_options(board, kind, f): # ranks for that destination file
def resolve(board, kind, sq):     # → one move | ask origin (2+ origins) | ask promotion
```
Pre-select the predicted move's piece, file, and rank. Auto-advance when a list has exactly one entry.

## Files on disk
| Path | What |
|---|---|
| `/opt/chaipi/engine/stockfish` | Stockfish 19 binary (symlink) |
| `/opt/chaipi/models/vosk-model-small-en-in-0.4/` | Voice model |
| `/data/chaipi/games/NNNN_YYYY-MM-DD_HHMM_<Color>_<Mode>.txt` | **One file per game** |
| `/data/chaipi/current.json` | The game in progress (start FEN, UCI moves, side, mode, preset, suggestions), for resume |
| `/data/chaipi/settings.toml` | User settings (written on change) |
| `/data/chaipi/counter` | Game number (stays unique even if the clock is wrong) |
| `/data/chaipi/logs/` | app/engine/voice logs, size-capped |
| `/data/voice-tests/` | Phase 3 recordings |

`/data` is a separate ext4 partition, so it survives the read-only root (overlayfs) mode.

**Atomic save after every move:** write to a temp file → `fsync` → `rename` over the old file → `fsync` the directory. A power cut can lose at most the move being typed.

### Game file format: PGN inside a `.txt` (paste straight into lichess → Import)
```
[Event "ChAIpi casual game"]
[Site "ChAIpi"]
[Date "2026.10.17"]
[Time "14:32:05"]
[Round "42"]
[White "You"]
[Black "Opponent"]
[Result "1-0"]
[Mode "Advisor"]
[Engine "Stockfish 19"]
[Preset "Deep 12s"]
[Termination "Checkmate"]
[FollowedSuggestions "34/41"]

1. e4 {sf e4 +0.31 d18} e5 2. Nf3 {sf Nf3 +0.35 d19} Nc6
3. Bc4 {you: Bc4 · sf: Bb5 +0.40 → +0.22} Nf6 ... 1-0
```
The player name ("You") is set in `settings.toml`, because typing a name with a joystick is painful.

## Memory budget (512 MB). Main risk, measured first in Phase 1
| Item | Estimate |
|---|---|
| Kernel + Pi OS Lite services | 60–80 MB |
| GPU reserve (`gpu_mem=16`, KMS overlay off) | 16 MB |
| Stockfish binary + NNUE net | 80–110 MB |
| Stockfish Hash | 64 MB |
| Python + python-chess + luma + Pillow | 40–60 MB |
| Vosk small model + grammar recognizer | **80–250 MB (unknown; measure)** |
| **Total** | **~340–580 MB** |

Mitigations, in order:
1. zram swap (compressed RAM, ~1 GB virtual)
2. Hash → 32 MB
3. Disable the KMS display overlay and Bluetooth
4. Load the Vosk *model* once at boot, but create recognizers only on MIC press
5. Last resort: a smaller acoustic model, or PocketSphinx keyword grammar (much less RAM, less accurate)

## Boot to "ready" (target ≤ 20 s)
- Pi OS Lite, `quiet` boot. Disable `bluetooth`, `hciuart`, `ModemManager`, `triggerhappy`, and `NetworkManager-wait-online`. Iterate with `systemd-analyze blame`.
- `chaipi.service` starts `After=local-fs.target`, **not** after the network.
- The splash is drawn within ~1 s of Python starting; Stockfish and Vosk load in parallel behind it.

## System integration
- `chaipi.service`: `User=pi`, `Restart=always`, `RestartSec=2`. The `pi` user is in the `gpio spi i2c audio` groups.
- Shutdown and reboot from the menu run `sudo systemctl poweroff|reboot`, allowed by a narrow sudoers rule.
- WiFi on/off via `nmcli radio wifi on|off`. The About screen shows the IP when connected.
- Time: DS3231 via `dtoverlay=i2c-rtc,ds3231`, synced from NTP whenever WiFi is on.

## Testing strategy
| Level | What | Where |
|---|---|---|
| Unit | Voice parser (~200 phrase → move cases across ~20 positions), entry filtering and autocomplete, storage (write / kill / resume), eval formatting, game-over detection, undo, and mode switching | Mac (pytest) |
| UI snapshots | Render every screen to PNG using luma's `dummy` device; eyeball once, then diff | Mac |
| Integration | Full games in the emulator using real Stockfish + scripted button events | Mac |
| Hardware | Button-test screen, mic-level screen, `bench`, 30-min thermal soak, 4-h battery rundown log | Pi |

## Deploy loop
```bash
tools/deploy.sh          # rsync src/ → pi@chaipi.local:~/chaipi/src && ssh … sudo systemctl restart chaipi
ssh pi@chaipi.local journalctl -u chaipi -f    # live logs
```
