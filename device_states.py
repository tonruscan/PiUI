# device_states.py
import json
import os
import showlog
from datetime import datetime

STATE_FILE = os.path.join(os.path.dirname(__file__), "config", "device_states.json")

_states_cache = {}

# -------------------------------------------------------
# Internal helpers
# -------------------------------------------------------

def _load_from_disk():
    """Load JSON into _states_cache if it exists (normalize keys to uppercase)."""
    global _states_cache

    if not os.path.exists(STATE_FILE):
        _states_cache = {}
        return

    try:
        with open(STATE_FILE, "r") as f:
            raw = json.load(f)

        # ✅ Normalize device names to uppercase
        _states_cache = {k.strip().upper(): v for k, v in raw.items()}

        showlog.debug(f"Loaded {len(_states_cache)} device states (keys normalized to uppercase)")

    except Exception as e:
        showlog.error(f"Failed to read {STATE_FILE}: {e}")
        _states_cache = {}



def _save_to_disk():
    """Write the in-memory cache to disk."""
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(_states_cache, f, indent=2)
    except Exception as e:
        showlog.error(f"Failed to write {STATE_FILE}: {e}")


# -------------------------------------------------------
# Public API
# -------------------------------------------------------

def load():
    """Load states file into memory."""
    _load_from_disk()
    showlog.info(f"Loaded device states ({len(_states_cache)} devices)")


def save():
    """Force-write cache to disk."""
    _save_to_disk()
    showlog.info("Saved device states")


def store_init(device_name, page_id, values, button_states=None):
    """
    Store the INIT preset for a given device/page.
    Each page now has its own {'init': {...}, 'current': {...}} dict.
    
    Supports both legacy format (list) and modern format (dict with dials/buttons).
    
    Args:
        device_name: Device name (e.g., 'QUADRAVERB')
        page_id: Page identifier (e.g., '01')
        values: List of 8 dial values OR dict with 'dials' and 'buttons'
        button_states: Optional dict of button states {button_id: numeric_state} (legacy)
    """
    showlog.debug(f"store_init CALLED for {device_name}:{page_id}")
    global _states_cache
    
    # Normalize values to modern format
    if isinstance(values, dict):
        # Modern format: {"dials": [...], "buttons": {"1": 0, "2": 1}}
        if "dials" not in values or not isinstance(values["dials"], list) or len(values["dials"]) != 8:
            showlog.error(f"Invalid 'dials' in init dict for {device_name}:{page_id}")
            return
        dial_values = values["dials"]
        button_data = values.get("buttons", button_states or {})
    elif isinstance(values, list):
        # Legacy format: [0, 0, 0, 0, 0, 0, 0, 0]
        if len(values) != 8:
            showlog.error(f"Invalid 'init' values for {device_name}:{page_id}")
            return
        dial_values = values
        button_data = button_states or {}
    else:
        showlog.error(f"Invalid values type for {device_name}:{page_id}: {type(values)}")
        return

    dev = _states_cache.setdefault(device_name, {})
    page = dev.setdefault(page_id, {})

    # Write new init values inside the page structure (modern format)
    page["init"] = {
        "dials": dial_values,
        "buttons": button_data  # Just a dict: {"1": 0, "2": 1}
    }
    
    dev["_last_saved"] = datetime.now().isoformat(timespec="seconds")

    _save_to_disk()
    showlog.info(f"Stored INIT for {device_name}:{page_id} = dials:{dial_values}, buttons:{button_data}")


def get_init(device_name, page_id):
    """Return stored 8-value list or None."""
    # Normalize to uppercase for consistent lookups
    device_name = device_name.strip().upper()

    dev = _states_cache.get(device_name)
    if not dev:
        showlog.warn(f"get_init() → no entry for {device_name}")
        return None

    showlog.debug(f"Returning {dev.get(page_id)} for {device_name}:{page_id} from {STATE_FILE}")
    return dev.get(page_id)



def get_all():
    """Return all stored device/page states."""
    return _states_cache


# -------------------------------------------------------
# Page-level state management
# -------------------------------------------------------

def store_current(device_name, page_id, values):
    """Temporarily disabled: do not write CURRENT to disk."""
    showlog.debug(f"Skipped CURRENT save for {device_name}:{page_id}")
    return


def get_page_state(device_name, page_id):
    """
    Return the best available state for a device/page.
    
    Handles both legacy format (list) and modern format (dict with dials/buttons).
    
    Returns:
        dict with:
        - 'values': 8-value list of dial values
        - 'buttons': dict of button states {"1": 0, "2": 1}
        
    Returns None if no state found.
    """
    global _states_cache
    dev = _states_cache.get(device_name)
    if not dev:
        return None

    page = dev.get(page_id)
    if not page:
        return None

    result = {}
    
    # Get the init or current state
    if isinstance(page, dict):
        state_data = page.get("current") or page.get("init")
        buttons = page.get("buttons")
    else:
        # Legacy: page is just a list
        state_data = page
        buttons = None
    
    # Parse state_data (can be list or dict)
    if isinstance(state_data, dict):
        # Modern format: {"dials": [...], "buttons": {"1": 0, "2": 1}}
        vals = state_data.get("dials", [0]*8)
        buttons = state_data.get("buttons", buttons or {})
        result = {
            "values": vals,
            "buttons": buttons
        }
    elif isinstance(state_data, list):
        # Legacy format: [0, 0, 0, 0, 0, 0, 0, 0]
        result = {
            "values": state_data,
            "buttons": buttons or {}
        }
    else:
        return None

    showlog.debug(f"Returning page state for {device_name}:{page_id} → {result}")
    
    return result

import midiserver, devices

def send_init_state(device_name):
    """
    Send all INIT values for the selected device over MIDI.
    Loads from device_states.json and sends each section/page via midiserver.
    """
    try:
        dev = _states_cache.get(device_name)
        if not dev:
            showlog.warn(f"No saved INIT for {device_name}")
            return

        device_def = devices.get_by_name(device_name)
        if not device_def:
            showlog.warn(f"Device definition not found for {device_name}")
            return

        # Loop through each page (section)
        for page_id, page_def in device_def["pages"].items():
            init_data = dev.get(page_id)
            if not init_data or "init" not in init_data:
                continue

            values = init_data["init"]
            showlog.info(f"Sending INIT for {device_name}:{page_id}")

            for dial_num, dial_value in enumerate(values, start=1):
                try:
                    dial_meta = page_def["dials"].get(f"{dial_num:02d}")
                    if not dial_meta:
                        continue

                    param_range = dial_meta.get("range", 127)
                    page_offset = dial_meta.get("page", 0)

                    midiserver.send_device_message(
                        device_name=device_name,
                        dial_index=dial_num,
                        value=dial_value,
                        param_range=param_range,
                        section_id=int(page_id),
                        page_offset=page_offset
                    )

                except Exception as e:
                    showlog.error(f"INIT send error for dial {dial_num}: {e}")

        showlog.info(f"All INIT pages sent for {device_name}")

    except Exception as e:
        showlog.error(f"send_init_state failed: {e}")
