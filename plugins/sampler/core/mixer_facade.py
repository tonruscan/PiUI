"""Facade around pygame's mixer to decouple sampler instruments from globals."""

from __future__ import annotations

from typing import Protocol


class MixerFacade(Protocol):
    """Protocol describing mixer operations used by instruments."""

    def ensure_ready(self) -> bool:
        """Return True when the mixer is initialized and ready for playback."""

    def play_sample(self, path: str, volume: float) -> None:
        """Schedule a sample for playback at the requested volume."""


class NullMixerFacade:
    """Placeholder mixer implementation used during scaffolding."""

    def ensure_ready(self) -> bool:  # pragma: no cover - trivial
        """Indicate that the mixer is not available so callers trigger legacy fallbacks."""
        return False

    def play_sample(self, path: str, volume: float) -> None:  # pragma: no cover
        """Ignore playback requests; pygame-backed fallbacks handle the work."""
        return None
