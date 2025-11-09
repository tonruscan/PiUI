# Plugin & Widget Quick Start Guide

**Logging Baseline**
- Begin every major hook (`__init__`, `on_init`, `on_button`, `on_dial_change`, widget attach/detach, preset handlers) with `showlog.debug("*[MODULE_ID STEP n] message")`. The star-prefixed format is mandatory for traceability.
- Keep these required debug anchors outside loops or high-frequency code paths; emit them once per decision point so logs stay readable.
- Add further `showlog.info` / `showlog.warn` / `showlog.error` lines as appropriate, but never delete the `showlog.debug("*[")` breadcrumbs expected by QA scripts.

This guide summarizes the essential steps for creating a plugin that integrates cleanly with the ModuleBase host and supports custom widgets. It distills the requirements from `plugins_and_widgets_universe_-_the_bible.md` and the latest session notes on the Spectra Switch integration.

---

## 1. Define Dial Metadata
1. Add control entries to `config/custom_dials.json`.
   ```json
   {
     "my_plugin_main_1": {
       "label": "Main 1",
       "range": [0, 127],
       "type": "raw",
       "page": 0,
       "description": "Primary dial"
     }
   }
   ```
2. Each control gets a unique ID, label, range, and type. Avoid hard-coding dial metadata in the plugin.

## 2. Scaffold the Module Class
1. Create `plugins/my_plugin.py`.
2. Inherit from `system.module_core.ModuleBase`.
3. Populate required attributes:
   ```python
   from system.module_core import ModuleBase


   class MyPluginModule(ModuleBase):
       MODULE_ID = "my_plugin"
       SLOT_TO_CTRL = {1: "my_plugin_main_1"}
       REGISTRY = {
           MODULE_ID: {
               "type": "module",
               "01": {
                   "label": "My Main Dial",
                   "range": [0, 127],
                   "type": "raw",
               },
           }
       }
       INIT_STATE = {
           "dials": [64, 0, 0, 0, 0, 0, 0, 0],  # slot-indexed list
           "button_states": {"1": 0},
       }

       def __init__(self):
           super().__init__()
           # prepare internal state here
   ```

### Key Rules
- `INIT_STATE["dials"]` must be a list indexed by slot (positions 1–8).
- Everything `on_init` needs (dials, button states, widgets) is already hydrated by `module_base.init_page()`; avoid calling `dialhandlers.set_dial_value` in `on_init` unless clamping corrupt data.

## 3. Implement Module Hooks
- `on_init`: use hydrated state (no manual dial writes).
- `on_dial_change(ctrl_id, value)`: respond to user moves; update widgets or internal caches.
- `on_button(btn_id, state_index, state_data)`: manage button toggles, widget swaps, etc.
- `attach_widget(widget)` / `detach_widget()`: store the active widget instance, push cached state via `set_state`, assign `widget.on_change`.
- `prepare_preset_save(data)` / `on_preset_loaded(data)`: persist/restore `button_states`, widget snapshots, and dial lists via helper functions.

Example preset helpers:
```python
def prepare_preset_save(self, data: Dict[str, Any]):
    data["dials"] = self._capture_live_dials()
    data["button_states"] = dict(self.button_states)
    data["widget"] = {
        "active_id": self._active_widget_id,
        "snapshots": dict(self._widget_state_cache),
    }
    return data
```

## 4. Register the Plugin Shell
- Create the plugin class that inherits from `core.plugin.Plugin`.
- Register the ModuleBase page in `on_load`.

```python
from core.plugin import Plugin as BasePlugin


class MyPlugin(BasePlugin):
    name = "My Plugin"
    version = "1.0.0"
    page_id = MyPluginModule.MODULE_ID

    def on_load(self, app):
        from pages import module_base as page
        app.page_registry.register(
            self.page_id,
            page,
            label=self.name,
            meta={"plugin": self.page_id, "version": self.version},
        )
```

## 5. Mode Manager Integration
- Add a branch to `managers/mode_manager.py` to activate your module. The sequence mirrors Spectra Switch:

```python
def _setup_my_plugin(self):
    self.header_text = "My Plugin"
    from pages import module_base as page
    from plugins.my_plugin import MyPluginModule
    from system import cc_registry
    import unit_router

    page.set_active_module(MyPluginModule)

    cc_registry.load_from_module(MyPluginModule.MODULE_ID, MyPluginModule.REGISTRY)

    if hasattr(page, "init_page"):
        page.init_page()

    unit_router.load_module(MyPluginModule.MODULE_ID, page.handle_hw_dial)
```

- This registers the module namespace with StateManager, hydrates the UI, and routes hardware dials. Ensure your navigation triggers `ui_mode` using the module `page_id`.

## 6. Widget Requirements
- Widget classes must accept `rect`, `on_change`, `theme`, `init_state`.
- Implement:
  - `get_state`, `set_state`
  - `mark_dirty`, `is_dirty`, `clear_dirty`
  - `update_value(ctrl_id, value)` if responding to dial changes
  - `draw(surface, device_name=None, offset_y=0, **kwargs)` and return the painted rect
  - `handle_event(event)` (even if it ignores events)

```python
class MyWidget:
    def __init__(self, rect, on_change=None, theme=None, init_state=None):
        self.rect = rect
        self.on_change = on_change
        self.theme = dict(theme or {})
        self._offset_y = 0
        self._state = {...}

    def draw(self, surface, device_name=None, offset_y=0, **_):
        self._offset_y = offset_y
        rect = self.rect.move(0, offset_y)
        # render contents
        return rect
```

## 7. Widget Attachment Flow
1. Module requests the widget:
   ```python
   host.set_custom_widget_override({
       "class": "MyWidget",
       "path": "widgets.my_widget",
       "grid_size": [4, 2],
       "grid_pos": [0, 0],
       "init_state": self._widget_state_cache.get(widget_id),
   })
   ```
2. `attach_widget(widget_obj)` is called by ModuleBase:
   - Set `self._widget_instance = widget_obj`.
   - Assign `widget_obj.on_change` to capture snapshot updates.
   - Call `widget_obj.set_state(snapshot)` if saved state exists.
   - Request repaint via `host.request_custom_widget_redraw(include_overlays=True)`.

## 8. Preset Lifecycle
- ModuleBase automatically calls:
  1. `prepare_preset_save(data)` when saving.
  2. `on_preset_loaded(data)` when loading or switching modules.
- Always keep saved payloads JSON-serializable (floats/ints, dicts).
- Example `on_preset_loaded`:
  ```python
  def on_preset_loaded(self, data):
      self.button_states = dict(data.get("button_states", self.button_states))
      widget = data.get("widget", {})
      self._widget_state_cache = dict(widget.get("snapshots", self._widget_state_cache))
      self._active_widget_id = widget.get("active_id", self._active_widget_id)
      self._load_active_widget()
  ```

## 9. Logging & Diagnostics
- Import `showlog` as a module and use the severity helpers (`showlog.debug`, `.info`, `.warn`, `.error`, `.exception`).
- Tag messages with your module ID (e.g., `showlog.info("my_plugin", "Widget toggled")`).
- Keep debug output minimal once the plugin stabilizes.

## 10. Final Checklist
1. **Metadata:** Custom dials defined, `SLOT_TO_CTRL` maps each slot.
2. **Class Setup:** Module inherits ModuleBase and calls `super().__init__()`.
3. **INIT_STATE:** Slot-indexed dial list; numeric values only.
4. **Slots & Buttons:** `BUTTONS` array reflects UI controls; `button_states` uses string keys.
5. **Widgets:** Implement required methods, accept `device_name`/`offset_y` in `draw`.
6. **Plugin Shell:** Subclass `core.plugin.Plugin`, register page in `on_load`.
7. **Mode Manager:** Branch routes `ui_mode` to `set_active_module`, `cc_registry.load_from_module`, `init_page`, and `unit_router.load_module`.
8. **Preset Hooks:** Save/load dial list, button states, widget snapshots.
9. **Registry Wiring:** Confirm `cc_registry.load_from_module` runs and logs `Loaded n module dials from my_plugin`.
10. **Live State:** `_capture_live_dials()` reads from `dialhandlers.live_states`.
11. **Testing:** Trigger navigation to ensure ModuleBase logs no warnings, widgets draw without argument errors, presets round-trip cleanly, and hardware dials route through `handle_hw_dial`.

Following these steps keeps new plugins consistent with existing modules (Vibrato, VK8M, Dual Widget Demo) and eliminates the need to touch shared runtime code.
