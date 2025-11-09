"""Legacy import shim for Drumbo widget.

The sampler version of the widget now lives in
``plugins.sampler.instruments.drumbo.ui.main_widget``.  Keep this module intact
so existing imports continue to resolve while we migrate callers.
"""

from plugins.sampler.instruments.drumbo.ui.main_widget import DrumboMainWidget

__all__ = ["DrumboMainWidget"]
