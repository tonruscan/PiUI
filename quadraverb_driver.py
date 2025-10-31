"""
quadraverb_driver.py
--------------------
Alesis Quadraverb SysEx driver.
Builds and sends SysEx messages with simple global duplicate filtering.
"""

from mido import Message
import showlog

_last_sysex_bytes = None  # global last message, like Bome's 'gl'


def build_sysex(section_id, dial_index, dial_value, parameter_range, page_offset=0, dial_obj=None):
    """
    Build a complete Quadraverb SysEx message.

    section_id: 1–4 (Reverb, Delay, Pitch, EQ)
    dial_index: 1–8 (which dial)
    dial_value: 0–127 from UI
    parameter_range: can be a number (e.g. 5) or a [min, max] list
    page_offset: dial’s actual Quadraverb page index (from devices.json)
    """
    try:
        # --- Determine range limits ---
        if isinstance(parameter_range, (list, tuple)) and len(parameter_range) == 2:
            min_val, max_val = float(parameter_range[0]), float(parameter_range[1])
        else:
            min_val, max_val = 0.0, float(parameter_range or 127)

        # --- Use absolute span for scaling (ignores sign) ---
        range_span = abs(max_val - min_val)

        # --- Scale 0–127 → full device range ---
        scaled_value = (dial_value / 127.0) * range_span

        # --- Core address math (verified logic) ---
        pair_index = int(scaled_value // 2)
        remainder = scaled_value - (pair_index * 2)
        low_byte = 0 if remainder == 0 else 64

        bank_number = pair_index // 128
        base_address = pair_index % 128
        high_bank_group = bank_number // 4
        reduced_bank = high_bank_group * 4
        high_address_nibble = (bank_number - reduced_bank) * 32
        if high_bank_group > 0:
            low_byte += high_bank_group

        lc = int(section_id)
        qq = int(page_offset)
        rr = int(base_address)
        ss = int(low_byte)
        tt = int(high_address_nibble)

        showlog.debug(f"[QV BUILD] lc={lc} qq={qq} base={rr} low={ss} high={tt} scaled={scaled_value:.2f}")

       
        # --- Package outputs ---
        sysex_bytes = [
            0xF0, 0x00, 0x00, 0x0E, 0x02, 0x01,
            lc, qq, rr, ss, tt, 0xF7
        ]
        value_bytes = (rr, ss, tt)

        global last_qv_bytes
        last_qv_bytes = value_bytes

        return {
            "sysex": sysex_bytes,
            "bytes": value_bytes,
            "scaled": scaled_value
        }

    except Exception as e:
        showlog.error(f"[QV SYSEX ERROR] build_sysex failed: {e}")
        return None


def send_sysex(out_port, section_id, dial_index, dial_value, parameter_range, page_offset=0, dial_obj=None):
    """Build and send a Quadraverb SysEx message, skipping duplicates."""
    global _last_sysex_bytes
    try:
        data = build_sysex(section_id, dial_index, dial_value, parameter_range, page_offset)
        if not data:
            return

        sysex = data["sysex"]
        rr, ss, tt = data["bytes"]
        scaled = data["scaled"]

                # --- store last sent bytes on dial (for label display) ---
        if dial_obj is not None:
            try:
                dial_obj.last_sysex_bytes = (rr, ss, tt)
            except Exception as e:
                showlog.error(f"[QV SYSEX] could not attach bytes to dial: {e}")

        # Skip if identical to last message
        if sysex == _last_sysex_bytes:
            return  # unchanged, skip like Bome's 'if gl==ss then exit'

        _last_sysex_bytes = sysex
        out_port.send(Message.from_bytes(sysex))
        showlog.debug(f"[QV SYSEX] {sysex}")

    except Exception as e:
        showlog.error(f"[QV SYSEX ERROR] {e}")


def reset_cache():
    """Reset duplicate filter (clear last SysEx memory)."""
    global _last_sysex_bytes
    _last_sysex_bytes = None
    showlog.error("[QV SYSEX] Cache cleared.")
