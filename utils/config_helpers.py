# /utils/config_helpers.py
from helper import hex_to_rgb  # or adjust path if different
import config as cfg

def get_cfg_color(attr_name: str, default_hex: str):
    """Safely get a color value from config, with fallback."""
    return hex_to_rgb(getattr(cfg, attr_name, default_hex))
