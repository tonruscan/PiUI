# /drivers/vk8m.py
# Roland VK-8M SysEx Helper (Complete Edition)
# ---------------------------------------------
# Provides high-level control wrappers for all known VK-8M parameters:
# Vibrato, Reverb, Distortion, Percussion, Tonewheel, Leakage,
# Rotary, Drawbars, Crescendo, and Glissando.

from typing import Callable
import midiserver

# Roland VK-8M identifiers
ROLAND_ID   = 0x41
DEVICE_ID   = 0x10      # Change if your VK-8M uses a different device ID
MODEL_ID_HI = 0x00
MODEL_ID_LO = 0x4D      # VK-8M
CMD_DT1     = 0x12      # Data Set 1 (write)
BASE_HI     = 0x10
BASE_LO     = 0x00


# ------------------------------------------------------
# Core Low-Level Functions
# ------------------------------------------------------
def _checksum(ww: int, xx: int, rr: int) -> int:
    """Roland checksum over address + data."""
    s = (BASE_HI + BASE_LO + (ww & 0x7F) + (xx & 0x7F) + (rr & 0x7F)) % 128
    return (128 - s) % 128


def send_param(ww: int, xx: int, rr: int) -> None:
    """
    Send a parameter change to VK-8M via midiserver.
    midiserver.send_sysex expects data WITHOUT F0/F7 wrappers.
    """
    ww &= 0x7F
    xx &= 0x7F
    rr &= 0x7F
    ck = _checksum(ww, xx, rr)

    data = [
        ROLAND_ID, DEVICE_ID, MODEL_ID_HI, MODEL_ID_LO,
        CMD_DT1, BASE_HI, BASE_LO, ww, xx, rr, ck
    ]
    midiserver.send_sysex(data, device="VK8M")


# ------------------------------------------------------
# Vibrato / Chorus
# ------------------------------------------------------
def set_vibrato_on(on: int) -> None:
    """Turn vibrato/chorus on (1) or off (0)."""
    send_param(0x20, 0x00, 1 if on else 0)

def set_vibrato_type(typ: int) -> None:
    """Vibrato/Chorus type: 0=V1,1=V2,2=V3,3=C1,4=C2,5=C3."""
    send_param(0x20, 0x01, max(0, min(5, typ)))


# ------------------------------------------------------
# Reverb
# ------------------------------------------------------
def set_reverb_type(typ: int) -> None:
    """Reverb type: 0-3."""
    send_param(0x20, 0x0B, max(0, min(3, typ)))

def set_reverb_level(val: int) -> None:
    """Reverb level 0-127."""
    send_param(0x20, 0x0C, max(0, min(127, val)))


# ------------------------------------------------------
# Distortion
# ------------------------------------------------------
def set_distortion_type(typ: int) -> None:
    """Distortion type: 0-3."""
    send_param(0x20, 0x06, max(0, min(3, typ)))

def set_distortion(val: int) -> None:
    """Distortion level 0-127."""
    send_param(0x20, 0x07, max(0, min(127, val)))


# ------------------------------------------------------
# Percussion
# ------------------------------------------------------
def set_percussion_on(on: int) -> None:
    """Master percussion on/off."""
    send_param(0x10, 0x13, 1 if on else 0)

def set_percussion_2nd_3rd(mode: int) -> None:
    """Harmonic: 0=None, 1=2nd, 2=3rd."""
    send_param(0x10, 0x14, max(0, min(2, mode)))

def set_percussion_soft(on: int) -> None:
    """Volume: 0=Normal, 1=Soft."""
    send_param(0x10, 0x16, 1 if on else 0)

def set_percussion_slow(on: int) -> None:
    """Decay: 0=Fast, 1=Slow."""
    send_param(0x10, 0x17, 1 if on else 0)


# ------------------------------------------------------
# Tonewheel Character / Leakage
# ------------------------------------------------------
def set_tonewheel_type(typ: int) -> None:
    """Tonewheel: 0=Vintage1, 1=Vintage2, 2=Clean."""
    send_param(0x10, 0x18, max(0, min(2, typ)))

def set_leakage(val: int) -> None:
    """Leakage amount 0-127."""
    send_param(0x10, 0x19, max(0, min(127, val)))


# ------------------------------------------------------
# Rotary Speaker
# ------------------------------------------------------
def set_rotary_speed(mode: int) -> None:
    """0=Slow, 1=Fast."""
    send_param(0x00, 0x06, 1 if mode else 0)

def set_rotary_brake(on: int) -> None:
    """0=Off, 1=Brake."""
    send_param(0x20, 0x04, 1 if on else 0)


# ------------------------------------------------------
# Drawbars (All 9)
# ------------------------------------------------------
def set_drawbar(index: int, val: int) -> None:
    """
    Set drawbar position (0-8).
    index: 1–9 (corresponding to 16′ → 1′)
    val:   0–8 (drawbar depth)
    """
    index = max(1, min(9, index))
    val = max(0, min(8, val))
    address = index - 1  # 0-based for 10 00 .. 10 08
    send_param(0x10, address, val)


# ------------------------------------------------------
# Crescendo / Glissando (Experimental)
# ------------------------------------------------------
def trigger_crescendo() -> None:
    """Trigger Crescendo (observed at 00 04 05)."""
    send_param(0x00, 0x04, 0x05)

def trigger_gliss() -> None:
    """Trigger Glissando (shared block with 00 04)."""
    send_param(0x00, 0x04, 0x05)  # Same address; timing handled externally
