"""
Layout Configuration
Positioning, spacing, and geometric layout for UI elements.
"""

# ================== DIAL LAYOUT ==================

DIAL_PADDING_X = 180  # horizontal spacing between dials
MINI_DIAL_PADDING_X = 18  # horizontal gap between mini dial edges (px)
MINI_DIALS_BANK_PADDING_Y = 90  # vertical gap between stacked mini dial banks
MINI_DIAL_LABEL_PADDING_Y = 4  # vertical gap between mini dial and its label background
MINI_DIAL_TOP_PADDING = 14 # distance from widget top edge to top of first mini dial (px)
MINI_DIAL_BOTTOM_PADDING = 32  # distance from widget bottom edge to bottom of last mini dial (px)
MINI_DIAL_ROW_SPACING = 0  # additional spacing between each row of mini dials (px)
MINI_DIAL_COLUMN_GAP = 18  # horizontal gap between mini dial centers (px)
MINI_DIAL_CLUSTER_OFFSET_X = 16  # horizontal offset that pushes the mini dial cluster into the widget (px)
MINI_DIAL_CLUSTER_RIGHT_MARGIN = 32  # keep-out margin from widget right edge for mini dial cluster (px)
MINI_DIAL_RADIUS = 21  # default radius (px) for mini dials; 25 -> 50px diameter
MINI_DIAL_SHOW_VALUE = False  # whether mini dial labels include numeric value text
MINI_DIAL_LABEL_EXTRA_WIDTH = 15  # additional pixels added to the background width (applied symmetrically)

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



LOG_BAR_HEIGHT = 20  # Pixel height of the on-screen log/status bar