# Sampler Backend Manual v3

> Service notes for the Drumbo auto-slicer integration and sampler backend work completed November 7 2025. This manual captures the new slicer pipeline, Drumbo UI toggling, and plugin boot expectations so future developers can extend the sampler, add widgets, or service the existing code without spelunking the diff history.

---

## 1. Scope & Highlights

- Added a sampler-core **auto-slicer** pipeline (conversion, transient detection, metadata persistence, widget).
- Integrated the slicer into Drumbo with button-driven widget swapping.
- Improved **error handling** and surfaced failure metadata for corrupt recordings.
- Hid/reshowed Drumbo dial banks when switching between drum kit and slicer views, giving the slicer its own background.
- Relaxed PluginManager logging to ignore intentionally removed legacy stubs.

All changes live under `plugins/sampler/...`, `pages/module_base.py`, `plugins/sampler/instruments/drumbo/...`, and `core/plugin.py`. Tests were expanded (`plugins/sampler/core/tests/test_slicer_detector.py`) and `verify_sampler_phase2.py` remains the regression harness.

---

## 2. Auto-Slicer Pipeline

### 2.1 Controller (`plugins/sampler/core/slicer/controller.py`)
Responsible for walking the field recorder inbox, running conversion, transient detection, and emitting metadata.

**Key traits (new in this iteration):**

```python
class AutoSlicerController:
    def __init__(...):
        self._errors: dict[str, str] = {}
        self._last_error_id: str | None = None

    def process_recording(self, recording_path: Path) -> SliceSet:
        try:
            converted = self.converter.convert(recording_path, converted_path)
        except ConversionError as exc:
            message = str(exc)
            self._errors[recording_id] = message
            self._last_error_id = recording_id
            self._write_failure_metadata(
                recording_id=recording_id,
                source_path=recording_path,
                metadata_path=metadata_path,
                message=message,
            )
            raise

        # ... detect_transients(), export slices ...

        self._write_metadata(slice_set)
        self._errors.pop(recording_id, None)
        if self._last_error_id == recording_id:
            self._last_error_id = None
        self._last_sets[recording_id] = slice_set
        self._notify(slice_set)
        return slice_set

    def get_last_error(self, recording_id: str | None = None) -> Optional[str]: ...
```

- The controller now writes **error metadata** (`status: "error"`) so corrupted recordings stop reprocessing.
- `discover_processed()` skips errored metadata, leaving `_errors` populated so the UI can report “moov atom not found”.
- `get_last_error()` lets callers fetch the most recent failure, either per recording or globally.

### 2.2 Converter (`plugins/sampler/core/slicer/converter.py`)
Wraps ffmpeg while normalising errors for humans:

```python
result = subprocess.run(cmd, stdout=PIPE, stderr=PIPE, check=False)
if result.returncode != 0:
    error_text = result.stderr.decode(errors="ignore")
    showlog.debug(f"[AutoSlicer] ffmpeg stderr ({result.returncode}): {error_text}")
    summary = _summarize_ffmpeg_error(error_text)
    raise ConversionError(f"ffmpeg failed ({result.returncode}): {summary}")
```

`_summarize_ffmpeg_error` collapses verbose logs into phrases such as “moov atom not found (file appears incomplete or truncated)”.

### 2.3 Models (`plugins/sampler/core/slicer/models.py`)
`SliceSet.to_dict()` now tags metadata with `status: "ok"`. The controller’s error writer produces `status: "error"` entries with `error_message`.

### 2.4 Widget (`plugins/sampler/core/slicer/widget.py`)
No structural changes beyond new consumers: still a 4×2 pygame panel expecting eight slices (`AutoSlicerWidget`).

---

## 3. Drumbo Integration

### 3.1 Module wiring (`plugins/sampler/instruments/drumbo/module.py`)
Drumbo now owns the slicer instance and handles widget mode toggling.

Key additions:

```python
class DrumboInstrument(ModuleBase, InstrumentModule):
    def __init__(self) -> None:
        ...
        self._auto_slicer = AutoSlicerController()
        self._auto_slicer.add_listener(self._handle_slice_set)
        self._latest_slice_set: SliceSet | None = None
        self._slicer_widget = None
        self._drumbo_widget = None
        self._widget_mode = "drumbo"
        self._auto_slicer_last_error: str | None = None
        self._dial_banks_visible = True

    def _show_widget_mode(self, mode: str, *, force: bool = False) -> None:
        target = "slicer" if str(mode or "").lower().startswith("s") else "drumbo"
        if target == "slicer":
            module_base.set_custom_widget_override(self.SLICER_WIDGET, include_overlays=True)
        else:
            module_base.clear_custom_widget_override(include_overlays=True)
            self._slicer_widget = None
        self._widget_mode = target
        self._set_dial_banks_visible(target == "drumbo")
        self.button_states["3"] = 1 if target == "slicer" else 0
        self._push_button_states()

    def _set_dial_banks_visible(self, visible: bool) -> None:
        self._dial_banks_visible = bool(visible)
        manager = self._ensure_bank_setup(default_bank=self.current_bank)
        if manager and hasattr(manager, "set_show_all_banks"):
            manager.set_show_all_banks(visible)
        for bank_key in ("A", "B"):
            if manager:
                manager.set_bank_visible(bank_key, visible)
        # mark widgets dirty + request redraw ...
```

- **Button 3** now toggles `self._widget_mode` (`drumbo` ⟷ `slicer`).
- When the slicer is active, `set_custom_widget_override` installs `AutoSlicerWidget` and hides the dial banks so the slicer draws against its own background.
- `button_states["3"]` mirrors the visible mode for the hardware overlay.
- **Button 1** (snare/kick) forces the Drumbo widget back so mic dials instantly reappear:

```python
elif btn_id == "1":
    target_instrument = "snare" if state_index == 0 else "kick"
    self._set_instrument(target_instrument)
    self._show_widget_mode("drumbo", force=True)
```

- `_ensure_auto_slicer_ready` now stores the controller’s `get_last_error()` message in `_auto_slicer_last_error`; this can be used to render status text later.

### 3.2 UI Service (`plugins/sampler/instruments/drumbo/services/ui_service.py`)
Still manages bank setup and dial wiring. No API changes, but `_set_dial_banks_visible` uses `set_show_all_banks(False)` and `set_bank_visible(False)` so dials truly vanish when the slicer is onscreen.

### 3.3 Widget override infrastructure (`pages/module_base.py`)
Already supported override specs; the slicer leverages the existing `set_custom_widget_override`/`clear_custom_widget_override` APIs. Dial hiding simply marks widgets dirty and asks `module_base.request_custom_widget_redraw(include_overlays=True)` to repaint.

---

## 4. Tests & Verification

### 4.1 Unit Tests
`plugins/sampler/core/tests/test_slicer_detector.py` now includes a failure regression:

```python
def test_controller_records_failed_conversion(self):
    class _FailingConverter(AudioConverter):
        def convert(...):
            raise ConversionError("ffmpeg failed (1): moov atom not found (file appears incomplete or truncated)")

    controller = AutoSlicerController(..., converter=_FailingConverter())
    results = controller.process_pending()
    self.assertEqual(results, [])

    meta_path = processed_root / "rec_999..." / "metadata.json"
    payload = json.loads(meta_path.read_text())
    self.assertEqual(payload.get("status"), "error")
    self.assertIn("moov atom not found", controller.get_last_error(...))
```

### 4.2 Harness
`python verify_sampler_phase2.py` remains the daily driver. It simulates both MixerFacade (true) and fallback (false) flows, ensuring:

- Mixer methods invoked as expected.
- Preset load/save happens multiple times per scenario.
- Event playback flags set to True.

Run after any slicer/Drumbo change to keep the legacy path healthy.

---

## 5. Plugin Boot Expectations

`core/plugin.py` discovery now treats the `plugins.drumbo_plugin` stub as an **expected skip**, logging at info level:

```python
except Exception as e:
    message = str(e)
    if isinstance(e, ImportError) and "has been removed" in message:
        showlog.info(f"[PluginManager] Skipping legacy plugin '{name}': {message}")
    else:
        showlog.error(...)
```

Make sure production configs point to `plugins.sampler.plugin:Plugin`. The stub import only exists to catch stragglers during migration.

---

## 6. Extending the System

### 6.1 Adding a New Instrument Widget
1. Author your widget (pygame surface) under `plugins/sampler/instruments/<instrument>/ui/`.
2. Provide a config entry (`SLICER_WIDGET`-style dict) describing the class path, grid size, and grid position.
3. In the instrument module, call `module_base.set_custom_widget_override(...)` when the widget should replace the dial grid. Pair with a call to `_set_dial_banks_visible(False)` if you need a bare background.
4. Attach the widget in `attach_widget(self, widget)` to wire callbacks and supply new data (see `AutoSlicerWidget.set_slice_set`).

### 6.2 Ingesting External Audio
- Plug your conversion into `AudioConverter` (or provide a subclass). Remember to set `ffmpeg_binary` if packaged builds store ffmpeg elsewhere.
- Use `process_recording(Path)` to convert a single file, or `process_pending()` to sweep the inbox.
- Store errors using `_write_failure_metadata` so the UI can display the failure reason and skip bad files.

### 6.3 Button/Widget Toggle Patterns
- Map multistate buttons in the instrument’s `config.py` (`BUTTONS` list). Drumbo uses:

```python
BUTTONS = [
    {"id": "1", "behavior": "multi", "states": ["S", "K"]},
    {"id": "2", "behavior": "multi", "label": "BANK", "states": ["A", "B"]},
    {"id": "3", "behavior": "multi", "label": "KIT", "states": ["D", "SL"]},
    ...
]
```

- Handle `button` events in `on_button` (or `_handle_button_event`). Update `self.button_states[...]` and push back through the UI service for LED feedback.
- Use `_show_widget_mode('slicer')` / `_show_widget_mode('drumbo')` as a template for future toggles.

### 6.4 Surfacing Errors to UI
- The module caches `_auto_slicer_last_error`. When you design a status overlay, render this string (or `"Ready"` if `None`) to inform the user about ffmpeg issues.

---

## 7. Operational Checklist

- ✅ Unit tests: `python -m unittest plugins.sampler.core.tests.test_slicer_detector`
- ✅ Harness: `python verify_sampler_phase2.py`
- ✅ Field recorder imports: watch `assets/samples/fieldrecorder/processed/<rec>/metadata.json`. Expect `status: "ok"` for good runs.
- ⚠️ `moov atom not found` indicates a truncated `.m4a`; delete or re-export, then remove the cached `processed/<rec>/` folder before re-running.
- 🔁 Manual UI check: toggle button 3 to ensure dial banks hide/show correctly; button 1 should restore the mic grid.

---

## 8. Future Enhancements

- Add visual status text to the slicer widget (`AutoSlicerWidget`) showing the latest error or most recent recording id.
- Watcher service to ingest new `.m4a` files automatically and push notifications via `EventBridge`.
- Persist slicer labels in presets (extend `SliceSummary.label` usage and widget state save/load).
- Expand PluginManager skip list to cover other retired plugins if we prune more legacy modules.

---

## 9. Appendix – Key Files

| Area | Path |
| --- | --- |
| Slicer controller | `plugins/sampler/core/slicer/controller.py` |
| ffmpeg converter | `plugins/sampler/core/slicer/converter.py` |
| Slicer widget | `plugins/sampler/core/slicer/widget.py` |
| Drumbo module | `plugins/sampler/instruments/drumbo/module.py` |
| Drumbo config | `plugins/sampler/instruments/drumbo/config.py` |
| Drumbo UI services | `plugins/sampler/instruments/drumbo/services/ui_service.py` |
| Module base overrides | `pages/module_base.py` |
| Plugin discovery | `core/plugin.py` |
| Unit tests | `plugins/sampler/core/tests/test_slicer_detector.py` |
| Harness | `verify_sampler_phase2.py` |

Keep this manual alongside `sampler_architecture_manual_v2.md` for a complete picture of the sampler backend. Update whenever the auto-slicer gains new features or additional instruments adopt the same widget toggle pattern.
