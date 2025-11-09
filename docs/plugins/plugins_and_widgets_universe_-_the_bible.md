# Plugins & Widgets Universe – The Bible

> Comprehensive field guide to the current PiUI plugin/widget architecture (Updated: November 8 2025, rev 2). Covers legacy plugins (Vibrato, VK-8M drawbar), modern sampler stack (Drumbo, Auto-Slicer, ASCII Animator), integration requirements, and the roadmap toward a fully modular widget ecosystem. Use this to bootstrap new plugins, refactor existing ones, and onboard tooling that can author code autonomously.

---

## 1. Architectural Lens

### 1.1 Terminology
- **Plugin**: Entry point registered with `core/plugin.PluginManager`. Supplies metadata plus a `ModuleBase`-derived page class. Legacy plugins are monolithic; sampler introduces per-instrument modules.
- **ModuleBase**: UI controller for a plugin page. Owns dial grid, buttons, widget host, state sync, and preset handoff. One active `ModuleBase` instance per visible page.
- **Widget**: Pygame component rendered inside the module host (drawbars, slicer grid, ASCII pads, ADSR envelopes). Widgets are hot-swappable through the override system.
- **Sampler Instrument Module**: `InstrumentModule` subclass that augments `ModuleBase` with sampler-specific services (facades, recorder, mixer). Lives under `plugins/sampler/instruments/<instrument>/`.
- **Legacy Services**: `dialhandlers`, `custom_controls`, `preset_manager`, etc. Historically singletons; sampler wraps them behind facades so code can be tested and reused.

### 1.2 Integration Path
1. **Discovery**: `PluginManager.discover()` scans `plugins/` for subclasses of `Plugin`. Each plugin registers a page in `on_load(app)` using `app.page_registry.register`.
2. **Activation**: `module_base.set_active_module(plugin_cls)` clears prior state, instantiates the module, and primes widgets/dials via `init_page()`.
3. **Render Loop**: `draw_ui()` builds dial widgets, applies bank visibility, sets up `dialhandlers`, and loads any override widget.
4. **Runtime Interaction**: Hardware/controller input hits `dialhandlers` + `ModuleBase.handle_button_input`, which dispatches to module hooks (`on_dial_change`, `on_button`, etc.).
5. **Teardown**: Switching modules or closing a page triggers `set_active_module(None)` which now clears custom widget overrides, unregisters widget-owned dials, and resets bank visibility.

### 1.3 System Actors At A Glance
- `core/plugin.py`: Discovery and lifecycle for `Plugin` objects (load, init, shutdown).
- `pages/module_base.py`: Host controller; exposes override APIs, dial bank manager, button dispatch, preset binding.
- `custom_controls.py`: Defines dial metadata (ranges, labels) keyed by slot IDs used by ModuleBase.
- `dialhandlers.py`: Runtime dial/button state tracker. Bridges hardware events to module callbacks.
- `plugins/sampler/plugin.py`: Sampler entry point; creates `InstrumentContext` (mixer/preset/event facades) and boots active instrument module.
- `plugins/sampler/core/slicer/*`: Auto-slicer controller, models, processor, widget.
- `widgets/*.py`: Widget implementations (drawbar, ASCII animator, ADSR, etc.).

---

## 2. Case Studies

### 2.1 Vibrato Plugin
- **Location**: `plugins/vibrato_plugin.py`.
- **Module**: `Vibrato(ModuleBase)` wires a custom ADSR-style widget (`VibratoField`), plus dials for rate/level and nav buttons. Buttons defined inline (`BUTTONS` list).
- **Widget**: Defined in the same file; manual Pygame drawing with background colors sourced from theme via `helper.theme_rgb`.
- **Integration Notes**:
  - Uses legacy pattern: direct imports of `pages.module_base`, `helper`, global services.
  - No dial banks; overlays follow static layout.
  - Widget state persisted manually through `self.vibrato_widget_state`.

### 2.2 ASCII Animator Plugin
- **Location**: `plugins/ascii_animator_plugin.py`, widget in `widgets/ascii_animator_widget.py`.
- **Behavior**: 8×8 pad grid controlling ASCII animation playback; multi-state button toggles play/pause/reset.
- **Integration Notes**:
  - Exposes `BUTTONS` with multi-state semantics (transport states).
  - Widget offers `get_state/set_state` so presets restore animation frames.
  - Still legacy-style; no sampler facades yet.

### 2.3 VK-8M Plugin + DrawBarWidget
- **Location**: `plugins/vk8m_plugin.py` with widget under `widgets/drawbar_widget.py`.
- **Widget**: Nine drawbars + speed dial. Animation methods (`start_animation`, `update_animation`) expect module to tick them via the loop.
- **Integration Notes**:
  - `attach_widget` registers a widget-owned dial via `register_widget_dial` so physical knob can control rotary speed.
  - Colors pulled from device theme; requires `bg`, `fill`, and `outline` keys.
  - Widget is tightly coupled to module; no shared config describing requirements yet.

### 2.4 Drumbo Sampler + Auto-Slicer
- **Locations**: `plugins/sampler/instruments/drumbo/module.py`, configs under `.../config.py`, UI sync service under `.../services/ui_service.py`.
- **Workflow**:
  1. Sampler plugin builds `InstrumentContext` (mixer, preset, event facades) and instantiates `DrumboInstrument`.
  2. Drumbo module configures dial banks from `DIAL_BANK_CONFIG`, registers button listeners, and mounts `LegacyUISyncService`.
  3. Button 3 toggles slicer mode: hides dial banks, sets custom widget override to `AutoSlicerWidget`, and binds controller callbacks for slice updates.
  4. Module ensures override cleared + dial banks restored when leaving slicer mode or switching modules.
- **Strengths**: Clear separation between instrument logic, UI sync, and widget. Demonstrates new override cleanup flow added to ModuleBase.

### 2.5 Auto-Slicer Pipeline
- **Location**: `plugins/sampler/core/slicer/` package (controller, models, widget, converter).
- **Highlights**:
  - `AutoSlicerController` orchestrates ffmpeg slicing, stores metadata (`status`, `error`, `slice_count`) alongside audio assets.
  - Widget exposes `set_slice_set(slice_set)` and emits `on_change(index, slice_summary)` when user selects slices.
  - Theme keys align with Drumbo theme; fallback colors provided for non-sampler modules.
- **Observations**: Currently consumed only by Drumbo. A widget registry could let other instruments request the same slicer spec.

---

## 3. Integration Mechanics

### 3.1 ModuleBase Lifecycle
1. `set_active_module(module_cls)` resets previous module state, clears widget overrides, resets dial banks, and logs the transition.
2. `_get_mod_instance()` lazily instantiates the module class (caching per module id). Modules must expose `MODULE_ID` to align with registry entries.
3. `init_page()` hydrates state (live → init → defaults), sets up dial banks, applies stored button states, and calls module `attach_widget(widget)` if one is present.
4. `draw_ui(surface)` builds dial widgets, handles overlay visibility, sets `dialhandlers` to point at the active dial list, then draws the custom widget.
5. `detach_widget()` / `clear_custom_widget_override()` run when widget is removed; ensure modules unregister widget-owned dials and stop animations inside these hooks.

**Lifecycle timeline**
- `set_active_module` → `_get_mod_instance` → `init_page` → module `on_init` → module `attach_widget` → optional `on_activate` → per-frame `draw_ui`/runtime hooks. `init_page` completes dial/widget hydration *before* `on_init` runs, so hook implementations should treat dial values and button states as already populated from `INIT_STATE` or live snapshots unless they need to override defaults deliberately.

### 3.2 Hook Dispatch Order
- Module hook priority during refresh: `on_init` → `attach_widget` → `on_activate` (if defined) → runtime event hooks (`on_dial_change`, `on_button`, `on_tick`).
- ModuleBase stores hook names in `_MODULE_HOOKS`; `module_base._dispatch_hook("on_button", ...)` handles missing methods gracefully.
- Always guard long operations inside hooks—ModuleBase runs on UI thread.
- Responsibilities by stage:
  - `init_page` (host) loads dial/bank/button state and queues widget override based on cached specs.
  - `on_init` (module) inspects hydrated state, clamps or seeds module-specific caches, and prepares any data needed before the first frame.
  - `attach_widget` (module) receives the live widget instance and is the correct place to wire callbacks or restore widget state.

### 3.3 Widget Override Flow
```python
module_base.set_custom_widget_override({
    "class": "AutoSlicerWidget",
    "path": "plugins.sampler.core.slicer.widget",
    "grid_size": [4, 2],
    "grid_pos": [0, 0],
})
```
- Spec fields: `class`, `path`, `grid_size`, `grid_pos`, optional `rect`, `include_overlays`.
- `_load_custom_widget()` calculates the target rect, imports the widget class, instantiates it with `(rect, on_change=None, theme=self.theme, init_state=widget_state)`.
- Module `attach_widget(widget)` receives the instance and should register callbacks (`widget.on_change = ...`) and widget-owned dials if needed.
- `clear_custom_widget_override()` removes the spec, deletes cached instance, and triggers layout rebuild; called automatically when module switches.

### 3.4 Button Flow & Multi-State Semantics
- Buttons defined in module config (`BUTTONS` list). Fields used by ModuleBase:
  - `id`: string identifier (`"1"`..`"10"`).
  - `behavior`: `transient`, `toggle`, `multi`, `state`, `nav`.
  - `states`: ordered list of dicts for `multi`/`state` behavior (each dict can include `label`, `icon`, `value`).
- Hardware event → `ModuleBase.handle_button_input` → `_dispatch_hook("on_button", btn_id, state_index, state_data)`.
- Persist state by updating `self.button_states` and calling `dialhandlers.update_button_state` (the latter keeps UI/hardware in sync).
- For sampler instruments, `LegacyUISyncService.push_button_states` coordinates button updates with hardware controllers.

  Example `multi` button for widget toggles:

  ```python
  BUTTONS = [
    {
      "id": "1",
      "behavior": "multi",
      "states": [
        {"label": "Widget A", "value": "widget_a"},
        {"label": "Widget B", "value": "widget_b"},
      ],
    }
  ]

  def on_button(self, btn_id, state_index, state_data):
    if btn_id == "1":
      next_widget_id = state_data["value"]  # matches _WIDGET_SPEC_MAP key
      self._switch_widget(next_widget_id)
  ```

  `state_data["value"]` is passed through untouched by ModuleBase, so choose identifiers that line up with `_WIDGET_SPEC_MAP` (or any handler-specific mapping) to avoid extra translation logic.

### 3.5 Dial Flow & State Persistence
- Control metadata (range, label, default, etc.) is loaded from `/build/config/custom_dials.json` via `custom_controls.py`. When you create new controls, always add them to that JSON file—not inside your plugin.
- `SLOT_TO_CTRL`: maps dial slot (row, col) to control id defined in `custom_controls.CONTROLS`.
- `REGISTRY`: metadata describing each control (range, default, label, optional `sm_param_id`). Used for automation and preset storage.
- State resolution order during `init_page()`:
  1. `dialhandlers.live_states[module_id]` (captured runtime state).
  2. Module `INIT_STATE`.
  3. Defaults derived from `REGISTRY` (min/mid values).
- `init_page()` hydrates dial values before module `on_init` runs. Most modules should *not* call `dialhandlers.set_dial_value` in `on_init` unless they need to override hydration (for example, to clamp out-of-range user data). When touching dials manually, use `dialhandlers.set_dial_value(ctrl_id, value)` (legacy signature) or `dialhandlers.set_dial_value(module_id, ctrl_id, value)` (module-aware signature) so hardware and UI stay in sync.
- Dial values are stored as normalized floats in the range `[0.0, 1.0]`. Legacy CC-style integers (0–127) are accepted; ModuleBase normalizes them, but prefer writing floats to avoid double conversions. When ingesting user data, coerce to float and guard against non-numeric types before passing to dialhandlers.
- Widget-owned dials: create via `assets.dial.Dial`. Register with `register_widget_dial(slot, dial_obj, visual_mode="hidden")` and remember to unregister in `detach_widget`.
- `capture_active_dial_bank_values()` and `get_dial_bank_values()` let modules snapshot values when switching overlays (Drumbo uses this before entering slicer mode).

Example safe `on_init` implementation:

```python
def on_init(self):
  # Dials are already hydrated by init_page; validate before using.
  for ctrl_id, value in self._main_dials.items():
    if isinstance(value, str):
      showlog.warn("spectra_switch", f"Skipping string value for {ctrl_id}: {value}")
      continue
    dialhandlers.set_dial_value(ctrl_id, float(value))
  self._load_active_widget_state()
```

Minimal `INIT_STATE` pattern:

```python
INIT_STATE = {
  "dials": {"spectra_main": 0.75},
  "button_states": {"1": 0},
  "widget": {"active_id": "widget_a", "snapshots": {"widget_a": {"progress": 0.5}}},
}
```

`dials` should map control ids to normalized floats (or convertible ints), `button_states` maps button id strings to active state indices, and the optional `widget` section stores JSON-serializable state blobs used by custom widgets.
> **Caution**: Never store control id strings (e.g., `"spectra_main_1"`) as the dial *values*. `module_base.init_page` feeds each entry into `Dial.set_value`, which attempts `int(val)`. If the value is a string, you’ll hit `ValueError: invalid literal for int() with base 10`. Always persist numeric dial values.

### 3.6 DialBankManager Quick Reference
- Configure with `module_base.configure_dial_banks(bank_config, default_bank)` where `bank_config` is a dict like Drumbo's `DIAL_BANK_CONFIG` (bank key → list of slot descriptors).
- `set_active_dial_bank(bank_key)` swaps the visible overlay and reapplies stored state.
- `set_show_all_banks(bool)` toggles multi-bank view; Drumbo hides banks while slicer widget is active.
- Bank values persist across module switches via `self._instrument_bank_values` (Drumbo) or `dialhandlers.live_states` (legacy modules).

### 3.7 Custom Widget State Handling
- Modules should store widget state in `self.widget_state` (or similar) and feed it into override spec as `init_state`.
- Widgets must implement `get_state()` / `set_state(state)` so preset saves capture user adjustments.
- ModuleBase will call `widget.get_state()` during `_capture_widget_state()` (triggered on preset save and module switch).
- Attach/detach responsibilities:
  - `set_custom_widget_override` mounts the widget and leaves dial banks as-is; any visibility changes (hiding overlays, muting hardware dials) remain the module's job both on attach *and* detach.
  - `detach_widget()` clears the widget instance but does **not** restore bank visibility automatically. Always undo overrides inside your module's `detach_widget` or `_switch_widget` helper.
  - Always call `request_custom_widget_redraw(include_overlays=True)` after mutating widget state so the buffer refreshes in the next frame.
- Widget state persistence timeline: ModuleBase captures state before preset saves, before module switches, and before widget overrides change. Keep `_widget_state_cache` JSON-serializable, and repopulate the active widget inside `on_init` / `attach_widget` using the latest snapshot.
- Defensive hydration tip: Treat any widget state you pull from `dialhandlers.live_states` or `_widget_state_cache` as untrusted—coerce floats back into the expected range and guard `.get()` chains so first-run modules or corrupt saves don't explode.

### 3.8 dialhandlers Interactions
- Core helpers exposed to plugins:

  | Helper | Signature | Purpose | Notes |
  | --- | --- | --- | --- |
  | `set_dials(dial_list)` | `dialhandlers.set_dials(List[DialWidget]) -> None` | Register the current overlay dial widgets so hardware events route correctly. | Called by ModuleBase; you rarely call it directly. |
  | `set_dial_value` | `dialhandlers.set_dial_value(ctrl_id, value)`<br/>`dialhandlers.set_dial_value(module_id, ctrl_id, value)` | Push a normalized value into the active dial (and optionally persist it under a module id). | Returns `None`. Accepts floats (0–1) or ints (0–127); guard against other types before calling. |
  | `get_dial_value` | `dialhandlers.get_dial_value(module_id, ctrl_id) -> float` | Fetch the last stored value for a dial. | Use when preparing preset saves. |
  | `update_button_state` | `dialhandlers.update_button_state(page_id, var_name, value) -> None` | Persist multi-state button indices so they restore on revisit. | Usually called from `on_button` handlers after mutating `self.button_states`. |
  | `get_button_states` | `dialhandlers.get_button_states(page_id) -> Dict[str, int]` | Read back stored button state map. | Safe for all modules. |

- `dialhandlers.live_states` is a nested dict keyed by `module_id` → `state_name` (usually `"main"`) → payload containing `dials`, `button_states`, etc. Modules may store additional slices (e.g., Drumbo uses `"slicer"`). Always guard lookups with `.get()` to avoid `KeyError` when a module activates for the first time.
- Legacy `register_transient_button` is no longer used; rely on `BUTTONS` configuration for persistent controls.

### 3.9 Preset Save/Load Workflow
- `ModuleBase.save_current_preset` → module `prepare_preset_save(data)` (overridable) to add extra payload (Drumbo attaches slicer metadata & bank state).
- `ModuleBase.load_preset(data)` → module `on_preset_loaded(data)` followed by `_sync_module_state_to_dials()` and widget `set_state()` if present.
- Preset files (handled by `preset_manager`) expect serializable dict; avoid storing raw widget objects.

### 3.10 Event Bus & Services
- `core/event_bus.py` dispatches cross-plugin events. Sampler instruments use it via `InstrumentContext.event_facade`.
- `LegacyUISyncService` (Drumbo) bridges ModuleBase with sampler facades: registers dials, pushes button states, syncs overlays.
- When building new sampler instruments, prefer services (UI sync, recorder sync, mixer sync) over embedding logic directly into ModuleBase.

### 3.11 Logging & Diagnostics
- `showlog` module provides `log_info`, `log_error`, `log_exception` tagged by module ID. Use for lifecycle logs.
- Auto-slicer writes metadata under `processed/<recording>/metadata.json`; errors appear in `status` + `error_details`.
- `ui_log.txt` captures runtime events; helpful when debugging override issues or dial mismatches.

### 3.11A Standard Logger Usage (Revision 2025-11 Update)
- Always import `showlog` as a module (`import showlog`) instead of pulling individual helpers.
- Severity guide:

  | Function | Visibility | Use When… | Extras |
  | --- | --- | --- | --- |
  | `showlog.debug("*message {var}")` | Log file only unless the string starts with `*`, in which case it appears in Loupemode overlay. | Temporary, high-volume tracing while authoring or diagnosing issues. | Remove or downgrade before shipping stable builds. |
  | `showlog.info("plugin_id", "status")` | ✅ UI overlay + log. | Lifecycle milestones, page switches, user-visible status. | Keep concise; avoid spamming the overlay. |
  | `showlog.warn("plugin_id", "warning")` | Log only (unless UI chooses to surface it). | Recoverable anomalies, missing optional config, retries. | Include recovery action in the message when possible. |
  | `showlog.error("plugin_id", "failure")` | Log + UI error indicator. | Fatal paths where the module cannot proceed. | Pair with graceful fallback/teardown logic. |
  | `showlog.exception("plugin_id", exc)` | Log + stack trace. | Inside exception handlers when re-raising or returning an error. | Automatically appends traceback and exception class.

- Tag every message with the plugin/service identifier (e.g., `"drumbo"`, `"spectra_switch"`) and avoid raising new exceptions within log statements. Ensure fatal paths log via `error`/`exception` before raising or returning, and strip noisy `debug` lines once the feature stabilises.

### 3.12 Device Select Pipeline
- Layout comes from `config/device_page_layout.json`. Each button entry supports `id`, `img`, `label`, and optional `plugin` routing.
- `pages/device_select.py` loads the JSON, caches button metadata, and records `_rect` hit-boxes. Images must live under `assets/images/`.
- On click, `handle_click` inspects `plugin`. If set, it posts `("ui_mode", plugin_page_id)` to the app queue; otherwise it treats the entry as a hardware device and emits `("device_selected", DEVICE_NAME)`.
- Plugin pages still register with `app.page_registry` in `Plugin.on_load`. Ensure the `page_id` matches the value stored in the JSON `plugin` field so navigator history and device select stay aligned.
- **Register the correct module**: the object you pass to `app.page_registry.register` must be `pages.module_base` (the host that implements `draw_ui`). Do not pass your `ModuleBase` subclass directly—doing so yields a blank page because the registry never gets a renderer.
- **Teach ModeManager about the page**:
  - File: `managers/mode_manager.py`. Insert `elif new_mode == "your_page_id": self._setup_your_page()` in the `switch_mode` chain.
  - Implement `_setup_your_page(self)` right below it. Pattern:
    ```python
    def _setup_your_page(self):
        self.header_text = "Your Plugin Name"
        from pages import module_base as page
        from plugins.your_plugin import YourModule
        page.set_active_module(YourModule)
        if hasattr(page, "init_page"):
            page.init_page()
    ```
  - This is what consumes the `ui_mode` message, sets the header, and hands control to `ModuleBase`. Without the branch nothing happens when the device-select button is tapped.

- **Widget overlays must manage dials explicitly**:
  - To hide the hardware dial grid while a widget is active, call `module_base.set_show_all_banks(False)` and optionally `module_base.set_active_dial_bank(None)`/`module_base.set_bank_visible(bank, False)` depending on layout needs. There is no `_set_dial_banks_visible` helper in the host; Drumbo’s method is private to that module.
  - Always pair your cleanup by restoring visibility (`set_show_all_banks(True)` or resetting any banks you disabled) when the widget detaches.

- **Widget mini-dials must target real slots**:
  - `register_widget_dial(slot, dial_obj, visual_mode="hidden")` expects a 1-based slot index (1–8). Passing `None` or out-of-range values logs an error and skips the registration.
  - Pick unused slots in the grid (e.g., 7 and 8) and store which slot each widget dial occupies so `unregister_widget_dial(slot)` can restore the original hardware dial later.

**Implementation Notes (Revision 2025-11 Update)**
- `id` values in `config/device_page_layout.json` must be numeric integers, not quoted strings. Example: `{ "id": 42, "img": "example.png", "label": "Example Plugin", "plugin": "example_plugin" }`.
- Keep the file valid JSON with a top-level object containing a `buttons` array (or equivalent). Double-check brackets and commas after edits.
- Match each entry’s `plugin` value exactly to the plugin `page_id` passed to `app.page_registry.register` inside `Plugin.on_load(app)`.
- `img` paths are relative to `/build/assets/images/` and should point to ~64×64 px `.png` assets.
- `label` is cosmetic only; `plugin` controls navigation, and the numeric `id` drives layout ordering and hit-testing.

---

## 4. Widget Contracts & Theme Keys

### 4.1 Common Interface Expectations
- Constructors follow `(rect, on_change=None, theme=None, init_state=None)`; pass `theme` dict even if widget has defaults.
- Implement dirty tracking: `mark_dirty()`, `is_dirty()`, `clear_dirty()` (inherit `DirtyWidgetMixin` where available).
- Provide `handle_event(event)` if widget processes input directly; ModuleBase funnels Pygame events into the widget each frame.
- For animated widgets (drawbars, slicer meters), expose `update_animation(dt)` or `tick(dt)` so ModuleBase can call during the main loop.

### 4.2 Theme Key Reference
| Widget | Required Theme Keys | Optional Enhancements |
| --- | --- | --- |
| Drumbo main widget | `plugin_background_color`, `dial_panel_color`, `dial_text_color`, `button_active_fill` | `drumbo_label_text_color`, `mini_dial_outline`, `mini_dial_fill` |
| AutoSlicerWidget | `plugin_background_color`, `outline`, `dial_panel_color`, `dial_text_color`, `preset_text_color` | `slicer_empty_cell`, `slicer_meter_color`, `slicer_meter_bg`, `slicer_waveform_color` |
| DrawBarWidget | `bg`, `fill`, `outline`, plus device theme `button_fill`, `button_outline`, `dial_text_color` | `drawbar_label_color`, `drawbar_inactive_fill` |
| ASCIIAnimatorWidget | `dial_panel_color`, `dial_text_color`, `preset_button_color` (falls back to theme defaults if missing) | `ascii_pad_active`, `ascii_pad_inactive`, `ascii_grid_lines` |
| VibratoField (ADSR) | `bg`, `fill`, `outline`, relies on global `BACKGROUND_COLOR` for canvas | `adsr_line_color`, `adsr_point_color` |

> When adding a widget, update this table and provide sensible defaults to avoid invisible UIs when keys are missing.

### 4.3 Behaviour Contracts
- **AutoSlicerWidget**: Emits `on_change(slice_index, slice_summary)`. Calls `controller.on_slice_selected` when bound by module. Expects `SliceSet` model containing `slices`, `status`, `error`.
- **DrawBarWidget**: Maintains internal animation state; call `load_animation(data)` before `start_animation()`. Registers speed dial (#2) via `register_widget_dial`.
- **ASCIIAnimatorWidget**: `get_state()` returns frame grid + transport state. `handle_button(btn_id, state)` manages play/pause/RTZ; module should route button events there.
- **VibratoField**: Normalizes drawn points to `[0, 1]`; `on_change` callback receives smoothed curve values and fade time in ms.

### 4.4 Widget Testing Tips
- Render widget standalone by instantiating with a dummy rect and calling `widget.draw(surface)`; use `pygame.display.set_mode` in a throwaway script.
- For slicer, run `python -m unittest plugins.sampler.core.tests.test_slicer_detector` to verify controller and widget integration.
- Add debug colors (temporary) by overriding theme dict while testing new widgets.

---

## 5. Plugin & Widget Build Recipes

### 5.1 Create a Legacy-Style Plugin (ModuleBase Only)
1. **Define Plugin class** in `plugins/<name>_plugin.py` inheriting `Plugin`. Populate metadata (`name`, `version`, `page_id`).
2. **Export `Plugin` alias** at the end of the file: set `Plugin = <YourPluginClass>` so the auto-discovery loader finds it. Without this line the manager skips your module entirely.
3. **Register page** in `on_load(app)` by calling `app.page_registry.register(page_id, pages.module_base, label=..., meta=...)`. Never register your `ModuleBase` subclass directly—`module_base` provides the renderer.
4. **Expose it on device select**: add an entry to `config/device_page_layout.json` with `"plugin": "<page_id>"` and drop an icon into `assets/images`. Device select will route clicks to your `ui_mode`.
5. **Update `ModeManager.switch_mode`**: add the `elif new_mode == "<page_id>"` branch plus a `_setup_<page_id>()` helper exactly as outlined in Section 3.12 so the queued `ui_mode` is handled.
6. **Describe controls**: set `SLOT_TO_CTRL`, `REGISTRY`, `BUTTONS`, `INIT_STATE`, `CUSTOM_WIDGET` (and any alternate widget specs) on the ModuleBase subclass. For dual-widget demos, include an `_WIDGET_SPEC_MAP` keyed by widget id so you can hot-swap overrides without rebuilding the spec each time.
7. **Implement hooks**: `on_init`, `on_dial_change`, `on_button`, `attach_widget`, `on_preset_loaded`. Use helper functions *from `pages.module_base`* (`set_custom_widget_override`, `clear_custom_widget_override`, `request_custom_widget_redraw`, `set_show_all_banks`, `set_bank_visible`, `register_widget_dial`). These are module-level functions—never call them as `self.*` inside your module.
  - When building `INIT_STATE`, ensure every dial entry is a numeric value (float 0–1 or int 0–127). Storing the control id string in place of the value will crash hydration with `ValueError: invalid literal for int()` the moment ModuleBase calls `Dial.set_value`.
8. **Theme**: provide `THEME` dict or rely on device theme. Document additional keys in Section 4.
9. **Validation**: manually switch into the page, exercise buttons/dials, trigger each widget override, and ensure `ui_log.txt` shows no errors. Confirm renderer dispatch (see Section 3.13) by checking that `draw_ui` runs for your page id.

### 5.1.1 Dual Widget Demo Checklist (Updated Nov 2025)

Use this when reproducing the dual-widget reference module or onboarding a new agent. The goal is a zero-debugging walkthrough.

1. **Renderer Dispatch** – ensure `rendering/renderer.py` includes the signature-aware fallback that calls `draw_ui` for pages outside the hard-coded list. Without it the dual widget page draws a blank frame.
2. **Module Wiring** – configure the module with:
  - `SLOT_TO_CTRL = {1: "main_dial_1", 2: "main_dial_2"}`
  - `_WIDGET_SPEC_MAP` providing specs for `widget_a` (default) and `widget_b` (alt) with identical `grid_size`/`grid_pos`.
  - `REGISTRY` entries for the two main dials (`Main 1`, `Main 2`) plus `INIT_STATE` containing dial/button/widget snapshots.
3. **State Lifecycle** – in `__init__`, hydrate `_main_dials`, `_widget_state_cache`, `_active_widget_id`, and `button_states` from `INIT_STATE`. Keep `_handle_widget_change` updating both the cache and active dial list.
4. **Hooks** – `on_init` must sync the main dials to `dialhandlers` *before* loading the active widget so the redraw happens with seeded values. `on_button` toggles widget id by reading `state_data['value']`.
5. **Widget Attach/Detach** – grid widgets just need `apply_theme`, `set_state`, and `on_change` wiring; no widget-owned dials in this demo. Always call `request_custom_widget_redraw(include_overlays=True)` after attaching to flush the new pixel buffer.
6. **Widgets** – both `WidgetA` and `WidgetB` implement:
  - Constructor accepting `(rect, on_change=None, theme=None, init_state=None)`.
  - Dirty tracking (`mark_dirty`, `is_dirty`, `clear_dirty`).
  - `set_state`, `get_state`, `update_value`, `handle_event` (no-op). Draw routine renders progress bars using theme keys: `plugin_background_color`, `mini_dial_fill`, `mini_dial_outline`, `dial_text_color`.
7. **Custom Dial Metadata** – open `/build/config/custom_dials.json` and insert entries for every new dial you introduce (for example, a control id like `my_new_dial`). The custom_controls system reads from this JSON file, not from Python code.
8. **ModuleBase Hook** – call the module’s `on_init()` from `init_page()` (already in host) or confirm it exists after refactors. Without it the widget never loads because `_load_widget` stays idle.
9. **Regression Tests** – run `py_compile` on `rendering/renderer.py`, `pages/module_base.py`, plugin, and widgets. Launch UI → select “Dual Widget Demo” → verify Widget A renders, button 1 toggles Widget B, dial changes echo on widget and in `ui_log.txt` (no errors).

### 5.2 Create a Sampler Instrument Module
1. **Config module**: replicate Drumbo’s `config.py` structure with `INIT_STATE`, `BUTTONS`, `DIAL_BANK_CONFIG`, `CUSTOM_WIDGET`, and theme overrides.
2. **Instrument class**: subclass `InstrumentModule` (provides sampler hooks) and `ModuleBase`. Receive `InstrumentContext` (mixer, preset, event, recorder) from sampler plugin.
3. **Expose in UI**: extend `config/device_page_layout.json` with a `plugin` entry (commonly `"drumbo_main"` style) to surface the instrument on device select. Update `ModeManager.switch_mode` to call your new `_setup_<module>()` handler.
4. **Services**: instantiate helper services (`LegacyUISyncService`, audio sync, etc.) inside `on_init` to keep ModuleBase lean.
5. **Widget toggles**: manage overrides via ModuleBase helpers (`set_custom_widget_override`, `clear_custom_widget_override`, `set_show_all_banks`, `set_bank_visible`) imported from `pages.module_base`—call them as functions, not `self.*` methods.
6. **Persistence**: override `prepare_preset_save` / `on_preset_loaded` to capture widget + dial bank state.
7. **Tests**: run `python -m unittest plugins.sampler.core.tests.test_slicer_detector` and `python verify_sampler_phase2.py` after changes.

### 5.3 Author a Reusable Widget
1. **Module**: place under `widgets/<name>_widget.py` with a top-level class export.
2. **Constructor**: accept `(rect, on_change=None, theme=None, init_state=None)` and apply defaults.
3. **State & Dirty**: implement `get_state`, `set_state`, `mark_dirty`, `is_dirty`, `clear_dirty`.
4. **Dial integration**: if widget controls dials, create `Dial` objects and expose `get_widget_dials()` or ask module to register them.
5. **Theme contract**: document required keys in Section 4.2 and provide fallback colors.
6. **Docs**: add entry to this bible, update any quick-start README inside `widgets/`.

### 5.4 Convert a Legacy Plugin to the New Pattern
1. Extract control metadata into `config.py` (buttons, dials, theme).
2. Relocate widget code into `widgets/<name>_widget.py` with proper state methods.
3. Replace direct singleton usage with facades or dependency injection (prefer sampler-style `InstrumentContext`).
4. Adopt `register_widget_dial` and bank helpers to manage overlays cleanly.
5. Ensure presets cover new widget state; update `INIT_STATE` accordingly.
6. Smoke-test UI switch-over and run applicable unit scripts.

---

## 6. Toward a Modular Future

| Requirement | Current State | Gap / Action |
| --- | --- | --- |
| **Widget Registry** | Modules hand-craft override specs | Create `widgets/registry.py` catalog (id → import path, theme keys, capabilities) so overrides become declarative. |
| **Plugin Descriptor** | Legacy plugins embed metadata in code | Mirror sampler descriptor: config-driven definitions for dials, buttons, widgets, services. |
| **Dial/Widget Separation** | Layout logic scattered inside modules | Move dial grid definitions to config, treat widgets as independent components with contracts. |
| **Theme Validation** | Widgets assume theme keys or fallback poorly | Introduce validator that warns when required keys missing; provide default palette. |
| **Lifecycle Hooks** | Attach/detach not standardized | Add `on_widget_attached` / `on_widget_detached` base hooks and enforce dial deregistration. |
| **Error Surfacing** | Controllers log errors but UI hides them | Provide shared status widget or message overlay for controllers (slicer, network, etc.). |
| **Facade Adoption** | Only sampler instruments use contexts | Port vibrato/VK-8M/ASCII to context-driven pattern, retiring singletons. |
| **Preset Schema** | Widgets store arbitrary dicts | Document preset schema per module and validate on load. |
| **Developer Tooling** | Docs exist but scattered | Maintain this bible + checklists, integrate into CI to ensure updates accompany code changes. |

---

## 7. Proposed Roadmap

### 7.1 Short Term
- Harden ModuleBase cleanup (override + widget-owned dial deregistration) — ✅ implemented.
- Document widget contracts (Section 4) — ✅ implemented.
- Expose slicer error status in widget (UI work pending).

### 7.2 Medium Term
- Implement widget registry + validation.
- Convert at least one legacy plugin (VK-8M) to config-driven structure.
- Provide command-line tooling to scaffold new plugin from templates.
- Extract shared services (preset, mixer, event) into `core/services` for reuse.

### 7.3 Long Term
- Support multi-widget layouts with z-order (host multiple widgets simultaneously).
- Enable hot-swappable widgets per slot (user chooses widget from registry).
- Add plugin sandboxing (declare dependencies, ensure compatibility before load).

---

## 8. Weak Points & Fixes Summary

1. **Manual Integration**: Widgets & dials wired manually per plugin.
   - *Fix*: Config descriptors + widget registry + standardized contracts.
2. **Global Override State**: Single override spec; no nesting.
   - *Fix*: Per-module override context or stack (design pending).
3. **Legacy Singletons**: Plugins import globals (preset manager, dialhandlers).
   - *Fix*: Adopt sampler-style facades and dependency injection.
4. **Theme Fragility**: Missing keys lead to invisible widgets.
   - *Fix*: Theme validator + documented defaults (Section 4).
5. **Preset Drift**: Widgets may not persist full state.
   - *Fix*: Enforce `get_state/set_state`, document expected schema.
6. **Error Visibility**: Controller failures hidden from UI.
   - *Fix*: Shared status overlay or widget-level notifications.

---

## 9. Recommended Practices (Current System)

- Always pair `set_custom_widget_override` with logic to restore dial banks and unregister widget-owned dials.
- Keep module hook bodies fast; offload heavy work to background threads or services.
- Capture widget state during `prepare_preset_save` and restore it in `on_preset_loaded`.
- Run regression scripts (`python -m unittest plugins.sampler.core.tests.test_slicer_detector`, `python verify_sampler_phase2.py`) after modifying sampler stack.
- Log lifecycle events via `showlog` for easier debugging (`log_info("drumbo", "Entering slicer mode")`).
- Sanity-check external inputs (preset payloads, live state) before writing to `dialhandlers` and skip or clamp unexpected types; log a warning rather than allowing crashes.
- Update this documentation whenever contracts/interfaces change.

---

## 10. Resource Index

| Component | File(s) |
| --- | --- |
| Plugin manager | `core/plugin.py` |
| Module host | `pages/module_base.py` |
| Device select page | `pages/device_select.py`, `handlers/device_select_handler.py` |
| Device select layout | `config/device_page_layout.json`, `config/layout.py` |
| Custom controls metadata | `custom_controls.py` |
| Dial handlers | `dialhandlers.py` |
| Vibrato plugin | `plugins/vibrato_plugin.py` |
| ASCII animator plugin/widget | `plugins/ascii_animator_plugin.py`, `widgets/ascii_animator_widget.py` |
| VK-8M plugin + drawbar widget | `plugins/vk8m_plugin.py`, `widgets/drawbar_widget.py` |
| Drumbo instrument | `plugins/sampler/instruments/drumbo/module.py`, `config.py`, `services/ui_service.py` |
| Auto-slicer pipeline | `plugins/sampler/core/slicer/` |
| Shared dials | `assets/dial.py` |
| Control surfaces | `control/dials_control.py`, `control/global_control.py` |
| Documentation | `docs/drumbo/sampler_backend_manual_v3.md`, `docs/drumbo/sampler_architecture_manual_v2.md` |

---

## 11. Next Actions Checklist

1. **Document widget specs** (drawbar, ASCII) including required theme keys. ✅ Section 4.2 updated.
2. **Prototype widget registry** allowing modules to request widgets by ID. → *Pending*
3. **Refactor one legacy plugin** (e.g., VK-8M) to adopt sampler-style config + override toggles as a proof of concept. → *Pending*
4. **Expose error status** in slicer widget UI. → *Pending*
5. **Create developer checklist** for new plugins/widgets referencing this bible. ✅ Section 5.

---

*Maintainers: update this bible whenever plugin/widget infrastructure evolves. The goal is a zero-guesswork experience when authoring the next instrument or utility.*
# Plugins & Widgets Universe – The Bible

> Comprehensive field guide to the current PiUI plugin/widget architecture (November 8 2025). Covers legacy plugins (Vibrato, VK-8M drawbar), modern sampler stack (Drumbo, Auto-Slicer, ASCII Animator), integration requirements, and gaps preventing a fully modular future. Use this to bootstrap new plugins, refactor existing ones, and understand the path to a universal widget ecosystem.

---

## 1. Architectural Lens

### 1.1 Terminology
- **Plugin**: Entry point registered with `core/plugin.py` that exposes a `ModuleBase`-derived UI page. Historically, each plugin hardwired UI + behavior for a specific device.
- **Widget**: Pygame-based component instantiated inside the plugin page (e.g., drawbar grid, slicer grid, ASCII animator pads). Widgets can be swapped at runtime using `module_base.set_custom_widget_override`.
- **ModuleBase**: Legacy page controller responsible for dials, buttons, and widget life-cycle. Each active plugin shares a single `ModuleBase` instance.
- **Sampler Instrument Module**: Newer construct (`InstrumentModule` interface) living under `plugins/sampler/instruments/<instrument>/module.py`, combined with the sampler shell (facades, context injection).

### 1.2 Integration Path
1. **Plugin discovery**: `core/plugin.PluginManager.discover()` scans `plugins/` for modules exposing `Plugin` subclasses. Sampler shell registers as `plugins.sampler.plugin:Plugin`. Older ones (Vibrato, VK-8M) run directly.
2. **Module activation**: `module_base.set_active_module()` resets state, instantiates the plugin module, loads widget/dials, and wires hardware interactions.
3. **Widget overrides**: Plugins request custom widgets (and dial overlays) through `module_base` helper functions; overrides persist until the module is switched or explicitly cleared.
4. **Facades** (Sampler only): Sampler plugin injects mixer/preset/event facades into instruments so they no longer depend on singletons.

---

## 2. Case Studies

### 2.1 Vibrato Plugin
- **Location**: `plugins/vibrato_plugin.py` (legacy).
- **Module**: `Vibrato(ModuleBase)` instantiates custom widget (vibrato envelope) and uses standard dial overlays.
- **Widget**: Defined inside the plugin file; uses manual dial hooking and event handling.
- **Integration**: Direct imports of `pygame`, `pages.module_base`, `helper`, etc. Hard-coded path to widget; no overlay switching.
- **Weaknesses**:
  - Fully legacy; no facade injection or modular widget override support.
  - Dial banks and widget logic tightly coupled to plugin class.
  - No auto-reset when switched—relies on `set_active_module` cleanup.

### 2.2 ASCII Animator Plugin/Widget
- **Location**: `plugins/ascii_animator_plugin.py`, widget under `widgets/ascii_animator_widget.py` (path approximate; real file check if needed).
- **Behavior**: Renders an 8-pad grid controlling ASCII animation playback; buttons on left/right map to transport controls.
- **Integration**: Uses `ModuleBase` patterns with custom widget placements; nav buttons triggered via plugin event handlers.
- **Strengths**:
  - Clean separation between widget drawing and plugin logic.
  - Registers nav buttons via `BUTTONS` config (if using new config pattern).
- **Weaknesses**:
  - Still a legacy plugin; does not leverage new sampler context/facades.
  - Widget override is static; no shared spec or theme integration of the sampler style.

### 2.3 VK-8M Plugin + Drawbar Widget
- **Location**: `plugins/vk8m_plugin.py`, drawbar widget under `widgets/drawbar_widget.py` (approximate).
- **Widget**: Multi-row drawbar representation; expects 9 bars, custom color scheme (orange-black) as seen in screenshot.
- **Integration**:
  - Plugin loads widget via `attach_widget` override; dials map to widget controls when overlay present.
  - `ModuleBase` handles dial overlay positions.
- **Weaknesses**:
  - Widget is strongly coupled to plugin: assumes specific dial ids + behavior.
  - No configuration describing the widget in a reusable form (hard-coded path/class instantiation).
  - Lacks runtime override toggles (widget is fixed).

### 2.4 Drumbo Sampler & Auto-Slicer
- **Locations**:
  - Drumbo Instrument: `plugins/sampler/instruments/drumbo/module.py`.
  - Slicer widget: `plugins/sampler/core/slicer/widget.py`.
  - Sampler plugin shell: `plugins/sampler/plugin.py`.
- **Integration Steps**:
  1. Sampler shell builds `InstrumentContext` (mixer, presets, events) and injects into `DrumboInstrument`.
  2. Drumbo module instantiates auto-slicer controller and registers button handlers.
  3. Widget override toggled via `module_base.set_custom_widget_override` when button 3 pressed; dial banks hidden via new `_set_dial_banks_visible` helper.
  4. `module_base.set_active_module` now clears override state on module switch, preventing widget bleed.
- **Strengths**:
  - Aligns with modular vision: instrument-specific module + reusable slicer widget spec.
  - Facade pattern isolates dependencies.
  - Buttons/dial layout described via config file (`plugins/sampler/instruments/drumbo/config.py`).
- **Weaknesses**:
  - Still requires manual code to hide dials and manage button states.
  - Widget override state global; no per-module stack (just cleared on switch).

### 2.5 Sampler Auto-Slicer Controller/Widget
- **Scope**: `plugins/sampler/core/slicer/` package (converter, controller, models, widget).
- **Highlights**:
  - Conversion errors produce metadata (`status: "error"`), stored under `processed/<rec>/metadata.json`.
  - `AutoSlicerWidget` expects theme dict with keys matching `Drumbo` theme; otherwise uses defaults.
  - Controller supports listeners so other modules can react to new slice sets.
- **Weaknesses**:
  - Widget currently used only by Drumbo; no registry for other instruments to adopt it automatically.
  - Assumes field recorder root layout; future modules would need config-driven path injection.

---

## 3. Integration Mechanics

### 3.1 ModuleBase Lifecycle
1. `set_active_module(module_ref)` resets previous widget/dial state, clears overrides (new addition), and records active module ID for logging.
2. `_get_mod_instance()` instantiates the module class if not already cached (prefers module-level `ModuleBase` subclass with matching `MODULE_ID`).
3. `init_page()` runs when module page becomes visible; it loads dial values, attaches widget by calling module `attach_widget` hook, and configures dial banks.
4. Widget overrides rely on `_CUSTOM_WIDGET_OVERRIDE_SPEC` + `_CUSTOM_WIDGET_INSTANCE`. The spec describes `class`, `path`, `grid_size`, and `grid_pos`.

### 3.2 Widget Override Flow
```python
module_base.set_custom_widget_override({
    "class": "AutoSlicerWidget",
    "path": "plugins.sampler.core.slicer.widget",
    "grid_size": [4, 2],
    "grid_pos": [0, 0],
})
```
- Creates override spec clone.
- `_load_custom_widget()` resolves grid rect, imports class, instantiates widget with theme/`init_state`.
- Module’s `attach_widget` receives widget instance to wire callbacks.
- Clearing override resets spec & widget; now automatic when module switches.

### 3.3 Dial Banks
- `LegacyUISyncService` ensures mic dial overlays exist for Drumbo; other plugins handle overlays manually.
- Dial manager supports `set_show_all_banks(True/False)` to toggle visibility (used by Drumbo slicer).
- Modules must restore defaults when widget hidden; new `_set_dial_banks_visible` convenience ensures consistent behavior.

---

## 4. Toward a Modular Future

| Requirement | Current State | Gap / Action |
| --- | --- | --- |
| **Widget Registry** | No central registry; modules hard-code widget specs | Create catalog describing widget class/path, required theme keys, capabilities; allow plugins to declare widget dependencies declaratively. |
| **Plugin Descriptor** | Legacy plugins register manually via `Plugin` classes with bespoke logic | Define metadata schema (id, default widget, dial config, button map, capabilities) similar to sampler instruments. |
| **Dial/Widget Separation** | Dials embedded in plugin layout logic | Promote dial layout description (grid, ctrl_ids, ranges) to config files per plugin/instrument. |
| **Theme Compatibility** | Widgets rely on module theme keys; not validated | Provide theme contract (list of required keys), apply defaults when missing. |
| **Lifecycle Hooks** | Modules rely on `attach_widget`, `detach_widget` but no standard for override cleanup | Add standardized hooks (`on_widget_attached`, `on_widget_detached`); enforce automatic cleanup when overrides cleared. |
| **Error Surfacing** | Slicer errors stored; no UI integration | Provide shared status widget or overlay; expose `get_status()` per module. |
| **Facades Accessibility** | Only sampler modules use InstrumentContext | Refactor other plugins to adopt facade/context approach for audio, presets, events. |
| **Widget Persistence** | Override spec global; only cleared on module switch | Implement scoped override stack or per-module spec so nested plugins/widgets can coexist (e.g., host plugin embedding child widget). |
| **Developer Onboarding** | Manuals exist (sampler v2/v3, backend manual v3) | Consolidate into step-by-step guide for: create plugin, define widget spec, register buttons/dials, integrate with ModuleBase. |

---

## 5. Proposed Roadmap

### 5.1 Short Term
- **Widget Reset Guard** ✅ Already added: clearing overrides when switching modules.
- **Documentation** ✅ `Sampler Backend Manual v3` and this bible provide baseline guidance.
- **Theme Contract**: Document required keys for `AutoSlicerWidget`, `DrawbarWidget`, ASCII Animator (pending file audit). Provide fallback colors to avoid blank widgets.

### 5.2 Medium Term
- **Widget Registry Module**: Create `widgets/registry.py` mapping widget IDs → spec/class/theme requirements. Plugins request by ID; registry handles import.
- **Plugin Descriptor Refactor**: Mirror sampler instrument descriptor for legacy plugins. Provide `plugins/<name>/config.py` describing buttons, dials, default widgets.
- **Context & Facades**: Extract audio/preset/event facades from sampler core into shared module so vibrato/VK-8M/ASCII can adopt them and drop legacy singletons.
- **Widget State Persistence**: Standardize on `INIT_STATE['widget']` + `widget.get_state()/set_state()` to ensure toggleable widgets restore state across plugin switches.

### 5.3 Long Term
- **Cross-Plugin Widget Reuse**: Example goal – VK-8M and future Rhodes module share drawbar widget. Steps: register drawbar widget spec, allow modules to compose `module_spec['widgets']`, provide `WidgetHost` component to embed multiple widgets into one module view.
- **Hot-Swappable Widgets**: Implement UI overlay to choose widget per slot. ModuleBase should support multiple override layers with z-order.
- **Plugin Sandboxing**: Provide API for plugin to declare dependencies (widgets, services) so host can pre-load resources and validate compatibility.

---

## 6. Weak Points & Fixes Summary

1. **Manual Integration**: Each plugin manually instantiates widgets/dials; no central schema.
   - *Fix*: configuration-driven descriptors, widget registry, shared dial layout definitions.

2. **Global Override State**: Single `_CUSTOM_WIDGET_OVERRIDE_SPEC` makes nested widgets tricky.
   - *Fix*: per-module override context or stack structure.

3. **Legacy Dependencies**: Many plugins still rely on global singletons and direct imports (pygame, module_base, preset_manager).
   - *Fix*: adopt facade/context pattern, similar to sampler instruments.

4. **Theme Inconsistency**: Widgets assume color keys; when missing, fallback is inconsistent.
   - *Fix*: enforce theme contract with defaults; central theme helper for widget use.

5. **Developer Guidance**: Prior docs scattered.
   - *Fix*: maintain this bible, update `sampler_architecture_manual_v2.md`, `sampler_backend_manual_v3`, and produce quick-start checklists.

6. **Error Handling**: Controllers store last error but UI not showing it.
   - *Fix*: instrumentation to display errors on screen; share pattern across widgets.

---

## 7. Recommended Practices (Current System)

- Use `set_active_module` to register module; ensure widgets/dials restored in `detach`/`deactivate` hooks.
- When swapping widgets at runtime (e.g., Drumbo button 3), always wrap with helper that clears overrides and resets dial visibility.
- Store widget state via `widget.get_state()` and restore in module `on_preset_loaded` to survive preset changes.
- Run `python -m unittest plugins.sampler.core.tests.test_slicer_detector` and `python verify_sampler_phase2.py` after modifying sampler-related code.
- Update documentation (`docs/drumbo/sampler_backend_manual_v3.md`, this bible) when altering core plugin/widget mechanics.

---

## 8. Resource Index

| Component | File(s) |
| --- | --- |
| Vibrato plugin | `plugins/vibrato_plugin.py` |
| ASCII Animator plugin/widget | `plugins/ascii_animator_plugin.py`, `widgets/ascii_animator_widget.py` (verify path) |
| VK-8M plugin + drawbar widget | `plugins/vk8m_plugin.py`, `widgets/drawbar_widget.py` |
| Drumbo instrument (sampler) | `plugins/sampler/instruments/drumbo/module.py`, `config.py`, `services/ui_service.py` |
| Auto-slicer pipeline | `plugins/sampler/core/slicer/*.py` |
| Module base | `pages/module_base.py` |
| Plugin manager | `core/plugin.py` |
| Documentation | `docs/drumbo/sampler_backend_manual_v3.md`, `docs/drumbo/sampler_architecture_manual_v2.md` |

---

## 9. Next Actions Checklist

1. **Document widget specs** (drawbar, ASCII) including required theme keys. → *Pending*
2. **Prototype widget registry** allowing modules to request widgets by ID. → *Pending*
3. **Refactor one legacy plugin** (e.g., VK-8M) to adopt sampler-style config + override toggles as a proof of concept. → *Pending*
4. **Expose error status** in slicer widget UI. → *Pending*
5. **Create developer checklist** for new plugins/widgets referencing this bible. → *Pending*

---

*Maintainers: update this bible whenever plugin/widget infrastructure evolves. The goal is a zero-guesswork experience when authoring the next instrument or utility.*
