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

# Pages that should NOT use dirty rect optimization (always full frame)
# Use this for pages with complex layouts that don't have dial widgets
EXCLUDE_DIRTY = ("presets", "module_presets", "patchbay", "device_select")

# --- Frame rate control ---
# FPS presets for different rendering scenarios
# - LOW: for static pages to save CPU (e.g. patchbay, device select)
# - NORMAL: default for most pages
# - BURST: during dial interactions (matches audio engine 100Hz)
FPS_LOW    = 12
FPS_NORMAL = 60          # default for most pages  
FPS_BURST  = 100         # burst mode for dial interactions (matches audio 100Hz)

# Page assignment for FPS presets. Any page not listed defaults to NORMAL.
# Use UI page keys (e.g. "dials", "device_select", "presets", "patchbay", "mixer").
FPS_LOW_PAGES = ("patchbay", "device_select")
