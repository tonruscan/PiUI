"""Core interfaces for sampler instrument modules.

The goal of this module is to provide a stable contract between the sampler
core (registry, event routing, preset handling) and individual instrument
implementations such as Drumbo.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any, Optional

from plugins.sampler.core.event_bridge import EventBridge, SamplerEvent
from plugins.sampler.core.mixer_facade import MixerFacade
from plugins.sampler.core.preset_facade import PresetFacade


@dataclass
class InstrumentDescriptor:
    """Metadata describing an instrument available to the sampler.

    The descriptor is intentionally mutable so the registry can update
    properties (e.g., metadata paths or display names) as new information is
    discovered during scans.
    """

    id: str
    display_name: str
    category: str
    version: str
    entry_module: str
    metadata_path: Optional[str] = None
    icon_path: Optional[str] = None
    default_preset: Optional[str] = None

    def to_dict(self) -> dict[str, Optional[str]]:
        """Return a JSON-friendly representation of the descriptor."""

        return {
            "id": self.id,
            "display_name": self.display_name,
            "category": self.category,
            "version": self.version,
            "entry_module": self.entry_module,
            "metadata_path": self.metadata_path,
            "icon_path": self.icon_path,
            "default_preset": self.default_preset,
        }


@dataclass
class InstrumentContext:
    """Shared services and configuration injected into every instrument."""

    mixer: MixerFacade
    presets: PresetFacade
    events: EventBridge
    config: dict[str, Any]


class InstrumentModule(abc.ABC):
    """Abstract base class implemented by every sampler instrument."""

    @abc.abstractmethod
    def activate(self, context: InstrumentContext) -> None:
        """Initialize instrument state and register event handlers."""

    @abc.abstractmethod
    def deactivate(self) -> None:
        """Release resources or unregister event handlers for the instrument."""

    @abc.abstractmethod
    def handle_event(self, event: SamplerEvent) -> None:
        """Process a sampler-level event (UI, MIDI, transport, etc.)."""


class InstrumentFactory(abc.ABC):
    """Optional factory hook for instruments that require custom setup."""

    @abc.abstractmethod
    def create(self) -> InstrumentModule:
        """Return a ready-to-activate instrument module instance."""
