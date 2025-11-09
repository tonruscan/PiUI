# Streamlined Plugin Creation Guide

## Overview
This guide provides a **step-by-step checklist** for creating new module-based plugins for the UI system. After implementing VK-8M, this process has been refined to be as smooth as possible.

## Quick Start Checklist

### ✅ Step 1: Create Plugin File
**File:** `plugins/<your_plugin>_plugin.py`

```python
# /plugins/vk8m_plugin.py
import showlog
from system.module_core import ModuleBase
from drivers import vk8m as driver  # Your hardware driver
from core.plugin import Plugin as PluginBase

class YourModule(ModuleBase):
    """Your device controller module."""
    
    MODULE_ID = "your_module"  # Unique ID
    page_id = "your_module_main"
    page_label = "Your Device Name"
    
    # Registry for module_base integration (optional - can be empty)
    REGISTRY = {}
    
    # Initial state for buttons and dials
    INIT_STATE = {
        "buttons": {"1": 0},  # Button state indices
        "dials": [64, 64],    # Default centered values
    }
    
    # Button definitions (10-button standard layout)
    BUTTONS = [
        {"id": "1", "label": "BTN1", "behavior": "state"},
        {"id": "2", "label": "BTN2", "behavior": "transient"},
        {"id": "5", "label": "5", "behavior": "transient", "action": "bypass_toggle"},
        {"id": "6", "label": "6", "behavior": "nav", "action": "store_preset"},
        {"id": "7", "label": "P", "behavior": "nav", "action": "presets"},
        {"id": "8", "label": "8", "behavior": "transient", "action": "mute_toggle"},
        {"id": "9", "label": "S", "behavior": "nav", "action": "save_preset"},
        {"id": "10", "label": "10", "behavior": "nav", "action": "device_select"},
    ]
    
    # Dial slot mapping (which dials to show in the grid)
    SLOT_TO_CTRL = {
        1: "control_name_1",
        2: "control_name_2",
        # Add up to 8 dials (2 rows x 4 cols)
    }

    def __init__(self):
        super().__init__()
        
        # Initialize state from INIT_STATE
        init = self.INIT_STATE
        self.dial_values = list(init.get("dials", [64, 64]))
        
        # Get MIDI service
        try:
            from system import service_registry
            midi_service = service_registry.get("midi")
            if midi_service and hasattr(midi_service, "send_message"):
                self._send_fn = midi_service.send_message
            else:
                self._send_fn = lambda b: showlog.warn(f"[YOUR_MODULE] No MIDI sender: {b}")
        except Exception as e:
            showlog.warn(f"[YOUR_MODULE] Could not get MIDI service: {e}")
            self._send_fn = lambda b: showlog.warn(f"[YOUR_MODULE] No MIDI sender: {b}")
        
        showlog.info("[YOUR_MODULE] Module initialized")
        
        # Push initial dial values to device
        self._apply_dial_values()

    def _apply_dial_values(self):
        """Send initial dial values to device."""
        for i, val in enumerate(self.dial_values):
            self.on_dial_change(i, val)

    def on_button(self, btn_id: str, state_index: int = 0, state_data: dict = None):
        """Handle button press (fallback for non-multi-state buttons)."""
        showlog.info(f"[YOUR_MODULE] Button {btn_id} pressed")
        # Implement your button logic

    def on_dial_change(self, dial_index: int, value: int):
        """Handle dial changes."""
        if dial_index == 0:
            self.dial_values[0] = value
            driver.set_control_1(self._send_fn, value)
        elif dial_index == 1:
            self.dial_values[1] = value
            driver.set_control_2(self._send_fn, value)

    def export_state(self):
        """Export state for preset saving."""
        # Get button states from module_base
        try:
            from pages import module_base
            button_states = getattr(module_base, "_BUTTON_STATES", {})
        except:
            button_states = {}
        
        return {
            "buttons": button_states.copy(),
            "dials": self.dial_values[:],
        }

    def import_state(self, state: dict):
        """Restore state from preset."""
        if not state:
            return
        
        # Restore button states to module_base
        btns = state.get("buttons", {})
        if isinstance(btns, dict):
            try:
                from pages import module_base
                for btn_id, state_idx in btns.items():
                    module_base._BUTTON_STATES[btn_id] = int(state_idx)
            except Exception as e:
                showlog.warn(f"[YOUR_MODULE] Failed to restore button states: {e}")
        
        # Restore dials and apply
        dials = state.get("dials", None)
        if isinstance(dials, list):
            self.dial_values = list(dials)
            self._apply_dial_values()


# Plugin Registration
class YourPlugin(PluginBase):
    """Your plugin registration."""
    
    name = "Your Device Name"
    version = "0.1.0"
    category = "synth"  # or "effect", "controller", etc.
    author = "System"
    description = "Your device description"
    icon = "your_icon.png"
    page_id = "your_module_main"
    
    def on_load(self, app):
        """Register page with module_base."""
        try:
            from pages import module_base as page
            
            rendering_meta = {
                "fps_mode": "high",
                "supports_dirty_rect": True,
                "burst_multiplier": 1.0,
            }
            
            app.page_registry.register(
                self.page_id,
                page,
                label=self.name,
                meta={"rendering": rendering_meta}
            )
            showlog.info(f"[YourPlugin] Registered page '{self.page_id}'")
        except Exception as e:
            import traceback
            showlog.error(f"[YourPlugin] Failed to register page: {e}")
            showlog.error(traceback.format_exc())


# Legacy exports for module_base compatibility
MODULE_ID = YourModule.MODULE_ID
REGISTRY = YourModule.REGISTRY
BUTTONS = YourModule.BUTTONS
SLOT_TO_CTRL = YourModule.SLOT_TO_CTRL

# Export the Plugin class for auto-discovery
Plugin = YourPlugin
```

---

### ✅ Step 2: Add Control Definitions
**File:** `config/custom_dials.json`

Add entries for each control in your `SLOT_TO_CTRL`:

```json
{
  "control_name_1": {
    "label": "Control 1",
    "range": [0, 127],
    "type": "raw",
    "page": 0,
    "description": "Description of control 1"
  },
  "control_name_2": {
    "label": "Control 2",
    "range": [0, 127],
    "type": "raw",
    "page": 0,
    "description": "Description of control 2"
  }
}
```

**Important:** The keys must match the values in your `SLOT_TO_CTRL` dictionary.

---

### ✅ Step 3: Add Device Button to Device Page
**File:** `config/device_page_layout.json`

Add a button entry:

```json
{
    "id": 6,
    "img": "icons/your_icon.png",
    "label": "Your Device",
    "plugin": "your_module_main"
}
```

**Note:** The `"plugin"` field must match your `page_id` from Step 1.

---

### ✅ Step 4: Add Mode Manager Setup
**File:** `managers/mode_manager.py`

Add three integrations:

#### A. Add mode check in `switch_mode()` method (around line 135):
```python
elif new_mode == "your_module_main":
    self._setup_your_module()
```

#### B. Add to navigator record list (around line 163):
```python
elif new_mode in ("patchbay", "text_input", "mixer", "vibrato", "vk8m_main", "your_module_main", "module_presets"):
```

#### C. Add setup function at the end of the class:
```python
def _setup_your_module(self):
    """Setup for Your Module mode."""
    from pages import module_base as page
    from plugins.your_module_plugin import YourModule
    
    # Set active module class BEFORE init_page
    page.set_active_module(YourModule)
    
    # Load CC registry (if you have custom controls)
    from system import cc_registry
    cc_registry.load_from_device("your_module")
    
    # Initialize page
    if hasattr(page, "init_page"):
        page.init_page()
    
    # Route hardware dial input
    import unit_router
    unit_router.load_module("your_module", page.handle_hw_dial)
    
    showlog.debug("[MODE_MGR] Your Module page initialized")
```

---

### ✅ Step 5: Add to Renderer
**File:** `rendering/renderer.py`

Add two integrations:

#### A. Add to draw method check (around line 89):
```python
elif ui_mode in ("mixer", "vibrato", "vk8m_main", "your_module_main"):
    page["draw_ui"](self.screen, offset_y=offset_y)
```

#### B. Add to themed pages list (around line 118):
```python
themed_pages = ("dials", "presets", "mixer", "vibrato", "vk8m_main", "your_module_main", "module_presets")
```

---

### ✅ Step 6: Create Hardware Driver (Optional)
**File:** `drivers/<your_device>.py`

If your device uses MIDI/SysEx:

```python
# /drivers/your_device.py
from typing import Callable

SendFn = Callable[[bytes], None]

def send_param(send_fn: SendFn, address: int, value: int) -> None:
    """Send a parameter change to the device."""
    # Construct your MIDI/SysEx message
    message = bytes([0xF0, 0x41, 0x10, address, value, 0xF7])
    send_fn(message)

def set_control_1(send_fn: SendFn, val: int) -> None:
    """Set control 1 value."""
    send_param(send_fn, 0x20, max(0, min(127, val)))

def set_control_2(send_fn: SendFn, val: int) -> None:
    """Set control 2 value."""
    send_param(send_fn, 0x21, max(0, min(127, val)))
```

---

## Key Architectural Points

### Module Class Contract
Your module class **must provide**:

**Required Attributes:**
- `MODULE_ID`: String identifier (e.g., "vk8m")
- `BUTTONS`: List of button definitions
- `REGISTRY`: Dict of CC mappings (can be empty `{}`)
- `SLOT_TO_CTRL`: Dict mapping dial slots to control IDs

**Required Methods:**
- `__init__(self)`: No parameters!
- `on_button(self, btn_id: str)`: Handle button press
- `on_dial_change(self, dial_index: int, value: int)`: Handle dial change

**Optional Methods for Presets:**
- `export_state(self) -> dict`: Return state for saving
- `import_state(self, state: dict)`: Restore state from dict

---

## Button Behaviors

The `BUTTONS` list supports these behavior types:

- **`"state"`**: Toggle button with persistent state (e.g., on/off)
- **`"transient"`**: Momentary button (fires once per press)
- **`"multi"`**: Multi-state cycling button (see Multi-State Buttons section)
- **`"nav"`**: Navigation button (opens another page)

Standard button IDs and recommended uses:

| Button | Position | Recommended Use |
|--------|----------|-----------------|
| 1-4    | Left     | Module-specific controls |
| 5      | Left     | Bypass toggle |
| 6      | Right    | Store preset |
| 7      | Right    | Presets page |
| 8      | Right    | Mute toggle |
| 9      | Right    | Save preset |
| 10     | Right    | Device select |

---

## Dial Layout

The grid supports **up to 8 dials** in a 2x4 layout (2 rows, 4 columns).

Map dial positions using `SLOT_TO_CTRL`:
```python
SLOT_TO_CTRL = {
    1: "control_name_1",  # Top-left
    2: "control_name_2",  # Top-second
    3: "control_name_3",  # Top-third
    4: "control_name_4",  # Top-right
    5: "control_name_5",  # Bottom-left
    6: "control_name_6",  # Bottom-second
    7: "control_name_7",  # Bottom-third
    8: "control_name_8",  # Bottom-right
}
```

**Important:** Each control name must have a matching entry in `config/custom_dials.json`.

---

## Preset System

The preset system is **automatic** if you implement:

```python
def export_state(self):
    """Called when saving a preset."""
    return {
        "buttons": self.button_states.copy(),
        "dials": self.dial_values[:],
        # Any other state you want to save
    }

def import_state(self, state: dict):
    """Called when loading a preset."""
    if not state:
        return
    self.button_states = state.get("buttons", {}).copy()
    self.dial_values = list(state.get("dials", [64, 64]))
    # Restore any other state
```

Users can then:
- Press button 9 to save a preset
- Press button 7 to open preset browser
- Select a preset to load it

---

## Common Patterns

### Multi-State Button with Lambda Handlers (Recommended - VK-8M Style)

The cleanest way to implement multi-state buttons is using `"behavior": "multi"` with lambda state handlers:

```python
class YourModule(ModuleBase):
    MODULE_ID = "your_module"
    
    # Define button with states array
    BUTTONS = [
        {
            "id": "1",
            "behavior": "multi",  # Multi-state cycling button
            "states": ["OFF", "MODE1", "MODE2", "MODE3"]  # Button label cycles through these
        },
        # ... other buttons
    ]
    
    def __init__(self):
        super().__init__()
        
        # Get MIDI service
        self._send_fn = self._setup_midi_service()
        
        # Define state handlers as lambdas (auto-called by module_base)
        # Method names match state labels (lowercase, spaces/dashes to underscores)
        self.off = lambda: driver.set_mode_off(self._send_fn)
        self.mode1 = lambda: (driver.set_mode_on(self._send_fn), driver.set_type(self._send_fn, 0))
        self.mode2 = lambda: (driver.set_mode_on(self._send_fn), driver.set_type(self._send_fn, 1))
        self.mode3 = lambda: (driver.set_mode_on(self._send_fn), driver.set_type(self._send_fn, 2))
    
    def _setup_midi_service(self):
        """Helper to get MIDI service."""
        try:
            from system import service_registry
            midi_service = service_registry.get("midi")
            if midi_service and hasattr(midi_service, "send_message"):
                return midi_service.send_message
        except Exception as e:
            showlog.warn(f"[YOUR_MODULE] Could not get MIDI service: {e}")
        return lambda b: showlog.warn(f"[YOUR_MODULE] No MIDI sender: {b}")
```

**How it works:**
1. Button displays current state label (OFF, MODE1, MODE2, MODE3)
2. Clicking cycles to next state automatically
3. Module_base calls the matching lambda (state "MODE1" → `self.mode1()`)
4. Label updates automatically on screen

**Benefits:**
- No manual label updating required
- No state tracking needed (module_base handles it)
- Super clean code - just define lambdas
- Automatically saves/restores with presets

**Lambda tips:**
- Use tuple trick for multiple calls: `lambda: (call1(), call2())`
- Define in `__init__` so they have access to `self._send_fn`
- Method name must match state label (lowercase, spaces→underscores)

### Multi-State Button with Manual Control (Legacy - Vibrato Style)

### Multi-State Button with Manual Control (Legacy - Vibrato Style)

If you need more control over state transitions or complex state logic:

```python
class YourModule(ModuleBase):
    LABELS = ["OFF", "MODE1", "MODE2", "MODE3"]
    
    BUTTONS = [
        {"id": "1", "label": "OFF", "behavior": "state"},  # Initial label
        # ... other buttons
    ]
    
    def __init__(self):
        super().__init__()
        self.button_states = {"1": 0}  # Index into LABELS
        self._sync_button_label()
    
    def on_button(self, btn_id: str, state_index: int = 0, state_data: dict = None):
        if btn_id == "1":
            idx = self.button_states.get("1", 0)
            idx = (idx + 1) % len(self.LABELS)
            self.button_states["1"] = idx
            self._sync_button_label()
            self._apply_state()
    
    def _sync_button_label(self):
        """Update button label dynamically."""
        label = self.LABELS[self.button_states.get("1", 0)]
        for btn in self.BUTTONS:
            if btn["id"] == "1":
                btn["label"] = label
                break
        # Trigger UI redraw
        try:
            import dialhandlers
            if hasattr(dialhandlers, 'msg_queue') and dialhandlers.msg_queue:
                dialhandlers.msg_queue.put(("force_redraw", 10))
        except Exception:
            pass
    
    def _apply_state(self):
        """Send the state to hardware."""
        idx = self.button_states.get("1", 0)
        if idx == 0:
            driver.set_mode_off(self._send_fn)
        else:
            driver.set_mode_on(self._send_fn)
            driver.set_mode_type(self._send_fn, idx - 1)
```

**Use this approach when:**
- You need conditional state transitions (not just cycling)
- States depend on other module state
- You need custom validation logic

**Otherwise, use the lambda approach** - it's much simpler!

### Range-Based Dial with Options

```json
{
  "waveform_select": {
    "label": "Waveform",
    "range": [0, 3],
    "type": "raw",
    "page": 0,
    "options": ["Sine", "Triangle", "Square", "Sawtooth"]
  }
}
```

The dial will snap to 4 positions showing the option labels.

---

## Testing Checklist

After creating your plugin:

- [ ] Plugin appears on device select page
- [ ] Clicking plugin button navigates to plugin page
- [ ] Page shows correct header text
- [ ] All 10 buttons render with correct labels
- [ ] Dials show correct labels (not "Slot 1", "Slot 2")
- [ ] Button presses trigger `on_button()` with correct IDs
- [ ] Dial changes trigger `on_dial_change()` with correct values
- [ ] MIDI/control messages are sent to hardware
- [ ] Pressing button 9 opens preset save UI
- [ ] Saving preset works
- [ ] Loading preset restores state correctly
- [ ] Pressing button 10 returns to device select page

---

## Troubleshooting

### Issue: "Slot 1", "Slot 2" instead of control names
**Solution:** Add control definitions to `config/custom_dials.json` matching your `SLOT_TO_CTRL` keys.

### Issue: Blank page after navigation
**Solution:** Check that your `page_id` is added to the renderer's page list in `rendering/renderer.py`.

### Issue: Module switching shows wrong data
**Solution:** Ensure `set_active_module()` is called in mode_manager's setup function, not in plugin's `on_load()`.

### Issue: `__init__() takes X arguments but Y were given`
**Solution:** Your module's `__init__()` must have NO parameters: `def __init__(self):`

### Issue: Buttons don't work
**Solution:** Ensure your `BUTTONS` list has correct IDs ("1"-"10") and `on_button()` handles them.

### Issue: Presets don't save/load
**Solution:** Implement `export_state()` and `import_state()` methods in your module class.

---

## Files You'll Touch

**Required:**
1. `plugins/<your_plugin>_plugin.py` - Your plugin implementation
2. `config/custom_dials.json` - Control definitions
3. `config/device_page_layout.json` - Device button
4. `managers/mode_manager.py` - Mode switching logic
5. `rendering/renderer.py` - Page rendering

**Optional:**
6. `drivers/<your_device>.py` - Hardware communication

---

## Example: Complete VK-8M Reference

See `plugins/vk8m_plugin.py` for a complete working example with:
- Multi-state button (vibrato mode cycling)
- Two dials (distortion, reverb)
- MIDI SysEx communication
- Preset save/load
- Proper MIDI service integration

---

## Future Improvements

The following would make plugin creation even more streamlined:

1. **Auto-register device buttons** - Plugins could register their own device page buttons
2. **Dynamic renderer** - Eliminate hardcoded page lists in renderer
3. **Plugin metadata system** - Declare rendering and navigation metadata in plugin class
4. **Template generator** - CLI tool to scaffold new plugins

For now, follow this checklist and you'll have a working plugin in ~30 minutes!
