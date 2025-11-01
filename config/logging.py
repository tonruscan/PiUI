"""
Logging Configuration
All logging-related settings for the UI system.
"""

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
LOUPE_MODE = True  # show only log network messages that start with * DOESN'T WORK YET!!
LOG_IT_ACTIVE = False  # master enable/disable for logging to file/network

# Master debug flag — must be True to show [DEBUG …] messages at all
DEBUG = True
VSCODE_LINKS = True  # clickable links in log to open in VSCode

# Optional: enable CPU meter in showlog bar
CPU_ON = True

# Optional: enable debug overlay (FPS, queue size, mode)
DEBUG_OVERLAY = False  # Set to True to enable performance overlay

# Log text color (hex)
LOG_TEXT_COLOR = "#FFFFFF"

# Shorten module names in the on-screen log bar (not in file)
LOG_SHORT_NAMES = False
SHOW_LOG_TYPE_AS_TEXT = True

# Remote log forwarding (optional)
LOG_REMOTE_ENABLED = True          # True -> send lines to remote
LOG_REMOTE_HOST = "192.168.137.1"  # change to your Windows PC IP
LOG_REMOTE_PORT = 5051             # match log_receiver.py
LOG_REMOTE_PROTO = "tcp"           # "tcp" (only tcp implemented here)
LOG_REMOTE_RECONNECT_SEC = 5       # reconnect backoff seconds (on failure)
