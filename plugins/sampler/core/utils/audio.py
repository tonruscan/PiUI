"""Audio related helpers reused across sampler instruments."""

from __future__ import annotations

from typing import Iterable, Optional


def match_device_by_name(needle: str | None, haystack: Iterable[str | bytes]) -> Optional[str]:
    """Return the first device name matching *needle* exactly or partially.

    The function mirrors Drumbo's behaviour: first attempt a case-insensitive
    exact match, then fall back to substring search. Bytes entries are decoded
    using UTF-8 with error ignore semantics, matching pygame's device listing.
    """

    if not needle:
        return None

    target = str(needle).lower()

    decoded = []
    for device in haystack:
        if isinstance(device, str):
            decoded.append(device)
        else:
            try:
                decoded.append(device.decode("utf-8", "ignore"))
            except Exception:
                continue

    for name in decoded:
        if name.lower() == target:
            return name

    for name in decoded:
        if target in name.lower():
            return name

    return None
