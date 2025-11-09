"""In-memory registry for sampler instruments.

The registry will eventually support dynamic discovery and hot reloads. For
now it provides simple registration helpers so scaffolding tests can assert
basic behaviour.
"""

from __future__ import annotations

from typing import Dict, Iterable

from plugins.sampler.core.engine import InstrumentDescriptor

# Internal map of instrument id -> descriptor.
_REGISTRY: Dict[str, InstrumentDescriptor] = {}


def register_instrument(descriptor: InstrumentDescriptor) -> None:
    """Register or update an instrument descriptor."""

    _REGISTRY[descriptor.id] = descriptor


def get_instrument(descriptor_id: str) -> InstrumentDescriptor | None:
    """Return the descriptor for the requested instrument, if present."""

    return _REGISTRY.get(descriptor_id)


def list_instruments() -> Iterable[InstrumentDescriptor]:
    """Iterate over registered instrument descriptors."""

    return _REGISTRY.values()


def clear_registry() -> None:
    """Remove all registered instruments (primarily for tests)."""

    _REGISTRY.clear()


# Pre-register Drumbo so existing entry points continue to function during
# the scaffolding phase. The descriptor will be replaced once Drumbo is fully
# migrated into the sampler instrument folder.
register_instrument(
    InstrumentDescriptor(
        id="drumbo",
        display_name="Drumbo",
        category="drums",
        version="0.1.0",
        entry_module="plugins.sampler.instruments.drumbo.module",
        metadata_path=None,
        icon_path=None,
        default_preset=None,
    )
)
