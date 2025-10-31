# /build/device/bmlpf.py
# Device definition for BM-11M Low-Pass Filter

DEVICE_INFO = {
    "id": "04",
    "name": "PSR-36",
    "default_page": "presets",
    "announce_msg": ["90", "7F", "7F"],
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
        }
    },
    "init_state": {
        "01": [0, 0, 0, 0, 0, 0, 0, 0]
    },
    "left_buttons": {
        "1": "1",
        "2": "2",
        "3": "3",
        "4": "4",
        "5": "5"
    }
}

# Override the MIDI channel for all outgoing messages (1–16)

CC_OVERRIDE = {
    "01": 11,   # Cutoff
    "02": 12,   # Resonance
    "03": 13,   # Range Lo
    "04": 14,   # Range Hi
    "05": 15,   # Amount
    "06": 16,   # Mix
    "07": 17,   # Speed
    "08": 18     # EMPTY
}

THEME = {
    # --- General page background ---
    "background_color": "#02060A",      # deep near-black blue base
    "accent_color": "#00F5CC",          # bright cyan-teal neon accent

    # --- Header bar ---
    "header_bg_color": "#001F1F",       # dark teal
    "header_text_color": "#00F5CC",     # glowing cyan text

    # --- Normal dial state ---
    "dial_panel_color": "#041012",      # subtle bluish black
    "dial_fill_color": "#00D4A5",       # teal-green inner fill
    "dial_outline_color": "#00F5CC",    # neon outline
    "dial_text_color": "#B0FFF2",       # soft mint text
    "dial_pointer_color": "#00FFF2",    # bright cyan pointer

    # --- Mute dial state ---
    "dial_mute_panel": "#0C1A1A",
    "dial_mute_fill": "#06403E",        # dim teal
    "dial_mute_outline": "#0FA89E",     # dull neon
    "dial_mute_text": "#6EE0CF",        # muted turquoise

    # --- Offline dial ---
    "dial_offline_panel": "#0A0A0A",
    "dial_offline_fill": "#1C1C1C",
    "dial_offline_outline": "#333333",
    "dial_offline_text": "#666666",

    # --- Dial buttons ---
    "button_fill": "#00D4A5",           # teal-green fill
    "button_outline": "#00F5CC",        # glowing border
    "button_text": "#FFFFFF",           # crisp white
    "button_disabled_fill": "#202828",  # dim grey-green
    "button_disabled_text": "#6F7A7A",  # soft grey text
    "button_active_fill": "#00F5CC",    # full neon when pressed
    "button_active_text": "#000000",    # black text on bright teal

    # --- Preset Page Colors ---
    "preset_button_color": "#061414",          # dark cyan background
    "preset_text_color": "#B0FFF2",            # mint text
    "preset_label_highlight": "#00F5CC",       # neon teal highlight
    "preset_font_highlight": "#000000",        # dark text on neon
    "scroll_bar_color": "#00E6B8",             # bright teal scrollbar

    # --- Mixer Page Colors ---
    "mixer_panel_color": "#031010",
    "mixer_panel_outline_color": "#00F5CC",
    "mixer_track_color": "#002E2E",            # dark teal base
    "mixer_knob_color": "#00F5CC",             # glowing knob
    "mixer_label_color": "#B0FFF2",
    "mixer_value_color": "#FFFFFF",
    "mixer_mute_color_off": "#303838",
    "mixer_mute_color_on": "#00F5CC",
}


# behaviour types: state / nav / transient
BUTTON_BEHAVIOR = {
    "1": "state",
    "2": "state",
    "3": "state",
    "4": "transient",
    "5": "transient",       # Mixer
    "6": "transient",       # Store preset
    "7": "nav",       # Presets
    "8": "transient", # Mute
    "9": "transient",       # Text input
    "10": "nav",      # Device select
}
