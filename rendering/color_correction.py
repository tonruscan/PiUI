"""Screen-wide color calibration helpers.

This module applies Lightroom-style temperature, tint, brightness, and blacks
adjustments after a frame (or dirty rect) is rendered. Temperature/tint are
implemented as per-channel multipliers, while brightness and blacks operate as
exposure-style remaps so each hardware profile can fine-tune its display.
"""

from __future__ import annotations

import pygame
from dataclasses import dataclass
from typing import Optional, Tuple

try:  # numpy enables blacks/curve style adjustments
    import numpy as np  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - runtime fallback when numpy missing
    np = None

import config as cfg

# Cached overlay surface reused between frames to avoid re-allocation.
_overlay_surface: Optional[pygame.Surface] = None
_overlay_size: Optional[Tuple[int, int]] = None
_overlay_color: Optional[Tuple[int, int, int, int]] = None
_numpy_warning_emitted = False


@dataclass(frozen=True)
class _Adjustment:
    multipliers: Tuple[float, float, float]
    brightness: float
    blacks: float

    @property
    def has_multiplier(self) -> bool:
        r, g, b = self.multipliers
        return (
            abs(r - 1.0) > 1e-3
            or abs(g - 1.0) > 1e-3
            or abs(b - 1.0) > 1e-3
        )

    @property
    def has_brightness(self) -> bool:
        return abs(self.brightness) > 1e-4

    @property
    def requires_numpy(self) -> bool:
        return abs(self.blacks) > 1e-4


def _clamp_unit(value: float) -> float:
    """Clamp value to the inclusive range [0.0, 1.0]."""
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _fetch_float(name: str, default: float) -> float:
    try:
        value = getattr(cfg, name, default)
    except Exception:
        return default
    try:
        return float(value)
    except Exception:
        return default


def _resolve_adjustments() -> Optional[_Adjustment]:
    """Compute final adjustment parameters from config values."""

    temp = _fetch_float("COLOR_TEMP", 0.0) + _fetch_float("COLOR_TEMP_OFFSET", 0.0)
    tint = _fetch_float("COLOR_TINT", 0.0) + _fetch_float("COLOR_TINT_OFFSET", 0.0)
    temp = max(-100.0, min(100.0, temp))
    tint = max(-100.0, min(100.0, tint))

    r = g = b = 1.0

    temp_strength = abs(_fetch_float("COLOR_TEMP_STRENGTH", 0.55))
    temp_green_ratio = abs(_fetch_float("COLOR_TEMP_GREEN_RATIO", 0.45))
    if temp > 0.0:
        delta = min(1.0, (temp / 100.0) * temp_strength)
        g *= _clamp_unit(1.0 - delta * temp_green_ratio)
        b *= _clamp_unit(1.0 - delta)
    elif temp < 0.0:
        delta = min(1.0, (-temp / 100.0) * temp_strength)
        r *= _clamp_unit(1.0 - delta)
        g *= _clamp_unit(1.0 - delta * temp_green_ratio)

    tint_strength = abs(_fetch_float("COLOR_TINT_STRENGTH", 0.55))
    tint_green_ratio = abs(_fetch_float("COLOR_TINT_GREEN_RATIO", 1.0))
    tint_magenta_ratio = abs(_fetch_float("COLOR_TINT_MAGENTA_RATIO", 0.6))
    if tint > 0.0:
        delta = min(1.0, (tint / 100.0) * tint_strength)
        g *= _clamp_unit(1.0 - delta * tint_green_ratio)
    elif tint < 0.0:
        delta = min(1.0, (-tint / 100.0) * tint_strength)
        rb_scale = _clamp_unit(1.0 - delta * tint_magenta_ratio)
        r *= rb_scale
        b *= rb_scale

    r = _clamp_unit(r)
    g = _clamp_unit(g)
    b = _clamp_unit(b)

    brightness_value = _fetch_float("COLOR_BRIGHTNESS", 0.0) + _fetch_float("COLOR_BRIGHTNESS_OFFSET", 0.0)
    brightness_value = max(-100.0, min(100.0, brightness_value))
    if abs(brightness_value) < 1e-3:
        brightness = 0.0
    else:
        strength = abs(_fetch_float("COLOR_BRIGHTNESS_STRENGTH", 0.45))
        brightness = max(-1.0, min(1.0, (brightness_value / 100.0) * strength))

    blacks_value = _fetch_float("COLOR_BLACKS", 0.0) + _fetch_float("COLOR_BLACKS_OFFSET", 0.0)
    blacks_value = max(-100.0, min(100.0, blacks_value))
    if abs(blacks_value) < 1e-3:
        blacks = 0.0
    else:
        strength = abs(_fetch_float("COLOR_BLACKS_STRENGTH", 0.35))
        blacks = max(-0.95, min(0.95, (blacks_value / 100.0) * strength))

    if (
        abs(r - 1.0) < 1e-3
        and abs(g - 1.0) < 1e-3
        and abs(b - 1.0) < 1e-3
        and abs(brightness) < 1e-4
        and abs(blacks) < 1e-4
    ):
        return None

    return _Adjustment(multipliers=(r, g, b), brightness=brightness, blacks=blacks)


def _ensure_overlay(size: Tuple[int, int], color: Tuple[int, int, int, int]) -> pygame.Surface:
    """Return an overlay surface of the requested size filled with color."""
    global _overlay_surface, _overlay_size, _overlay_color

    if _overlay_surface is None or _overlay_size != size:
        _overlay_surface = pygame.Surface(size, flags=pygame.SRCALPHA)
        _overlay_size = size
        _overlay_color = None

    if _overlay_color != color:
        _overlay_surface.fill(color)
        _overlay_color = color

    return _overlay_surface


def _apply_multiplier_overlay(
    surface: pygame.Surface,
    area: pygame.Rect,
    multipliers: Tuple[float, float, float],
) -> None:
    width, height = surface.get_size()
    color = (
        int(_clamp_unit(multipliers[0]) * 255),
        int(_clamp_unit(multipliers[1]) * 255),
        int(_clamp_unit(multipliers[2]) * 255),
        255,
    )
    overlay = _ensure_overlay((width, height), color)
    surface.blit(
        overlay,
        area.topleft,
        area,
        special_flags=pygame.BLEND_RGBA_MULT,
    )


def _apply_brightness_overlay(
    surface: pygame.Surface,
    area: pygame.Rect,
    brightness: float,
) -> None:
    magnitude = int(round(abs(brightness) * 255))
    if magnitude <= 0:
        return

    width, height = surface.get_size()
    color = (magnitude, magnitude, magnitude, 0)
    overlay = _ensure_overlay((width, height), color)
    flag = pygame.BLEND_RGB_ADD if brightness > 0 else pygame.BLEND_RGB_SUB
    surface.blit(overlay, area.topleft, area, special_flags=flag)


def _warn_numpy_missing() -> None:
    global _numpy_warning_emitted
    if _numpy_warning_emitted:
        return
    _numpy_warning_emitted = True
    notifier = getattr(cfg, "_queue_startup_log", None)
    if callable(notifier):
        notifier(
            "warn",
            "[COLOR] numpy not available; skipping blacks calibration adjustments",
        )


def _apply_numpy(surface: pygame.Surface, area: pygame.Rect, adj: _Adjustment) -> None:
    if np is None:
        return

    view = pygame.surfarray.pixels3d(surface)
    sub_view = view[area.left : area.right, area.top : area.bottom]
    if sub_view.size == 0:
        del view
        return

    working = sub_view.astype(np.float32) / 255.0

    if adj.has_multiplier:
        multipliers = np.array(adj.multipliers, dtype=np.float32).reshape((1, 1, 3))
        working *= multipliers

    blacks = adj.blacks
    if abs(blacks) > 1e-4:
        if blacks < 0.0:  # crush blacks by raising black point
            black_point = min(0.95, -blacks)
            working -= black_point
            working /= max(1e-4, 1.0 - black_point)
        else:  # lift blacks by lowering contrast near zero
            black_point = min(0.95, blacks)
            working = working * (1.0 - black_point) + black_point

    if adj.has_brightness:
        working += adj.brightness

    np.clip(working, 0.0, 1.0, out=working)
    working *= 255.0
    np.clip(working, 0.0, 255.0, out=working)
    sub_view[...] = working.astype(sub_view.dtype)

    del sub_view
    del view


def apply(surface: pygame.Surface, rect: Optional[pygame.Rect] = None) -> None:
    """Apply color calibration to the surface (optionally constrained to rect)."""
    if surface is None:
        return

    adjustments = _resolve_adjustments()
    if not adjustments:
        return

    surface_rect = surface.get_rect()
    if rect is None:
        area = surface_rect
    else:
        area = pygame.Rect(rect).clip(surface_rect)
    if area.width <= 0 or area.height <= 0:
        return

    if adjustments.requires_numpy:
        if np is None:
            _warn_numpy_missing()
            if adjustments.has_multiplier:
                _apply_multiplier_overlay(surface, area, adjustments.multipliers)
            if adjustments.has_brightness:
                _apply_brightness_overlay(surface, area, adjustments.brightness)
            return

        _apply_numpy(surface, area, adjustments)
        return

    if adjustments.has_multiplier:
        _apply_multiplier_overlay(surface, area, adjustments.multipliers)
    if adjustments.has_brightness:
        _apply_brightness_overlay(surface, area, adjustments.brightness)