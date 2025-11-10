"""
Runtime platform detection helpers.

Determines which hardware profile to load by inspecting the primary
framebuffer's resolution (primary distinguisher between Pi 3B display and
Pi 5 + 7" v2 touchscreen in this deployment).

Exports:
    CURRENT_PLATFORM (PlatformInfo): frozen snapshot of the detected platform.
    PLATFORM_ID (str): shorthand identifier (e.g. "pi3b", "pi5").
    apply_platform_overrides(globals_dict): inject profile overrides into the
        provided globals dictionary (usually config.__dict__).

Detection order:
    1. PIUI_PLATFORM environment variable (explicit override by id)
    2. PIUI_SCREEN_RES environment variable (explicit width x height)
    3. /sys/class/graphics/fb0/virtual_size (preferred sysfs source)
    4. /sys/class/graphics/fb0/modes or /mode
    5. fbset -s output (as a fallback when sysfs is unavailable)
    6. Default to classic 800x480 layout (Pi 3B profile)

Additional calibration overrides can be merged by adding JSON or other data
sources in the future; see TODO markers in this module.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from importlib import import_module
from typing import Dict, Iterable, Optional, Tuple

# Known resolution → profile mappings.
_RESOLUTION_PROFILE_MAP: Dict[Tuple[int, int], str] = {
    (800, 480): "pi3",
    (1280, 720): "pi5",
}

# Aliases for PIUI_PLATFORM environment variable.
_PLATFORM_ALIASES: Dict[str, str] = {
    "pi3": "pi3",
    "pi3b": "pi3",
    "pi-3": "pi3",
    "pi5": "pi5",
    "pi-5": "pi5",
    "rpi5": "pi5",
}


@dataclass(frozen=True)
class PlatformInfo:
    """Describes a detected runtime platform."""

    id: str
    screen_width: int
    screen_height: int
    detection_source: str
    settings: Dict[str, object]

    @property
    def screen_size(self) -> Tuple[int, int]:
        return (self.screen_width, self.screen_height)

    @property
    def description(self) -> str:
        return f"{self.id} {self.screen_width}x{self.screen_height}"


def _parse_resolution(text: str) -> Optional[Tuple[int, int]]:
    if not text:
        return None

    match = re.search(r"(\d{3,5})\D+(\d{3,5})", text)
    if not match:
        return None

    try:
        w = int(match.group(1))
        h = int(match.group(2))
    except (TypeError, ValueError):
        return None

    if w <= 0 or h <= 0:
        return None
    return (w, h)


def _read_first_existing(paths: Iterable[str]) -> Optional[str]:
    for path in paths:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                data = handle.read().strip()
                if data:
                    return data
        except OSError:
            continue
    return None


def _detect_resolution_from_sysfs() -> Optional[Tuple[int, int]]:
    data = _read_first_existing((
        "/sys/class/graphics/fb0/virtual_size",
        "/sys/class/graphics/fb0/modes",
        "/sys/class/graphics/fb0/mode",
    ))
    if not data:
        return None
    return _parse_resolution(data)


def _detect_resolution_from_fbset() -> Optional[Tuple[int, int]]:
    try:
        proc = subprocess.run(
            ["fbset", "-s"],
            check=False,
            capture_output=True,
            text=True,
            timeout=0.5,
        )
    except (FileNotFoundError, PermissionError, subprocess.SubprocessError):
        return None

    output = (proc.stdout or "") + (proc.stderr or "")
    return _parse_resolution(output)


def _resolve_profile_for_resolution(resolution: Tuple[int, int]) -> str:
    profile = _RESOLUTION_PROFILE_MAP.get(resolution)
    if profile:
        return profile

    width, height = resolution
    if width >= 1000 or height >= 600:
        return "pi5"
    return "pi3"


def _load_profile_settings(profile_id: str) -> Dict[str, object]:
    module_name = f"config.profiles.{profile_id}"
    module = import_module(module_name)

    settings = getattr(module, "SETTINGS", None)
    if not isinstance(settings, dict):
        raise ValueError(f"Profile module {module_name} does not expose SETTINGS dict")

    return dict(settings)


def _detect_platform() -> PlatformInfo:
    override_id = os.getenv("PIUI_PLATFORM")
    if override_id:
        profile_id = _PLATFORM_ALIASES.get(override_id.strip().lower())
        if not profile_id:
            raise ValueError(
                f"PIUI_PLATFORM override '{override_id}' is not recognized; "
                f"known: {sorted(set(_PLATFORM_ALIASES))}"
            )
        settings = _load_profile_settings(profile_id)
        width = int(settings.get("SCREEN_WIDTH", 800))
        height = int(settings.get("SCREEN_HEIGHT", 480))
        return PlatformInfo(
            id=profile_id,
            screen_width=width,
            screen_height=height,
            detection_source="env:PIUI_PLATFORM",
            settings=settings,
        )

    override_res = os.getenv("PIUI_SCREEN_RES")
    resolution: Optional[Tuple[int, int]] = None
    detection_source = "env:PIUI_SCREEN_RES"

    if override_res:
        resolution = _parse_resolution(override_res)
    if not resolution:
        detection_source = "sysfs"
        resolution = _detect_resolution_from_sysfs()
    if not resolution:
        detection_source = "fbset"
        resolution = _detect_resolution_from_fbset()
    if not resolution:
        detection_source = "default"
        resolution = (800, 480)

    profile_id = _resolve_profile_for_resolution(resolution)
    settings = _load_profile_settings(profile_id)

    return PlatformInfo(
        id=profile_id,
        screen_width=resolution[0],
        screen_height=resolution[1],
        detection_source=detection_source,
        settings=settings,
    )


CURRENT_PLATFORM: PlatformInfo = _detect_platform()
PLATFORM_ID: str = CURRENT_PLATFORM.id

# Ensure the profile settings contain the ID for downstream consumers.
CURRENT_PLATFORM.settings.setdefault("PLATFORM_ID", CURRENT_PLATFORM.id)
CURRENT_PLATFORM.settings.setdefault("SCREEN_WIDTH", CURRENT_PLATFORM.screen_width)
CURRENT_PLATFORM.settings.setdefault("SCREEN_HEIGHT", CURRENT_PLATFORM.screen_height)
CURRENT_PLATFORM.settings.setdefault("ACTIVE_PLATFORM", CURRENT_PLATFORM.id)


def apply_platform_overrides(target_globals: Dict[str, object]) -> None:
    """Inject detected platform settings into target globals."""

    for key, value in CURRENT_PLATFORM.settings.items():
        target_globals[key] = value

    # Expose convenience globals even if profiles don't set them explicitly.
    target_globals.setdefault("PLATFORM_ID", CURRENT_PLATFORM.id)
    target_globals.setdefault("ACTIVE_PLATFORM", CURRENT_PLATFORM.id)
    target_globals.setdefault("SCREEN_WIDTH", CURRENT_PLATFORM.screen_width)
    target_globals.setdefault("SCREEN_HEIGHT", CURRENT_PLATFORM.screen_height)


__all__ = [
    "CURRENT_PLATFORM",
    "PLATFORM_ID",
    "apply_platform_overrides",
]
