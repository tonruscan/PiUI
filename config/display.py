"""
Display & Hardware Configuration
Settings for physical display, I2C devices, and LEDs.
"""

# Display routing
LED_IS_NETWORK = False   # False = local I2C; True = send to Pico over TCP

# I2C addresses
HT16K33_ADDR       = 0x70
LCD1602_ADDR       = 0x3E
LCD_BACKLIGHT_ADDR = 0x6B  # SN3193 on Waveshare LCD1602 v2.0

# Brightness
SEG_BRIGHT = 8     # 0..15  (7-seg)
LCD_BRIGHT = 70    # 0..100 (LCD backlight percent)

# Minimum gap between DEV1/DEV2 updates (seconds). 0 = no throttle.
LED_THROTTLE_DELAY = 0.06  # ~60 ms is a good starting point

# Disable header rendering (troubleshooting)
DISABLE_HEADER = False

# Screen color calibration (Lightroom-style temperature/tint)
# Values are expressed on an arbitrary +/-100 scale similar to photo editors.
# Positive temperature warms (yellow), negative cools (blue).
# Positive tint shifts toward magenta, negative toward green.
COLOR_TEMP = 0
COLOR_TINT = 0
# Strength controls (higher = stronger effect per 100 units)
COLOR_TEMP_STRENGTH = 0.55
COLOR_TEMP_GREEN_RATIO = 0.45  # how much the green channel follows temp shifts
COLOR_TINT_STRENGTH = 0.55
COLOR_TINT_GREEN_RATIO = 1.0   # how strongly green is reduced for magenta tint
COLOR_TINT_MAGENTA_RATIO = 0.6 # how strongly red/blue are reduced for green tint

# Exposure-style luminance controls (Lightroom-style +/-100 scale)
# Brightness adjusts overall luminance uniformly.
COLOR_BRIGHTNESS = 0
COLOR_BRIGHTNESS_OFFSET = 0
COLOR_BRIGHTNESS_STRENGTH = 0.45
# Blacks adjusts the black point; negative values crush, positive lift shadows.
COLOR_BLACKS = 0
COLOR_BLACKS_OFFSET = 0
COLOR_BLACKS_STRENGTH = 0.35
