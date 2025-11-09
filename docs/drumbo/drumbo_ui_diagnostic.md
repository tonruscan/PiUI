# Drumbo UI Failure Diagnostic Report

## 🧩 Observed Symptoms
From your screenshots:

| Symptom | Likely Cause |
|----------|--------------|
| Missing 2nd bank of 8 dials (only 8 visible instead of 16) | The `LegacyUISyncService` refactor broke the `_position_mini_dials()` or `_refresh_widget_bank_refs()` calls — either not triggering, or pointing to a stale bank manager reference. |
| Background box and labels gone | The legacy layout/draw routine from the original `DrumboMainWidget` isn’t being called or the draw rect context was dropped when the service took over rendering. |
| No sound when triggering via MIDI | `_play_sample()` isn’t being called — likely because the event bridge or bank/instrument bindings weren’t restored in the final cleanup (facade context lost or muted). |
| Sample labels not updating when loading origin samples | `_set_instrument()` or `_apply_mic_value()` calls no longer reach the widget because they now route through the service but the widget reference is `None` or desynced. |

In short: logic may be intact, but the **wiring between the widget, sampler context, and UI service** broke during cleanup.

---

## 🧠 Why This Happened
Even though each migration phase verified correctly, the **last cleanup phase** removed or relocated the final “bridge points” that actually *draw* and *update* the interface:

- When `LegacyUISyncService` took over, it abstracted away `_position_mini_dials()` and `_refresh_widget_bank_refs()`.
- The tests (`verify_sampler_phase2.py`) **don’t exercise any visual paths**, only audio, preset, and mixer logic.
- So the verification passed — but UI rendering, which happens later in the frame lifecycle, silently broke.

This is why the “be very careful and debug everything” process missed it — the UI part wasn’t under test coverage.

---

## 🩺 Diagnostic Steps
Before touching any code, run this small diagnostic in your console inside your `midi39` venv:

```python
from plugins.drumbo_plugin import Drumbo
d = Drumbo()
print("Widget:", getattr(d, "widget", None))
print("Has _position_mini_dials:", hasattr(d, "_position_mini_dials"))
print("Has _refresh_widget_bank_refs:", hasattr(d, "_refresh_widget_bank_refs"))
```

Then also check the UI service path:

```python
from plugins.sampler.instruments.drumbo.ui import ui_service
print(dir(ui_service))
```

This will help confirm:
- Whether the widget reference is missing.
- Whether the UI service functions exist but aren’t bound to the plugin.
- Whether the sampler shell stopped calling `DrumboPlugin.on_load()` for UI registration.

---

## 🧭 How to Ask GPT / the Dev Agent Next
Use this diagnostic framing for the code agent (or next GPT):

> Drumbo’s UI has stopped rendering correctly after the cleanup phase.  
> The plugin loads, but only shows 8 dials (instead of 16), no background box or labels, and MIDI playback no longer triggers.  
>  
> Please do not rewrite anything yet — first, diagnose.  
>  
> 1. Inspect `drumbo_plugin.py`, `ui_service.py`, and `drumbo_main_widget.py` for where `_refresh_widget_bank_refs()` and `_position_mini_dials()` are called.  
> 2. Trace whether the `widget` attribute on the Drumbo instance is being set or passed into the `LegacyUISyncService`.  
> 3. Identify which link (Drumbo → UI Service → Widget → Renderer) is now broken.  
> 4. Provide a diff or snippet showing the missing call sequence so we can confirm before restoring any code.  
>  
> We only want the wiring analysis right now, not fixes.

---

## 🧩 Next Steps After Diagnosis
Once the broken call path is confirmed, restoration should:
1. Reconnect the widget assignment in `Drumbo.on_load()` or context binding.
2. Ensure `_position_mini_dials()` runs after widget creation or bank setup.
3. Verify the sampler shell triggers the UI service when banks or instruments change.
4. Re-run visual verification (16 dials visible, labels restored, MIDI-triggered playback working).

This structured approach ensures the fix targets the actual break in linkage rather than reintroducing legacy coupling.

