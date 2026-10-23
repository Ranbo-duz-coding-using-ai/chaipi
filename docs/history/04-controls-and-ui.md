# 04 — Controls & UI

## The controls: 8 buttons + 1 switch

| Control | Short press | Long press (≥ 0.6 s) | Hold |
|---|---|---|---|
| **Joystick ↑ ↓ ← →** | Move the cursor / change a value | — | Auto-repeat (after 0.4 s, 8 per second) |
| **Joystick press = OK** | Select / confirm / "Next" / "I played it" | **Accept the predicted move** (move entry) or **play now** (while thinking) | — |
| **KEY1 = MIC** | Listen for up to 4 s (stops on silence) | — | **Push-to-talk**: listen while held |
| **KEY2 = BACK** | Go back one step | **Undo last move** (asks to confirm) | — |
| **KEY3 = MENU** | Context menu | — | **Peek at the board** while held |
| **Slide switch** | Power on / off (hard cut; games are already saved) | | |

Global rules:
- **Any press while the screen is asleep only wakes it.** That press isn't acted on, so you can't trigger anything by accident.
- **← → change values, ↑ ↓ move between rows.** Every list wraps around.
- **BACK never loses data.** It steps back, and at the top of the game screen it offers Undo.
- The bottom line of every screen shows what OK and ← do there.

## Screen map

```
 Boot splash ──▶ [Resume unfinished game?] ──▶ HOME
                                               ├── New game ──▶ Game setup ──▶ GAME LOOP ──▶ Game over ──▶ HOME
                                               ├── Resume
                                               ├── Saved games ──▶ Game viewer
                                               ├── Settings
                                               └── Shut down
```

## Mockups (128 × 64 px; each box line is one ~8 px text row)

### Boot splash (shown within ~1 s of the app starting)
```
┌──────────────────────────┐
│        ☕ ChAIpi ♟        │
│                          │
│   brewing Stockfish 19…  │
│   engine ✓  voice …      │
│   ▓▓▓▓▓▓▓▓▓▓░░░░░        │
└──────────────────────────┘
```

### Home
```
┌──────────────────────────┐
│ ChAIpi           ▮▮▮ 78% │
│ ▶ New game               │
│   Resume (move 23)       │
│   Saved games            │
│   Settings               │
│   Shut down              │
└──────────────────────────┘
```

### Game setup (one screen; your last choices are remembered)
```
┌──────────────────────────┐
│ NEW GAME                 │
│ You play   ◄ White ►     │
│ Mode       ◄ Advisor ►   │
│ Strength   ◄ 🧠 Deep ►    │
│                          │
│ OK = start   BACK = home │
└──────────────────────────┘
```
- **You play:** White / Black / Random
- **Mode:**
  - Advisor: ChAIpi suggests *your* moves.
  - Opponent: ChAIpi *is* your opponent.
  - Analysis: you enter both sides and it shows the eval.
- **Strength:** ⚡ Fast / ⚖ Medium / 🧠 Deep / ∞ Manual / 🎯 Elo 1320 … 2800 (see [05-engine.md](05-engine.md))

### Thinking
```
┌──────────────────────────┐
│ ○W  12.  Thinking  ▮▮ 78%│
│  best so far:  Nf3       │
│  depth 17   +0.38        │
│  ▓▓▓▓▓▓▓▓▓▓░░░░  7s/12s  │
│                          │
│ hold OK = play now       │
└──────────────────────────┘
```
The best move updates live as the search goes deeper. In ∞ Manual mode, the time bar is replaced by a counter, and a short OK plays the current best.

### Suggestion (Advisor mode). Vibrates once when it appears.
```
┌──────────────────────────┐
│ ○W  12.  Your move  78%  │
│        Nf3               │  ← big font (~22 px)
│        g1 → f3           │
│ +0.42  W58 D35 L7   d18  │
│ OK=played  ◄=other  ▼alts│
└──────────────────────────┘
```
| Press | Effect |
|---|---|
| **OK** | "I played it". Pushes the move and goes to opponent entry (your "Next" button) |
| **←** | "I played something else". Enter your actual move, and ChAIpi continues from that |
| **▼** | Alternatives: the top 3 moves with evals (shown if the multi-move setting is on, otherwise it calculates them on demand) |
| **→** or hold MENU | Board view with an arrow for the suggested move |

Extra banners when relevant: **"Only move!"** (best is ≥ 1.5 pawns better than the 2nd), **"Mate in 4"**, **"Opponent blundered (+3.1)"**.

**Hint style** (setting): *Full move* (default), or *Piece first*: the screen shows "Move a ♞ knight", and OK reveals the square. Good for training.

### Opponent's move entry: step 1, choose the piece
```
┌──────────────────────────┐
│ ●B  12…  Opponent  78%   │
│ You: Nf3 ✓   guess: …e5  │
│                          │
│  [P]  N   B   R   Q   K  │
│  0-0                     │
│ hold OK=e5  🎤 hold MIC  │
└──────────────────────────┘
```
- Only pieces with at least one legal move are shown. `0-0` / `0-0-0` appear only when castling is legal.
- **The cursor starts on the predicted move's piece.** The prediction comes from ChAIpi's own analysis.
- **Long-press OK** accepts the predicted move instantly.

### Step 2, choose the destination file (only legal files are shown)
```
│ Opp: Pawn → ?            │
│   a  b  c  d [e] f  g  h │   ← illegal files shown dim or hidden
```
### Step 3, choose the rank (only legal ranks for that file)
```
│ Opp: Pawn → e?           │
│      [5]  6              │
```
### Extra steps, only when needed
- **Disambiguation:** if two knights can reach d7: `Which ♞?  [b8]  f6`
- **Promotion:** `Promote to  [Q]  R  B  N` (Q is pre-selected)

### Auto-complete (this is what makes it fast)
- If the chosen piece has exactly one legal move, it's entered immediately.
- If the chosen file has exactly one legal rank, the rank step is skipped.
- Captures, check, en passant, and castling rights are all worked out automatically (python-chess). **You never enter "takes".**

Typical press counts:

| Move | Presses |
|---|---|
| Predicted move | **1** (long-press OK) |
| Most moves | **2–3** |
| Worst case | Queen with 20+ moves: piece + up to 7 scrolls + OK + rank |

### After a move is entered (non-blocking confirm)
```
│ Opp played …e5 ✓  BACK=undo │   ← shown for ~1.5 s while the engine is already thinking
```
No extra "are you sure" press for button entry. If you made a mistake, BACK puts it right.

### Voice entry (hold MIC on any move-entry screen)
```
┌──────────────────────────┐
│ 🎤 listening…   ▁▃▅▇▅▃▁   │
└──────────────────────────┘
        ↓ release
┌──────────────────────────┐
│ heard: "knight f six"    │
│      …Nf6 ✓              │
│ auto-OK in 1.5s  BACK=no │
└──────────────────────────┘
```
- **One legal match:** auto-accepted after 1.5 s (setting: *Auto* or *Always ask*).
- **Several matches** (e.g. "knight d7" when both knights can go there): it shows the choices like the disambiguation step.
- **No match:** "Didn't catch that: 'knight z9'". Two short buzzes; try again or use the joystick.

### Board view (→ from the suggestion screen, hold MENU anywhere, or MENU → Board)
```
┌────────────┬─────────────┐
│ ♜♞♝♛♚♝ ♜  │ 12. Nf3     │
│ ♟♟♟♟ ♟♟♟  │ +0.42       │
│     ♞     │ last: …e5   │
│    ♟      │ ▓▓▓▓▓░ eval │
│    ♙      │             │
│     ♘→    │ OK = back   │
│ ♙♙♙♙ ♙♙♙  │             │
│ ♖♘♗♕♔♗ ♖  │             │
└────────────┴─────────────┘
```
A 64 × 64 px board (8 px squares, hand-drawn 7 × 7 piece sprites), drawn from your side. The last move's squares are outlined and the suggested move is drawn as an arrow. **Use this to check the device's board matches the real board.**

### Game over
```
│ CHECKMATE  — you win 1-0 │
│ 41 moves · followed 34/41│
│ saved: 0042_2026-10-17…  │
│ OK = home   ▼ = moves    │
```
Detected automatically: checkmate, stalemate, threefold repetition, 50-move rule, insufficient material. Resignations and agreed draws are entered from MENU.

## In-game MENU (KEY3)
1. Undo last move
2. Edit my last move (I played something else)
3. Board view
4. Move list (scrollable, with evals)
5. Strength & think time → takes effect from the next move
6. Think on opponent's time: On / Off
7. Switch mode / side (e.g. Analysis → "Advise me as Black"). Use this to **join a game in progress**: start in Analysis, enter the moves so far, then switch
8. Result: I resigned / Opponent resigned / Draw agreed
9. Save & exit to Home (the game stays resumable)
10. Screen off

## Settings (Home → Settings)
| Group | Setting | Values (default **bold**) |
|---|---|---|
| Engine | Strength preset | ⚡ Fast / ⚖ Medium / **🧠 Deep** / ∞ Manual / 🎯 Elo |
| | Elo (when 🎯) | 1320, 1500, 1800, 2000, 2200, 2500, 2800 |
| | Think time (custom) | 0.5 / 1 / 2 / 4 / 8 / **12** / 20 / 30 s / Until OK |
| | Think on opponent's time | **On** / Off / Auto (off below 20% battery) |
| | Show alternatives | **Off** / 2 / 3 |
| | Opening book (later) | Off / On |
| Display | Show eval | **On** / Off |
| | Show win/draw/loss % | **On** / Off |
| | Notation | SAN / from→to / **both** |
| | Hint style | **Full move** / Piece first |
| | Brightness | Low / **Med** / High |
| | Dim after / Sleep after | 30 s / **2 min** / 5 min / Never |
| | Flip screen 180° | **Off** / On |
| Input | Voice | **On** / Off |
| | Voice model | **Indian English** / US English |
| | Voice confirm | **Auto** (1.5 s) / Always ask |
| | Entry style | **Piece → square** / From → to |
| Device | Vibration | **On** / Off |
| | WiFi | **Off** / On (shows IP address) |
| | Run benchmark | shows nodes/sec and temperature |
| | About | versions, battery V/%, temperature, free RAM, IP |
| | Factory reset settings | — |

## Screen-saving and OLED burn-in protection
- Dim at 30 s idle, sleep at 2 min. It **never sleeps while thinking**.
- When the engine finishes, the screen wakes and the motor buzzes.
- Static elements (status bar) shift by 1 px every few minutes.

## Vibration patterns
| Pattern | Meaning |
|---|---|
| 1 short | Move ready |
| 2 short | Voice not understood / illegal |
| 1 long | Check or mate-in-N found |
| 3 long | Low battery |
