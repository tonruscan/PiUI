# Quadraverb Dial Latch Issue (2025-11-05)

## Summary
Quadraverb hardware controller cannot latch onto certain discrete dials when latch mode is enabled. The affected controls never receive controller input after the UI value changes via mouse.

## Affected Controls
- Page 01 (Reverb) Dial 01: "Type" (CC30, range [0, 4], options list)
- Page 01 (Reverb) Dial 08: "Gate" (CC37, range [0, 1], options list)

Other dials with larger continuous ranges (e.g., PreDelay, Decay) latch and respond correctly.

## Current Behavior
1. Adjust the "Type" or "Gate" dial in the UI with the mouse.
2. Move the matching physical controller knob.
3. The latch never releases, so the controller is ignored and the value does not change.

The issue persists regardless of the UI value chosen or the controller position. Disabling the latch system entirely restores hardware control, confirming the latch logic is the root cause.

## Notes & Hypotheses
- Dial metadata uses small integer ranges (`[0, 4]` and `[0, 1]`) with discrete options.
- Latch logic in `dialhandlers.DialLatchManager` compares raw MIDI 0–127 values against the dial's current value; discrete dials may never hit the exact stored target.
- Quadraverb driver might snap values internally, causing mismatch between UI-stored value and incoming controller value.
- No recent config changes to CC mapping; other dials on the same CC bank behave normally.

## Next Steps
- Inspect `DialLatchManager.evaluate` for tolerance when `dial_meta.options` is present.
- Consider quantizing controller values to the dial's discrete steps before applying latch thresholds.
- Add diagnostic logging for discrete dials to capture `ui_val` vs `ctrl_val` during latch attempts.
- Retest after adjustments to ensure latch works for both continuous and enumerated parameters.
