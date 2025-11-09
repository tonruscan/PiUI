# /build/device_presets.py
"""
device_presets.py
-----------------
Manages named presets for each device and page (separate from INIT states).
Similar structure to device_states.py, but supports multiple named presets.
"""

# -------------------------------------------------------
# Import guard (ensures it works from /build/pages/*)
# -------------------------------------------------------
import os, sys
if __package__ is None or __package__ == "":
    build_root = os.path.abspath(os.path.dirname(__file__))
    if build_root not in sys.path:
        sys.path.insert(0, build_root)

import json
import showlog
from datetime import datetime

# -------------------------------------------------------
# File paths and globals
# -------------------------------------------------------
# Correct path to /config/device_presets.json (one level up from /build)
PRESET_FILE = os.path.join(os.path.dirname(__file__), "config", "device_presets.json")
_presets_cache = {}

# -------------------------------------------------------
# Internal helpers
# -------------------------------------------------------

def _load_from_disk():
    global _presets_cache
    from showlog import log
    try:
        with open(PRESET_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        # normalize device keys to uppercase
        _presets_cache = {k.upper(): v for k, v in data.items()}
        log(None, f"[PRESETS] Loaded {len(_presets_cache)} devices (upper-case normalized)")
    except Exception as e:
        log(None, f"[PRESETS] load() error: {e}")
        _presets_cache = {}



def _save_to_disk():
    """Write the in-memory cache to disk."""
    try:
        with open(PRESET_FILE, "w", encoding="utf-8") as f:
            json.dump(_presets_cache, f, indent=2)
    except Exception as e:
        showlog.log(None, f"[PRESETS] Failed to write {PRESET_FILE}: {e}")


# -------------------------------------------------------
# Public API
# -------------------------------------------------------

def load():
    """Load presets file into memory."""
    _load_from_disk()
    showlog.log(None, f"[PRESETS] Loaded ({len(_presets_cache)} devices)")


def save():
    """Force-write cache to disk."""
    _save_to_disk()
    showlog.log(None, "[PRESETS] Saved all devices")


def store_preset(device_name, page_id, preset_name, dial_values):
    """
    Save a named preset for a given device and page.
    Example:
      store_preset("Quadraverb", "Reverb", "HugeVerb", [64, 127, 90, 0, 32, 100, 20, 127])
    """
    if not isinstance(dial_values, list) or len(dial_values) != 8:
        showlog.log(None, f"[PRESETS] Invalid values for {device_name}:{page_id}")
        return

    if device_name not in _presets_cache:
        _presets_cache[device_name] = {}

    if page_id not in _presets_cache[device_name]:
        _presets_cache[device_name][page_id] = {}

    _presets_cache[device_name][page_id][preset_name] = {
        "values": dial_values,
        "timestamp": datetime.now().isoformat(timespec="seconds")
    }

    _save_to_disk()
    showlog.log(None, f"[PRESETS] Stored {device_name}:{page_id}:{preset_name}")


def get_patch(device_name, preset_name):
    """Return patch info from patches.json for flat synths (case-insensitive, partial match)."""
    from showlog import log

    try:
        patches = load_patches()
        target_device = device_name.strip().lower()

        # --- Find matching device (case-insensitive / partial match) ---
        dev_patches = None
        for key in patches.keys():
            if key.strip().lower() == target_device or target_device in key.strip().lower():
                dev_patches = patches[key]
                break

        if not dev_patches:
            log(None, f"[PATCHES] Device '{device_name}' not found in patches.json")
            return None

        # --- Search preset name case-insensitively ---
        for num, name in dev_patches.items():
            if (preset_name.strip().lower().endswith(name.strip().lower())
                or name.strip().lower() in preset_name.strip().lower()):
                return {"program": int(num), "name": name}

        log(None, f"[PATCHES] Not found: {device_name}:{preset_name}")
        return None

    except Exception as e:
        log(None, f"[PATCHES ERROR] get_patch() failed for {device_name}:{preset_name}: {e}")
        return None


def get_pi_preset(device_name, page_id, preset_name):
    """Return bespoke preset values stored on the Pi (Quadraverb, etc)."""
    try:
        entry = _presets_cache[device_name][page_id][preset_name]
        # Support both legacy { "values": [...] } and flat [ ... ]
        if isinstance(entry, dict) and "values" in entry:
            return entry["values"]
        elif isinstance(entry, list):
            return entry
        else:
            showlog.log(None, f"[PRESETS] Invalid format for {device_name}:{page_id}:{preset_name} ({type(entry).__name__})")
            return None
    except KeyError:
        showlog.log(None, f"[PRESETS] Not found: {device_name}:{page_id}:{preset_name}")
        return None


def get_preset(device_name, page_id, preset_name):
    """
    Wrapper: choose between flat patch lookup and page-based preset lookup.
    """
    # Quadraverb and similar use page-level Pi presets
    if device_name.lower().startswith("quadraverb"):
        return get_pi_preset(device_name, page_id, preset_name)
    # everything else uses patches.json
    return get_patch(device_name, preset_name)


def list_presets(device_name, page_id=None):
    """List all preset names for a given device (and optionally a single page)."""
    from showlog import log
    log(None, f"[DEBUG] list_presets() called → device={device_name}, page={page_id}")
    log(None, f"[DEBUG] _presets_cache keys: {list(_presets_cache.keys())}")

    if device_name not in _presets_cache:
        log(None, f"[DEBUG] device '{device_name}' not found in _presets_cache")
        return []

    if page_id:
        available_pages = list(_presets_cache[device_name].keys())
        log(None, f"[DEBUG] available pages for {device_name}: {available_pages}")

        # Try exact match first
        if page_id in _presets_cache[device_name]:
            result = list(_presets_cache[device_name][page_id].keys())
            log(None, f"[DEBUG] returning {len(result)} presets for page '{page_id}'")
            return result

        # Fallbacks for simple devices
        for fallback in ("Reverb", "01", "Presets", "Main"):
            if fallback in _presets_cache[device_name]:
                log(None, f"[DEBUG] page '{page_id}' not found, using fallback '{fallback}'")
                return list(_presets_cache[device_name][fallback].keys())

        # If nothing found
        log(None, f"[DEBUG] no presets found for page '{page_id}' or fallbacks")
        return []

    result = list(_presets_cache[device_name].keys())
    log(None, f"[DEBUG] returning top-level pages: {result}")
    return result


def delete_preset(device_name, page_id, preset_name):
    """Remove a stored preset."""
    try:
        del _presets_cache[device_name][page_id][preset_name]
        _save_to_disk()
        showlog.log(None, f"[PRESETS] Deleted {device_name}:{page_id}:{preset_name}")
    except KeyError:
        showlog.log(None, f"[PRESETS] Delete failed (not found): {device_name}:{page_id}:{preset_name}")



# -------------------------------------------------------
# Internal device patch lists (factory/internal presets)
# -------------------------------------------------------
PATCHES_FILE = os.path.join(os.path.dirname(__file__), "config", "patches.json")
_patches_cache = None

def load_patches():
    """Load patches.json into _patches_cache once."""
    global _patches_cache
    from showlog import log
    try:
        with open(PATCHES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        # normalize device keys to uppercase
        _patches_cache = {k.upper(): v for k, v in data.items()}
        log(None, f"[PATCHES] Loaded {len(_patches_cache)} devices (upper-case normalized)")
        return _patches_cache
    except Exception as e:
        log(None, f"[PATCHES] load_patches() error: {e}")
        _patches_cache = {}
        return {}


def list_device_patches(device_name):
    """Return the factory/internal patch list for a given device."""
    patches = load_patches()
    if device_name not in patches:
        return []
    dev_patches = patches[device_name]
    # Return names sorted by program number
    return [v for k, v in sorted(dev_patches.items(), key=lambda kv: kv[0])]



# -------------------------------------------------------
# Auto-load on import
# -------------------------------------------------------
load()
