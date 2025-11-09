"""Legacy Drumbo plugin stub.

This duplicate module has been fully replaced by the sampler-native Drumbo
implementation in ``plugins.sampler.instruments.drumbo.module``. Importing this
module is now considered an error so any lingering references can be cleaned
up.
"""

raise ImportError(
    "'drumbo_plugin' has been removed. Use DrumboInstrument from "
    "plugins.sampler.instruments.drumbo.module instead."
)
