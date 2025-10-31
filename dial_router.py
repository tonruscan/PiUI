# /build/dial_router.py
import os, json, importlib
import devices
import showlog
from typing import Union, Optional, Dict, Any

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "custom_page.json")
_slots = {}

def _read_json():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load()
    except FileNotFoundError:
        showlog.warn(f"[DialRouter] {CONFIG_PATH} not found; router map empty.")
    except Exception as e:
        showlog.warn(f"[DialRouter] Failed to read {CONFIG_PATH}: {e}")
    return {}

def reload():
    """(Re)load mapping from disk."""
    global _slots
    data = _read_json()
    _slots = data.get("slots", {}) if isinstance(data, dict) else {}
    showlog.debug(f"[DialRouter] Loaded {_slots and len(_slots) or 0} slots")

def get(slot_id: Union[int, str]) -> Optional[Dict[str, Any]]:
    """Raw map entry (may be 'dial' or 'modulator')."""
    if not _slots:
        reload()
    return _slots.get(str(slot_id))

def resolve(slot_id: Union[int, str]) -> Optional[Dict[str, Any]]:
    """
    Return a fully-resolved descriptor for this slot, or None.
    For 'dial' entries we locate the real device/page/dial meta + theme.
    For 'modulator' entries we pass through target info to the mod engine.
    """
    entry = get(slot_id)
    if not entry:
        return None

    t = entry.get("type", "dial").strip().lower()
    if t == "modulator":
        # Example entry:
        # {"type":"modulator","mod_type":"vibrato","target_device":"BMLPF","target_dial":"05","target_page":"01"}
        return {
            "type": "modulator",
            "mod_type": entry.get("mod_type", "vibrato"),
            "target_device": entry.get("target_device"),
            "target_dial": f"{int(entry.get('target_dial')):02d}" if entry.get("target_dial") else None,
            "target_page": entry.get("target_page"),
            "params": entry.get("params", {}),  # depth/rate/etc. if provided
        }

    # Normal 'dial' slot: {"device":"Quadraverb","dial":"03", "page":"01"(optional)}
    dev_name = entry.get("device")
    dial_id  = entry.get("dial")
    page_id  = entry.get("page")

    if not dev_name or not dial_id:
        showlog.warn(f"[DialRouter] Slot {slot_id} missing device/dial")
        return None

    dial_id = f"{int(dial_id):02d}"

    # Find device dict (from JSON/device module cache)
    dev = devices.get_by_name(dev_name)
    if not dev:
        showlog.warn(f"[DialRouter] Device not found: {dev_name}")
        return None

    pages = dev.get("pages", {})
    dial_meta = None
    resolved_page = None

    # If page provided, try it first
    if page_id and page_id in pages:
        dial_meta = pages[page_id].get("dials", {}).get(dial_id)
        if dial_meta:
            resolved_page = page_id

    # Else search all pages for that dial id
    if dial_meta is None:
        for pid, pdata in pages.items():
            dm = pdata.get("dials", {}).get(dial_id)
            if dm:
                dial_meta = dm
                resolved_page = pid
                break

    if not dial_meta:
        showlog.warn(f"[DialRouter] Dial {dial_id} not found in any page for {dev_name}")
        return None

    # Theme inheritance
    theme = devices.get_theme(dev.get("name", dev_name)) or {}

    return {
        "type": "dial",
        "device_name": dev.get("name", dev_name),
        "device_id": dev.get("id"),
        "page_id": resolved_page,        # where we found that dial
        "dial_id": dial_id,
        "meta": dial_meta,               # label, range, page_offset, etc.
        "theme": theme,
    }
