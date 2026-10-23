"""Events that flow into the app's single queue (see docs/history/07-software.md, runtime model)."""
from __future__ import annotations

from dataclasses import dataclass, field

import chess
import chess.engine


# --- buttons -------------------------------------------------------------------------
# kind: "down"   raw press (every button; MIC uses it for push-to-talk)
#       "press"  a short press. Joystick directions send it on the way down; OK/BACK/MENU/MIC
#                send it on release if they were not held past the long-press time
#       "long"   OK/BACK/MENU held for long_press_s (sent once, while still held)
#       "repeat" a joystick direction still held (auto-repeat)
#       "up"     raw release
@dataclass(frozen=True)
class ButtonEvent:
    button: str
    kind: str

    @property
    def is_step(self) -> bool:
        """A cursor step: a direction press or its auto-repeat."""
        return self.kind in ("press", "repeat")


# --- engine --------------------------------------------------------------------------
@dataclass(frozen=True)
class Line:
    """One principal variation (MultiPV line)."""
    score: chess.engine.PovScore | None
    wdl: chess.engine.PovWdl | None
    pv: tuple[chess.Move, ...]


@dataclass(frozen=True)
class Snapshot:
    """What the engine knows right now about one search."""
    depth: int = 0
    seldepth: int = 0
    nodes: int = 0
    nps: int = 0
    time: float = 0.0
    lines: tuple[Line, ...] = ()

    @property
    def main(self) -> Line | None:
        return self.lines[0] if self.lines else None

    @property
    def score(self) -> chess.engine.PovScore | None:
        return self.lines[0].score if self.lines else None

    @property
    def wdl(self) -> chess.engine.PovWdl | None:
        return self.lines[0].wdl if self.lines else None

    @property
    def pv(self) -> tuple[chess.Move, ...]:
        return self.lines[0].pv if self.lines else ()


@dataclass(frozen=True)
class EngineReady:
    name: str


@dataclass(frozen=True)
class EngineInfo:
    tag: int
    kind: str            # "search" | "ponder"
    snapshot: Snapshot


@dataclass(frozen=True)
class EngineDone:
    tag: int
    kind: str
    best: chess.Move | None
    snapshot: Snapshot


@dataclass(frozen=True)
class EngineRestarted:
    reason: str


@dataclass(frozen=True)
class EngineFailed:
    error: str


# --- voice (Phase 3) -----------------------------------------------------------------
@dataclass(frozen=True)
class VoiceLevel:
    level: float         # 0..1


@dataclass(frozen=True)
class VoiceResult:
    alternatives: tuple[tuple[str, float], ...] = field(default_factory=tuple)   # (text, confidence)


# --- device --------------------------------------------------------------------------
@dataclass(frozen=True)
class BatteryEvent:
    percent: float | None
    charging: bool | None


@dataclass(frozen=True)
class QuitEvent:
    reason: str = ""
