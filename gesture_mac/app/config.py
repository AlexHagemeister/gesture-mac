"""On-disk settings. Everything lives under
~/Library/Application Support/gesture-mac/:

    config.json     enabled, camera name, frame rates
    mappings.json   the bindings document (seeded from presets/default.json)
"""
from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "gesture-mac"
CONFIG_PATH = SUPPORT_DIR / "config.json"
MAPPINGS_PATH = SUPPORT_DIR / "mappings.json"
DEFAULT_PRESET = Path(__file__).resolve().parents[2] / "presets" / "default.json"


@dataclass(slots=True)
class Config:
    enabled: bool = True
    """Whether gestures perform actions. Tracking runs either way."""
    camera: str | None = None
    """Camera name as AVFoundation reports it; None = built-in."""
    fps: float = 15.0
    """Tracking rate while a hand is in view."""
    idle_fps: float = 4.0
    """Tracking rate after idle_after_s with no hand in view."""
    idle_after_s: float = 3.0
    flip_handedness: bool = False
    """Set true for a non-selfie camera (rear-facing or mirrored feed)."""


def load_config() -> Config:
    if CONFIG_PATH.exists():
        raw = json.loads(CONFIG_PATH.read_text())
        known = {k: v for k, v in raw.items() if k in Config.__dataclass_fields__}
        return Config(**known)
    return Config()


def save_config(cfg: Config) -> None:
    SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(asdict(cfg), indent=2) + "\n")


def ensure_mappings() -> Path:
    """Seed the user's mappings from the default preset on first run."""
    if not MAPPINGS_PATH.exists():
        SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy(DEFAULT_PRESET, MAPPINGS_PATH)
    return MAPPINGS_PATH
