# Patch-select case mismatch fix: change log

This document summarizes the exact code changes made to fix the issue where turning the hardware dial did not send Program Changes and the LED showed just numbers. The root cause was device-name case/alias mismatches causing patch-name lookups to fail and messages without names to be ignored by the UI parser.

## Summary of the fix

- Make the lightweight patch SysEx handler match `patches.json` device keys case-insensitively and tolerate aliases/partials.
- Always include a trailing dot after the numeric program in the emitted message (e.g., `09.`) to keep a stable parser contract.
- Make the UI-side `[PATCH_SELECT]` parser tolerant of messages that don’t include a `.Name` segment; it now extracts leading digits and sends the Program Change regardless.
- Make the Presets page highlight tolerant of messages without a name.

Files changed:
- `t:\UI\build\dialhandlers.py`
- `t:\UI\build\ui.py`
- `t:\UI\build\pages\presets.py`

---

## 1) dialhandlers.py – robust SysEx → patches.json matching and stable message format

Location:
- Function: `on_midi_sysex(device, layer, dial_id, value, cc_num)`
- Branch: lightweight patch SysEx (`if layer == 0 and dial_id == 0 and cc_num == 0:`)

What changed and why:
- Keep the device’s human-readable name for display. For lookups, compare case-insensitively and allow partial matches so aliases like `QVPlus` or `Quadraverb Plus` match `Quadraverb` in `patches.json`.
- Always build `display_text` with a trailing dot: `"NN."` when the name is missing. This guarantees the UI parser has a consistent delimiter.
- Uppercase the device portion in the emitted `[PATCH_SELECT]` message for consistency across modules.

Inserted/replaced block (core logic):

```python
from devices import DEVICE_DB
from device_patches import _patch_cache as PATCH_DB

dev_entry = DEVICE_DB.get(f"{device:02d}")
# Keep original name for human display; use lowercase for matching
dev_name = dev_entry["name"].strip() if dev_entry else f"DEV{device:02d}"
dev_name_lc = dev_name.lower()

# Patch numbers in patches.json are zero-padded strings
patch_key = f"{value:02d}"
patch_name = None

# Find device entry in patches DB case-insensitively, allowing partials
patch_dev_key = None
for key in PATCH_DB.keys():
    k_lc = key.lower()
    if k_lc == dev_name_lc or k_lc in dev_name_lc or dev_name_lc in k_lc:
        patch_dev_key = key
        break

if patch_dev_key:
    patch_name = PATCH_DB.get(patch_dev_key, {}).get(patch_key)

# Always include a dot so UI parser can extract the number reliably
display_text = f"{patch_key}.{patch_name or ''}"

showlog.log(None, f"[SysEx] Patch select → {dev_name.upper()} {display_text}")
msg_queue.put(f"[PATCH_SELECT] {dev_name.upper()}|{display_text}")
```

Effect:
- Even if the name isn’t found in `patches.json`, the UI still receives `DEV|NN.` and can reliably extract `NN` to send a Program Change.
- LED lines show the device and the number; the name appears when available.

---

## 2) ui.py – robust `[PATCH_SELECT]` parsing that always sends Program Change

Location:
- Function: `process_msg_queue()`
- Branch handling string messages, inside the `[PATCH_SELECT]` / `[PATCH_SELECT_UI]` block.

What changed and why:
- The parser previously required a `"NN.Name"` format. It now extracts leading digits from the right side even if no dot is present (e.g., `"NN"`), then sends the Program Change. This removes the dependency on patch names being present.

Inserted/replaced block (core logic):

```python
core = msg.split("]", 1)[1].strip()
if "|" in core:
    dev, rest = core.split("|", 1)

    # Extract preset number even if there's no dot/name
    num_str = None
    if "." in rest:
        num_str = rest.split(".", 1)[0]
    else:
        # take leading digits from the string
        digits = []
        for ch in rest.strip():
            if ch.isdigit():
                digits.append(ch)
            else:
                break
        num_str = "".join(digits) if digits else None

    if not num_str:
        raise ValueError(f"No preset number found in '{rest}'")

    preset_num = int(num_str)

    from pages import presets
    import dialhandlers

    current_dev = getattr(dialhandlers, "current_device_name", None)
    if current_dev != dev:
        print(f"[UI] Device changed → {current_dev} → {dev}")
        dialhandlers.current_device_name = dev
        page_id = getattr(dialhandlers, "current_page_id", "01")
        presets.init(screen, dev, page_id)

    presets.selected_preset = preset_num
    print(f"[UI] Highlight preset → {num_str}")
    presets.ensure_visible(presets.selected_preset, screen)
    presets.draw(screen)

    # Only send MIDI if the message was external
    if not msg.startswith("[PATCH_SELECT_UI]"):
        import midiserver
        midiserver.send_program_change(preset_num)

    if ui_mode != "presets":
        msg_queue.put(("ui_mode", "presets"))
        print(f"[UI] Auto-switch → Presets page for {dev}")
```

Effect:
- Program Changes are sent reliably whenever a number is present, regardless of whether a patch name accompanies it.

---

## 3) pages/presets.py – tolerant highlight logic

Location:
- Function: `highlight_preset(screen, raw_message: str)`

What changed and why:
- The function can now highlight based on just the numeric part from the `[PATCH_SELECT]` payload if no `".Name"` is present.

Inserted/replaced block (core logic):

```python
core = raw_message[len("[PATCH_SELECT]"):].strip()

# Parse "DEVICE|NN.Name" but tolerate missing name ("NN")
try:
    dev, rest = core.split("|", 1)
    if "." in rest:
        num_str = rest.split(".", 1)[0]
    else:
        # take leading digits only
        digits = []
        for ch in rest.strip():
            if ch.isdigit():
                digits.append(ch)
            else:
                break
        num_str = "".join(digits)
    preset_num = int(num_str)
    name = rest.split(".", 1)[1] if "." in rest else ""
except Exception:
    return  # bad format, ignore
```

Effect:
- The visible preset list highlights the correct row using the standard numeric prefix (`"NN:"`) even when names are missing in the incoming message.

---

## Verification steps

- Turn the hardware preset dial so that the device sends the lightweight patch SysEx (F0 7D …) to the UI.
  - Logs show: `[SysEx] Patch select → QUADRAVERB 09.Piano` or `QUADRAVERB 09.`
  - Presets UI highlights the `09:` row (name when known).
  - Program Change is sent (logged in `midiserver`): `[MIDI] Program Change → ch1 prog=9`.
  - LED/LCD update to show device and `NN.Name` (or `NN.` if the name is not found).

---

## Notes

- No changes were needed in `device_patches.py` or `config/patches.json`. The fix lives at ingress (SysEx) and UI parsing layers.
- If desired, we can further harden `device_presets.py` to perform case-insensitive device/page key lookups for Pi-stored presets. This is optional and not required for the specific issue fixed here.
