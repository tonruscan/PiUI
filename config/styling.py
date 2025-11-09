"""
Visual Styling Configuration
Colors, fonts, and visual appearance for all UI elements.
"""

import os
import sys

# Import font helper for font path resolution
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
import utils.font_helper as font_helper

# ================== DIAL STYLING ==================

# Dial drawing configuration
DIAL_SUPERSAMPLE = 4        # 1=off, 2 recommended
DIAL_FACE_SUPERSAMPLE = 4   # cached dial face supersample (override if you want different AA)
DIAL_FACE_CACHE_VERSION = 2 # bump to force dial face cache rebuild after tuning AA settings
DIAL_RING_AA_SHELLS = 0.5   # 0..2 (try 1 for a touch more softness)
DIAL_SIZE = 50
DIAL_LINE_WIDTH = 4         # circle outline width
DIAL_POINTER_WIDTH = 8      # pointer thickness

# --- Dial Colors (Active) ---
DIAL_PANEL_COLOR = "#0A2F65"     # background panel behind dial
DIAL_FILL_COLOR = "#000000"      # inner filled circle color
DIAL_OUTLINE_COLOR = "#000000"   # dial outline color
DIAL_TEXT_COLOR = "#FF8000"      # label text color

# Label rectangles inherit dial panel color by default
DIAL_LABEL_COLOR = "#000000"

# Mini dial specific label styling
MINI_DIAL_LABEL_COLOR = "#0A2752"
MINI_DIAL_LABEL_TEXT_COLOR = "#FFFFFF"
MINI_DIAL_LABEL_HEIGHT = 20
MINI_DIAL_LABEL_PADDING_X = 0
MINI_DIAL_FONT_SIZE = 16

# Plugin / widget background color (default to dial panel color)
PLUGIN_BACKGROUND_COLOR = "#0A2F65"

# --- Dial Colors (Offline/Empty) ---
DIAL_OFFLINE_PANEL   = "#111111"
DIAL_OFFLINE_FILL    = "#000000"
DIAL_OFFLINE_OUTLINE = "#000000"
DIAL_OFFLINE_TEXT    = "#000000"

# --- Dial Colors (Muted) ---
DIAL_MUTE_PANEL   = "#222222"   # background block
DIAL_MUTE_FILL    = "#000000"   # inner circle
DIAL_MUTE_OUTLINE = "#222222"   # circle outline
DIAL_MUTE_TEXT    = "#555555"   # label text

# --- Dial Typography ---
DIAL_FONT_SIZE = 22
DIAL_FONT_SPACING = 1
DIAL_FONT_UPPER = True

# --- Dial Value Type (unit) Appearance ---
TYPE_FONT_SCALE = 0.9        # relative to DIAL_FONT_SIZE (e.g., 0.7 = 70%)
TYPE_FONT_COLOR = "#B4B4B4"  # smaller text color
TYPE_FONT_OFFSET_Y = 3       # pixels down relative to main text baseline
TYPE_FONT_SPACING = -3       # pixels of space between value and unit

# ================== BUTTON STYLING ==================

BUTTON_FILL = "#071C3C"               # normal button fill (default blue)
BUTTON_OUTLINE = "#0D3A7A"            # button border/outline
BUTTON_TEXT = "#FFFFFF"               # button text color
BUTTON_DISABLED_FILL = "#1E1E1E"      # disabled button fill
BUTTON_DISABLED_TEXT = "#646464"      # disabled button text
BUTTON_ACTIVE_FILL = "#0050A0"        # active/pressed button fill (brighter blue)
BUTTON_ACTIVE_TEXT = "#FFFFFF"        # active/pressed button text

BUTTON_SELECTED_COLOR = "#BCBCBC"     # background when page is selected
BUTTON_TEXT_SELECTED = "#06214B"      # text color when page is selected

# ================== LABEL STYLING ==================

LABEL_RECT_WIDTH = 130
LABEL_RECT_HEIGHT = 24
LABEL_COLOR = DIAL_LABEL_COLOR
LABEL_RECT = False

# ================== HEADER STYLING ==================

HEADER_TEXT_COLOR = "#BCBCBC"
HEADER_BG_COLOR = "#0B1C34"
HEADER_LETTER_SPACING = 0
HEADER_HEIGHT = 60    # height of header bar (pixels)

# ================== MENU STYLING ==================

MENU_COLOR = "#060606"                        # Background color of dropdown
MENU_FONT = font_helper.main_font("Thin")     # Path to TTF font file
MENU_FONT_SIZE = 60                           # Font size for menu labels
MENU_FONT_COLOR = "#FFFFFF"                   # Text color
MENU_ANIM_SPEED = 0.5                         # higher = faster, lower = slower
MENU_HEIGHT = 200                             # height of dropdown menu when open (pixels)
MENU_BUTTON_WIDTH = 140
MENU_BUTTON_HEIGHT = 65                       # width, height of each button in dropdown
MENU_BUTTON_RADIUS = 4                        # corner radius of buttons
MENU_BUTTON_COLOR = "#000000"                 # default button color

# ================== PATCHBAY STYLING ==================

PORT_SPACING = 30                       # horizontal distance between sockets
PORT_NUMBER_SIZE = 14                   # font size for numbers inside circles
PORTS_TOP_PADDING = 132                 # distance from top of screen to first row
PORT_COLOR_USED = "#9D9D9D"             # orange-ish for labelled sockets
PORT_COLOR_UNUSED = "#0B1C34"           # grey for empty sockets
PORT_NUMBER_USED_COLOR = "#0B1C34"      # orange-ish for labelled sockets
PORT_NUMBER_UNUSED_COLOR = "#9D9D9D"    # grey for empty sockets
PORT_ROW_SPACING = 45                   # vertical distance between rows
PORT_BORDER_COLOR = "#FFFFFF"           # outline color around every socket
PORT_BORDER_WIDTH = 2                   # thickness of the outline
PORT_LABEL_OFFSET = 18                  # distance between top of circle and label text
PORT_BANK_GAP = 37                      # vertical gap between banks of ports
PORT_LABEL_COLOR = "#FF8000"            # color for port labels

# --- Patchbay Connections ---
PORT_LINK_COLOR = "#04FF00"             # bright green
PORT_LINK_WIDTH = 1                     # thickness of connection lines

# --- IN/OUT LABEL SETTINGS ---
INOUT_LABEL_FONT = "Arial"
INOUT_LABEL_SIZE = 14
INOUT_LABEL_BOLD = True
INOUT_LABEL_COLOR = "#DDDDDD"
INOUT_LABEL_ROTATION = 90               # degrees CCW
INOUT_LABEL_OFFSET_X = 4                # horizontal distance from sockets
INOUT_LABEL_BANKS = True                # True = draw both top + bottom banks
INOUT_LABEL_LETTER_SPACING = 7          # pixels between letters
INOUT_LABEL_MIRROR = True               # draw mirrored text on right side

# --- IN/OUT LABEL COLORS ---
IN_TEXT_LEFT_COLOR  = "#FFFFFF"
OUT_TEXT_LEFT_COLOR = "#C3C3C3"
IN_TEXT_RIGHT_COLOR  = "#C3C3C3"
OUT_TEXT_RIGHT_COLOR = "#969696"

# ================== PRESETS PAGE STYLING ==================

NUMBER_OF_PRESET_COLUMNS = 4            # Default; can be 3 or 4 for tighter layout
PRESET_FONT_SIZE = 30
PRESET_BUTTON_WIDTH = 165
PRESET_BUTTON_HEIGHT = 50
PRESET_BUTTON_COLOR = "#090909"
PRESET_TEXT_COLOR = "#FF8000"
PRESET_SPACING_Y = 15
PRESET_MARGIN_X = 50
PRESET_MARGIN_Y = 80
PRESET_TEXT_PADDING_X = 10              # padding inside button for text
PRESET_TEXT_PADDING_y = 10
PRESET_LABEL_HIGHLIGHT_COLOR = "#202020"  # when mouse is over button
PRESET_FONT_HIGHLIGHT = "#FFFFFF"       # when mouse is over button
PRESET_LABEL_HIGHLIGHT = "#202020"      # when selected
PRESET_FONT_WEIGHT = "Thin"
SCROLL_BAR_COLOR = "#232323"            # color of the scrollbar

# ================== MIXER PAGE STYLING ==================

# --- Mixer Colors ---
MIXER_TRACK_COLOR         = "#1A1A1A"   # main track background
MIXER_KNOB_COLOR          = "#FF8000"   # bright orange knob
MIXER_MUTE_COLOR_OFF      = "#3C3C3C"   # dark grey mute
MIXER_MUTE_COLOR_ON       = "#FF3232"   # red mute
MIXER_LABEL_COLOR         = "#C8C8C8"   # light grey label
MIXER_VALUE_COLOR         = "#939393"   # numeric readout color
MIXER_BG_COLOR            = "#000000"   # optional page background

# --- Mixer Panel ---
MIXER_PANEL_ENABLED       = True        # master on/off
MIXER_PANEL_COLOR         = "#0E0E0E"
MIXER_PANEL_RADIUS        = 12
MIXER_PANEL_WIDTH         = 120         # pixels — all fader panels use this fixed width
MIXER_PANEL_PADDING_Y     = 14          # top/bottom padding around the whole fader module
MIXER_PANEL_OUTLINE_WIDTH = 0           # set >0 to draw an outline
MIXER_PANEL_OUTLINE_COLOR = "#202020"

# --- Mixer Typography ---
MIXER_LABEL_FONT_SCALE = 1.2
MIXER_VALUE_FONT_SCALE = 1.0
MIXER_MUTE_FONT_SCALE  = 1.2
MIXER_LABEL_SPACING = 5  # pixels between letters
