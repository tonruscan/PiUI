"""
Configuration Package with Profile Loading
Automatically loads the appropriate profile based on UI_ENV environment variable.

Usage:
    export UI_ENV=development  # or 'production', 'safe'
    python ui.py

    Or in code:
    import config
    print(config.FPS_NORMAL)
"""

import os
import sys
from typing import List, Tuple


_PENDING_LOGS: List[Tuple[str, str]] = []


def _queue_startup_log(level: str, message: str, loupe: bool = False) -> None:
    payload = message
    if loupe and not payload.startswith("*"):
        payload = f"*{payload}"

    logger = sys.modules.get("showlog")
    handler = getattr(logger, level, None) if logger else None
    if callable(handler):
        handler(payload)
    else:
        _PENDING_LOGS.append((level, payload))


def _flush_pending_logs() -> None:
    if not _PENDING_LOGS:
        return

    logger = sys.modules.get("showlog")
    if not logger:
        return

    remaining: List[Tuple[str, str]] = []
    for level, payload in _PENDING_LOGS:
        handler = getattr(logger, level, None)
        if callable(handler):
            handler(payload)
        else:
            remaining.append((level, payload))

    _PENDING_LOGS[:] = remaining


def _notify_showlog_ready() -> None:
    _flush_pending_logs()

    try:
        from . import platform as _platform_module
        flush_fn = getattr(_platform_module, "_flush_pending_platform_logs", None)
        if callable(flush_fn):
            flush_fn()
    except Exception:
        # Avoid breaking startup if platform logging flush fails.
        pass


def _log_debug(message: str) -> None:
    _queue_startup_log("debug", f"[CONFIG] {message}", loupe=True)


def _log_info(message: str) -> None:
    _queue_startup_log("info", f"[CONFIG] {message}")


def _log_warn(message: str) -> None:
    _queue_startup_log("warn", f"[CONFIG] {message}")

# Import all base configuration modules first
from .logging import *
from .display import *
from .performance import *
from .midi import *
from .styling import *
from .layout import *
from .pages import *
from .paths import *

# Detect platform via framebuffer resolution (Pi 3B vs. Pi 5, etc.)
from .platform import CURRENT_PLATFORM, PLATFORM_ID, apply_platform_overrides

apply_platform_overrides(globals())

_log_debug(
    f"Platform detected: {CURRENT_PLATFORM.description} "
    f"(source={CURRENT_PLATFORM.detection_source})"
)
# Detect environment profile
_env = os.getenv("UI_ENV", "production").lower()

# Load profile-specific overrides
if _env == "development" or _env == "dev":
    _log_info("Loading DEVELOPMENT profile")
    from .profiles.dev import *
elif _env == "safe":
    _log_info("Loading SAFE MODE profile")
    from .profiles.safe import *
else:
    _log_info("Loading PRODUCTION profile")
    from .profiles.prod import *

# Export current profile name
ACTIVE_PROFILE = _env if _env in ("development", "dev", "safe") else "production"

_log_debug(f"Active platform: {PLATFORM_ID}")
_log_info(f"Active profile: {ACTIVE_PROFILE}")
_log_debug(f"FPS_NORMAL={FPS_NORMAL}, FPS_BURST={FPS_BURST}, DEBUG={DEBUG}")


def _apply_scale_dependent_dimensions(ns):
    """Scale header/log heights once UI scale is known."""
    try:
        scale_x = float(ns.get("UI_SCALE", 1.0))
    except Exception:
        scale_x = 1.0
    if scale_x <= 0:
        scale_x = 1.0

    try:
        scale_y = float(ns.get("UI_SCALE_Y", scale_x))
    except Exception:
        scale_y = scale_x
    if scale_y <= 0:
        scale_y = scale_x

    if "_BASE_HEADER_HEIGHT" not in ns and "HEADER_HEIGHT" in ns:
        ns["_BASE_HEADER_HEIGHT"] = ns["HEADER_HEIGHT"]
    if "HEADER_HEIGHT" in ns and "_BASE_HEADER_HEIGHT" in ns:
        base_header = ns["_BASE_HEADER_HEIGHT"]
        try:
            ns["HEADER_HEIGHT"] = max(1, int(round(float(base_header) * scale_y)))
        except Exception:
            ns["HEADER_HEIGHT"] = base_header

    if "_BASE_LOG_BAR_HEIGHT" not in ns and "LOG_BAR_HEIGHT" in ns:
        ns["_BASE_LOG_BAR_HEIGHT"] = ns["LOG_BAR_HEIGHT"]
    if "LOG_BAR_HEIGHT" in ns and "_BASE_LOG_BAR_HEIGHT" in ns:
        base_log = ns["_BASE_LOG_BAR_HEIGHT"]
        try:
            ns["LOG_BAR_HEIGHT"] = max(1, int(round(float(base_log) * scale_y)))
        except Exception:
            ns["LOG_BAR_HEIGHT"] = base_log


_apply_scale_dependent_dimensions(globals())
