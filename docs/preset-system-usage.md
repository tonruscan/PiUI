# Preset System Usage Guide

## Overview
The modular preset system allows you to save and load complete module states (including dial values and widget positions) on a per-page/module basis.

## Files Created

### 1. `config/save_state_vars.json`
Configuration file that defines what variables to save for each page/module.

**Structure:**
```json
{
  "page_id": {
    "variables": ["list of module instance variables"],
    "widget_state": ["list of widget state attributes"],
    "registry_slots": ["list of registry slot IDs"],
    "description": "Human-readable description"
  }
}
```

**Example (Vibrato):**
```json
{
  "vibrato": {
    "variables": [
      "division_value",
      "is_on",
      "current_hz"
    ],
    "widget_state": [
      "a_y",
      "b_x",
      "b_y"
    ],
    "registry_slots": ["01", "02"],
    "description": "Vibrato module - saves division, depth, widget dot positions"
  }
}
```

### 2. `preset_manager.py`
Core preset management module with these key functions:

- **`save_preset(page_id, preset_name, module_instance, widget=None)`** - Save current state
- **`load_preset(page_id, preset_name, module_instance, widget=None)`** - Load saved state
- **`list_presets(page_id)`** - List all presets for a page
- **`delete_preset(page_id, preset_name)`** - Delete a preset
- **`get_preset_manager()`** - Get singleton instance

### 3. `preset_ui.py`
UI overlay component for preset name input with:
- Text input field with cursor
- Save/Cancel buttons
- Keyboard support (Enter to save, Escape to cancel)
- Visual feedback

### 4. `config/presets/`
Directory where presets are stored as JSON files:
```
config/presets/
  vibrato/
    my_preset.json
    fast_vibrato.json
  tremolo/
    smooth_trem.json
```

## How to Use

### For End Users

1. **Save a Preset:**
   - Navigate to your module page (e.g., vibrato)
   - Set up your desired configuration (dial positions, widget state)
   - Press button 9 (labeled "SV" for Save)
   - Enter a name in the text input overlay
   - Press Save or hit Enter

2. **Load a Preset:**
   - Button 7 will navigate to the presets page (to be implemented)
   - Select a preset to load

### For Developers: Adding Preset Support to a New Module

1. **Update `config/save_state_vars.json`:**
```json
{
  "your_module_id": {
    "variables": [
      "state_var1",
      "state_var2"
    ],
    "widget_state": [
      "widget_property1",
      "widget_property2"
    ],
    "registry_slots": ["01", "02"],
    "description": "Your module description"
  }
}
```

2. **Ensure your module uses `module_base.py` pattern:**
   - The preset system is already integrated into `pages/module_base.py`
   - Button 9 automatically triggers the preset save UI
   - Just make sure your module follows the ModuleBase structure

3. **Add button labels in your module's BUTTONS config:**
```python
BUTTONS = [
    # ... other buttons ...
    {"id": "9", "label": "SV", "behavior": "transient", "action": "save_preset"},
    # ... more buttons ...
]
```

## Preset File Format

Presets are stored as JSON files in `config/presets/<page_id>/<preset_name>.json`:

```json
{
  "page_id": "vibrato",
  "preset_name": "fast_vibrato",
  "variables": {
    "division_value": 4,
    "is_on": true,
    "current_hz": 120
  },
  "widget_state": {
    "a_y": 0.25,
    "b_x": 0.5,
    "b_y": 0.75
  },
  "registry_values": {
    "01": 3,
    "02": 75
  }
}
```

## Integration with Existing Code

The preset system integrates with:

- **StateManager** - Syncs with the existing state management system
- **Module System** - Works with ModuleBase-derived modules
- **Widget System** - Saves custom widget state (like VibratoField dot positions)
- **Registry System** - Saves dial/registry values

## Next Steps

To complete the integration:

1. **Adapt the presets page** (`pages/presets.py`) to:
   - Use `preset_manager.list_presets(page_id)` to show available presets
   - Call `load_preset(page_id, preset_name)` when user selects a preset
   - Add delete functionality using `delete_preset()`

2. **Add keyboard support** (optional):
   - The UI already supports keyboard input when the overlay is active
   - Just ensure keyboard events are routed to the page

3. **Add more modules**:
   - Update `save_state_vars.json` for each new module
   - Follow the same pattern as vibrato

## Example: Manual Preset Operations

```python
from preset_manager import get_preset_manager

# Get the manager
pm = get_preset_manager()

# List all vibrato presets
presets = pm.list_presets("vibrato")
print(presets)  # ['fast_vibrato', 'slow_deep']

# Get preset data without loading
data = pm.get_preset_data("vibrato", "fast_vibrato")
print(data["variables"])

# Save/load from code
module_instance = _get_mod_instance()
widget = _load_custom_widget()

# Save
pm.save_preset("vibrato", "new_preset", module_instance, widget)

# Load
pm.load_preset("vibrato", "fast_vibrato", module_instance, widget)

# Delete
pm.delete_preset("vibrato", "old_preset")
```

## Benefits

1. **Modular** - Just update JSON config to add preset support to new pages
2. **Flexible** - Saves any combination of module vars, widget state, and registry values
3. **User-friendly** - Clean UI with text input and keyboard support
4. **Persistent** - Presets are stored as readable JSON files
5. **Extensible** - Easy to add new features (categories, tags, export/import, etc.)
