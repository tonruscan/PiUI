# modules/modhelper.py
import re

def division_label_from_index(registry: dict, slot="01", idx=0) -> str:
    opts = (registry.get("vibrato", {}).get(slot, {}) or {}).get("options") or []
    if not opts: return "1"
    idx = max(0, min(len(opts)-1, int(idx)))
    return str(opts[idx])

def _parse_division_label(label: str) -> tuple[int, bool, bool]:
    # returns (x, dotted, triplet) for "1/x[.][T]"
    s = str(label).strip().lower().replace(" ", "")
    dotted = s.endswith(".")
    if dotted: s = s[:-1]
    triplet = s.endswith("t")
    if triplet: s = s[:-1]
    if s == "1":
        x = 1
    elif "/" in s:
        num, den = s.split("/", 1)
        if num != "1": raise ValueError(f"Unsupported note '{label}'")
        x = int(den)
        if x <= 0: raise ValueError(f"Bad denominator in '{label}'")
    else:
        raise ValueError(f"Unrecognized division '{label}'")
    return x, dotted, triplet

def rate_hz_from_division_label(bpm: float, label: str) -> float:
    # Base: Hz = (BPM/60)*(x/4) for "1/x"
    x, dotted, triplet = _parse_division_label(label)
    hz = (float(bpm) / 60.0) * (x / 4.0)
    if triplet: hz *= 3.0/2.0      # triplet is 2/3 duration → 3/2 frequency
    if dotted:  hz *= 2.0/3.0      # dotted is 3/2 duration → 2/3 frequency
    return hz
