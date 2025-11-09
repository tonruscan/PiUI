"""Drumbo configuration values shared between the legacy module and sampler."""

from __future__ import annotations

from pathlib import Path

import config as cfg

from plugins.sampler.core import config as sampler_config


_SAMPLER_SAMPLE_ROOT = getattr(sampler_config, "SAMPLE_ROOT", None)
if _SAMPLER_SAMPLE_ROOT:
    _sampler_root_path = Path(_SAMPLER_SAMPLE_ROOT)
    if not _sampler_root_path.is_absolute():
        _sampler_root_path = Path(__file__).resolve().parents[3] / _sampler_root_path
else:
    _sampler_root_path = None

SAMPLE_ROOT = _sampler_root_path or (
    Path(__file__).resolve().parents[3] / "assets" / "samples" / "drums"
)

SAMPLE_FOLDERS = {
    "snare": "snare",
    "kick": "kick",
}

NOTE_MAP = {
    "kick": {35, 36},
    "snare": {37, 38, 39, 40},
}

DEFAULT_METADATA_DIAL_VALUE = int(
    max(
        0,
        min(
            127,
            getattr(cfg, "DRUMBO_METADATA_DEFAULT_LEVEL", sampler_config.DEFAULT_DIAL_LEVEL),
        ),
    )
)

DEFAULT_AUDIO_DEVICE_KEYWORDS = ("justboom",)

THEME = {
    "header_bg_color": "#2C1810",
    "header_text_color": "#FFE4C4",
    "dial_panel_color": "#000000",
    "plugin_background_color": "#1A0F08",
    "dial_fill_color": "#CD853F",
    "dial_outline_color": "#DEB887",
    "dial_text_color": "#FF8C00",
    "dial_pointer_color": "#F5DEB3",
    "dial_label_color": getattr(cfg, "MINI_DIAL_LABEL_COLOR", "#0D47A1"),
    "drumbo_label_text_color": getattr(cfg, "MINI_DIAL_LABEL_TEXT_COLOR", "#FFFFFF"),
    "dial_mute_panel": "#0D0805",
    "dial_mute_fill": "#4A2818",
    "dial_mute_outline": "#6A3828",
    "dial_mute_text": "#7C7C7C",
    "button_fill": "#8B4513",
    "button_outline": "#CD853F",
    "button_text": "#FFE4C4",
    "button_active_fill": "#CD853F",
    "button_active_text": "#2C1810",
    "preset_button_color": "#1A0F08",
    "preset_text_color": "#FFE4C4",
    "preset_label_highlight": "#CD853F",
    "preset_font_highlight": "#2C1810",
    "scroll_bar_color": "#DEB887",
}

INIT_STATE = {
    "buttons": {},
    "dials": [],
}

PRESET_STATE = {
    "variables": [
        "preset_bank_a_values",
        "preset_bank_b_values",
        "preset_instrument",
    ],
    "widget_state": ["current_instrument"],
}

MINI_DIAL_RADIUS = int(round(getattr(cfg, "MINI_DIAL_RADIUS", 25)))

GRID_LAYOUT = {
    "rows": 2,
    "cols": 4,
    "dial_size": MINI_DIAL_RADIUS,
}

DIAL_LAYOUT_HINTS = {
    "type": "overlay_top_row",
    "row": 0,
    "col": 0,
    "width": 4,
    "height": 1,
    "y_offset": -12,
}

CUSTOM_WIDGET = {
    "class": "DrumboMainWidget",
    "path": "plugins.sampler.instruments.drumbo.ui.main_widget",
    "grid_size": [4, 2],
    "grid_pos": [0, 0],
}

SLICER_WIDGET = {
    "class": "AutoSlicerWidget",
    "path": "plugins.sampler.core.slicer.widget",
    "grid_size": [4, 2],
    "grid_pos": [0, 0],
}


def _build_bank_registry(start_mic: int) -> dict:
    """Generate the legacy registry mapping for a contiguous block of mics."""

    entries = {"type": "module"}
    for offset in range(8):
        slot = offset + 1
        mic_number = start_mic + offset
        label = f"M{mic_number}"
        entries[f"{slot:02d}"] = {
            "label": label,
            "range": [0, 127],
            "type": "raw",
            "default_slot": slot,
            "family": "drumbo",
            "variable": f"mic_{mic_number}_level",
        }

    return {"drumbo": entries}


BANK_A_REGISTRY = _build_bank_registry(1)
BANK_B_REGISTRY = _build_bank_registry(9)
LABEL_TO_VARIABLE = {f"M{idx}": f"mic_{idx}_level" for idx in range(1, 17)}

DIAL_BANK_CONFIG = {
    "A": {
        "ctrl_ids": [
            "mic_1",
            "mic_2",
            "mic_3",
            "mic_4",
            "mic_5",
            "mic_6",
            "mic_7",
            "mic_8",
        ],
        "layout": {
            "row": 0,
            "col": 0,
            "width": 4,
            "height": 1,
            "y_offset": -12,
        },
        "dial_size": MINI_DIAL_RADIUS,
    },
    "B": {
        "ctrl_ids": [
            "mic_9",
            "mic_10",
            "mic_11",
            "mic_12",
            "mic_13",
            "mic_14",
            "mic_15",
            "mic_16",
        ],
        "layout": {
            "row": 1,
            "col": 0,
            "width": 4,
            "height": 1,
            "y_offset": -12,
        },
        "dial_size": MINI_DIAL_RADIUS,
    },
}

BANK_SWITCH_NOTE_MAP = {
    67: "A",
    63: "B",
}

BANK_SWITCH_ALLOWED_CHANNELS = {10, 9}

BUTTONS = [
    {
        "id": "1",
        "behavior": "multi",
        "states": ["S", "K"],
    },
    {
        "id": "2",
        "behavior": "multi",
        "label": "BANK",
        "states": ["A", "B"],
    },
    {
        "id": "3",
        "behavior": "multi",
        "label": "KIT",
        "states": ["D", "SL"],
    },
    {"id": "7", "label": "P", "behavior": "nav", "action": "presets"},
    {"id": "9", "label": "S", "behavior": "nav", "action": "save_preset"},
]
