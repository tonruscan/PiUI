# /build/control/tremolo_control.py
# Master tempo + rhythmic division control for Tremolo Designer
import time
import threading
import showlog

# ---------------------------------------------------------------------
# GLOBAL STATE
# ---------------------------------------------------------------------
_BPM = 120.0           # default tempo
_DIVISION = "1/8"      # default rhythmic division
_last_taps = []        # tap-tempo timestamps (for averaging)
_lock = threading.Lock()

# rhythmic divisions (relative to a quarter note)
_DIVISIONS = {
    "1/1": 1.0,        # whole
    "1/2": 0.5,        # half
    "1/4": 0.25,       # quarter
    "1/8": 0.125,
    "1/16": 0.0625,
    "1/32": 0.03125,
    "1/8T": 0.0833,    # triplet
    "1/8.": 0.1875,    # dotted
}

# ---------------------------------------------------------------------
# TAP TEMPO HANDLER
# ---------------------------------------------------------------------
def tap():
    """Record a tap; update BPM from average of last few taps."""
    global _BPM
    now = time.time()

    with _lock:
        _last_taps.append(now)
        # keep only the last 5 taps
        if len(_last_taps) > 5:
            _last_taps.pop(0)

        if len(_last_taps) >= 2:
            intervals = [t2 - t1 for t1, t2 in zip(_last_taps[:-1], _last_taps[1:])]
            avg_interval = sum(intervals) / len(intervals)
            if avg_interval > 0:
                _BPM = 60.0 / avg_interval
                showlog.info(f"[TAP] Tempo set to {_BPM:.1f} BPM")

# ---------------------------------------------------------------------
# DIVISION + RATE
# ---------------------------------------------------------------------
def set_division(name: str):
    """Set rhythmic division (e.g., '1/8', '1/16', '1/8T')."""
    global _DIVISION
    if name in _DIVISIONS:
        _DIVISION = name
        showlog.info(f"[TREM] Division set to {_DIVISION}")
    else:
        showlog.warn(f"[TREM] Unknown division: {name}")

def get_rate_hz():
    """Return current LFO frequency in Hz based on BPM + division."""
    quarter_note = 60.0 / _BPM        # seconds per quarter note
    mult = _DIVISIONS.get(_DIVISION, 0.125)
    period = quarter_note * mult * 4  # full cycle (4 beats per bar)
    rate_hz = 1.0 / period
    return rate_hz

def get_bpm():
    return _BPM

# ---------------------------------------------------------------------
# PLACEHOLDER: envelope trigger (to be implemented)
# ---------------------------------------------------------------------
def trigger_envelope():
    """This will start the ADSR + LFO modulation later."""
    showlog.debug("[TREM] Envelope trigger placeholder (coming soon)")
