# Legacy Drumbo plugin has been retired.
#
# The sampler-native implementation now lives at
# `plugins.sampler.instruments.drumbo.module.DrumboInstrument` and the sampler
# plugin shell handles page registration directly. Importers should depend on
# the sampler package instead of this module.

raise ImportError(
    "'plugins.drumbo_plugin' has been removed. Import DrumboInstrument from "
    "plugins.sampler.instruments.drumbo.module instead."
)
