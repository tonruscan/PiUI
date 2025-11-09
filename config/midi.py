"""
MIDI Configuration
MIDI channel assignments and CC mappings.
"""

# --- Button MIDI settings ---
BUTTON_CC_START = 16  # base CC number for buttons 1–5

# --- Dial MIDI settings ---
DIAL_CC_START = 70  # first dial sends CC70, next 71, etc.

# MIDI channel (0 = CH1, 1 = CH2, etc.)
CC_CHANNEL = 9

# --- External controller latch behaviour ---
DIAL_LATCH_ENABLED = True
DIAL_LATCH_THRESHOLD = 15      # trigger latch when controller differs from UI by more than this many steps
DIAL_LATCH_RELEASE = 5         # release once controller comes back within this window of the UI target
