"""Utilities for resolving and loading bundled fonts.

The UI previously relied on system fonts (Arial, Rasegard, DejaVu) which made
deployment brittle on systems without those font families. This module now
centralises font resolution so call sites can ask for a bundled font weight and
receive a fully qualified path (and optionally a cached ``pygame.font.Font``
instance) that ships with the repository.
"""

# Helper to return the full path of the selected weight
def main_font(weight=None):
    """Return absolute path to the selected UI font.

    - Resolves fonts relative to project root (one level above /utils)
    - Uses config.DIAL_FONT_WEIGHT/WEIGHTS if available; otherwise defaults
    - Accepts an optional explicit weight override
    """
    import os as _os

    # Compute project root from this file (../)
    _utils_dir = _os.path.dirname(_os.path.abspath(__file__))
    _project_root = _os.path.dirname(_utils_dir)
    _font_dir = _os.path.join(_project_root, "assets", "fonts")

    # Fallbacks if path isn't found (defensive)
    if not _os.path.isdir(_font_dir):
        candidates = [
            _os.path.join(_utils_dir, "assets", "fonts"),
            _os.path.join(_project_root, "build", "assets", "fonts"),
            _os.path.join(_os.path.dirname(_project_root), "assets", "fonts"),
        ]
        for c in candidates:
            if _os.path.isdir(c):
                _font_dir = c
                break

    # Pull weights from config when available
    _default_weights = {
        "Thin": "DevantPro-Thin.ttf",
        "ExtraLight": "DevantPro-ExtraLight.ttf",
        "Light": "DevantPro-Light.ttf",
        "Regular": "DevantPro-Regular.ttf",
        "Medium": "DevantPro-Medium.ttf",
        "SemiBold": "DevantPro-SemiBold.ttf",
        "Bold": "DevantPro-Bold.ttf",
        "Heavy": "DevantPro-Heavy.ttf",
        "UltraBold": "DevantPro-UltraBold.ttf",
    }

    try:
        import config as _cfg
        weights = getattr(_cfg, "DIAL_FONT_WEIGHTS", _default_weights)
        default_weight = getattr(_cfg, "DIAL_FONT_WEIGHT", "Regular")
    except Exception:
        weights = _default_weights
        default_weight = "Regular"

    selected = weight if isinstance(weight, str) and weight in weights else default_weight
    filename = weights.get(selected) or weights.get("Regular") or next(iter(weights.values()))
    return _os.path.join(_font_dir, filename)


def mono_font(weight=None):
    """Return absolute path to the selected monospace (diagnostic) font."""
    import os as _os

    # Reuse the same directory detection logic as main_font
    _utils_dir = _os.path.dirname(_os.path.abspath(__file__))
    _project_root = _os.path.dirname(_utils_dir)
    _font_dir = _os.path.join(_project_root, "assets", "fonts")

    if not _os.path.isdir(_font_dir):
        candidates = [
            _os.path.join(_utils_dir, "assets", "fonts"),
            _os.path.join(_project_root, "build", "assets", "fonts"),
            _os.path.join(_os.path.dirname(_project_root), "assets", "fonts"),
        ]
        for c in candidates:
            if _os.path.isdir(c):
                _font_dir = c
                break

    _default_weights = {
        "Regular": "Expanse-Regular.ttf",
        "Bold": "Expanse-Bold.ttf",
        "Italic": "Expanse-Italic.ttf",
        "BoldItalic": "Expanse-BoldItalic.ttf",
    }

    try:
        import config as _cfg
        weights = getattr(_cfg, "MONO_FONT_WEIGHTS", _default_weights)
        default_weight = getattr(_cfg, "MONO_FONT_WEIGHT", "Regular")
    except Exception:
        weights = _default_weights
        default_weight = "Regular"

    selected = weight if isinstance(weight, str) and weight in weights else default_weight
    filename = weights.get(selected) or weights.get("Regular") or next(iter(weights.values()))
    return _os.path.join(_font_dir, filename)


_FONT_CACHE = {}


def load_font(size, weight=None, *, family="main", cache=True):
    """Return a cached ``pygame.font.Font`` for the requested family/weight."""
    import pygame

    family_key = str(family or "main").lower().strip()
    weight_key = str(weight) if weight else None
    key = (family_key, weight_key, int(size))

    if cache and key in _FONT_CACHE:
        return _FONT_CACHE[key]

    if family_key == "mono":
        path = mono_font(weight_key)
    else:
        path = main_font(weight_key)

    font = pygame.font.Font(path, int(size))

    if cache:
        _FONT_CACHE[key] = font

    return font


def load_mono_font(size, weight=None, *, cache=True):
    """Convenience wrapper for ``load_font(..., family="mono")``."""
    return load_font(size, weight, family="mono", cache=cache)
