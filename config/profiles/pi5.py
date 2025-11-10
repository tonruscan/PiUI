"""Profile overrides for Raspberry Pi 5 + 1280x720 7" v2 touchscreen."""

SETTINGS = {
    "PLATFORM_ID": "pi5",
    "SCREEN_WIDTH": 1280,
    "SCREEN_HEIGHT": 720,
    # Slight positive shift to counteract the yellow tint observed on Pi 5 panel.
    # Downstream code can translate this abstract offset into actual color
    # corrections. Adjust via forthcoming calibration UI.
    "COLOR_TEMP_OFFSET": -12,
    "UI_SCALE": 1.0,
}
