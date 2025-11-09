"""Utility helpers for working with sampler dial bank arrays."""

from __future__ import annotations

from typing import Iterable, List


def normalize_bank(values: Iterable[int] | None, size: int = 8, fill: int = 0) -> List[int]:
    """Return a list padded or truncated to *size* entries.

    Mirrors the legacy Drumbo behaviour of clamping bank arrays to eight
    elements, defaulting missing positions to zero. Inputs may be any iterable
    of ints (or coercible to int) and are converted into a concrete list.
    """

    padded = list(values or [])
    if len(padded) < size:
        padded.extend([fill] * (size - len(padded)))
    return padded[:size]
