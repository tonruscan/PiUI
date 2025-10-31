"""
module_core.py
--------------
Neutral home for the ModuleBase superclass.
Keeps it outside the UI layer to avoid circular imports.
"""

import showlog

class ModuleBase:
    """Base class for all modules (no UI code)."""

    def __init__(self):
        showlog.debug(f"[ModuleBase] init {self.__class__.__name__}")

    # --- Standard hooks (default no-ops) ---
    def on_init(self):          pass
    def on_dial_change(self, *a): pass
    def on_button(self, *a):    pass
