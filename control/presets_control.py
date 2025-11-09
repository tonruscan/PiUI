# /build/control/presets_control.py
from showlog import log
import pages.presets as presets_page
import showheader
import device_patches  # minimal: used only to fetch (num, name) pairs for  internal patches

def handle_message(tag, payload, ui):
    """Update the selected preset number; draw() handles the visuals each frame."""
    if ui.get("ui_mode") != "presets":
        return False

    if tag == "PATCH" and isinstance(payload, dict):
        num = payload.get("preset")
        if not isinstance(num, int):
            return False
        presets_page.selected_preset = num
        # Use None for screen (so showlog uses its stored screen_ref)
        log(None, f"Preset highlight set → #{num}")
        return True

    return False


def set_context_menu():
    """
    Tell showheader which buttons to display in the dropdown
    when we're on the Presets page.
    """
    buttons = [
        {"label": "Internal", "action": "set_mode_patches"},
        {"label": "External", "action": "set_mode_presets"}
    ]
    showheader.set_context_buttons(buttons)
    # Use None for screen (so showlog uses its stored screen_ref)
    log(None, "[Presets] Context menu configured: Internal/External")



import device_presets
import pages.presets as presets_page
from showlog import log

def handle_header_action(action, ui):
    """Handle actions triggered by the header dropdown buttons."""
    if ui.get("ui_mode") != "presets":
        return False

    device_name = presets_page.active_device
    section_name = presets_page.active_section
    screen = ui["screen"]

    if action == "set_mode_patches":
        # Show onboard / external patches with numeric prefixes
        pairs = device_patches.list_patches(device_name)  # [(num, name), ...]
        preset_names = [f"{int(num):02d}: {name}" for num, name in pairs]
        presets_page.preset_source = "patches"
        presets_page.reload_presets(screen, preset_names)
        log(None, f"[Presets] Switched to INTERNAL patches for {device_name}")
        return True

    elif action == "set_mode_presets":
        # Show internal Pi presets
        preset_names = device_presets.list_presets(device_name, section_name)
        presets_page.preset_source = "presets"
        presets_page.reload_presets(screen, preset_names)
        log(None, f"[Presets] Switched to EXTERNAL Pi presets for {device_name}")
        return True

    return False
