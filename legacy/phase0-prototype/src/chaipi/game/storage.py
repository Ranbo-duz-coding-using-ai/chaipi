"""Game files on disk: one PGN `.txt` per game, `current.json` for resume, a game counter.

Every write is atomic (temp file → fsync → rename → fsync the directory), so a power cut
loses at most the move being typed. Layout under the data dir:

    games/NNNN_YYYY-MM-DD_HHMM_<Color>_<Mode>.txt
    current.json      the game in progress (removed when the game ends)
    counter           last game number used
    logs/
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chaipi.game.session import Session

log = logging.getLogger(__name__)

CURRENT_VERSION = 1
_GAME_FILE = re.compile(r"^(\d{4,})_.*\.txt$")


def _fsync_dir(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass  # some filesystems refuse fsync on a directory; the rename is still atomic
    finally:
        os.close(fd)


def atomic_write(path: Path | str, data: str | bytes) -> None:
    """temp → fsync → rename over the old file → fsync the directory."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = data.encode("utf-8") if isinstance(data, str) else data
    tmp = path.with_name(f".{path.name}.tmp")
    with open(tmp, "wb") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    _fsync_dir(path.parent)


class Storage:
    def __init__(self, data_dir: Path | str):
        self.root = Path(data_dir)
        self.games_dir = self.root / "games"
        self.logs_dir = self.root / "logs"
        self.current_path = self.root / "current.json"
        self.counter_path = self.root / "counter"
        self.games_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    # --- game numbers ----------------------------------------------------------------
    def _highest_file_number(self) -> int:
        best = 0
        for p in self.games_dir.iterdir():
            m = _GAME_FILE.match(p.name)
            if m:
                best = max(best, int(m.group(1)))
        return best

    def read_counter(self) -> int:
        try:
            return int(self.counter_path.read_text().strip() or 0)
        except (OSError, ValueError):
            return 0

    def next_game_number(self) -> int:
        """Bump and persist the counter. Never reuses a number already on disk."""
        n = max(self.read_counter(), self._highest_file_number()) + 1
        atomic_write(self.counter_path, f"{n}\n")
        return n

    # --- saving ----------------------------------------------------------------------
    def game_path(self, session: Session) -> Path:
        return self.games_dir / session.filename

    def save(self, session: Session) -> Path:
        """Write the PGN, then current.json (or remove it once the game is over)."""
        path = self.game_path(session)
        atomic_write(path, session.pgn())
        if session.is_over:
            self.clear_current()
        else:
            atomic_write(self.current_path, json.dumps(session.to_dict(), indent=1) + "\n")
        return path

    def load_current(self) -> dict | None:
        """The unfinished game, or None. A damaged file is set aside, not deleted."""
        try:
            raw = self.current_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except OSError as e:
            log.error("cannot read %s: %s", self.current_path, e)
            return None
        try:
            data = json.loads(raw)
            if data.get("version") != CURRENT_VERSION or "plies" not in data:
                raise ValueError(f"unexpected format (version {data.get('version')!r})")
            return data
        except (ValueError, AttributeError) as e:
            bad = self.current_path.with_name("current.json.bad")
            log.error("bad %s (%s); moved to %s", self.current_path, e, bad)
            os.replace(self.current_path, bad)
            return None

    def clear_current(self) -> None:
        try:
            self.current_path.unlink()
        except FileNotFoundError:
            return
        _fsync_dir(self.root)

    def list_games(self) -> list[Path]:
        """Saved games, newest first."""
        return sorted((p for p in self.games_dir.iterdir() if _GAME_FILE.match(p.name)), reverse=True)
