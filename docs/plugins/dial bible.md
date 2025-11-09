# Dial Integration Bible

**Logging Baseline**
- Start each lifecycle method (`__init__`, `on_init`, `on_button`, `on_dial_change`, etc.) with a `showlog.debug("*[TAG STEP n] description")` call so test runs have deterministic breadcrumbs. Use the star-prefixed format (`"*[...]")` exactly—keep the tag consistent across the module.
- Avoid emitting these required breadcrumbs inside loops or tight update paths; place them at decision points only (e.g., widget swap, preset load) to prevent log spam while preserving traceability.
- Add supplemental `showlog.info` / `showlog.warn` / `showlog.error` lines as needed, but do not remove the mandatory `showlog.debug("*[")` anchors—the automation harness checks for them.

This document is the canonical reference for dial plumbing in ModuleBase-driven plugins. The Vibrato “Division” dial (device-backed) and the Spectra Switch dials (pure ModuleBase plugin) represent the two supported patterns. Every future plugin dial must follow this workflow so the UI, StateManager, presets, and hardware routing remain in sync.

---

## Quick Reference
- Define every dial in `config/custom_dials.json`.
- Map slots in your `ModuleBase` subclass via `SLOT_TO_CTRL`, `REGISTRY`, and a list-based `INIT_STATE["dials"]`.
- During mode setup call: `module_base.set_active_module(...)`, `cc_registry.load_from_module(...)`, `module_base.init_page()`, then `unit_router.load_module(...)`.
- Let `pages/module_base.py` create the dial widgets; it now auto-attaches `sm_source_name`/`sm_param_id` using the module registry.
- Persist state via `dialhandlers.live_states` and `StateManager` IDs; never write directly to dial objects outside ModuleBase.
- Provide `prepare_preset_save` / `on_preset_loaded` hooks so presets round-trip your dial/button/widget data.

---

## 1. Define Dial Metadata (`config/custom_dials.json`)
All dial metadata lives in JSON. Never hardcode ranges or labels in the plugin.

```json
{
  "spectra_main_1": {
  "label": "Spectra Main 1",
  "range": [0, 127],
  "type": "raw",
  "page": 0,
  "description": "Spectra Switch primary dial"
  }
}
```

Each ID referenced anywhere else (e.g., `SLOT_TO_CTRL`) must exist here. Options arrays are honored automatically by the dial renderer.

---

## 2. Implement the Module (`plugins/<plugin>_plugin.py`)
Subclass `system.module_core.ModuleBase`. The Spectra implementation is the template:

```python
from system.module_core import ModuleBase


class SpectraSwitchModule(ModuleBase):
  MODULE_ID = "spectra_switch"
  SLOT_TO_CTRL = {1: "spectra_main_1", 2: "spectra_main_2"}

  REGISTRY = {
    MODULE_ID: {
      "type": "module",
      "01": {"label": "Spectra Main 1", "range": [0, 127], "type": "raw"},
      "02": {"label": "Spectra Main 2", "range": [0, 127], "type": "raw"},
    }
  }

  INIT_STATE = {
    "dials": [32, 95, 0, 0, 0, 0, 0, 0],  # slot-indexed list (max length 8)
    "button_states": {"1": 0},
    "widget": {"active_id": "widget_luma", "snapshots": {"widget_luma": {}}},
  }
```

Key requirements:
- `REGISTRY` keys must be two-digit slot numbers (`"01"`…`"08"`). Non-dict members (e.g., `"type"`) are skipped automatically.
- `INIT_STATE["dials"]` **must** be a list indexed by slot position. Supplying strings or dicts raises `ValueError` when ModuleBase hydrates the UI.
- Any widget caches or buttons live alongside the dial list.

Module lifecycle methods delegate to ModuleBase; only add custom behavior (`on_button`, widget switching, etc.) where necessary.

---

## 3. Wire the Mode (`managers/mode_manager.py`)
Every ModuleBase plugin needs a setup routine like `_setup_spectra_switch`:

```python
def _setup_spectra_switch(self):
  self.header_text = "Spectra Switch"
  from pages import module_base as page
  from plugins.spectra_switch_plugin import SpectraSwitchModule
  from system import cc_registry
  import unit_router

  page.set_active_module(SpectraSwitchModule)

  cc_registry.load_from_module(SpectraSwitchModule.MODULE_ID, SpectraSwitchModule.REGISTRY)

  if hasattr(page, "init_page"):
    page.init_page()

  unit_router.load_module(SpectraSwitchModule.MODULE_ID, page.handle_hw_dial)
```

This mirrors `_setup_vibrato`, but uses `load_from_module` because plugins don’t have a `device.<name>` module. Order matters:
1. `set_active_module` primes ModuleBase with the new subclass.
2. `load_from_module` registers knobs in StateManager under `source_name="spectra_switch"` (avoid Quadraverb bleed-through).
3. `init_page` builds the dial widgets and hydrates values.
4. `unit_router.load_module` routes hardware dials to `module_base.handle_hw_dial`.

Future plugins should copy this shape; replace names only.

---

## 4. ModuleBase Dial Construction (`pages/module_base.py`)
`module_base.draw_ui()` owns dial creation. After the Spectra upgrade it also attaches StateManager metadata automatically:

```python
dialhandlers.set_dials(dial_objs)
cc_registry.attach_mapping_to_dials(module_id, dial_objs)
```

Prerequisites for this to work:
- `SLOT_TO_CTRL` maps slot → custom dial ID.
- Corresponding metadata is present in `custom_dials.json`.
- `REGISTRY` exposes each slot with `label`/`range` so the hash `_make_param_id(module_id, label)` is stable.

Dial banks follow the same path via `_register_active_bank_with_dialhandlers()`, so hot-swapped banks inherit the correct `sm_source_name` / `sm_param_id` metadata.

---

## 5. State Capture and Presets
Always capture dial values via `dialhandlers.live_states`. Spectra exposes a reusable helper:

```python
def _capture_live_dials(self) -> list:
  live_main = dialhandlers.live_states.get(self.MODULE_ID, {}).get("main")
  if isinstance(live_main, dict):
    dial_vals = live_main.get("dials", [])
  elif isinstance(live_main, list):
    dial_vals = live_main
  else:
    dial_vals = self.INIT_STATE.get("dials", [])
  values = list(dial_vals) if isinstance(dial_vals, list) else []
  while len(values) < 8:
    values.append(0)
  return values[:8]
```

Preset hooks then look like:

```python
def prepare_preset_save(self, data: dict):
  data["dials"] = self._capture_live_dials()
  data["button_states"] = dict(self.button_states)
  data["widget"] = {
    "active_id": self._active_widget_id,
    "snapshots": dict(self._widget_state_cache),
  }
  return data

def on_preset_loaded(self, data: dict):
  self.button_states = dict(data.get("button_states", self.button_states))
  widget = data.get("widget", {})
  self._widget_state_cache = dict(widget.get("snapshots", self._widget_state_cache))
  self._active_widget_id = widget.get("active_id", self._active_widget_id)
  self._load_active_widget()
```

Never modify `dialhandlers.dials` directly; ModuleBase drives hydration through `load_from_module` plus the metadata attachments.

---

## 6. Hardware & StateManager Lifecycle
Once the mode is active:
1. Hardware movement reaches `module_base.handle_hw_dial` (via `unit_router.load_module`).
2. `handle_hw_dial` snaps values, updates UI widgets, and calls `state_manager.manager.set_value(module_id, param_id, value)` using the metadata attached in §4.
3. `dialhandlers.on_dial_change` mirrors that flow for mouse/touch events, persisting through `_persist_state()`.

Any log of the form `Knob QUADRAVERB:XXXX not found` means `cc_registry.load_from_module` was skipped or `attach_mapping_to_dials` did not run (usually due to missing `REGISTRY`/metadata). Fix the wiring before shipping.

---

## 7. Validation Checklist (Run After Integration)
- Load the plugin’s mode in UI; verify the log contains `Loaded <n> module dials from <module_id>`.
- Spin each dial; ensure the log persists under your module namespace, e.g. `[STATE PERSIST] slot=1 src=spectra_switch`.
- Confirm no `[STATE_MGR] ... not found in registry` warnings appear.
- Trigger `prepare_preset_save`; verify the captured list length is 8 and numeric.
- Reload the preset; ensure dials/buttons/widgets restore without manual intervention.
- For hardware testing, twist a physical knob and confirm `handle_hw_dial` log lines show `src=spectra_switch` (or your module ID).

---

## 8. Appendix: Vibrato vs. Spectra
- **Vibrato** rides the device infrastructure. `_setup_vibrato` calls `cc_registry.load_from_device("vibrato")`, which automatically wired the knobs. The device dial manager then attached the metadata, so additional code was unnecessary.
- **Spectra (and all future ModuleBase plugins)** lack a `device.<name>` module. Without the explicit `load_from_module` call and the new metadata attachment in `module_base`, Spectra inherited Quadraverb’s namespace, causing state persistence warnings. The documented pattern closes that gap and is now the standard for every new plugin dial.

Follow this playbook verbatim for all future ModuleBase-driven dials. Deviations should be called out in docs along with the rationale.
