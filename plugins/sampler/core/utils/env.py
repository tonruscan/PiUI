"""Environment variable parsing helpers shared by sampler instruments."""

from __future__ import annotations

import os
from typing import Optional


def parse_int(key: str) -> Optional[int]:
    """Return integer value from environment *key* or None if unset/invalid."""

    raw = os.environ.get(key)
    if raw is None:
        return None
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return None


def parse_bool(key: str) -> Optional[bool]:
    """Return boolean value from environment *key* with Drumbo semantics."""

    raw = os.environ.get(key)
    if raw is None:
        return None

    value = str(raw).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return None
