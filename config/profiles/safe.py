"""
Safe Mode Profile - Minimal Features
For troubleshooting or low-resource scenarios.
"""

# Safe mode performance (very conservative)
FPS_NORMAL = 10
FPS_TURBO = 20          # Much slower turbo
FPS_LOW = 5

# Minimal logging (errors only)
LOG_LEVEL = 0           # ERROR only
DEBUG = False
VERBOSE_LOG = False
DEBUG_LOG = False
LOG_REMOTE_ENABLED = False
NET_DEBUG = False
ECO_MODE = True         # Enable eco mode

# Disable dirty rect optimization (use full redraws)
DIRTY_MODE = False
DIRTY_BURST_MODE = False

# Simplified UI
DIAL_SUPERSAMPLE = 1    # No antialiasing
DIAL_RING_AA_SHELLS = 0
