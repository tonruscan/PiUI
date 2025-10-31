## CC Config


# -------------------------------------------------------
# Logging configuration
# -------------------------------------------------------

# Verbosity levels:
#   0 = ERROR  → only critical errors
#   1 = WARN   → warnings and errors
#   2 = INFO   → normal info (default)
LOG_OFF = False
ECO_MODE = False  # activates low-CPU selective logging

LOG_LEVEL = 0
NET_DEBUG = True
VERBOSE_LOG = False
DEBUG_LOG = False
LOUPE_MODE = True # show only log network messages that start with * DOESN'T WORK YET!!
LOG_IT_ACTIVE = False  # master enable/disable for logging to file/network
# Master debug flag — must be True to show [DEBUG …] messages at all
DEBUG = True
VSCODE_LINKS = True  # clickable links in log to open in VSCode
# Optional: enable CPU meter in showlog bar
CPU_ON = True

# Log text color (hex)
LOG_TEXT_COLOR = "#FFFFFF"
# Shorten module names in the on-screen log bar (not in file)
LOG_SHORT_NAMES = False
SHOW_LOG_TYPE_AS_TEXT = True
DISABLE_HEADER = False  # Set to True to disable header rendering (troubleshooting)

# --- System Settings ---

# --- Partial update burst mode (only while a dial is moving) ---

DIRTY_MODE = True            # master switch
DIRTY_FALLBACK_MS = 1500     # force a full repaint at least this often (safety)
DIRTY_BURST_MODE = True      # enable burst-only dirty updates
DIRTY_GRACE_MS = 120         # keep dirty mode this long after the last dial update
DIRTY_FORCE_FULL_FRAMES = 2  # draw this many full frames after burst ends


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

# remote log forwarding (optional)
LOG_REMOTE_ENABLED = True          # True -> send lines to remote
LOG_REMOTE_HOST = "192.168.137.1"  # change to your Windows PC IP
LOG_REMOTE_PORT = 5051             # match log_receiver.py
LOG_REMOTE_PROTO = "tcp"           # "tcp" (only tcp implemented here)
LOG_REMOTE_RECONNECT_SEC = 5       # reconnect backoff seconds (on failure)

# --- Frame rate control ---
# Tri-state FPS presets
# - LOW: for lightweight/static pages to save CPU (e.g. patchbay)
# - NORMAL: default for most pages
# - TURBO: for highly animated pages that need extra smoothness
FPS_LOW    = 12
FPS_NORMAL = 25          # default for most pages
FPS_TURBO  = 120

# Page assignment for FPS presets. Any page not listed defaults to NORMAL.
# Use UI page keys (e.g. "dials", "device_select", "presets", "patchbay", "mixer").

FPS_LOW_PAGES   = ("patchbay","device_select")
FPS_TURBO_PAGES = ("dials",)
# Legacy single-page override (no longer used by ui.py)
# PATCHBAY_FPS = 25


# --- Presets Page ---
PRESET_SCROLL_SPEED = 3.0   # higher = faster scrolling (try 2.0–5.0)
PRESET_LOAD_DELAY_MS = 10
PRESET_INITIAL_SCROLL_DELAY_MS = 5000  # delay before first scroll step
PRESET_INITIAL_SCROLL_MAX_WAIT_MS = 1000  # max total wait time before giving up
PRESET_SELECTED_PADDING = 177  # extra vertical padding for selected preset button

# --- Button MIDI settings ---
BUTTON_CC_START = 16  # base CC number for buttons 1–5
# --- Dial MIDI settings ---
DIAL_CC_START = 70  # first dial sends CC30, next 31, etc.
CC_CHANNEL = 9           # MIDI channel (0 = CH1, 1 = CH2, etc.)




import utils.font_helper as font_helper

# Styling configuration
# =======================================================
DIAL_SUPERSAMPLE = 4        # 1=off, 2 recommended
DIAL_RING_AA_SHELLS = 0.5     # 0..2 (try 1 for a touch more softness)
# DIAL_LINE_WIDTH = 0       # alternative: disable ring entirely


# config.py (example)
DIAL_SIZE = 50
DIAL_PADDING_X = 100  # tighter layout
DIAL_PADDING_X = 180  # more breathing room

# Dial drawing widths
DIAL_LINE_WIDTH     = 4     # circle outline width
DIAL_POINTER_WIDTH  = 8     # pointer thickness

# --- Dial Appearance ---
DIAL_PANEL_COLOR = "#0A2F65"     # background panel behind dial
DIAL_FILL_COLOR = "#000000"      # inner filled circle color
DIAL_OUTLINE_COLOR = "#000000"   # dial outline color
DIAL_TEXT_COLOR = "#FF8000" # label text color

# ---------- Dial Offline (EMPTY) ----------
DIAL_OFFLINE_PANEL   = "#313134"
DIAL_OFFLINE_FILL    = "#222222"
DIAL_OFFLINE_OUTLINE = "#222222"
DIAL_OFFLINE_TEXT    = "#000000"

DIAL_OFFLINE_PANEL   = "#111111"
DIAL_OFFLINE_FILL    = "#000000"
DIAL_OFFLINE_OUTLINE = "#000000"
DIAL_OFFLINE_TEXT    = "#000000"

# --- Dial colours when muted ---
DIAL_MUTE_PANEL   = "#222222"   # background block
DIAL_MUTE_FILL    = "#000000"   # inner circle
DIAL_MUTE_OUTLINE = "#222222"   # circle outline
DIAL_MUTE_TEXT    = "#555555"   # label text


# --- Disabled button colours ---
BUTTON_DISABLED_COLOR = "#333333"       # background
BUTTON_TEXT_DISABLED = "#777777"        # text



BUTTON_OFFSET_X = 40   # closer to left edge
BUTTON_SPACING_Y = 13  # increase gap between buttons
BUTTON_OFFSET_Y = 100   # top offset for first button

BUTTON_COLOR = "#071C3C"       # default blue
BUTTON_ACTIVE_COLOR = "#000000"   # highlighted when pressed
BUTTON_TEXT_COLOR = "#FFFFFF"       # default text

BUTTON_SELECTED_COLOR = "#BCBCBC"   # background when page is selected
BUTTON_TEXT_SELECTED = "#06214B"    # text color when page is selected

LABEL_RECT_WIDTH = 130
LABEL_RECT_HEIGHT = 24
LABEL_COLOR = "#000000"
LABEL_RECT = False

# ---------- Dial Value Type (unit) Appearance ----------
TYPE_FONT_SCALE = .9        # relative to DIAL_FONT_SIZE (e.g., 0.7 = 70%)
TYPE_FONT_COLOR = "#B4B4B4"  # smaller text color (e.g., warm orange)
TYPE_FONT_OFFSET_Y = 3      # pixels down relative to main text baseline
TYPE_FONT_SPACING = -3       # pixels of space between value and unit

HEADER_TEXT_COLOR = "#BCBCBC"
HEADER_BG_COLOR = "#0B1C34"
HEADER_LETTER_SPACING = 0

# ---------------- PATCHBAY STYLE ----------------
PORT_SPACING = 30          # horizontal distance between sockets
PORT_NUMBER_SIZE = 14      # font size for numbers inside circles
PORTS_TOP_PADDING = 132    # distance from top of screen to first row
PORT_COLOR_USED = "#9D9D9D"  # orange-ish for labelled sockets
PORT_COLOR_UNUSED = "#0B1C34"   # grey for empty sockets
PORT_NUMBER_USED_COLOR  = "#0B1C34"  # orange-ish for labelled sockets
PORT_NUMBER_UNUSED_COLOR = "#9D9D9D"   # grey for empty sockets
PORT_ROW_SPACING = 45           # vertical distance between rows
PORT_BORDER_COLOR = "#FFFFFF"   # outline color around every socket
PORT_BORDER_WIDTH = 2              # thickness of the outline
PORT_LABEL_OFFSET = 18   # distance between top of circle and label text
PORT_BANK_GAP = 37      # vertical gap between banks of ports
PORT_LABEL_COLOR = "#FF8000"  # color for port labels

# ---------------- PATCHBAY CONNECTIONS ----------------
PORT_LINK_COLOR = "#04FF00"   # bright orange
PORT_LINK_WIDTH = 1           # thickness of connection lines

BACK_BUTTON_SIZE = 50  # or (40, 40)
BACK_BUTTON_TOP_PAD = 2  # move slightly up
BACK_BUTTON_LEFT_PAD = 8

BURGER_BUTTON_SIZE = 42  # or (40, 40)
BURGER_BUTTON_TOP_PAD = 0  # move slightly up
BURGER_BUTTON_RIGHT_PAD = 12

# -------------------------------------------------------
# Dropdown Menu (Header Menu) Styling
# -------------------------------------------------------
MENU_COLOR = "#060606"         # Background color of dropdown
#DIAL_FONT_WEIGHT = "UltraBold"
MENU_FONT = font_helper.main_font("Thin")  # Path to TTF font file
# MENU_FONT = "Courier"     # Default font (or None for system default)
MENU_FONT_SIZE = 60            # Font size for menu labels
MENU_FONT_COLOR = "#FFFFFF"    # Text color

MENU_ANIM_SPEED = 0.5   # higher = faster, lower = slower (e.g. 0.15 for slower)
HEADER_HEIGHT = 60    # height of header bar (pixels)
MENU_HEIGHT = 200   # height of dropdown menu when open (pixels)
MENU_BUTTON_WIDTH = 140
MENU_BUTTON_HEIGHT = 65  # width, height of each button in dropdown
MENU_BUTTON_RADIUS = 4  # corner radius of buttons

MENU_BUTTON_COLOR = "#000000"          # default button color

# --- IN/OUT LABEL SETTINGS ---
INOUT_LABEL_FONT = "Arial"
INOUT_LABEL_SIZE = 14
INOUT_LABEL_BOLD = True
INOUT_LABEL_COLOR = "#DDDDDD"
INOUT_LABEL_ROTATION = 90        # degrees CCW
INOUT_LABEL_OFFSET_X = 4       # horizontal distance from sockets
INOUT_LABEL_BANKS = True         # True = draw both top + bottom banks
INOUT_LABEL_LETTER_SPACING = 7   # pixels between letters
INOUT_LABEL_MIRROR = True            # draw mirrored text on right side

# --- IN/OUT LABEL COLORS ---

IN_TEXT_LEFT_COLOR  = "#FFFFFF"
OUT_TEXT_LEFT_COLOR = "#C3C3C3"
IN_TEXT_RIGHT_COLOR  = "#C3C3C3"
OUT_TEXT_RIGHT_COLOR = "#969696"



# Add configuration variables for presets
NUMBER_OF_PRESET_COLUMNS = 4  # Default; can be 3 or 4 for tighter layout

PRESET_FONT_SIZE = 30
PRESET_BUTTON_WIDTH = 165
PRESET_BUTTON_HEIGHT = 50
PRESET_BUTTON_COLOR = "#090909"
PRESET_TEXT_COLOR = "#FF8000"
PRESET_SPACING_Y = 15
PRESET_MARGIN_X = 50
PRESET_MARGIN_Y = 80
PRESET_TEXT_PADDING_X = 10  # padding inside button for text
PRESET_TEXT_PADDING_y = 10

PRESET_LABEL_HIGHLIGHT_COLOR = "#202020"  # when mouse is over button
PRESET_FONT_HIGHLIGHT = "#FFFFFF"   # when mouse is over button
PRESET_LABEL_HIGHLIGHT = "#202020"  # when selected
PRESET_FONT_WEIGHT = "Thin"
SCROLL_BAR_COLOR = "#232323"  # color of the scrollbar



# Font appearance
DIAL_FONT_SIZE = 22
DIAL_FONT_SPACING = 1
DIAL_FONT_UPPER = True

DEVICE_BUTTON_TOP_PADDING = 100  # Top padding for device select buttons




# ================================
# 🎚️  MIXER PAGE CONFIG
# ================================

# Mixer performance tuning
MIXER_MIDI_THROTTLE = 0.1   # seconds between sends (10 Hz)

# --- Layout Geometry ---
MIXER_TOP_MARGIN          = 140      # distance from top of screen to top of faders
MIXER_HEIGHT              = 220      # fader height in pixels
MIXER_WIDTH               = 28       # fader track width
MIXER_SPACING             = 160      # horizontal spacing between faders
MIXER_LABEL_OFFSET_Y      = 30       # distance above fader for label
MIXER_VALUE_OFFSET_Y      = 15       # distance below fader for numeric value
MIXER_MUTE_OFFSET_Y       = 36       # distance below value for mute button
MIXER_VALUE_OFFSET_X      = -2        # horizontal offset for numeric value
MIXER_MUTE_WIDTH          = 28       # mute button width
MIXER_MUTE_HEIGHT         = 28       # mute button height
MIXER_CORNER_RADIUS       = 6        # rounded corner for tracks and mute buttons

# --- Colors ---
MIXER_TRACK_COLOR         = "#1A1A1A"   # main track background
MIXER_KNOB_COLOR          = "#FF8000"   # bright orange knob
MIXER_MUTE_COLOR_OFF      = "#3C3C3C"   # dark grey mute
MIXER_MUTE_COLOR_ON       = "#FF3232"   # red mute
MIXER_LABEL_COLOR         = "#C8C8C8"   # light grey label
MIXER_VALUE_COLOR         = "#939393"   # numeric readout color
MIXER_BG_COLOR            = "#000000"   # optional page background

# --- Typography ---
# MIXER_FONT_NAME           = font_helper.main_font("Thin")       # main mixer label font
# MIXER_FONT_SIZE           = 20
# MIXER_FONT_WEIGHT         = "medium"
# MIXER_LABEL_CASE          = "upper"       # "upper", "lower", or "title"
# MIXER_LABEL_SPACING       = 1.2           # optional letter spacing multiplier

# In config.py
MIXER_LABEL_FONT_SCALE = 1.2
MIXER_VALUE_FONT_SCALE = 1.0
MIXER_MUTE_FONT_SCALE  = 1.2
MIXER_LABEL_SPACING = 5  # pixels between letters

MIXER_PANEL_ENABLED       = True     # master on/off
MIXER_PANEL_COLOR         = "#0E0E0E"
MIXER_PANEL_RADIUS        = 12
MIXER_PANEL_WIDTH         = 120  # pixels — all fader panels use this fixed width
MIXER_PANEL_PADDING_Y     = 14       # top/bottom padding around the whole fader module
MIXER_PANEL_OUTLINE_WIDTH = 0        # set >0 to draw an outline
MIXER_PANEL_OUTLINE_COLOR = "#202020"

# --- Behaviour ---
MIXER_VALUE_RANGE         = 99            # Quadraverb uses 0–99
MIXER_MUTE_FLASH_MS       = 120           # optional visual flash duration
MIXER_MUTE_SEND_CC        = True          # whether mute toggles send CC/SysEx


import os, sys

# Base path for the project
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Font directory (relative to this file)
FONT_DIR = os.path.join(BASE_DIR, "assets", "fonts")

# Config directory for JSON files
CONFIG_DIR = os.path.join(BASE_DIR, "config")

# --- Core project directories ---
DEVICE_DIR = os.path.join(BASE_DIR, "device")
SYSTEM_DIR = os.path.join(BASE_DIR, "system")
PAGES_DIR  = os.path.join(BASE_DIR, "pages")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
STATES_DIR = os.path.join(BASE_DIR, "states")
UTILS_DIR = os.path.join(BASE_DIR, "utils")


def config_path(filename):
    """Return full path for a JSON config file inside /config."""
    return os.path.join(CONFIG_DIR, filename)


def sys_folders():
    """Ensure all key project folders are importable."""
    for path in (BASE_DIR, DEVICE_DIR, SYSTEM_DIR, PAGES_DIR, ASSETS_DIR):
        if path not in sys.path:
            sys.path.append(path)

