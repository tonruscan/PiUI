# control/vibrato_control.py
import showlog

# -----------------------------------------------------------
# Vibrato Control (initial placeholder)
# -----------------------------------------------------------

def init(device=None):
    """Initialize Vibrato control module."""
    showlog.info("[VibratoControl] Initialized")
    return True


def handle(tag, data=None):
    """Handle messages routed from the Vibrato page."""
    showlog.debug(f"[VibratoControl] handle() tag={tag}, data={data}")


def update():
    """Periodic update hook (if needed)."""
    pass

# Keep a tiny state dict
_state = {
    "vibrato_time_fraction": 52,   # index into options
    # add more as you add controllers
}

def get_state():
    return dict(_state)

def apply(control_id: str, value: int):
    """Called by the page when a controller dial moves."""
    # clamp to int
    try:
        v = int(value)
    except Exception:
        v = 0
    _state[control_id] = v

    # Dispatch per-control behavior here
    if control_id == "vibrato_time_fraction":
        # Example: just log for now; your engine can translate this index
        showlog.info(f"[VIBRATO] Division index → {v}")
        # TODO: hook this into your actual LFO/clock division engine

    # You can emit UI messages if needed:
    # msg_queue.put(("vibrato_update", control_id, v))

    # --- Division → Hz helpers (no side effects) -------------------------------

def _parse_note_fraction(text: str) -> int:
    """
    Accepts '1', '1/2', '1/4', '1/8', '1/16', '1/32' (case/space tolerant).
    Returns denominator x as int (1, 2, 4, 8, 16, 32).
    Raises ValueError for bad input (e.g., '3/8').
    """
    s = str(text).strip().lower().replace(" ", "")
    if s == "1":
        return 1
    if "/" in s:
        num, den = s.split("/", 1)
        if num != "1":
            raise ValueError(f"Unsupported note value '{text}'; numerator must be 1.")
        x = int(den)
        # Require power-of-two note denominators (common musical divisions)
        if x <= 0 or (x & (x - 1)) != 0:
            raise ValueError(f"Unsupported denominator in '{text}'.")
        return x
    raise ValueError(f"Unrecognized note value '{text}'.")


def hz_from_division(bpm: float, division_text: str) -> float:
    """
    Convert a musical note division to Hz at a given BPM.
    Formula: Hz = (BPM / 60) * (x / 4), where division '1/x' (or '1') maps to x.
    Examples at 120 BPM: 1 → 0.5 Hz, 1/2 → 1 Hz, 1/4 → 2 Hz, 1/8 → 4 Hz, 1/16 → 8 Hz, 1/32 → 16 Hz.
    """
    x = _parse_note_fraction(division_text)
    return (float(bpm) / 60.0) * (x / 4.0)

