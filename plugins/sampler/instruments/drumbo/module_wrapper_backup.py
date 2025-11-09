"""Drumbo wrapper backup stub.

The sampler-native Drumbo instrument now lives in
``plugins.sampler.instruments.drumbo.module``. This module only exists to flag
any lingering imports from the old wrapper during cleanup.
"""

raise ImportError(
	"Drumbo wrapper backup removed; use DrumboInstrument from "
	"plugins.sampler.instruments.drumbo.module."
)
