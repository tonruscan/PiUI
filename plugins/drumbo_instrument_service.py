"""High-level accessors for Drumbo instrument metadata.

Wraps :mod:`drumbo_instrument_scanner` with caching and convenience helpers so
UI pages or the Drumbo module can retrieve available instruments on demand.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Dict, Iterable, Optional

import showlog

from plugins.drumbo_instrument_scanner import (
    DiscoveryResult,
    InstrumentSpec,
    scan_instrument_roots,
)

try:
    from config.paths import ASSETS_DIR
except Exception:  # pragma: no cover - config import issues should be visible via logs
    ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"

# Default search roots: everything under assets/samples/drums
DEFAULT_ROOTS = [Path(ASSETS_DIR) / "samples" / "drums"]

_registry: Dict[str, InstrumentSpec] = {}
_errors: Dict[str, list] = {}
_cached_roots: Iterable[Path] = DEFAULT_ROOTS
_selected_instrument_id: Optional[str] = None


def _normalise_roots(roots: Optional[Iterable[Path]]) -> Iterable[Path]:
    if roots is None:
        return DEFAULT_ROOTS
    normalised = []
    for entry in roots:
        path = Path(entry).resolve()
        normalised.append(path)
    return normalised


def refresh(roots: Optional[Iterable[Path]] = None) -> DiscoveryResult:
    """Rescan instrument metadata.

    Args:
        roots: Optional iterable of root directories. When omitted, the default
            ``assets/samples/drums`` tree is used.
    """
    global _registry, _errors, _cached_roots
    _cached_roots = _normalise_roots(roots)
    result = scan_instrument_roots(_cached_roots)
    _registry = result.instruments
    _errors = {"scan": result.errors}
    showlog.debug(
        f"*[DrumboService] refresh completed: instruments={len(_registry)} errors={len(result.errors)}"
    )
    return result


def get_registry() -> Dict[str, InstrumentSpec]:
    """Return the current instrument registry, reloading if empty."""
    if not _registry:
        refresh(_cached_roots)
    return _registry


def get_selected_id() -> Optional[str]:
    return _selected_instrument_id


def list_instruments() -> Dict[str, Dict]:
    """Return a serialisable view of instruments keyed by id."""
    instruments = get_registry()
    return {instrument_id: asdict(spec) for instrument_id, spec in instruments.items()}


def get_instrument(instrument_id: str) -> Optional[InstrumentSpec]:
    """Return the metadata for a single instrument, refreshing if needed."""
    registry = get_registry()
    return registry.get(instrument_id)


def get_errors() -> Dict[str, list]:
    """Return the latest scan errors (if any)."""
    if not _errors:
        refresh(_cached_roots)
    return _errors


def select(instrument_id: str, *, auto_refresh: bool = True) -> Optional[InstrumentSpec]:
    """Select an instrument by id and return its spec if available."""
    global _selected_instrument_id

    if not instrument_id:
        showlog.warn("*[DrumboService] select called with empty instrument_id")
        return None

    target = str(instrument_id).strip()
    registry = get_registry()
    spec = registry.get(target)

    if spec is None and auto_refresh:
        showlog.debug(f"*[DrumboService] '{target}' not cached; refreshing registry")
        refresh(_cached_roots)
        registry = get_registry()
        spec = registry.get(target)

    if spec is None:
        showlog.warn(f"*[DrumboService] Instrument '{target}' not found after refresh")
        return None

    _selected_instrument_id = target
    showlog.debug(f"*[DrumboService] Selected instrument set → {target}")
    return spec


def get_selected() -> Optional[InstrumentSpec]:
    """Return the spec for the currently selected instrument (if any)."""
    if not _selected_instrument_id:
        return None
    return get_registry().get(_selected_instrument_id)
