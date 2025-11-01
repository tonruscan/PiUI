"""
Layout Configuration
Positioning, spacing, and geometric layout for UI elements.
"""

# ================== DIAL LAYOUT ==================

DIAL_PADDING_X = 180  # horizontal spacing between dials

# ================== BUTTON LAYOUT ==================

BUTTON_OFFSET_X = 40    # closer to left edge
BUTTON_SPACING_Y = 13   # increase gap between buttons
BUTTON_OFFSET_Y = 100   # top offset for first button

BACK_BUTTON_SIZE = 50
BACK_BUTTON_TOP_PAD = 2   # move slightly up
BACK_BUTTON_LEFT_PAD = 8

BURGER_BUTTON_SIZE = 42
BURGER_BUTTON_TOP_PAD = 0   # move slightly up
BURGER_BUTTON_RIGHT_PAD = 12

# ================== DEVICE SELECT LAYOUT ==================

DEVICE_BUTTON_TOP_PADDING = 100  # Top padding for device select buttons

# ================== MIXER LAYOUT ==================

MIXER_TOP_MARGIN          = 140      # distance from top of screen to top of faders
MIXER_HEIGHT              = 220      # fader height in pixels
MIXER_WIDTH               = 28       # fader track width
MIXER_SPACING             = 160      # horizontal spacing between faders
MIXER_LABEL_OFFSET_Y      = 30       # distance above fader for label
MIXER_VALUE_OFFSET_Y      = 15       # distance below fader for numeric value
MIXER_MUTE_OFFSET_Y       = 36       # distance below value for mute button
MIXER_VALUE_OFFSET_X      = -2       # horizontal offset for numeric value
MIXER_MUTE_WIDTH          = 28       # mute button width
MIXER_MUTE_HEIGHT         = 28       # mute button height
MIXER_CORNER_RADIUS       = 6        # rounded corner for tracks and mute buttons
