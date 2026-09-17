"""On-disk settings. Everything lives under
~/Library/Application Support/gesture-mac/:

    config.json     enabled, camera name, frame rates, smoothing, HUD port
    mappings.json   the bindings document (seeded from presets/default.json)
"""
from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path

SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "gesture-mac"
CONFIG_PATH = SUPPORT_DIR / "config.json"
MAPPINGS_PATH = SUPPORT_DIR / "mappings.json"
DEFAULT_PRESET = Path(__file__).resolve().parents[2] / "presets" / "default.json"
DEFAULT_FPS = 30.0
OLD_DEFAULT_FPS = 15.0
"""The active-rate default before issue #6; read as DEFAULT_FPS when found on disk."""


@dataclass(slots=True)
class Config:
    enabled: bool = True
    """The master switch: off releases the camera and performs nothing."""
    camera: str | None = None
    """Camera name as AVFoundation reports it; None = built-in."""
    fps: float = DEFAULT_FPS
    """Ceiling on the tracking rate while a hand is in view. The camera's
    own rate is the other ceiling; the built-in camera delivers 30."""
    idle_fps: float = 4.0
    """Tracking rate after idle_after_s with no hand in view."""
    idle_after_s: float = 3.0
    flip_handedness: bool = False
    """Set true for a non-selfie camera (rear-facing or mirrored feed)."""
    hand_confidence: float = 0.7
    """Floor for the tracker's detection, presence, and tracking confidence
    (MediaPipe default 0.5 tracked a pillow corner as a hand: issue #12)."""
    min_in_frame: float = 0.9
    """Fraction of a hand's landmarks that must be inside the image."""
    smoothing: dict[str, float] = field(default_factory=dict)
    """The engine's smoothing constants as last set from the panel
    (min_cutoff, beta, d_cutoff). Empty means the engine's defaults."""
    hud_port: int = 8765
    """Local port for the HUD page. Bound to 127.0.0.1 only."""


def load_config() -> Config:
    if CONFIG_PATH.exists():
        raw = json.loads(CONFIG_PATH.read_text())
        known = {k: v for k, v in raw.items() if k in Config.__dataclass_fields__}
        if known.get("fps") == OLD_DEFAULT_FPS:
            # A file written by an earlier version carries the old default,
            # never a choice; read it as the current default (issue #6).
            known["fps"] = DEFAULT_FPS
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
