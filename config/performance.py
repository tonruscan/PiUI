"""
Performance & Rendering Configuration
FPS control, dirty rect optimization, and rendering modes.
"""

# --- Partial update burst mode (only while a dial is moving) ---
DIRTY_MODE = True            # master switch
DIRTY_FALLBACK_MS = 1500     # force a full repaint at least this often (safety)
DIRTY_BURST_MODE = True      # enable burst-only dirty updates
DIRTY_GRACE_MS = 120         # keep dirty mode this long after the last dial update
DIRTY_FORCE_FULL_FRAMES = 2  # draw this many full frames after burst ends

# Extra padding (pixels) applied to every widget dirty rect. Accepts int or (x, y).
DIRTY_WIDGET_PADDING = (16, 16)

# Pages that should NOT use dirty rect optimization (always full frame)
# Use this for pages with complex layouts that don't have dial widgets
# DEPRECATED: Use PLUGIN_METADATA with requires_full_frame=True instead.
# This tuple is kept for backward compatibility only.
EXCLUDE_DIRTY = ("presets", "module_presets", "patchbay", "drumbo")

# --- Frame rate control ---
# FPS presets for different rendering scenarios
# - LOW: for static pages to save CPU (e.g. patchbay, device select)
# - NORMAL: default for most pages
# - HIGH: for MIDI/CV interaction pages (dials, vibrato, mixer)
# - BURST: during dial interactions (matches audio engine 100Hz)
FPS_LOW    = 12
FPS_NORMAL = 60          # default for most pages  
FPS_HIGH   = 100         # all MIDI/CV interaction pages like dials
FPS_BURST  = 100         # burst mode for dial interactions (matches audio 100Hz)

# Page assignment for FPS presets. Any page not listed defaults to NORMAL.
# Use UI page keys (e.g. "dials", "device_select", "presets", "patchbay", "mixer").
# DEPRECATED: Use PLUGIN_METADATA in page modules instead. These tuples are kept
# for backward compatibility with pages that haven't been migrated yet.
FPS_LOW_PAGES  = ("patchbay", "device_select")
FPS_HIGH_PAGES = ("dials", "vibrato", "mixer", "drumbo") 

# --- Dynamic FPS Scaling ---
# Experimental: Reduce FPS for idle pages (no user interaction)
DYNAMIC_FPS_SCALING = False  # Default off - enable in dev profile for testing

# Frames before considering page "idle" and reducing FPS to 50%
IDLE_FPS_THRESHOLD = 30  # ~0.5 seconds at 60 FPS

# --- Dirty Rect Debug & Safety ---
# Auto-disable dirty rect for "silent" plugins (don't mark dirty after N full frames)
DIRTY_RECT_TIMEOUT = 3  # Number of consecutive full frames before disabling

# Debug overlay: Draw magenta boxes around dirty regions
DEBUG_DIRTY_OVERLAY = False  # Enable in dev profile

# Optional: emit detailed dirty rect logging for diagnostics
DEBUG_DIRTY_LOG = False

# Frame trace: Log every frame render with timing (very verbose)
FRAME_TRACE = False  # Enable for debugging render bottlenecks

# --- Hardware Dial Pickup/Latch System ---
# When hardware dial position doesn't match visual dial, latch until crossover
# Prevents jumps when switching banks or pages
DIAL_PICKUP_THRESHOLD = 10  # Units within target for crossover detection (0-127 scale)
 
# --- Logger Bar Throttling ---
LOG_BAR_UPDATE_HZ = 25      # updates per second (1 = once every second)
