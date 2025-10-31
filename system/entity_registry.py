"""
entity_registry.py
------------------
Unified access layer for both devices (from devices.json)
and modules (from modules/<name>_mod.py).

Usage:
    from system import entity_registry as er
    info = er.get_entity("vibrato")
    typ  = er.get_type("bmlpf")
"""

import importlib
import traceback
import showlog
import devices  # existing device registry
from functools import lru_cache


# ------------------------------------------------------------
# Core lookup
# ------------------------------------------------------------

@lru_cache(maxsize=None)
def get_entity(name: str):
    """
    Return the registry entry for either a device or a module.
    Tries devices.json first, then modules/<name>_mod.py.
    """
    if not name:
        return None

    name = str(name).strip().lower()

    # 1️⃣ Try devices.json / devices.py first
    try:
        if hasattr(devices, "get_by_name"):
            dev = devices.get_by_name(name)
        else:
            dev = getattr(devices, "get", lambda _: None)(name)

        if dev:
            entry = dict(dev)  # shallow copy to avoid mutation
            entry.setdefault("type", "device")
            showlog.debug(f"[ENTITY_REGISTRY] Found device: {name}")
            return entry
    except Exception as e:
        showlog.warn(f"[ENTITY_REGISTRY] Device lookup failed for '{name}': {e}")

    # 2️⃣ Try plugins/<name>_plugin.py
    try:
        mod = importlib.import_module(f"plugins.{name}_plugin")
        reg = getattr(mod, "REGISTRY", None)

        if isinstance(reg, dict):
            # usually single-key dict like {"vibrato": {...}}
            entry = reg.get(name) or next(iter(reg.values()), None)
            if entry:
                entry = dict(entry)  # detach
                entry.setdefault("type", "module")
                showlog.debug(f"[ENTITY_REGISTRY] Found plugin: {name}")
                return entry

        showlog.warn(f"[ENTITY_REGISTRY] Plugin '{name}' has no REGISTRY dict")

    except ModuleNotFoundError:
        showlog.warn(f"[ENTITY_REGISTRY] No plugin named '{name}_plugin'")
    except Exception as e:
        tb = traceback.format_exc(limit=1)
        showlog.error(f"[ENTITY_REGISTRY] Module import error for '{name}': {e}\n{tb}")

    showlog.warn(f"[ENTITY_REGISTRY] Entity not found: {name}")
    return None


# ------------------------------------------------------------
# Convenience helpers
# ------------------------------------------------------------

def get_type(name: str) -> str:
    """Return 'device', 'module', or 'unknown' for a given entity name."""
    try:
        ent = get_entity(name)
        return ent.get("type", "unknown") if isinstance(ent, dict) else "unknown"
    except Exception:
        return "unknown"


def is_module(name: str) -> bool:
    """Quick check if entity is a module."""
    return get_type(name) == "module"


def is_device(name: str) -> bool:
    """Quick check if entity is a device."""
    return get_type(name) == "device"


# ------------------------------------------------------------
# Cached bulk fetch (optional future use)
# ------------------------------------------------------------

@lru_cache(maxsize=1)
def all_entities():
    """Return a combined dict of all devices and modules (by name)."""
    result = {}

    # Load all devices
    try:
        db = getattr(devices, "DEVICE_DB", {})
        for dev in db.values():
            nm = str(dev.get("name", "")).lower()
            if not nm:
                continue
            result[nm] = dict(dev)
            result[nm].setdefault("type", "device")
    except Exception as e:
        showlog.warn(f"[ENTITY_REGISTRY] Failed to enumerate devices: {e}")

    # Attempt to import known modules dynamically (optional)
    try:
        import pkgutil, modules
        for _, modname, _ in pkgutil.iter_modules(modules.__path__):
            if not modname.endswith("_mod"):
                continue
            try:
                m = importlib.import_module(f"modules.{modname}")
                reg = getattr(m, "REGISTRY", {})
                if isinstance(reg, dict):
                    for k, v in reg.items():
                        result[k.lower()] = dict(v)
                        result[k.lower()].setdefault("type", "module")
            except Exception as e:
                showlog.warn(f"[ENTITY_REGISTRY] Skipped module {modname}: {e}")
    except Exception:
        pass

    return result
