# 06 — Voice Input

## Engine: Vosk (offline, runs on the Pi)
- **Model:** `vosk-model-small-en-in-0.4`, a lightweight **Indian-English** model (~36 MB). Fallback model: `vosk-model-small-en-us-0.15` (~40 MB). It's a setting, and Phase 3 picks whichever recognises *your* voice better.
- **Why small models:** Vosk's small models allow **runtime vocabulary restriction** (a "grammar"); the big 1 GB models don't, and wouldn't fit in 512 MB anyway. Whisper is far too slow on a Zero 2 W.
- **Fully offline.** No WiFi needed, and no audio ever leaves the device.
- Python: `pip install vosk sounddevice` (aarch64 wheels exist). Models go in `/opt/chaipi/models/`.

## Restricted vocabulary (the grammar)
The recognizer may only output these words, plus `[unk]` for anything else:

| Group | Words → meaning |
|---|---|
| Pieces | pawn, knight, bishop, rook, queen, king |
| Indian / casual synonyms | horse → knight, camel → bishop, elephant → rook |
| Files | a, b, c, d, e, f, g, h |
| Files (NATO, much harder to mishear) | alpha, bravo, charlie, delta, echo, foxtrot, golf, hotel |
| Ranks | one, two, three, four, five, six, seven, eight |
| Capture | takes, captures, x, on |
| Movement | to |
| Castling | castle, castles, short, long, kingside, queenside, "king side", "queen side", oh |
| Promotion | promote, promotes, equals (followed by a piece word) |
| Decorations (ignored) | check, mate, checkmate |
| Commands | undo, cancel, yes, no |

That's about 60 words. At startup Vosk logs any grammar word missing from the model's lexicon. The app records those in `voice.log`, and Phase 3 replaces any that are dropped (e.g. if a single letter is missing, NATO still works).

"castle" means **castling only**, never the rook. Use "rook" or "elephant" for the piece.

## Things you can say
| Say | Result |
|---|---|
| "e four" / "echo four" | e4 (or any unique legal move to e4) |
| "knight f three" / "horse f three" | Nf3 |
| "knight takes e five" | Nxe5 |
| "e takes d five" | exd5 |
| "bishop takes knight" | The unique legal capture of a knight by a bishop |
| "knight b d seven" | Nbd7 (disambiguated) |
| "rook one e one" | R1e1 |
| "e two e four" / "e two to e four" | e2e4 (coordinate style) |
| "castle" / "castle kingside" / "castle short" / "oh oh" | O-O (plain "castle" works if only one side is legal) |
| "castle long" / "castle queenside" / "oh oh oh" | O-O-O |
| "e eight queen" / "e eight promote queen" | e8=Q (if nothing is said, the joystick step defaults to Q) |
| "queen h five check" | Qh5+ ("check" is ignored, but harmless) |
| "undo" | Same as long-press BACK |

**You never have to say "takes".** It's accepted but optional, because the legal-move list already knows what's a capture.

## Parser pipeline
```
mic (16 kHz mono) ──▶ Vosk + grammar ──▶ up to 5 alternative transcripts (with confidence)
      ──▶ normalize words (synonyms, NATO → letters, "to" → separator or 2)
      ──▶ build a pattern {piece?, from-file?, from-rank?, capture?, to-square?, promo?, castle?}
      ──▶ match against python-chess legal moves
      ──▶ pick: exactly 1 match → accept | 2+ → show choices | 0 → confusion fallback → else "didn't catch that"
```

### 1. Normalization rules
- `two` / `to`: a "to" right after a file letter is the rank **2** ("e to" → e2). A "to" between two squares is a **separator** ("e2 to e4").
- `x`, `takes`, `captures`, `on` set the capture flag (optional).
- `check`, `mate`, `checkmate` are dropped.
- Promotion: a piece word directly after a square on rank 1/8 is the promotion piece.

### 2. Pattern matching
Patterns accepted, in order:
1. `castle [short|long|kingside|queenside]` / `oh oh [oh]`
2. `[piece] [from-file|from-rank|from-square]? [capture]? to-square [promo]?`
3. `file capture to-square` (pawn capture: "e takes d5")
4. `from-square [to]? to-square [promo]?` (coordinates)
5. `to-square` alone: all legal moves to that square, preferring pawn moves
6. `piece capture piece` ("bishop takes knight"): legal captures by that piece type of that piece type

### 3. Confusion fallback (the "b-d-e-g" problem)
Letter names that rhyme are the #1 error source, so if no alternative gives a legal move, retry with confusable substitutions, each one adding a cost:

| Heard | Also try | Cost |
|---|---|---|
| b, d, e, g, c | each other (the "-ee" group) | 1 |
| a, h | each other | 1 |
| f, x | each other ("ef" / "ex") | 1 |
| a missing rank or file | every legal value | 2 |

The lowest-cost **unique legal** match wins. Ties go to the move ChAIpi's own analysis rated higher (the predicted move first). This is the same idea lichess's voice input uses. With only ~20–40 legal moves in a typical position, a garbled letter almost always resolves correctly.

### 4. Confirmation UX
- **High confidence + exactly one match:** shows "…Nf6 ✓" and auto-accepts after 1.5 s (BACK cancels).
- **Low confidence or a fallback was used:** waits for OK.
- Setting "Voice confirm = Always ask" forces OK every time.

## Audio pipeline details
- USB mic opened through ALSA `plughw` at **16 kHz, mono, S16_LE**; the plug layer resamples if the mic only does 44.1/48 kHz.
- **0.5 s pre-roll ring buffer** while on a move-entry screen, so a word spoken a split-second before the button goes down isn't clipped. The stream is closed on other screens.
- **Hold MIC:** recognizes until release (max 6 s). **Tap MIC:** listens until 1.2 s of silence (max 4 s).
- Background pondering is **paused** during recognition so Vosk gets the CPU. Expected latency on release: **≤ 1 s**.
- A level meter (`▁▃▅▇`) on screen shows the mic is hearing you. If it stays flat, check the mic or gain.
- Mic gain is set once in setup (`alsamixer`, about 80%). Optional software normalisation for quiet speakers.

## Accent tuning plan (Phase 3)
1. ChAIpi shows a 60-move script on screen (all pieces, all files and ranks, castling, promotions, captures).
2. You say each one while holding MIC. The WAV files are saved to `/data/voice-tests/`.
3. A script runs both models × several grammar variants over the recordings and reports the accuracy of each.
4. We keep the winner, add synonyms for any word that keeps failing, and adjust the confusion costs from the real errors.
5. **Target:** ≥ 90% correct first time, ≥ 98% within the confirm step (fallback + choices).
