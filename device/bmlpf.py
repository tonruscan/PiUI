# /build/device/bmlpf.py
# Device definition for BM-11M Low-Pass Filter

DEVICE_INFO = {
    "id": "05",
    "name": "BMLPF",
    "default_page": "dials",
    "announce_msg": ["90", "71", "7F"],
    "pages": {
        "01": {
            "name": "Main",
            "dials": {
                "01": { "label": "Cutoff",    "range": 127 },
                "02": { "label": "Resonance", "range": 127 },
                "03": { "label": "Range Lo",  "range": 127 },
                "04": { "label": "Range Hi",  "range": 127 },
                "05": { "label": "Amount",    "range": 127 },
                "06": { "label": "Mix",       "range": 127 },
                "07": { "label": "Speed",     "range": 127 },
                "08": { "label": "EMPTY",     "range": 127 }
            }
        },
        "02": {
            "name": "Stereo",
            "dials": {
                "01": { "label": "Cutoff",      "range": 127 },
                "02": { "label": "Resonance",   "range": 127 },
                "03": { "label": "Cut Offset",  "range": 127 },
                "04": { "label": "Res Offset",  "range": 127 },
                "05": { "label": "EMPTY",       "range": 127 },
                "06": { "label": "EMPTY",       "range": 127 },
                "07": { "label": "EMPTY",       "range": 127 },
                "08": { "label": "EMPTY",       "range": 127 }
            }
        }
    },
    "init_state": {
        "01": {
            "dials": [0, 0, 0, 0, 0, 0, 0, 0],
            "buttons": {}
        },
        "02": {
            "dials": [0, 0, 64, 64, 0, 0, 0, 0],  # Stereo page: offsets at center (64)
            "buttons": {}
        }
    }
}


# --- Registry Data ------------------------------------------------------

REGISTRY = {
    "bmlpf": {
        "type": "device",  # ← add this line

        "01": {
            "label": "Cutoff",
            "cc": 16,
            "range": [0, 100],
            "type": "raw",
            "options": None,
            "default_slot": 1,
            "family": "bmlpf"
        },
        "02": {
            "label": "Resonance",
            "cc": 17,
            "range": [0, 100],
            "type": "raw",
            "options": None,
            "default_slot": 2,
            "family": "bmlpf"
        },
        "03": {
            "label": "Range Lo",
            "cc": 18,
            "range": [0, 100],
            "type": "raw",
            "options": None,
            "default_slot": 3,
            "family": "bmlpf"
        },
        "04": {
            "label": "Range Hi",
            "cc": 19,
            "range": [0, 100],
            "type": "raw",
            "options": None,
            "default_slot": 4,
            "family": "bmlpf"
        },
        "05": {
            "label": "Amount",
            "cc": 20,
            "range": [0, 100],
            "type": "raw",
            "options": None,
            "default_slot": 5,
            "family": "bmlpf"
        },
        "06": {
            "label": "Mix",
            "cc": 21,
            "range": [0, 100],
            "type": "raw",
            "options": None,
            "default_slot": 6,
            "family": "bmlpf"
        },
        "07": {
            "label": "Speed",
            "cc": 22,
            "range": [0, 100],
            "type": "raw",
            "options": None,
            "default_slot": 7,
            "family": "bmlpf"
        },
        "test": {
            "label": "Test",
            "cc": 23,
            "range": [0, 100],
            "type": "raw",
            "options": None,
            "default_slot": 1,
            "family": "bmlpf"
        }
    }
}

# -----------------------------------------------------------
# CV (Control Voltage) mapping
# -----------------------------------------------------------

TRANSPORT = "cv"        # identifies this as a CV-based device

# Map UI dial → DAC channel
# e.g. Dial 1 (Cutoff) drives channel 16 on the DAC
CV_MAP = {
    "01": 17,    # Cutoff → DAC 17 (L)
    "02": 4,     # Resonance → DAC 4 (L)
    "05": 16,    # Cutoff 2 → DAC 16 (L)
    "06": 2,     # Resonance 2 → DAC 2 (L)
    "test": 1,   # Test → DAC 1 (L)
}

# Stereo CV mapping for page 02 - maps single dial to multiple DAC channels
CV_MAP_STEREO = {
    "01": [17, 16],  # Cutoff Stereo → DAC 17 (L) + DAC 16 (R)
    "02": [4, 2],    # Resonance Stereo → DAC 4 (L) + DAC 2 (R)
}

# Offset controls - these don't map directly but modify the stereo pairs
CV_OFFSET_CONTROLS = {
    "03": {"type": "cutoff_offset", "affects": ["01"]},      # Cut Offset affects Cutoff stereo
    "04": {"type": "resonance_offset", "affects": ["02"]},   # Res Offset affects Resonance stereo
}

# Maximum offset amounts (in DAC units, not percentage)
STEREO_OFFSET_LIMITS = {
    "cutoff_offset": 500,      # Max cutoff offset in DAC units (±500)
    "resonance_offset": 300,   # Max resonance offset in DAC units (±300)
}

# Soft calibration (per logical parameter, not per channel)
CV_CALIB = {
    "01": {"cal_lo": 300, "cal_hi": 3500},  
    "02": {"cal_lo": 300, "cal_hi": 4095},    
    "05": {"cal_lo": 300, "cal_hi": 3500},     
    "06": {"cal_lo": 300, "cal_hi": 4095},
    "test": {"cal_lo": 300, "cal_hi": 4095}
}

# Stereo calibration - same values applied to both channels
CV_CALIB_STEREO = {
    "01": {"cal_lo": 300, "cal_hi": 3500},  # Cutoff Stereo (both channels)
    "02": {"cal_lo": 300, "cal_hi": 4095},  # Resonance Stereo (both channels)
}

# 12-bit DAC value range (0–4095)
CV_RESOLUTION = 4095



THEME = {
    # --- General page background ---
    "background_color": "#2C0A00",      # deep burnt red base (sunset shadow)
    "accent_color": "#FFD166",          # warm honey-yellow highlight

    # --- Header bar ---
    "header_bg_color": "#5B0E00",       # dark amber-red
    "header_text_color": "#FFECA1",     # soft pale yellow

    # --- Normal dial state ---
    "dial_panel_color": "#3E1200",      # rich brownish-red
    "dial_fill_color": "#FF9500",       # tangerine inner fill
    "dial_outline_color": "#FFD166",    # golden outline
    "dial_text_color": "#FFF2C6",       # warm cream text
    "dial_pointer_color": "#FFE66D",    # bright sunrise yellow pointer

    # --- Mute dial state ---
    "dial_mute_panel": "#402010",
    "dial_mute_fill": "#804020",        # muted bronze
    "dial_mute_outline": "#E6A15D",     # dull gold outline
    "dial_mute_text": "#FFD8A1",        # soft peach text

    # --- Offline dial ---
    "dial_offline_panel": "#1C0C00",
    "dial_offline_fill": "#2C1A0A",
    "dial_offline_outline": "#4A3320",
    "dial_offline_text": "#7A5E40",

    # --- Dial buttons ---
    "button_fill": "#FF9500",           # orange fill
    "button_outline": "#FFD166",        # glowing border
    "button_text": "#2C0A00",           # dark brown text
    "button_disabled_fill": "#4A2A0A",  # dim bronze
    "button_disabled_text": "#C4A480",  # muted tan
    "button_active_fill": "#FFE66D",    # bright yellow when pressed
    "button_active_text": "#3E1200",    # dark red text on yellow

    # --- Preset Page Colors ---
    "preset_button_color": "#4B1C00",          # dark orange background
    "preset_text_color": "#FFF2C6",            # cream text
    "preset_label_highlight": "#FFD166",       # golden highlight
    "preset_font_highlight": "#2C0A00",        # dark text on gold
    "scroll_bar_color": "#FFB347",             # orange scrollbar

    # --- Mixer Page Colors ---
    "mixer_panel_color": "#3E1400",
    "mixer_panel_outline_color": "#FFD166",
    "mixer_track_color": "#5A1E00",            # dark reddish-orange
    "mixer_knob_color": "#FFB347",             # amber knob
    "mixer_label_color": "#FFF2C6",
    "mixer_value_color": "#FFFFFF",
    "mixer_mute_color_off": "#5A2E10",
    "mixer_mute_color_on": "#FFD166",
}



# ---- Modern unified schema (v2) ----
SCHEMA_VERSION = 2
DEVICE_ID = "BMLPF"

# Optional (future): stable slot→control ids if you want to modernize dials too
# DIALS = {
#     1: "cutoff",
#     2: "resonance",
#     3: "range_lo",
#     4: "range_hi",
#     5: "amount",
#     6: "mix",
#     7: "speed",
#     # 8: "EMPTY"
# }

# Unified buttons list: ids "1".."10" carry label + behavior (+ optional action)
BUTTONS = [
    # Left column (1–5)
    {"id": "1",  "label": "1",   "behavior": "state"},
    {"id": "2",  "label": "2",   "behavior": "state"},
    {"id": "5",  "label": "T",   "behavior": "transient", "action": "bypass_toggle"},  # or whatever you want 5 to do

    # Right column (6–10)
    {"id": "6",  "label": "S", "behavior": "nav", "action": "store_preset"},
    {"id": "7",  "label": "P",  "behavior": "nav", "action": "presets"},
    {"id": "10", "label": "D",  "behavior": "nav", "action": "device_select"},
]






import cv_client
import config as cfg
import showlog
import devices
import sys

# -----------------------------------------------------------
# Custom CV handling for BMLPF stereo mode
# -----------------------------------------------------------

# Global state tracking for stereo mode
_stereo_base_values = {
    "01": 0,  # Base cutoff value (0-127)
    "02": 0,  # Base resonance value (0-127)
}

_stereo_offset_values = {
    "03": 64,  # Cutoff offset value (0-127, center at 64)
    "04": 64,  # Resonance offset value (0-127, center at 64)
}

def handle_cv_send(dial_id, value, current_page_id):
    """
    Custom CV send handler for BMLPF that supports stereo mode with offsets.
    Returns True if handled, False to fall back to default CV logic.
    """
    global _stereo_base_values, _stereo_offset_values
    
    try:
        showlog.debug(f"*[BMLPF CV] handle_cv_send called: dial_id={dial_id}, value={value}, page_id={current_page_id}")
        
        dial_key = f"{dial_id:02d}"
        
        # Check if we're on page 02 (stereo mode)
        if current_page_id == "02":
            showlog.debug(f"*[BMLPF CV] Stereo mode detected for page 02")
            
            # Update stored values
            if dial_key in ["01", "02"]:
                # Base value update
                _stereo_base_values[dial_key] = value
                showlog.debug(f"*[BMLPF CV] Updated base value for dial {dial_key}: {value}")
            elif dial_key in ["03", "04"]:
                # Offset value update
                _stereo_offset_values[dial_key] = value
                showlog.debug(f"*[BMLPF CV] Updated offset value for dial {dial_key}: {value}")
            
            # Handle stereo pairs with offsets
            if dial_key in CV_MAP_STEREO:
                _send_stereo_pair(dial_key)
                _notify_vibrato_stereo_update()
                return True
            elif dial_key in CV_OFFSET_CONTROLS:
                # Offset control changed - recalculate affected stereo pairs
                offset_info = CV_OFFSET_CONTROLS[dial_key]
                for affected_dial in offset_info["affects"]:
                    _send_stereo_pair(affected_dial)
                _notify_vibrato_stereo_update()
                return True
            else:
                showlog.debug(f"*[BMLPF CV] No stereo mapping for dial {dial_key} on page 02")
                return False
        else:
            # Not stereo mode, let default CV logic handle it
            showlog.debug(f"*[BMLPF CV] Not stereo mode (page {current_page_id}), using default CV logic")
            return False
            
    except Exception as e:
        showlog.error(f"*[BMLPF CV] Error in handle_cv_send: {e}")
        import traceback
        showlog.debug(f"*[BMLPF CV] Traceback: {traceback.format_exc()}")
        return False

def _send_stereo_pair(dial_key):
    """
    Send CV values to a stereo pair with offset applied.
    dial_key: "01" for cutoff, "02" for resonance
    """
    global _stereo_base_values, _stereo_offset_values
    
    try:
        if dial_key not in CV_MAP_STEREO:
            showlog.debug(f"*[BMLPF CV] No stereo mapping for {dial_key}")
            return
            
        channels = CV_MAP_STEREO[dial_key]
        base_value = _stereo_base_values.get(dial_key, 0)
        
        # Determine which offset applies
        offset_raw = 0
        offset_type = None
        if dial_key == "01":  # Cutoff
            offset_raw = _stereo_offset_values.get("03", 64)  # Default center
            offset_type = "cutoff_offset"
        elif dial_key == "02":  # Resonance
            offset_raw = _stereo_offset_values.get("04", 64)  # Default center
            offset_type = "resonance_offset"
            
        showlog.debug(f"*[BMLPF CV] Stereo pair {dial_key}: base={base_value}, offset_raw={offset_raw}, type={offset_type}")
        
        # Convert base value to DAC range
        max_val = CV_RESOLUTION
        base_dac = int(round((base_value / 127.0) * max_val))
        base_dac = max(0, min(max_val, base_dac))
        
        # Calculate offset amount (center at 64, range 0-127 maps to -max_offset to +max_offset)
        if offset_type and offset_type in STEREO_OFFSET_LIMITS:
            max_offset = STEREO_OFFSET_LIMITS[offset_type]
            # Map 0-127 to -max_offset to +max_offset, with 64 being center (0 offset)
            offset_dac = int(((offset_raw - 64) / 63.5) * max_offset)
            showlog.debug(f"*[BMLPF CV] Calculated offset: {offset_dac} DAC units (max: ±{max_offset})")
        else:
            offset_dac = 0
            showlog.debug(f"*[BMLPF CV] No offset applied")
        
        # Calculate L and R values with offset
        # L channel gets -offset, R channel gets +offset for stereo spread
        left_val = base_dac - offset_dac
        right_val = base_dac + offset_dac
        
        # Clamp to valid DAC range
        left_val = max(0, min(max_val, left_val))
        right_val = max(0, min(max_val, right_val))
        
        # Send to channels (assuming first channel is L, second is R)
        cv_client.send(channels[0], left_val)   # L channel
        cv_client.send(channels[1], right_val)  # R channel
        
        showlog.debug(f"*[BMLPF CV] Stereo send {dial_key}: L(CH{channels[0]})={left_val}, R(CH{channels[1]})={right_val}, offset={offset_dac}")
        
    except Exception as e:
        showlog.error(f"*[BMLPF CV] Error in _send_stereo_pair: {e}")
        import traceback
        showlog.debug(f"*[BMLPF CV] _send_stereo_pair traceback: {traceback.format_exc()}")


def _notify_vibrato_stereo_update():
    """Inform the vibrato module that stereo calibration changed."""
    try:
        from plugins import vibrato_plugin
        vibrato_plugin.notify_bmlpf_stereo_offset_change()
    except Exception as exc:
        showlog.debug(f"*[BMLPF CV] Vibrato notify failed: {exc}")

# -----------------------------------------------------------
# Configuration and utility functions
# -----------------------------------------------------------

def set_offset_limits(cutoff_offset=None, resonance_offset=None):
    """
    Dynamically adjust the maximum offset amounts.
    
    Args:
        cutoff_offset: Maximum cutoff offset in DAC units (default: 500)
        resonance_offset: Maximum resonance offset in DAC units (default: 300)
    """
    global STEREO_OFFSET_LIMITS
    
    if cutoff_offset is not None:
        STEREO_OFFSET_LIMITS["cutoff_offset"] = cutoff_offset
        showlog.info(f"*[BMLPF CONFIG] Set cutoff offset limit to {cutoff_offset} DAC units")
        
    if resonance_offset is not None:
        STEREO_OFFSET_LIMITS["resonance_offset"] = resonance_offset
        showlog.info(f"*[BMLPF CONFIG] Set resonance offset limit to {resonance_offset} DAC units")
        
    showlog.debug(f"*[BMLPF CONFIG] Current offset limits: {STEREO_OFFSET_LIMITS}")


def get_stereo_offset_value(dial_key):
    """
    Get the current offset value for a specific dial.
    
    Args:
        dial_key: "03" for cutoff offset, "04" for resonance offset
        
    Returns:
        int: Current offset value (0-127, center at 64)
    """
    global _stereo_offset_values
    return _stereo_offset_values.get(dial_key, 64)


def get_stereo_offset_dac(offset_type):
    """
    Calculate the DAC offset value for vibrato/modulation use.
    
    Args:
        offset_type: "cutoff_offset" or "resonance_offset"
        
    Returns:
        int: Offset in DAC units (can be positive or negative)
    """
    global _stereo_offset_values, STEREO_OFFSET_LIMITS
    
    # Get the raw dial value
    if offset_type == "cutoff_offset":
        offset_raw = _stereo_offset_values.get("03", 64)
    elif offset_type == "resonance_offset":
        offset_raw = _stereo_offset_values.get("04", 64)
    else:
        return 0
    
    # Get max offset limit
    max_offset = STEREO_OFFSET_LIMITS.get(offset_type, 0)
    
    # Calculate offset: 0-127 maps to -max to +max, center at 64
    offset_dac = int(((offset_raw - 64) / 63.5) * max_offset)
    
    showlog.debug(f"*[BMLPF OFFSET] {offset_type}: raw={offset_raw}, dac={offset_dac}, max=±{max_offset}")
    
    return offset_dac

# -----------------------------------------------------------
# Debug and verification functions
# -----------------------------------------------------------

def debug_current_state():
    """Debug function to check current device state"""
    try:
        import dialhandlers
        
        current_device_name = getattr(dialhandlers, "current_device_name", None)
        current_device_id = getattr(dialhandlers, "current_device_id", None)
        current_page_id = getattr(dialhandlers, "current_page_id", None)
        msg_queue = getattr(dialhandlers, "msg_queue", None)
        dials = getattr(dialhandlers, "dials", None)
        
        showlog.debug(f"*[BMLPF DEBUG] current_device_name: '{current_device_name}'")
        showlog.debug(f"*[BMLPF DEBUG] current_device_id: '{current_device_id}'")
        showlog.debug(f"*[BMLPF DEBUG] current_page_id: '{current_page_id}'")
        showlog.debug(f"*[BMLPF DEBUG] msg_queue available: {msg_queue is not None}")
        showlog.debug(f"*[BMLPF DEBUG] dials available: {dials is not None}")
        showlog.debug(f"*[BMLPF DEBUG] dials count: {len(dials) if dials else 0}")
        
        # Check device config
        dev = devices.get("05")
        if dev:
            showlog.debug(f"*[BMLPF DEBUG] devices.json config found: {dev.get('name')}")
            showlog.debug(f"*[BMLPF DEBUG] devices.json pages: {list(dev.get('pages', {}).keys())}")
        else:
            showlog.error(f"*[BMLPF DEBUG] No device config found for ID '05' in devices.json")
            
        # Check device file DEVICE_INFO
        try:
            if DEVICE_INFO:
                showlog.debug(f"*[BMLPF DEBUG] Device file DEVICE_INFO found: {DEVICE_INFO.get('name')}")
                showlog.debug(f"*[BMLPF DEBUG] Device file pages: {list(DEVICE_INFO.get('pages', {}).keys())}")
                
                # Show stereo mappings
                showlog.debug(f"*[BMLPF DEBUG] CV_MAP_STEREO: {CV_MAP_STEREO}")
                showlog.debug(f"*[BMLPF DEBUG] CV_OFFSET_CONTROLS: {CV_OFFSET_CONTROLS}")
                showlog.debug(f"*[BMLPF DEBUG] STEREO_OFFSET_LIMITS: {STEREO_OFFSET_LIMITS}")
                showlog.debug(f"*[BMLPF DEBUG] Current base values: {_stereo_base_values}")
                showlog.debug(f"*[BMLPF DEBUG] Current offset values: {_stereo_offset_values}")
        except NameError:
            showlog.debug(f"*[BMLPF DEBUG] No DEVICE_INFO in device file")
            
        return True
        
    except Exception as e:
        showlog.error(f"*[BMLPF DEBUG] Error in debug_current_state: {e}")
        import traceback
        showlog.debug(f"*[BMLPF DEBUG] Traceback: {traceback.format_exc()}")
        return False

# -----------------------------------------------------------
# Global state tracking
# -----------------------------------------------------------
_trem_active = False
_trem_thread = None
_trem_2_active = False

# -----------------------------------------------------------
# BMLPF Page Switching Override
# -----------------------------------------------------------

def handle_bmlpf_page_switch(button_id, msg_queue, dials):
    """
    Handle page switching specifically for BMLPF device.
    This bypasses the hardcoded Quadraverb logic in dialhandlers.py
    """
    showlog.verbose(f"*[BMLPF] handle_bmlpf_page_switch called with button_id={button_id}")
    
    try:
        import dialhandlers
        showlog.verbose(f"[BMLPF] dialhandlers imported successfully")

        showlog.verbose(f"[BMLPF] msg_queue type: {type(msg_queue)}, dials type: {type(dials)}")
        showlog.verbose(f"[BMLPF] dials length: {len(dials) if dials else 'None'}")

        # Get device info - FIRST check device file's DEVICE_INFO, then fall back to devices.json
        dev = None
        page_key = f"{int(button_id):02d}"
        showlog.verbose(f"[BMLPF] Generated page_key: '{page_key}' from button_id: {button_id}")

        # Try device file DEVICE_INFO first
        try:
            if DEVICE_INFO and page_key in DEVICE_INFO.get("pages", {}):
                dev = DEVICE_INFO
                showlog.verbose(f"[BMLPF] Using device file DEVICE_INFO - found page {page_key}")
                showlog.verbose(f"[BMLPF] Device file pages: {list(DEVICE_INFO.get('pages', {}).keys())}")
            else:
                showlog.verbose(f"[BMLPF] Page {page_key} not found in device file DEVICE_INFO")
        except NameError:
            showlog.verbose(f"[BMLPF] No DEVICE_INFO found in device file")
        
        # Fall back to devices.json if not found in device file
        if not dev:
            showlog.verbose(f"[BMLPF] Falling back to devices.json")
            dev = devices.get("05")  # BMLPF device ID
            showlog.verbose(f"[BMLPF] devices.get('05') returned: {type(dev)} - {dev is not None}")

            if dev and page_key in dev.get("pages", {}):
                showlog.verbose(f"[BMLPF] Using devices.json - found page {page_key}")
                showlog.verbose(f"[BMLPF] devices.json pages: {list(dev.get('pages', {}).keys())}")
            else:
                showlog.verbose(f"[BMLPF] Page {page_key} not found in devices.json either")

        if not dev:
            showlog.error("[BMLPF] Device not found in either device file or devices.json")
            return False
            
        if page_key not in dev.get("pages", {}):
            showlog.error(f"[BMLPF] Page {page_key} not found in any device config")
            available_pages = list(dev.get("pages", {}).keys())
            showlog.verbose(f"[BMLPF] Available pages: {available_pages}")
            msg_queue.put(f"[BMLPF] Page {page_key} not found")
            return False

        showlog.verbose(f"[BMLPF] Found page {page_key} in device config")
        page_info = dev["pages"][page_key]
        showlog.verbose(f"[BMLPF] Page info: {page_info}")

        # Store previous page for debugging
        prev_page = getattr(dialhandlers, "current_page_id", "??")
        prev_device = getattr(dialhandlers, "current_device_id", "??")
        prev_device_name = getattr(dialhandlers, "current_device_name", "??")

        showlog.verbose(f"[BMLPF] Before switch - current_page_id: {prev_page}, current_device_id: {prev_device}, current_device_name: {prev_device_name}")

        # Update the global current_page_id
        dialhandlers.current_page_id = page_key
        showlog.verbose(f"[BMLPF] Set dialhandlers.current_page_id to: {page_key}")

        # Verify the update took
        new_page = getattr(dialhandlers, "current_page_id", "??")
        showlog.verbose(f"[BMLPF] Verified dialhandlers.current_page_id is now: {new_page}")

        # Update dial layout for new page
        try:
            showlog.verbose(f"[BMLPF] Calling devices.update_from_device with device_id='05', page_id='{page_key}'")
            header_text, button_info = devices.update_from_device(
                "05", page_key, dials, "Header"
            )
            showlog.verbose(f"[BMLPF] devices.update_from_device returned header_text: '{header_text}', button_info: {button_info}")
        except Exception as e:
            showlog.error(f"[BMLPF] Error updating device layout: {e}")
            import traceback
            showlog.verbose(f"[BMLPF] devices.update_from_device traceback: {traceback.format_exc()}")
            return False
        
        page_name = dev["pages"][page_key]["name"]
        showlog.verbose(f"[BMLPF] Page name: '{page_name}'")

        # Send messages to UI
        msg1 = f"[PAGE] Switched to {dev['name']} - {page_name}"
        msg2 = ("sysex_update", header_text, str(button_id))
        msg3 = ("select_button", str(button_id))
        # REMOVED: ("force_redraw", 30) - mode_manager already requests full frames
        # The excessive redraws were causing blurry header text due to anti-aliasing accumulation
        
        showlog.debug(f"[BMLPF] Sending messages: msg1='{msg1}', msg2={msg2}, msg3={msg3}")
        
        msg_queue.put(msg1)
        msg_queue.put(msg2)
        msg_queue.put(msg3)
        
        showlog.debug(f"[BMLPF] All messages sent to queue")
        
        # Recall states (simplified version)
        live_states = getattr(dialhandlers, "live_states", {})
        showlog.verbose(f"[BMLPF] live_states type: {type(live_states)}, keys: {list(live_states.keys()) if isinstance(live_states, dict) else 'not dict'}")
        
        page_vals = None
        page_buttons = {}

        if dev["name"] in live_states and page_key in live_states[dev["name"]]:
            page_vals = live_states[dev["name"]][page_key]
            msg_queue.put(f"[STATE] Recalling LIVE state for {dev['name']}:{page_key}")
            showlog.verbose(f"[BMLPF] Using LIVE state: {page_vals}")
        else:
            # Use init state - check device file first, then devices.json, then default
            init_state = None
            
            # Try device file init_state first
            try:
                if DEVICE_INFO:
                    init_state = DEVICE_INFO.get("init_state", {})
                    showlog.verbose(f"[BMLPF] Device file init_state: {init_state}")
            except NameError:
                showlog.warn(f"[BMLPF] No DEVICE_INFO available for init_state")
            
            # Fall back to devices.json init_state
            if not init_state and dev:
                init_state = dev.get("init_state", {})
                showlog.debug(f"[BMLPF] devices.json init_state: {init_state}")
            
            # Get page values or default to zeros
            raw_page_state = init_state.get(page_key) if isinstance(init_state, dict) else None

            if isinstance(raw_page_state, dict):
                page_vals = raw_page_state.get("dials", [0] * 8)
                page_buttons = raw_page_state.get("buttons", {}) or {}
                showlog.debug(f"[BMLPF] INIT state contains dials+buttons for page {page_key}")
            elif isinstance(raw_page_state, list):
                page_vals = raw_page_state
                page_buttons = {}
                showlog.debug(f"[BMLPF] INIT state list detected for page {page_key}")
            else:
                page_vals = [0] * 8
                page_buttons = {}
                showlog.warn(f"[BMLPF] INIT state missing for page {page_key}, defaulting to zeros")

            # Always operate on a copy so we do not mutate shared init data
            if isinstance(page_vals, list):
                page_vals = list(page_vals)

            msg_queue.put(f"[STATE] Using INIT state for {dev['name']}:{page_key}")
            showlog.verbose(f"[BMLPF] Using INIT state: {page_vals}")
        
        # Apply values to dials
        if page_vals and dials:
            showlog.verbose(f"[BMLPF] Applying {len(page_vals)} values to {len(dials)} dials")
            for dial_id, val in enumerate(page_vals, start=1):
                if dial_id <= len(dials):
                    try:
                        dial_obj = dials[dial_id - 1]
                        old_value = getattr(dial_obj, "value", "unknown")
                        old_label = getattr(dial_obj, "label", "unknown")

                        showlog.verbose(f"[BMLPF] Dial {dial_id} before: value={old_value}, label='{old_label}'")

                        dial_obj.set_value(val)
                        dial_obj.display_text = f"{dial_obj.label}: {val}"
                        
                        new_value = getattr(dial_obj, "value", "unknown")
                        new_label = getattr(dial_obj, "label", "unknown")

                        showlog.verbose(f"[BMLPF] Dial {dial_id} after: value={new_value}, label='{new_label}', display_text='{dial_obj.display_text}'")
                    except Exception as e:
                        showlog.error(f"[BMLPF] Error setting dial {dial_id}: {e}")
                        import traceback
                        showlog.error(f"[BMLPF] Dial {dial_id} error traceback: {traceback.format_exc()}")
                else:
                    showlog.verbose(f"[BMLPF] Skipping dial {dial_id} (beyond available dials)")
        else:
            showlog.verbose(f"[BMLPF] Not applying values - page_vals: {page_vals}, dials: {dials is not None}")

        showlog.verbose(f"[BMLPF] Page switch completed successfully")
        showlog.debug(f"[BMLPF] Successfully switched to page {page_key} ({page_name})")
        return True
        
    except Exception as e:
        showlog.error(f"*[BMLPF] Page switch error: {e}")
        import traceback
        showlog.error(f"*[BMLPF] Full traceback: {traceback.format_exc()}")
        return False

# -----------------------------------------------------------
# Button Press Handler
# -----------------------------------------------------------

def on_button_press(button_id: int):
    """Custom button actions for Behringer BM-11M."""
    global _trem_active, _trem_thread, _trem_2_active
    
    showlog.debug(f"*[BMLPF] on_button_press called with button_id={button_id}")
    
    # Debug current state for troubleshooting
    if button_id in [1, 2]:
        showlog.debug(f"*[BMLPF] Running debug_current_state for button {button_id}")
        debug_current_state()
    
    try:
        import dialhandlers
        showlog.debug(f"*[BMLPF] dialhandlers imported successfully")
        
        msg_queue = getattr(dialhandlers, "msg_queue", None)
        dials = getattr(dialhandlers, "dials", None)
        current_device_name = getattr(dialhandlers, "current_device_name", None)
        current_device_id = getattr(dialhandlers, "current_device_id", None)
        
        showlog.debug(f"*[BMLPF] Retrieved from dialhandlers - msg_queue: {msg_queue is not None}, dials: {dials is not None}")
        showlog.debug(f"*[BMLPF] current_device_name: '{current_device_name}', current_device_id: '{current_device_id}'")
        
        # Handle page switching for buttons 1 and 2
        if button_id in [1, 2]:
            showlog.debug(f"*[BMLPF] Processing page switch button {button_id}")
            
            # Check if we're the current device
            if current_device_name != "BMLPF":
                showlog.debug(f"*[BMLPF] Not current device (current: '{current_device_name}'), allowing default behavior")
                return False
            
            showlog.debug(f"*[BMLPF] BMLPF is current device, handling page switch")
            
            if msg_queue and dials:
                showlog.debug(f"*[BMLPF] msg_queue and dials available, calling handle_bmlpf_page_switch")
                success = handle_bmlpf_page_switch(button_id, msg_queue, dials)
                showlog.debug(f"*[BMLPF] handle_bmlpf_page_switch returned: {success}")
                if success:
                    showlog.debug(f"*[BMLPF] Page switch successful, returning True")
                    return True  # We handled it
                else:
                    showlog.debug(f"*[BMLPF] Page switch failed, falling back to default")
                    return False  # Let system try default behavior
            else:
                showlog.error(f"*[BMLPF] msg_queue or dials not available - msg_queue: {msg_queue is not None}, dials: {dials is not None}")
                return False

        if button_id == 4:  
            showlog.debug(f"*[BMLPF] Processing tremolo button {button_id}")
            # Button 4: tremolo toggle
            if not _trem_2_active:
                _trem_2_active = True
                cv_client.send_raw("VIBEON 16 8.0")
                showlog.debug(f"*[BMLPF] Tremolo activated, _trem_2_active: {_trem_2_active}")
                showlog.info("*[BMLPF] Button 4 pressed Trem ON")
                return True
            else:
                _trem_2_active = False
                cv_client.send_raw("VIBEOFF 16")
                showlog.debug(f"*[BMLPF] Tremolo deactivated, _trem_2_active: {_trem_2_active}")
                showlog.info("*[BMLPF] Button 4 released Trem OFF")
                return True
            
        if button_id == 5:
            showlog.debug(f"*[BMLPF] Processing vibrato navigation button {button_id}")
            # Button 5: vibrato page navigation
            import queue
            showlog.info("[BMLPF] Vibrato page requested via Button 5")
            
            try:
                q = getattr(dialhandlers, "msg_queue", None)
                showlog.debug(f"*[BMLPF] Got msg_queue for vibrato: {q is not None}, type: {type(q)}")
                if isinstance(q, queue.Queue):
                    q.put(("entity_select", "vibrato"))
                    q.put("[NAV] UI mode changed to VIBRATO")
                    showlog.debug("*[BMLPF] Queued vibrato navigation messages")
                else:
                    showlog.error(f"*[BMLPF] msg_queue not available or wrong type: {type(q)}")
            except Exception as e:
                showlog.error(f"*[BMLPF] Vibrato button error: {e}")
                import traceback
                showlog.debug(f"*[BMLPF] Vibrato error traceback: {traceback.format_exc()}")
            return True

        # Allow normal behavior for other buttons
        showlog.debug(f"*[BMLPF] Button {button_id} not handled by BMLPF, returning False for default behavior")
        return False
        
    except Exception as e:
        showlog.error(f"*[BMLPF] Button press error: {e}")
        import traceback
        showlog.debug(f"*[BMLPF] Button press error traceback: {traceback.format_exc()}")
        return False
