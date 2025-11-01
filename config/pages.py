"""
Page-Specific Configuration
Settings specific to individual pages (presets, mixer, etc.)
"""

# ================== PRESETS PAGE ==================

PRESET_SCROLL_SPEED = 3.0                      # higher = faster scrolling (try 2.0–5.0)
PRESET_LOAD_DELAY_MS = 10
PRESET_INITIAL_SCROLL_DELAY_MS = 5000          # delay before first scroll step
PRESET_INITIAL_SCROLL_MAX_WAIT_MS = 1000       # max total wait time before giving up
PRESET_SELECTED_PADDING = 177                  # extra vertical padding for selected preset button

# ================== MIXER PAGE ==================

# Mixer performance tuning
MIXER_MIDI_THROTTLE = 0.1                      # seconds between sends (10 Hz)

# --- Mixer Behaviour ---
MIXER_VALUE_RANGE         = 99                 # Quadraverb uses 0–99
MIXER_MUTE_FLASH_MS       = 120                # optional visual flash duration
MIXER_MUTE_SEND_CC        = True               # whether mute toggles send CC/SysEx
