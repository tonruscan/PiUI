"""
Development Profile - Debug-Friendly Settings
Enhanced logging and slower frame rates for easier debugging.
"""

# Development performance (easier to debug)
FPS_NORMAL = 15         # Slower for easier visual debugging
FPS_TURBO = 60          # Half speed turbo
FPS_LOW = 8

# Verbose logging for development
LOG_LEVEL = 2           # INFO level
DEBUG = True
VERBOSE_LOG = True
DEBUG_LOG = True
LOG_REMOTE_ENABLED = True
NET_DEBUG = True

# Enable debug overlay in development
DEBUG_OVERLAY = True    # Show FPS and queue metrics

# Still use dirty rect but with more visual feedback
DIRTY_MODE = True
DIRTY_BURST_MODE = True
DIRTY_GRACE_MS = 200    # Longer grace period for debugging
