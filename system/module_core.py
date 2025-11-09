"""
module_core.py
--------------
Neutral home for the ModuleBase superclass.
Keeps it outside the UI layer to avoid circular imports.
"""

import showlog
import config.performance as perf_cfg

class ModuleBase:
    """Base class for all modules (no UI code)."""

    def __init__(self):
        showlog.debug(f"[ModuleBase] init {self.__class__.__name__}")
        
        # Hardware dial pickup/latch system
        # Tracks hardware dial positions and latch states to prevent jumps
        self.hardware_dial_positions = {i: 0 for i in range(1, 9)}  # Slots 1-8
        self.dial_latch_states = {
            i: {
                "latched": False,        # Is this dial currently latched?
                "target_value": 0,       # Value we're waiting to cross
                "previous_hw_value": 0   # Last hardware position (for crossover detection)
            }
            for i in range(1, 9)
        }
        self.dial_pickup_threshold = perf_cfg.DIAL_PICKUP_THRESHOLD

    # --- Standard hooks (default no-ops) ---
    def on_init(self):          pass
    def on_dial_change(self, *a): pass
    def on_button(self, *a):    pass
