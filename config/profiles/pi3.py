"""Profile overrides for Raspberry Pi 3B + 800x480 display."""

SETTINGS = {
    "PLATFORM_ID": "pi3",
    "SCREEN_WIDTH": 800,
    "SCREEN_HEIGHT": 480,
    # Manual color temperature bias (RGB offset in Kelvin-ish units or arbitrary scale).
    # Zero indicates no shift applied; positive warms, negative cools once the
    # renderer hooks this value up.
    "COLOR_TEMP_OFFSET": 0,
    # Future knob for per-platform UI scaling (kept at 1.0 for classic layout).
    "UI_SCALE": 1.0,
}
