# Unified Preset System Refactoring

## Overview
Consolidated device presets and module presets into a single unified system that handles both through one interface.

## Problem
Previously:
- Device presets used `pages/presets.py`
- Module presets (vibrato) used `pages/module_presets.py`
- Required duplicate initialization and rendering logic
- Two separate code paths for similar functionality

## Solution
Created `managers/preset_manager.py` with `UnifiedPresetManager` class that:
- Handles both device and module presets through a single interface
- Maintains current entity type ("device" or "module")
- Delegates to appropriate underlying page module
- Provides consistent initialization, drawing, and event handling

## Architecture

### New Module
**`managers/preset_manager.py`**
- `UnifiedPresetManager` class
- Methods:
  - `init_for_device(device_name, page_id)` - Initialize for device presets
  - `init_for_module(module_name, module_instance, widget_instance)` - Initialize for module presets
  - `draw(offset_y)` - Draw appropriate preset page
  - `handle_event(event, msg_queue)` - Handle events for appropriate preset page
  - `get_current_type()` - Get "device" or "module"
  - `get_current_name()` - Get entity name

### Modified Modules

**`managers/mode_manager.py`**
- Added `preset_manager: UnifiedPresetManager` instance
- Modified `_setup_presets()` to use `preset_manager.init_for_device()`
- Modified `_setup_module_presets()` to use `preset_manager.init_for_module()`
- Automatically retrieves module instance and widget from `module_base`

**`rendering/renderer.py`**
- Removed direct imports of `presets` and `module_presets`
- Added `preset_manager` parameter to `__init__()`
- Unified `draw_current_page()` to handle both "presets" and "module_presets" modes with single code path
- Uses `preset_manager.draw()` for both modes

**`core/app.py`**
- Pass `mode_manager.preset_manager` to `Renderer` during initialization
- Unified event handling for "presets" and "module_presets" modes
- Uses `preset_manager.handle_event()` for both modes

## Benefits
1. **Single Responsibility**: One manager handles all preset pages
2. **Reduced Duplication**: No repeated init/draw/event handling logic
3. **Easier Maintenance**: Changes to preset behavior only need to be made in one place
4. **Extensibility**: Easy to add new preset types (tremolo, etc.) without duplicating code
5. **Cleaner Architecture**: Clear separation between preset coordination and page implementation

## Usage Example

### Device Presets
```python
# Automatically called when switching to device preset page
mode_manager.preset_manager.init_for_device("QUADRAVERB", "01")
```

### Module Presets (Vibrato)
```python
# Automatically called when switching to module preset page
mode_manager.preset_manager.init_for_module("vibrato", vibrato_instance, widget)
```

### Rendering (Both Types)
```python
# Single code path handles both
preset_manager.draw(offset_y=0)
```

## Files Changed
- **New**: `managers/preset_manager.py`
- **Modified**: `managers/mode_manager.py`
- **Modified**: `rendering/renderer.py`
- **Modified**: `core/app.py`

## Testing
To test the unified system:
1. Navigate to device preset page (works with Quadraverb, PSR-36, etc.)
2. Navigate to vibrato page, press "P" button to open vibrato presets
3. Verify both preset types display and function correctly
4. Verify preset loading/saving works for both types

## Future Enhancements
- Add support for tremolo module presets (when implemented)
- Consider adding preset type validation
- Add preset change notifications/callbacks
- Cache preset lists to reduce file I/O
