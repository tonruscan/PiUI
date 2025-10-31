# Helper to return the full path of the selected weight
def main_font(weight=None):
    """Return absolute path to the selected TTF font.

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
