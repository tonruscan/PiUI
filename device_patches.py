# /build/device_patches.py
"""
device_patches.py
-----------------
Loads simple name→number preset lists from /config/patches.json
(for devices that have fixed built-in patch banks).
"""

import os, sys, json, showlog

# --- Ensure we can import from /build ---
if __package__ is None or __package__ == "":
    build_root = os.path.abspath(os.path.dirname(__file__))
    if build_root not in sys.path:
        sys.path.insert(0, build_root)

PATCH_FILE = os.path.join(os.path.dirname(__file__), "config", "patches.json")
_patch_cache = {}

def load():
    """Load patches.json into memory."""
    global _patch_cache
    try:
        with open(PATCH_FILE, "r", encoding="utf-8") as f:
            _patch_cache = json.load(f)
        showlog.log(None, f"[PATCHES] Loaded {len(_patch_cache)} devices")
    except Exception as e:
        showlog.log(None, f"[PATCHES] Failed to load {PATCH_FILE}: {e}")
        _patch_cache = {}

def list_patches(device_name):
    """Return (number, name) pairs for a device. Supports partial name matches."""
    try:
        if not _patch_cache:
            load()

        # 1️⃣ Try exact match
        dev = _patch_cache.get(device_name)
        if not dev:
            # 2️⃣ Try partial match (e.g. "PogoLab II" -> "PogoLab")
            for key in _patch_cache.keys():
                if key.lower() in device_name.lower() or device_name.lower() in key.lower():
                    dev = _patch_cache[key]
                    showlog.log(None, f"[PATCHES] Using partial match: {key}")
                    break

        if not dev:
            showlog.log(None, f"[PATCHES] No patches found for {device_name}")
            return []

        # sort numerically by key
        return [(k, v) for k, v in sorted(dev.items(), key=lambda x: int(x[0]))]

    except Exception as e:
        showlog.log(None, f"[PATCHES] Error listing patches for {device_name}: {e}")
        return []


# auto-load
load()
