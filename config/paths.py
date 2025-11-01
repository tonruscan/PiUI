"""
Path Configuration
Directory paths for assets, configs, devices, and system files.
"""

import os
import sys

# Base path for the project
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Font directory (relative to this file)
FONT_DIR = os.path.join(BASE_DIR, "assets", "fonts")

# Config directory for JSON files
CONFIG_DIR = os.path.join(BASE_DIR, "config")

# --- Core project directories ---
DEVICE_DIR = os.path.join(BASE_DIR, "device")
SYSTEM_DIR = os.path.join(BASE_DIR, "system")
PAGES_DIR  = os.path.join(BASE_DIR, "pages")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
STATES_DIR = os.path.join(BASE_DIR, "states")
UTILS_DIR = os.path.join(BASE_DIR, "utils")


def config_path(filename):
    """Return full path for a JSON config file inside /config."""
    return os.path.join(CONFIG_DIR, filename)


def sys_folders():
    """Ensure all key project folders are importable."""
    for path in (BASE_DIR, DEVICE_DIR, SYSTEM_DIR, PAGES_DIR, ASSETS_DIR):
        if path not in sys.path:
            sys.path.append(path)
