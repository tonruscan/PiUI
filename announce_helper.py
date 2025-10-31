# announce_helper.py
import devices
import midiserver
import showlog

def send_device_announce(device_name: str):
    """Send the announce MIDI message defined in devices.json for this device."""
    try:
        if not device_name:
            return

        dev = devices.get_by_name(device_name)
        msg = dev.get("announce_msg")
        if not msg:
            showlog.info(f"[ANNOUNCE] No announce_msg defined for {device_name}")
            return

        data = [int(x, 16) for x in msg]
        midiserver.send_bytes(data)

    except Exception as e:
        showlog.error(f"[ANNOUNCE] Failed for {device_name}: {e}")
