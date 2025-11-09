"""Event shims that translate UI or MIDI signals into sampler events."""

from __future__ import annotations

from typing import Any, Protocol

# Temporary event alias used while the sampler event taxonomy is designed.
SamplerEvent = Any


class EventBridge(Protocol):
    """Protocol describing the methods the sampler expects for event routing."""

    def publish(self, event: SamplerEvent) -> None:
        ...


class NullEventBridge:
    """No-op bridge used during scaffolding and tests."""

    def publish(self, event: SamplerEvent) -> None:  # pragma: no cover - trivial
        return None
