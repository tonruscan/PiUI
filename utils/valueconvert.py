# /build/utils/valueconvert.py
"""
Utility functions for converting between MIDI 0–127 values and
real-world parameter ranges (e.g. dB, Hz, Octaves, etc.)

This ensures that all modules (UI, device handlers, presets)
use a consistent scaling model.
"""

def _clamp(val, lo, hi):
    """Clamp a numeric value between lo and hi."""
    return max(lo, min(hi, val))


def real_to_midi(real_val, param_range):
    """
    Convert a real-world value (e.g. -12.5 dB) to a 0–127 MIDI integer.
    param_range may be [min, max] (floats or ints).
    """
    try:
        # Default linear if no range given
        if not isinstance(param_range, (list, tuple)) or len(param_range) != 2:
            return int(_clamp(round(real_val), 0, 127))

        lo, hi = map(float, param_range)
        # Avoid division by zero
        if hi == lo:
            return 0
        scaled = (float(real_val) - lo) / (hi - lo) * 127
        return int(round(_clamp(scaled, 0, 127)))
    except Exception:
        return 0


def midi_to_real(midi_val, param_range):
    """
    Convert a MIDI 0–127 value to its real-world equivalent.
    Returns float.
    """
    try:
        if not isinstance(param_range, (list, tuple)) or len(param_range) != 2:
            return float(_clamp(midi_val, 0, 127))

        lo, hi = map(float, param_range)
        scaled = lo + (float(_clamp(midi_val, 0, 127)) / 127.0) * (hi - lo)
        return round(scaled, 2)
    except Exception:
        return 0.0
