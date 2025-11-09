# ✅ Drumbo Facade Resolution – Recovery Instructions

Drumbo’s UI, mixer, and event flow all broke after the cleanup pass because the new `_resolve` helper in `configure_sampler_facades()` rejected the sampler’s **proxy facades**.  
These proxy objects use `__getattr__` for lazy binding, so your validation logic dropped them and silently replaced all three with `Null*Facade` fallbacks.  
As a result:

- The **event bridge** went null → no bank-change events → only **Bank A (8 dials)** rendered.  
- The **mixer facade** went null → no redraw callbacks → **background box and labels vanished**.  
- The **preset/mixer signals** stopped driving widget updates → MIDI playback and UI feedback died.  

This is why the layout changed from two 4-wide rows on the right to a single 8-wide horizontal line:  
`_refresh_widget_bank_refs()` and `_position_mini_dials()` only ever saw one bank, so the dials flattened into one row.

---

## 🧩 Required Fix

Please patch `configure_sampler_facades` in **`plugins/drumbo_plugin.py`** as follows:

### 1. Relax the `_resolve` logic
Accept facade proxy objects that implement `__getattr__`, not just ones that expose every method via `hasattr`.

```python
def _resolve(self, candidate, expected_methods, fallback):
    if candidate is None:
        return fallback
    for name in expected_methods:
        if hasattr(candidate, name):
            continue
        # Accept dynamic proxies (facades using __getattr__)
        if hasattr(candidate, "__getattr__") and not isinstance(
            candidate, type(fallback)
        ):
            return candidate
        return fallback
    return candidate
```

### 2. Rebind real facades from the sampler context
```python
def configure_sampler_facades(self, mixer=None, presets=None, events=None):
    self._mixer_facade = self._resolve(mixer, ("ensure_ready", "play_sample"), NullMixerFacade())
    self._preset_facade = self._resolve(presets, ("load_state", "save_state"), NullPresetFacade())
    self._event_bridge = self._resolve(events, ("publish",), NullEventBridge())
```

### 3. Add a clear inline note
```python
# NOTE: Sampler facades may be proxy objects exposing methods via __getattr__;
# do not reject them, or Drumbo will drop into NullFacade mode and lose UI/mixer sync.
```

---

## 🔁 Verification Steps

1. **Re-run regression:**
   ```powershell
   C:/venvs/midi39/Scripts/python.exe verify_sampler_phase2.py
   ```
   Expect both *facade* and *fallback* runs to pass with identical gain/sample names and return flags.

2. **Visually confirm:**
   - 16 dials (two stacked rows of 8) visible on the right.  
   - Background box and mic-label text restored.  
   - MIDI kick/snare triggers playback again.

3. **Log parity:**  
   The verification output should match the pre-cleanup Step 6 baseline.

---

## 🧠 Optional Hardening
If desired, introduce a `__facade__ = True` attribute in each real facade and create a small helper in `core/utils/validation.py`:

```python
def is_facade_proxy(obj):
    return getattr(obj, "__facade__", False) or hasattr(obj, "__getattr__")
```

Then `_resolve()` can safely accept both explicit and proxy facades while still rejecting true `Null*Facade` instances.

---

### ✅ Goal
Once this patch is applied, Drumbo will again receive its real facades, restoring:

- Bank A + B dial registration  
- Background panel redraw  
- Mixer playback and event routing  

The UI and audio behaviour should match the verified baseline before cleanup.

