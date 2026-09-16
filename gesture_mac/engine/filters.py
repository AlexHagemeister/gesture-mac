"""One Euro filter (Casiez et al. 2012): low lag when moving fast, low jitter
when still. Used on continuous-gesture anchors so axes do not shiver.
Tune min_cutoff down for less jitter, beta up for less lag.
"""
from __future__ import annotations

import math


class _LowPass:
    def __init__(self) -> None:
        self.y: float | None = None

    def filter(self, x: float, alpha: float) -> float:
        self.y = x if self.y is None else alpha * x + (1 - alpha) * self.y
        return self.y

    def reset(self) -> None:
        self.y = None


class OneEuro:
    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.02, d_cutoff: float = 1.0) -> None:
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self._x = _LowPass()
        self._dx = _LowPass()
        self._last_t: float | None = None
        self._last_x: float | None = None

    @staticmethod
    def _alpha(cutoff: float, dt_sec: float) -> float:
        tau = 1 / (2 * math.pi * cutoff)
        return 1 / (1 + tau / dt_sec)

    def filter(self, x: float, t_ms: float) -> float:
        if self._last_t is None or self._last_x is None:
            self._last_t, self._last_x = t_ms, x
            self._dx.filter(0, 1)
            return self._x.filter(x, 1)
        dt = max((t_ms - self._last_t) / 1000, 1e-3)
        self._last_t = t_ms
        dx = (x - self._last_x) / dt
        self._last_x = x
        edx = self._dx.filter(dx, self._alpha(self.d_cutoff, dt))
        cutoff = self.min_cutoff + self.beta * abs(edx)
        return self._x.filter(x, self._alpha(cutoff, dt))

    def reset(self) -> None:
        self._last_t = self._last_x = None
        self._x.reset()
        self._dx.reset()


class OneEuro2D:
    """A 2D pair of One Euro filters."""

    def __init__(self, **opts: float) -> None:
        self.fx = OneEuro(**opts)
        self.fy = OneEuro(**opts)

    def filter(self, x: float, y: float, t_ms: float) -> tuple[float, float]:
        return self.fx.filter(x, t_ms), self.fy.filter(y, t_ms)

    def reset(self) -> None:
        self.fx.reset()
        self.fy.reset()
