"""
Configuration Package with Profile Loading
Automatically loads the appropriate profile based on UI_ENV environment variable.

Usage:
    export UI_ENV=development  # or 'production', 'safe'
    python ui.py

    Or in code:
    import config
    print(config.FPS_NORMAL)
"""

import os

# Import all base configuration modules first
from .logging import *
from .display import *
from .performance import *
from .midi import *
from .styling import *
from .layout import *
from .pages import *
from .paths import *

# Detect environment profile
_env = os.getenv("UI_ENV", "production").lower()

# Load profile-specific overrides
if _env == "development" or _env == "dev":
    print(f"[CONFIG] Loading DEVELOPMENT profile")
    from .profiles.dev import *
elif _env == "safe":
    print(f"[CONFIG] Loading SAFE MODE profile")
    from .profiles.safe import *
else:
    print(f"[CONFIG] Loading PRODUCTION profile")
    from .profiles.prod import *

# Export current profile name
ACTIVE_PROFILE = _env if _env in ("development", "dev", "safe") else "production"

print(f"[CONFIG] Active profile: {ACTIVE_PROFILE}")
print(f"[CONFIG] FPS_NORMAL={FPS_NORMAL}, FPS_TURBO={FPS_TURBO}, DEBUG={DEBUG}")
