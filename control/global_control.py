import showlog

def handle_message(tag, msg, ui):
    try:
        if tag is None:
            # Plain string message
            showlog.verbose(msg)
        elif isinstance(msg, tuple):
            # Tuple payload → show tag + args (without 'msg=')
            payload = msg[1:] if len(msg) > 1 else ()
            showlog.debug(f"{tag} {payload}")
        else:
            # Fallback
            showlog.verbose(tag)
    except Exception as e:
        showlog.error(e)

import showlog

_current_presets = {}  # keep this near the top of the file

def set_current_preset(preset, values=None, program=None):
    """
    Store the most recently loaded preset for the current device and page.
    Automatically detects the active device and page using dialhandlers/presets.

    Parameters:
    - preset: human-friendly preset label (e.g., "01: Warm Pad")
    - values: optional list of 8 dial values when using Pi-stored presets
    - program: optional program number when using patches.json

    At least one of 'values' or 'program' must be provided.
    """
    try:
        import dialhandlers
        from pages import presets as presets_page

        device = getattr(dialhandlers, "current_device_name", None)
        if not device:
            return
        device = device.upper()

        page_id = getattr(dialhandlers, "current_page_id", None)
        page_name = getattr(presets_page, "active_section", str(page_id))

        # Require some payload to store
        if values is None and program is None:
            return

        entry = {
            "page_id": str(page_id),
            "page_name": page_name,
            "preset": preset,
        }
        if values is not None:
            entry["values"] = values
        if program is not None:
            try:
                entry["program"] = int(program)
            except Exception:
                entry["program"] = program

        _current_presets[device] = entry

        suffix = f"values={len(values)}" if isinstance(values, list) else f"program={program}"
        showlog.debug(f"Current preset set for {device}:{page_id} ({page_name}) → {preset} ({suffix})")

    except Exception as e:
        showlog.error(f"set_current_preset: {e}")


def get_current_preset(device):
    """Return last stored preset info for the given device."""
    device = device.upper()

    return _current_presets.get(device)

