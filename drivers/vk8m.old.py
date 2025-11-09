# /drivers/vk8m.py
# Lightweight Roland VK-8M SysEx helper

import midiserver
from typing import Callable

# Type for whatever you use to send raw MIDI bytes (mido, rtmidi, your midi client, etc.)
SendFn = Callable[[bytes], None]

ROLAND_ID = 0x41
DEVICE_ID = 0x10      # change if you address a different device ID
MODEL_ID_HI = 0x00
MODEL_ID_LO = 0x4D    # VK-8M
CMD_DT1 = 0x12        # Data Set 1 (write)
BASE_HI = 0x10
BASE_LO = 0x00

def _checksum(ww: int, xx: int, rr: int) -> int:
    # Roland checksum over address+data: (128 - ((10 + 00 + ww + xx + rr) % 128)) % 128
    s = (BASE_HI + BASE_LO + ww + xx + rr) % 128
    return (128 - s) % 128

def send_param(ww: int, xx: int, rr: int) -> None:
    """Send a parameter change to VK-8M via midiserver."""
    ck = _checksum(ww, xx, rr)
    # midiserver.send_sysex expects data WITHOUT F0/F7 wrappers
    data = [
        ROLAND_ID, DEVICE_ID, MODEL_ID_HI, MODEL_ID_LO,
        CMD_DT1, BASE_HI, BASE_LO, ww, xx, rr, ck
    ]
    midiserver.send_sysex(data, device="VK8M")

# -------- Convenience wrappers for the params we already know --------
def set_vibrato_on(on: int) -> None:          # 0/1
    """Turn vibrato on/off."""
    send_param(0x20, 0x00, 1 if on else 0)

def set_vibrato_type(typ: int) -> None:       # 0..5 (V1..C3)
    """Set vibrato type: 0=V1, 1=V2, 2=V3, 3=C1, 4=C2, 5=C3."""
    send_param(0x20, 0x01, max(0, min(5, typ)))

def set_reverb_type(typ: int) -> None:        # 0..3
    """Set reverb type: 0-3 (4 types)."""
    send_param(0x20, 0x0B, max(0, min(3, typ)))

def set_distortion_type(typ: int) -> None:    # 0..3
    """Set distortion type: 0-3 (4 types)."""
    send_param(0x20, 0x06, max(0, min(3, typ)))

def set_distortion(val: int) -> None:         # 0..127
    """Set distortion level."""
    send_param(0x20, 0x07, max(0, min(127, val)))

def set_reverb_level(val: int) -> None:       # 0..127
    """Set reverb level."""
    send_param(0x20, 0x0C, max(0, min(127, val)))
