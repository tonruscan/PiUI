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
