"""Configuration helpers for the sampler auto-slicer pipeline."""

from __future__ import annotations

import os
from pathlib import Path

import config.paths as path_config

# Root directory containing phone field recorder drops (typically .m4a files).
FIELD_RECORDER_ROOT = Path(path_config.ASSETS_DIR) / "samples" / "fieldrecorder"

# Directory where processed recordings (converted PCM and slices) live.
PROCESSED_ROOT = FIELD_RECORDER_ROOT / "processed"

# Maximum slices to extract per recording (matches 4x2 widget layout).
MAX_SLICES = int(os.environ.get("SAMPLER_AUTOSLICER_MAX_SLICES", "8") or 8)

# Minimum slice length and silence gap defaults (milliseconds).
MIN_SLICE_MS = float(os.environ.get("SAMPLER_AUTOSLICER_MIN_SLICE_MS", "80") or 80.0)
MIN_GAP_MS = float(os.environ.get("SAMPLER_AUTOSLICER_MIN_GAP_MS", "60") or 60.0)

# Target PCM format for converted assets.
TARGET_SAMPLE_RATE = int(os.environ.get("SAMPLER_AUTOSLICER_SAMPLE_RATE", "44100") or 44100)
TARGET_CHANNELS = int(os.environ.get("SAMPLER_AUTOSLICER_CHANNELS", "1") or 1)
TARGET_SAMPLE_WIDTH = int(os.environ.get("SAMPLER_AUTOSLICER_SAMPLE_WIDTH", "2") or 2)  # bytes

# Metadata filename stored alongside converted assets.
METADATA_FILENAME = "metadata.json"
