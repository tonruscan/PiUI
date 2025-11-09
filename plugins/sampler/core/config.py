"""Shared configuration defaults for the sampler core.

This file will eventually centralize paths, environment overrides, and
feature toggles that apply across all sampler instruments.
"""

from __future__ import annotations

from pathlib import Path

# Base path used to resolve instrument assets. Individual instruments can
# override this via their own configuration modules or metadata.
SAMPLE_ROOT = Path("assets") / "samples" / "instruments"

# Default value applied to instrument dials when metadata omits explicit
# defaults. Instruments can override this through their own config modules.
DEFAULT_DIAL_LEVEL = 100

# Toggle for enabling the forthcoming multi-instrument sampler shell.
SAMPLER_SHELL_ENABLED = False
