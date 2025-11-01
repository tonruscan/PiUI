"""
Production Profile - Optimized Settings
Default configuration for production/hardware use.
"""

# Override performance settings for production
FPS_NORMAL = 25
FPS_TURBO = 120
FPS_LOW = 12

# Production logging (minimal)
LOG_LEVEL = 0
DEBUG = False
VERBOSE_LOG = False
DEBUG_LOG = False
LOG_REMOTE_ENABLED = True

# Full dirty rect optimization
DIRTY_MODE = True
DIRTY_BURST_MODE = True
