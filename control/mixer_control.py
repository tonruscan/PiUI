# /build/control/mixer_control.py
import showlog
import quadraverb_driver as qv
import midiserver
import device_states

def handle_message(tag, msg, ui):
    """
    Respond to ('mixer_value', {'section': <id>, 'value': <0-127>})
    """
    if tag != "mixer_value":
        return False

    # Unpack tuple
    _, payload = msg
    section = int(payload.get("section", 0))
    ui_val  = int(payload.get("value", 0))

    # Convert 0–127 UI range → 0–99 Quadraverb level
    qv_val = int(round(ui_val * 99 / 127))

    from dialhandlers import current_device_name
    import midiserver

    try:
        sysex = send_mixer_volume(section, ui_val)
        showlog.debug(f"Sent mixer SysEx sec={section} bytes={sysex}")

    except Exception as e:
        showlog.error(e)
    # Persist current mixer state (optional)
    try:
        state = device_states.get_state("Quadraverb", "mixer") or [50, 50, 50, 50]
        if isinstance(state, dict) and "init" in state:
            state = state["init"]
        if isinstance(state, list) and len(state) >= section:
            state[section - 1] = qv_val
            device_states.store_init("Quadraverb", "mixer", state)
    except Exception:
        pass

    return True

def send_mixer_volume(section_id: int, value_0_127: int):
    """
    Send live mixer volume for a section (1–4) using the same format as mute/unmute codes.
    0–127 UI range → 0–99 Quadraverb value.
    """
    # Map mixer sections to correct byte order (same as mute codes)
    section_map = {1: 0x05, 2: 0x04, 3: 0x03, 4: 0x02}
    sec_byte = section_map.get(section_id, 0x05)

    # Convert UI 0–127 → QV 0–99
    scaled = (value_0_127 / 99) * 50
    val99 = int(min(99, round(scaled)))

    # Build the same structure as unmute, replacing the value byte
    sysex = [
        0xF0, 0x00, 0x00, 0x0E, 0x02, 0x01,
        0x08, sec_byte, val99, 0x00, 0x00, 0xF7
    ]

    import midiserver
    midiserver.send_bytes(sysex)
    return sysex

