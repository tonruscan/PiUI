"""Sample naming helpers used for round-robin playback grouping."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Tuple, Union

PathOrStr = Union[str, Path]


def extract_sample_tokens(sample_path: PathOrStr) -> Tuple[str, Optional[int]]:
    """Return (label, sequence) parsed from *sample_path*.

    Mirrors Drumbo's legacy helper, ensuring existing metadata mappings remain
    compatible when shared with the sampler core utilities.
    """

    stem = sample_path.stem if isinstance(sample_path, Path) else Path(sample_path).stem
    parts = stem.split("_") if stem else []
    if len(parts) >= 3:
        label_segment = parts[2]
    elif len(parts) >= 2:
        label_segment = parts[1]
    else:
        label_segment = parts[0] if parts else "mic"

    label_segment = label_segment.strip() or "mic"
    suffix_parts = label_segment.split("-")
    label_token = suffix_parts[0] if suffix_parts and suffix_parts[0] else label_segment

    sequence = None
    for chunk in suffix_parts[1:]:
        match = re.search(r"(\d+)", chunk)
        if match:
            sequence = int(match.group(1))
            break

    if sequence is None:
        match = re.search(r"(\d+)$", stem)
        if match:
            sequence = int(match.group(1))

    label = label_token.replace(" ", "").replace("-", "_").strip().upper() or "MIC"
    return label, sequence
