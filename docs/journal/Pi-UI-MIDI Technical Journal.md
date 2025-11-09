% Pi-UI-MIDI Technical Journal

## 2025-11-06 – Preset Exit Dirty-Rect Recovery

### Context
- Reported regression: returning from `module_presets` occasionally left the Drumbo main widget background unpainted.
- Root cause suspicion: dirty-rect pipeline never received a redraw request because the preset page releases its widget reference before the module is rehydrated.

### Changes
- Introduced `request_custom_widget_redraw(include_overlays: bool = False)` in `pages/module_base.py` to encapsulate widget repaint requests and queue them if the widget is not yet instantiated.
- Added pending flags (`_PENDING_WIDGET_REDRAW`, `_PENDING_WIDGET_REDRAW_INCLUDE_OVERLAY`) so deferred redraws fire automatically when `_load_custom_widget()` recreates the widget.
- Updated `pages/module_presets.py` back-button handler to:
	- Prefer `navigator.go_back()` results for the target mode, with a fallback to `dials` when navigation history is exhausted.
	- Call `request_custom_widget_redraw(include_overlays=True)` in addition to `active_widget.mark_dirty()` to guarantee the custom widget and its overlay dial widgets repaint after exiting presets.
	- Queue `invalidate` and `force_redraw` messages so the frame controller produces full frames across the transition.
- Hooked `ModeManager.switch_mode()` (in `managers/mode_manager.py`) to call `request_custom_widget_redraw(include_overlays=True)` whenever leaving `module_presets`, covering cases where other callers initiate the transition.

### Rationale
- Centralising the redraw request in `module_base` keeps the fix generic for any module supplying a custom widget.
- Deferred redraw flags prevent missed paints when presets unloads the widget before the redraw request executes.
- Forcing a short burst of full-frame renders ensures the dirty-rect manager does not coalesce the request away while the mode is reconfiguring.

### Verification
- Manual testing pending: need to load multiple module presets (Drumbo + control cases) and confirm background stays intact when returning to the main page.
- No automated tests available for the UI pipeline; visual verification required.

### Follow-Up Notes
- Consider adding targeted logging around `request_custom_widget_redraw()` to trace future issues.
- Monitor performance—extra full-frame requests are limited to three frames to minimise overhead, but keep an eye on low-power devices.
