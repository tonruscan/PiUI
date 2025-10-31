# /build/device/quadraverb.py
# Device definition for Quadraverb

DEVICE_INFO = {

    "id": "01",
    "name": "Quadraverb",
    "default_page": "dials",
    "announce_msg": ["90", "7B", "7F"],
    "pages": {
        "01": {
            "name": "Reverb",
            "dials": {
            "01": { "label": "Type", "cc": 30, "range": [0, 4], "type": "raw", "page": 0, "options": ["Plate 1", "Room 1", "Chamber 1", "Hall 1", "Reverse 1"] },
            "02": { "label": "PreDelay", "cc": 31, "range": [1, 140], "type": "ms", "page": 4 },
            "03": { "label": "Decay", "cc": 32, "range": [0, 99], "type": "", "page": 6 },
            "04": { "label": "Diffusion", "cc": 33, "range": [1, 9], "type": "", "page": 7 },
            "05": { "label": "Density", "cc": 34, "range": [1, 9], "type": "", "page": 8 },
            "06": { "label": "Lo Decay", "cc": 35, "range": [-60, 0], "type": "", "page": 9 },
            "07": { "label": "Hi Decay", "cc": 36, "range": [-60, 0], "type": "", "page": 10 },
            "08": { "label": "Gate", "cc": 37, "range": [0, 1], "type": "", "page": 11, "options": ["Off", "On"] }
            }
        },
        "02": {
            "name": "Delay",
            "dials": {
            "01": { "label": "Type", "cc": 30, "range": [0, 3], "type": "raw", "page": 0, "options": ["Mono", "Stereo", "Ping Pong"] },
            "02": { "label": "L Time", "cc": 31, "range": [1, 400], "type": "ms", "page": 3 },
            "03": { "label": "R Time", "cc": 32, "range": [1, 400], "type": "ms", "page": 5 },
            "04": { "label": "L Feedback", "cc": 33, "range": [0, 99], "type": "%", "page": 4 },
            "05": { "label": "R Feedback", "cc": 34, "range": [0, 99], "type": "%", "page": 6 },
            "06": { "label": "EMPTY", "cc": 35, "range": 127, "type": "raw" },
            "07": { "label": "EMPTY", "cc": 36, "range": 127, "type": "raw" },
            "08": { "label": "EMPTY", "cc": 37, "range": 127, "type": "raw" }
            }
        },
        "03": {
            "name": "Pitch",
            "dials": {
            "01": { "label": "Type", "cc": 30, "range": [0, 6], "type": "raw", "page": 0, "options": ["M Chorus", "S Chorus", "M Flange", "S Flange", "Detune", "Phaser"] },
            "02": { "label": "Shape", "cc": 31, "range": [0, 2], "type": "raw", "page": 2, "options": ["Triangle", "Square"] },
            "03": { "label": "LFO Speed", "cc": 32, "range": [1, 99], "type": "", "page": 3 },
            "04": { "label": "LFO Depth", "cc": 33, "range": [1, 99], "type": "", "page": 4 },
            "05": { "label": "Pitch Fbck", "cc": 34, "range": [1, 99], "type": "%", "page": 5 },
            "06": { "label": "EMPTY", "cc": 35, "range": 127, "type": "raw", "page": 6 },
            "07": { "label": "EMPTY", "cc": 36, "range": 127, "type": "raw" },
            "08": { "label": "EMPTY", "cc": 37, "range": 127, "type": "raw" }
            }
        },
        "04": {
            "name": "EQ",
            "dials": {
            "01": { "label": "Lo Freq", "cc": 30, "range": [20, 999], "type": "Hz", "page": 0 },
            "02": { "label": "Lo Amp", "cc": 31, "range": [-14.00, 14.00], "type": "dB", "page": 1 },
            "03": { "label": "Mid Freq", "cc": 32, "range": [200, 9999], "type": "Hz", "page": 2 },
            "04": { "label": "Mid Q", "cc": 33, "range": [0.20, 2.55], "type": "Oct", "page": 3 },
            "05": { "label": "Mid Amp", "cc": 34, "range": [-14.00, 14.00], "type": "dB", "page": 4 },
            "06": { "label": "Hi Freq", "cc": 35, "range": [2000, 18000], "type": "Hz", "page": 5 },
            "07": { "label": "Hi Amp", "cc": 36, "range": [-14.00, 14.00], "type": "dB", "page": 6 },
            "08": { "label": "EMPTY", "cc": 37, "range": 127, "type": "raw" }
            }
        },
        "05": {
            "name": "Mixer",
            "type": "mixer",
            "faders": {
            "01": { "label": "Reverb", "sysex_section": 1, "range": [0, 99], "type": "", "init": 50 },
            "02": { "label": "Delay",  "sysex_section": 2, "range": [0, 99], "type": "", "init": 50 },
            "03": { "label": "Pitch",  "sysex_section": 3, "range": [0, 99], "type": "", "init": 50 },
            "04": { "label": "EQ",     "sysex_section": 4, "range": [0, 99], "type": "", "init": 50 }
            }
        }

    },
    "init_state": {
        "01": [0, 0, 0, 0, 0, 0, 0, 0]
    }

}


# --------------------------------------------------------
# Per-device theme colors
# --------------------------------------------------------
THEME = {
    # --- General page background ---
    "background_color": "#202020",      # overall background behind dials
    "accent_color": "#FF00AA",          # optional accent used for highlights

    # --- Header bar (maps to HEADER_BG_COLOR / HEADER_TEXT_COLOR) ---
    "header_bg_color": "#DC00B3",
    "header_text_color": "#FFC4C4",

    # --- Normal dial state (matches config: DIAL_PANEL_COLOR, etc.) ---
    "dial_panel_color": "#301020",      # background behind the dial
    "dial_fill_color": "#FF0090",       # inner circle color
    # "dial_outline_color": "#301020",    # circle border
    "dial_outline_color": "#FFB0D0",    # circle border
    "dial_text_color": "#FFFFFF",       # label/value text
    "dial_pointer_color": "#FFBBDD",    # small indicator/pointer

    # --- Mute dial state (matches DIAL_MUTE_*) ---
    "dial_mute_panel": "#100010",
    "dial_mute_fill": "#4A004A",
    "dial_mute_outline": "#804080",
    "dial_mute_text": "#B088B0",

    # --- Offline dial (matches DIAL_OFFLINE_*) ---
    "dial_offline_panel": "#101010",
    "dial_offline_fill": "#303030",
    "dial_offline_outline": "#505050",
    "dial_offline_text": "#707070",

    # --- Dial buttons (matches BUTTON_*) ---
    "button_fill": "#FF0090",           # normal fill color
    "button_outline": "#FFB0D0",        # border
    "button_text": "#FFFFFF",           # label text
    "button_disabled_fill": "#3A003A",  # when inactive
    "button_disabled_text": "#703070",  # when inactive
    "button_active_fill": "#FF33AA",    # when pressed
    "button_active_text": "#FFFFFF",    # pressed text

    # --- Preset Page Colors ---
    "preset_button_color": "#351530",          # normal preset background
    "preset_text_color": "#FFC4C4",            # normal preset text
    "preset_label_highlight": "#FF00AA",       # selected preset background
    "preset_font_highlight": "#FFFFFF",        # selected preset text
    "scroll_bar_color": "#FF66CC",             # scrollbar accent (optional)

    # --- Mixer Page Colors ---
    "mixer_panel_color": "#301020",
    "mixer_panel_outline_color": "#FF66CC",
    "mixer_track_color": "#601545",
    "mixer_knob_color": "#FF00AA",
    "mixer_label_color": "#FFC4C4",
    "mixer_value_color": "#FFFFFF",
    "mixer_mute_color_off": "#3C3C3C",
    "mixer_mute_color_on": "#FF00AA",

}



BUTTONS = [
    # Left column (1–5)
    {"id": "1",  "label": "R",   "behavior": "state"},
    {"id": "2",  "label": "D",   "behavior": "state"},
    {"id": "3",  "label": "P",   "behavior": "state"},
    {"id": "4",  "label": "E",   "behavior": "state"},
    {"id": "5",  "label": "M",   "behavior": "nav"},

    # Right column (6–10)
    {"id": "6",  "label": "S", "behavior": "transient", "action": "store_preset"},
    {"id": "7",  "label": "P",  "behavior": "nav", "action": "presets"},
    {"id": "8",  "label": "M",  "behavior": "transient", "action": "mute"},
    {"id": "9",  "label": "T",  "behavior": "transient", "action": "text_input"},
    {"id": "10", "label": "D",  "behavior": "nav", "action": "device_select"},
]





# -------------------------------------------------------
# QuadraVerb Specific
# -------------------------------------------------------

# Ensure project root is on sys.path via config.BASE_DIR (avoid using os here)
import sys
import config as cfg
if cfg.BASE_DIR not in sys.path:
    sys.path.append(cfg.BASE_DIR)

import showlog
import mido
import midiserver


# --- Page mute tracking ---
page_mute_states = {
    "01": False,
    "02": True,
    "03": True,
    "04": True
}

# --- SysEx commands ---
mute_codes = {
    "01": "F0 00 00 0E 02 01 08 05 00 00 00 F7",  # Reverb
    "02": "F0 00 00 0E 02 01 08 04 00 00 00 F7",  # Delay
    "03": "F0 00 00 0E 02 01 08 03 00 00 00 F7",  # Pitch
    "04": "F0 00 00 0E 02 01 08 02 00 00 00 F7"   # EQ
}

unmute_reverb = "F0 00 00 0E 02 01 08 05 19 00 00 F7"

# Full unmute map (include reverb via alias)
unmute_codes = {
    "01": unmute_reverb,
    "02": "F0 00 00 0E 02 01 08 04 19 00 00 F7",
    "03": "F0 00 00 0E 02 01 08 03 19 00 00 F7",
    "04": "F0 00 00 0E 02 01 08 02 19 00 00 F7",
}


def set_default_mute_state():
    """
    Send default mute setup for the Alesis Quadraverb:
      • Page 1 (Reverb) → Unmuted
      • Pages 2–4 (Delay, Pitch, EQ) → Muted
    """
    try:
        # Update UI state first so dials grey/un-grey immediately on load
        page_mute_states.update({
            "01": False,
            "02": True,
            "03": True,
            "04": True,
        })

        # --- Unmute Reverb (page 1) ---
        data = [int(x, 16) for x in unmute_reverb.split()]

        # -- TODO: Refactor common SysEx code into helper function --
        if data[0] == 0xF0:
            data = data[1:]
        if data[-1] == 0xF7:
            data = data[:-1]

        msg = mido.Message("sysex", data=data)
        midiserver.outport.send(msg)
        showlog.log(None, "[INIT MUTE] Reverb (page 1) → UNMUTED")

        # --- Mute Delay, Pitch, EQ (skip Reverb page '01') ---
        for pid, syx_str in mute_codes.items():
            if pid == "01":
                continue  # keep Reverb unmuted by default
            data = [int(x, 16) for x in syx_str.split()]
            if data[0] == 0xF0:
                data = data[1:]
            if data[-1] == 0xF7:
                data = data[:-1]
            msg = mido.Message("sysex", data=data)
            midiserver.outport.send(msg)
            showlog.log(None, f"[INIT MUTE] Page {pid} → MUTED")

    except Exception as e:
        showlog.log(None, f"[INIT MUTE ERROR] {e}")


def toggle_page_mute(page_key: str, dev_name: str, msg_queue=None):
    """Toggle mute/unmute for the given Quadraverb page.

    Args:
        page_key: "01".."04"
        dev_name: Device display name for logs/messages
        msg_queue: Optional queue to post UI messages
    """
    try:
        # Determine current state
        is_muted = page_mute_states.get(page_key, False)

        # Choose appropriate SysEx
        syx_str = mute_codes.get(page_key) if not is_muted else unmute_codes.get(page_key)
        if not syx_str:
            showlog.log(None, f"*[QV MUTE] No SysEx mapping for page {page_key}")
            if msg_queue:
                msg_queue.put(f"[MUTE] No SysEx mapping for page {page_key}")
            return

        # Build and send SysEx (strip F0/F7 for mido)
        data = [int(x, 16) for x in syx_str.split()]
        if data and data[0] == 0xF0:
            data = data[1:]
        if data and data[-1] == 0xF7:
            data = data[:-1]

        msg = mido.Message("sysex", data=data)
        midiserver.outport.send(msg)

        # Flip state and report
        page_mute_states[page_key] = not is_muted
        state_str = "MUTED" if page_mute_states[page_key] else "UNMUTED"

        if msg_queue:
            msg_queue.put(f"[MUTE] {dev_name} page {page_key} → {state_str}")
        showlog.log(None, f"[MUTE SEND] {syx_str}")

    except Exception as e:
        if msg_queue:
            msg_queue.put(f"[MUTE ERROR] {e}")
        showlog.log(None, f"[MUTE ERROR] {e}")


