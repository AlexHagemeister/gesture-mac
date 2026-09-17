"""Config loading: the old active-rate default reads as the current one."""
from __future__ import annotations

import json

from gesture_mac.app import config


def _load(tmp_path, monkeypatch, raw: dict) -> config.Config:
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw))
    monkeypatch.setattr(config, "CONFIG_PATH", path)
    return config.load_config()


def test_old_default_fps_reads_as_current_default(tmp_path, monkeypatch):
    cfg = _load(tmp_path, monkeypatch, {"fps": config.OLD_DEFAULT_FPS})
    assert cfg.fps == config.DEFAULT_FPS == 30.0


def test_chosen_fps_is_kept(tmp_path, monkeypatch):
    cfg = _load(tmp_path, monkeypatch, {"fps": 24.0, "idle_fps": 2.0})
    assert cfg.fps == 24.0
    assert cfg.idle_fps == 2.0


def test_unknown_keys_are_ignored(tmp_path, monkeypatch):
    cfg = _load(tmp_path, monkeypatch, {"fps": 30.0, "mystery": 1})
    assert cfg.fps == 30.0


def test_smoothing_round_trips_and_defaults_empty(tmp_path, monkeypatch):
    assert _load(tmp_path, monkeypatch, {"fps": 30.0}).smoothing == {}
    cfg = config.Config(smoothing={"min_cutoff": 3.0, "beta": 20.0, "d_cutoff": 4.0})
    monkeypatch.setattr(config, "SUPPORT_DIR", tmp_path)
    config.save_config(cfg)
    assert config.load_config().smoothing == {"min_cutoff": 3.0, "beta": 20.0, "d_cutoff": 4.0}
