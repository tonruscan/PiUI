"""Profile overrides for Raspberry Pi 5 + 1280x720 7" v2 touchscreen."""

SETTINGS = {
    "PLATFORM_ID": "pi5",
    "SCREEN_WIDTH": 1280,
    "SCREEN_HEIGHT": 720,
    # Screen calibration (Lightroom-style temp/tint scale; -100..+100)
    # Negative temp leans blue, positive leans yellow. Positive tint leans magenta.
    "COLOR_TEMP": -20,
    "COLOR_TINT": 30,
    "COLOR_BRIGHTNESS": 0,
    "COLOR_BLACKS": 0,
    "UI_SCALE": 1.55,
    "UI_SCALE_Y": 1.43,
    # Use a dedicated remote logging port so the Windows viewer can separate
    # Pi 5 traffic; ensure the receiver listens on this port.
    "LOG_REMOTE_PORT": 5052,
}
