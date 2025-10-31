# /build/device/pogolab.py
# Device definition for PogoLab

DEVICE_INFO = {
    "id": "04",
    "name": "PogoLab",
    "default_page": "presets",
    "announce_msg": ["90", "7E", "7F"],
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
    "background_color": "#FFF9E8",      # soft cream base (sunlit paper)
    "accent_color": "#FFD94D",          # vivid golden accent

    # --- Header bar (unchanged) ---
    "header_bg_color": "#FFE066",       # glowing warm yellow
    "header_text_color": "#8A4B00",     # rich honey-amber text

    # --- Preset Page Colors ---
    "preset_button_color": "#C17100",          # warm orange base
    "preset_text_color": "#E0D0A4",            # creamy white text
    "preset_label_highlight": "#FFD94D",       # bright golden highlight
    "preset_font_highlight": "#8A4B00",        # honey-amber highlight text
    "scroll_bar_color": "#FFD94D",             # gold scrollbar

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
