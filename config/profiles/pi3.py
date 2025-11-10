"""Profile overrides for Raspberry Pi 3B + 800x480 display."""

SETTINGS = {
    "PLATFORM_ID": "pi3",
    "SCREEN_WIDTH": 800,
    "SCREEN_HEIGHT": 480,
    # Screen calibration tweaks (Lightroom-style temp/tint scale; -100..+100)
    "COLOR_TEMP": 0,
    "COLOR_TINT": 0,
    "COLOR_BRIGHTNESS": 0,
    "COLOR_BLACKS": 0,
    # Future knob for per-platform UI scaling (kept at 1.0 for classic layout).
    "UI_SCALE": 1.0,
}
