# /build/unit_router.py
# Minimal, page-agnostic router for HW dial ownership.
# Lets us "load" either a DEVICE (e.g., bmlpf) or a MODULE (e.g., vibrato)
# and set the live hardware dial handler in one place.

from typing import Callable, Optional
import showlog

# Public types
DialHandler = Callable[[int, int, object], bool]

# Internal state
_KIND: Optional[str] = None          # "device" | "module" | None
_NAME: Optional[str] = None          # device/module name
_HANDLER: Optional[DialHandler] = None

def _bind_midiserver(handler: DialHandler) -> None:
    """Install the handler into midiserver (single source of truth)."""
    try:
        import midiserver
        midiserver.dial_handler = handler
        showlog.debug(f"[unit_router] HW dials → {current_kind()}:{current_name()}")
    except Exception as e:
        showlog.error(f"[unit_router] Failed to bind midiserver handler: {e}")

def _set(kind: str, name: str, handler: DialHandler) -> None:
    global _KIND, _NAME, _HANDLER
    _KIND, _NAME, _HANDLER = kind, name, handler
    _bind_midiserver(handler)

# ---- Public API ------------------------------------------------------------

def load_device(name: str, handler: DialHandler) -> None:
    """Declare that a DEVICE is now active and owns the HW dials."""
    _set("device", name, handler)

def load_module(name: str, handler: DialHandler) -> None:
    """Declare that a MODULE is now active and owns the HW dials."""
    _set("module", name, handler)

def current_kind() -> Optional[str]:
    return _KIND

def current_name() -> Optional[str]:
    return _NAME

def current_handler() -> Optional[DialHandler]:
    return _HANDLER
