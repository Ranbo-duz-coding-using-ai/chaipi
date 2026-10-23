"""Strength presets = think time × Elo limit (Stockfish itself has no "modes"; docs/history/05-engine.md)."""
from __future__ import annotations

from dataclasses import dataclass

import chess.engine

from chaipi.config import Config

PRESET_KEYS = ("fast", "medium", "deep", "manual", "elo")
ELO_MIN, ELO_MAX = 1320, 3190     # Stockfish 19's UCI_Elo range
_TITLES = {"fast": "Fast", "medium": "Medium", "deep": "Deep", "manual": "Manual", "elo": "Elo"}


@dataclass(frozen=True)
class Preset:
    key: str
    seconds: float            # 0 = think until OK is pressed
    limit_strength: bool
    elo: int | None = None

    @property
    def infinite(self) -> bool:
        return self.seconds <= 0

    @property
    def short(self) -> str:
        """For the setup screen: 'Deep', 'Elo 2000'."""
        if self.key == "elo":
            return f"Elo {self.elo}"
        return _TITLES.get(self.key, self.key.title())

    @property
    def label(self) -> str:
        """For the PGN header and status: 'Deep 12s', 'Manual', 'Elo 2000 1s'."""
        if self.infinite:
            return self.short
        secs = f"{self.seconds:g}s"
        return f"{self.short} {secs}"

    def limit(self) -> chess.engine.Limit | None:
        """None = `go infinite` (stopped by "play now")."""
        return None if self.infinite else chess.engine.Limit(time=self.seconds)

    def options(self) -> dict:
        """Per-search UCI options; always sent in full so no earlier search leaks into this one."""
        elo = clamp_elo(self.elo or ELO_MAX)
        return {"UCI_LimitStrength": self.limit_strength, "UCI_Elo": elo}


def clamp_elo(elo: int) -> int:
    return max(ELO_MIN, min(ELO_MAX, int(elo)))


def make_preset(cfg: Config, key: str, elo: int | None = None) -> Preset:
    if key not in PRESET_KEYS:
        key = "deep"
    spec = cfg.get(f"engine.presets.{key}", {}) or {}
    limit = bool(spec.get("limit_strength", key == "elo"))
    if key == "elo":
        elo = clamp_elo(elo if elo is not None else cfg.get("engine.elo", 2000))
    else:
        elo = None
    return Preset(key=key, seconds=float(spec.get("seconds", 1.0)), limit_strength=limit, elo=elo)


def preset_choices(cfg: Config) -> list[Preset]:
    """What Game setup cycles through: Fast, Medium, Deep, Manual, Elo 1320 … Elo 2800."""
    out = [make_preset(cfg, k) for k in PRESET_KEYS if k != "elo"]
    out += [make_preset(cfg, "elo", e) for e in cfg.get("engine.elo_steps", [2000])]
    return out


def engine_options(cfg: Config) -> dict:
    """Options set once at engine start (and re-applied after an auto-restart)."""
    opts = {
        "Threads": int(cfg.get("engine.threads", 4)),
        "Hash": int(cfg.get("engine.hash_mb", 64)),
        "UCI_ShowWDL": True,
    }
    syzygy = cfg.get("engine.syzygy_path", "")
    if syzygy:
        opts["SyzygyPath"] = syzygy
    return opts
