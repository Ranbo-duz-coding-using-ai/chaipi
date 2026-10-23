"""Settings: shipped defaults + the user's settings.toml, platform detection, pin maps.

The shipped `config/chaipi.example.toml` holds every default. On first run it is copied
to `<data_dir>/settings.toml`; after that the two are merged (user values win), so new
defaults added in a later version still appear. Changes made on the device are written
back to settings.toml atomically.
"""
from __future__ import annotations

import copy
import logging
import os
import shutil
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tomli_w

from chaipi.game.storage import atomic_write

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_CONFIG = PROJECT_ROOT / "config" / "chaipi.example.toml"
BUTTONS = ("up", "down", "left", "right", "ok", "back", "menu", "mic")


def detect_platform() -> str:
    """'pi' on a Raspberry Pi (device-tree model string), else 'desktop'."""
    try:
        model = Path("/proc/device-tree/model").read_text(errors="ignore")
    except OSError:
        return "desktop"
    return "pi" if "Raspberry Pi" in model else "desktop"


def deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


@dataclass
class Config:
    data: dict[str, Any]
    platform: str                      # resolved: "pi" | "desktop"
    data_dir: Path
    engine_path: str
    settings_path: Path | None = None
    user: dict[str, Any] = field(default_factory=dict)   # the settings.toml layer only

    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self.data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, dotted: str, value: Any) -> None:
        """Change a setting in memory (call save() to persist it)."""
        for target in (self.data, self.user):
            node = target
            *parents, leaf = dotted.split(".")
            for part in parents:
                node = node.setdefault(part, {})
            node[leaf] = value

    def save(self) -> None:
        if self.settings_path is None:
            return
        atomic_write(self.settings_path, tomli_w.dumps(self.user))

    def button_pins(self) -> dict[str, int]:
        pins = self.get("hardware.buttons", {})
        return {name: int(pins[name]) for name in BUTTONS}

    def desktop_keys(self) -> dict[str, str]:
        keys = self.get("desktop.keys", {})
        return {name: str(keys[name]) for name in BUTTONS}


def load_config(
    path: str | os.PathLike | None = None,
    platform: str | None = None,
    data_dir: str | os.PathLike | None = None,
    overrides: dict | None = None,
    use_settings_file: bool = True,
) -> Config:
    """Load defaults (+ settings.toml) and resolve platform-specific paths.

    `overrides` is merged last and never written to settings.toml (tests, CLI flags).
    """
    defaults_path = Path(path) if path else Path(os.environ.get("CHAIPI_CONFIG", EXAMPLE_CONFIG))
    with open(defaults_path, "rb") as f:
        defaults = tomllib.load(f)
    if overrides:
        defaults = deep_merge(defaults, overrides)

    plat = platform or defaults.get("hardware", {}).get("platform", "auto")
    if plat == "auto":
        plat = detect_platform()

    if data_dir is None:
        if plat == "desktop":
            data_dir = defaults.get("desktop", {}).get("data_dir", "var/chaipi")
        else:
            data_dir = defaults.get("storage", {}).get("data_dir", "/data/chaipi")
    data_root = Path(data_dir).expanduser()
    if not data_root.is_absolute():
        data_root = PROJECT_ROOT / data_root
    data_root.mkdir(parents=True, exist_ok=True)

    user: dict = {}
    settings_path = None
    if use_settings_file:
        settings_path = data_root / "settings.toml"
        if not settings_path.exists():
            shutil.copyfile(defaults_path, settings_path)
            log.info("first run: copied %s to %s", defaults_path, settings_path)
        try:
            with open(settings_path, "rb") as f:
                user = tomllib.load(f)
        except (OSError, tomllib.TOMLDecodeError) as e:
            log.error("ignoring unreadable %s: %s", settings_path, e)
            user = {}

    merged = deep_merge(defaults, user)
    if overrides:  # overrides beat settings.toml too
        merged = deep_merge(merged, overrides)

    if plat == "desktop":
        engine_path = merged.get("desktop", {}).get("engine_path") or merged["engine"]["path"]
    else:
        engine_path = merged["engine"]["path"]

    return Config(
        data=merged,
        platform=plat,
        data_dir=data_root,
        engine_path=str(engine_path),
        settings_path=settings_path,
        user=user,
    )
