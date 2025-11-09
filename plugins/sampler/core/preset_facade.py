"""Facade around preset persistence used by sampler instruments."""

from __future__ import annotations

from typing import Any, Protocol


class PresetFacade(Protocol):
    """Protocol describing preset-manager interactions."""

    def save_state(self, instrument_id: str, state: dict[str, Any]) -> None:
        """Persist sampler state for the given instrument."""

    def load_state(self, instrument_id: str) -> dict[str, Any] | None:
        """Return previously saved state for the instrument, if available."""


class NullPresetFacade:
    """Placeholder preset facade for scaffolding and tests."""

    def save_state(self, instrument_id: str, state: dict[str, Any]) -> None:  # pragma: no cover
        """Drop state updates so callers can continue with legacy fallbacks."""
        return None

    def load_state(self, instrument_id: str) -> dict[str, Any] | None:  # pragma: no cover
        """Report that no preset data is available."""
        return None
