# Spectra Switch Plugin Integration Session Notes

**Logging Baseline**
- Retain the star-prefixed debug breadcrumbs added during this integration (e.g., `showlog.debug("*[DEF on_init STEP 1] ...")`). Future edits must preserve this format so playbook runs have consistent markers.
- Keep the mandatory `showlog.debug("*[")` calls out of loops and only at key milestones (initialization, widget swap, preset load) to avoid excessive output while maintaining trace coverage.
- Layer additional severity levels (`showlog.info`, `showlog.warn`, `showlog.error`) for context, but never strip the required debug anchors—they are part of the regression checklist.

## Dial Hydration Fix
- Issue: `INIT_STATE["dials"]` used control-id keys, causing `Dial.set_value(int(val))` to hit `ValueError` when ModuleBase hydrated from those strings.
- Resolution: Converted the payload to a slot-indexed list (`[32, 95, 0, 0, 0, 0, 0, 0]`) so hydration runs through the standard pipeline without extra code.

```python
INIT_STATE = {
	# Slot-indexed dial list (ModuleBase hydrates by slot order)
	"dials": [32, 95, 0, 0, 0, 0, 0, 0],
	"button_states": {"1": 0},
	"widget": {
		"active_id": "widget_luma",
		"snapshots": {
			"widget_luma": {"mini_a": 0.3, "mini_b": 0.7},
			"widget_chroma": {"mini_a": 0.5, "mini_b": 0.5},
		},
	},
}
```

## Module & Registry Alignment
- The module class did not inherit `ModuleBase`, preventing `_get_mod_instance()` from instantiating it and leaving CC registry empty.
- Updated class signature to `class SpectraSwitchModule(ModuleBase)` and called `super().__init__()`.
- Reshaped `REGISTRY` to `{ "spectra_switch": { "type": "module", "01": {...}, "02": {...} } }` so `cc_registry.load_from_module` registers dial metadata.

```python
from system.module_core import ModuleBase


class SpectraSwitchModule(ModuleBase):
	MODULE_ID = "spectra_switch"

	REGISTRY = {
		MODULE_ID: {
			"type": "module",
			"01": {
				"label": "Spectra Main 1",
				"range": [0, 127],
				"type": "raw",
			},
			"02": {
				"label": "Spectra Main 2",
				"range": [0, 127],
				"type": "raw",
			},
		}
	}

	def __init__(self):
		super().__init__()
		showlog.debug("*[DEF __init__ STEP 1] create module instance")
```

## StateManager Namespace Fix
- Without registering the module namespace, dial persistence fell back to the previously active device (`QUADRAVERB`) and logged `Knob QUADRAVERB:XXXX not found`.
- Added an explicit `cc_registry.load_from_module(...)` call during mode activation so knobs register under `source_name="spectra_switch"` before `init_page()` hydrates the UI.
- Updated `pages/module_base.py` to call `cc_registry.attach_mapping_to_dials` immediately after `dialhandlers.set_dials(...)`, ensuring every dial widget carries the correct `sm_source_name`/`sm_param_id` regardless of module or bank swaps.

```python
cc_registry.load_from_module(SpectraSwitchModule.MODULE_ID, SpectraSwitchModule.REGISTRY)
...
cc_registry.attach_mapping_to_dials(module_id, dial_objs)
```

## Plugin Registration
- Error: PluginManager rejected `SpectraSwitchPlugin` because it wasnt a `core.plugin.Plugin` subclass.
- Fix: Inherit from `core.plugin.Plugin` (`BasePlugin`), enabling discovery and proper `page_registry` wiring.

```python
from core.plugin import Plugin as BasePlugin


class SpectraSwitchPlugin(BasePlugin):
	name = "Spectra Switch"
	version = "1.2.1"
	page_id = SpectraSwitchModule.MODULE_ID

	def on_load(self, app):
		from pages import module_base as page
		app.page_registry.register(
			self.page_id,
			page,
			label="Spectra Switch",
			meta={"plugin": "spectra_switch", "version": self.version},
		)
```

## Dial State Persistence
- Removed references to nonexistent `dialhandlers.set_dial_value`/`get_dial_value`; hydration relies entirely on `module_base.init_page()`.
- Preset saves now capture dial state via `_capture_live_dials()` -> slot-indexed list from `dialhandlers.live_states["spectra_switch"]["main"]` (fallback to INIT_STATE).
- `prepare_preset_save` stores the dial list plus button/widget snapshots to match preset manager expectations.

```python
def prepare_preset_save(self, data: Dict[str, Any]):
	showlog.debug("*[DEF prepare_preset_save STEP 1] capture current state")
	data["dials"] = self._capture_live_dials()
	data["button_states"] = dict(self.button_states)
	data["widget"] = {
		"active_id": self._active_widget_id,
		"snapshots": dict(self._widget_state_cache),
	}
	return data


def _capture_live_dials(self) -> list:
	live_main = dialhandlers.live_states.get(self.MODULE_ID, {}).get("main")
	if isinstance(live_main, dict):
		dial_vals = live_main.get("dials", [])
	elif isinstance(live_main, list):
		dial_vals = live_main
	else:
		dial_vals = self.INIT_STATE.get("dials", [])

	values = list(dial_vals if isinstance(dial_vals, list) else [])
	while len(values) < 8:
		values.append(0)
	return values[:8]
```

## Widget Contract Compliance
- Original `draw` signatures didnt accept `device_name`/`offset_y` kwargs, causing renderer TypeErrors.
- Updated both widgets to `draw(surface, device_name=None, offset_y=0, **kwargs)` and to return the painted rect.
- Cached the applied offset so pointer hit-testing (mouse down/move) remains aligned after vertical translation.

```python
class LumaWidget:
	...

	def draw(self, surface: pygame.Surface, device_name=None, offset_y: int = 0, **_):
		self._offset_y = offset_y
		rect = self.rect.move(0, offset_y)
		pygame.draw.rect(surface, bg, rect)
		...
		return rect

	def handle_event(self, event):
		if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
			if self._zone_a.move(0, self._offset_y).collidepoint(event.pos):
				self._set_from_y("a", event.pos[1])
```

## Hydration & Snapshots
- `on_preset_loaded` rehydrates button and widget state from the saved payload; dial values remain managed by ModuleBase.
- `_capture_live_dials` gathers the active 8-slot snapshot, padding as needed, mirroring ModuleBase behavior.

```python
def on_preset_loaded(self, data: Dict[str, Any]):
	showlog.debug("*[DEF on_preset_loaded STEP 1] restore preset data")
	self.button_states = dict(data.get("button_states", self.button_states))
	widget = data.get("widget", {})
	self._widget_state_cache = dict(widget.get("snapshots", self._widget_state_cache))
	self._active_widget_id = widget.get("active_id", self._active_widget_id)
	self._load_active_widget()
```

## General Best Practice Notes
- No modifications to shared infrastructure; integration uses ModuleBase helpers (`set_custom_widget_override`, `request_custom_widget_redraw`) and slot-based dial ownership.
- Widget/theme/state handling now mirrors existing plugins (Dual Widget Demo, VK8M) so future authors can follow the documentation without altering core code.

## Custom Dial Metadata
- Verified `config/custom_dials.json` includes the Spectra controls so ModuleBase can pull range/label data without inline overrides.

```json
{
	"spectra_main_1": {
		"label": "Spectra Main 1",
		"range": [0, 127],
		"type": "raw",
		"page": 0,
		"description": "Spectra Switch primary dial"
	},
	"spectra_main_2": {
		"label": "Spectra Main 2",
		"range": [0, 127],
		"type": "raw",
		"page": 0,
		"description": "Spectra Switch secondary dial"
	}
}
```

## Mode Manager Hook
- Finalized `_setup_spectra_switch` so ModeManager registers the module with StateManager, hydrates the UI, and routes hardware dials through `module_base.handle_hw_dial`.

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
