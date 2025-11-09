"""
Production Profile - Optimized Settings
Default configuration for production/hardware use.
"""

# Override performance settings for production
FPS_LOW    = 12          # Static pages
FPS_NORMAL = 60          # Normal idle FPS
FPS_HIGH   = 100         # MIDI/CV interaction pages
FPS_BURST  = 100         # Burst mode during dial interactions (matches audio 100Hz)

# Production logging (minimal)
LOG_LEVEL = 0
DEBUG = False
VERBOSE_LOG = False
DEBUG_LOG = False
LOG_REMOTE_ENABLED = True

# Full dirty rect optimization
DIRTY_MODE = True
DIRTY_BURST_MODE = True
