# VK8M Plugin Integration: Technical Deep Dive

## Overview
This document details the complete journey of integrating the Roland VK-8M organ controller plugin into the modular UI system, including all challenges encountered, solutions implemented, and architectural insights gained.

## Initial Challenge: Making Plugin Appear on Device Page

### Goal
Add a VK-8M button to the device selection page that navigates to a dedicated VK-8M control page, similar to how the Vibrato Maker plugin works.

### Initial Assumption (Wrong)
The plugin system would automatically discover and register plugins, making them available on the device page. Just creating a plugin file would be enough.

### Reality Check
The device page (`pages/device_select.py`) loads buttons from a static JSON configuration file (`config/device_page_layout.json`). Plugins don't automatically appear - they must be explicitly added to this configuration.

### Solution 1: Device Page Configuration
Added VK-8M button to `device_page_layout.json`:
```json
{
    "id": 6,
    "img": "icons/quadverb.png",
    "label": "VK-8M",
    "plugin": "vk8m_main"
}
```

The `"plugin": "vk8m_main"` field is critical - it tells `device_select.py` to send a `("ui_mode", "vk8m_main")` message instead of loading a device.

## Challenge 2: Module Architecture Mismatch

### The Problem
The existing `module_base.py` page renderer was **hardcoded** to the vibrato plugin:
```python
from plugins import vibrato_plugin as mod
```

This meant only vibrato could use the module_base renderer. Any attempt to create a second plugin would fail.

### Root Cause Analysis
`module_base.py` was never designed to be generic. It had direct imports and references to vibrato-specific code:
- `mod.MODULE_ID`
- `mod.REGISTRY`
- `mod.BUTTONS`
- `mod.SLOT_TO_CTRL`

### Solution 2: Dynamic Module Reference System
Refactored `module_base.py` to use a dynamic module reference system:

**Before:**
```python
from plugins import vibrato_plugin as mod

# Direct references everywhere
showlog.info(f"[{mod.MODULE_ID}] Message")
registry = mod.REGISTRY
buttons = mod.BUTTONS
```

**After:**
```python
_ACTIVE_MODULE = None  # Global reference to current plugin module

def set_active_module(module_ref):
    """Called by plugins to register themselves with this page renderer."""
    global _ACTIVE_MODULE, _LOGTAG
    _ACTIVE_MODULE = module_ref
    module_id = getattr(module_ref, "MODULE_ID", "MODULE")
    _LOGTAG = module_id.upper()
    showlog.info(f"[MODULE_BASE] Active module set to: {_LOGTAG}")

def _get_module_attr(attr_name, default=None):
    """Get attribute from active module with fallback."""
    if _ACTIVE_MODULE is None:
        return default
    return getattr(_ACTIVE_MODULE, attr_name, default)

# Dynamic references everywhere
showlog.info(f"[{_get_module_attr('MODULE_ID', 'MODULE')}] Message")
registry = _get_module_attr("REGISTRY", {})
buttons = _get_module_attr("BUTTONS", [])
```

### Challenge 2.1: F-String Syntax Errors
**Problem:** Direct substitution caused nested quote issues:
```python
# SYNTAX ERROR - nested quotes
f"{_get_module_attr("MODULE_ID")}"
```

**Solution:** Extract variable before f-string:
```python
_mod_id = _get_module_attr("MODULE_ID", "MODULE")
showlog.debug(f"[{_mod_id}] Message")
```

Applied this pattern to ~6 locations throughout `module_base.py`.

## Challenge 3: Module Switching Timing

### The Problem
Both plugins were calling `set_active_module()` during `on_load()` at application startup:

**vibrato_plugin.py:**
```python
def on_load(self, app):
    import plugins.vibrato_plugin as vibrato_module
    vibrato_page.set_active_module(vibrato_module)  # Called at startup
```

**vk8m_plugin.py:**
```python
def on_load(self, app):
    import plugins.vk8m_plugin as vk8m_module
    vk8m_page.set_active_module(vk8m_module)  # Called at startup
```

**Result:** Whichever plugin loaded last won. VK8M loaded after vibrato, so when navigating to vibrato page, it showed VK8M data!

### Root Cause
Module switching was happening at the **wrong time** - during plugin discovery (startup) instead of during **page entry** (navigation).

### Solution 3: Move set_active_module() to Page Setup
**Removed from plugin on_load():**
```python
def on_load(self, app):
    # Note: set_active_module() is called by mode_manager when page is entered
    app.page_registry.register(self.page_id, vibrato_page, ...)
```

**Added to mode_manager page setup functions:**
```python
def _setup_vibrato(self):
    """Setup for vibrato mode."""
    from pages import module_base as vibrato
    import plugins.vibrato_plugin as vibrato_module
    
    # Set active module BEFORE init_page
    vibrato.set_active_module(vibrato_module)
    
    vibrato.init_page()
    unit_router.load_module("vibrato", vibrato.handle_hw_dial)

def _setup_vk8m(self):
    """Setup for VK8M mode."""
    from pages import module_base as vk8m_page
    import plugins.vk8m_plugin as vk8m_module
    
    # Set active module BEFORE init_page
    vk8m_page.set_active_module(vk8m_module)
    
    vk8m_page.init_page()
    unit_router.load_module("vk8m", vk8m_page.handle_hw_dial)
```

Now each page sets the correct active module when you navigate to it.

## Challenge 4: ModuleBase __init__() Signature

### The Problem
VK8M's `__init__()` was defined with parameters:
```python
def __init__(self, app=None, *args, **kwargs):
    super().__init__(app, *args, **kwargs)
```

But `module_base.py` instantiates modules with **no arguments**:
```python
# In _get_mod_instance()
_MOD_INSTANCE = ModuleClass()  # No arguments!
```

**Error:**
```
_get_mod_instance failed: __init__() takes 1 positional argument but 2 were given
```

### Root Cause
Copy-paste from a different codebase pattern. Vibrato's actual signature:
```python
def __init__(self):  # No parameters!
    super().__init__()
```

### Solution 4: Match Vibrato's Signature
```python
def __init__(self):
    super().__init__()
    
    # Get MIDI service from global registry instead of app parameter
    from system import service_registry
    midi_service = service_registry.get("midi")
    if midi_service and hasattr(midi_service, "send_message"):
        self._send_fn = midi_service.send_message
```

## Challenge 5: Blank Screen - The Renderer Hardcoding

### The Problem
After all previous fixes:
- ✅ Module switching worked correctly
- ✅ VK8M class instantiated without errors
- ✅ init_page() completed successfully
- ✅ Header text updated to "Roland VK-8M"
- ❌ **But the page was completely blank!**

### Investigation Process
Logs showed everything working:
```
[MODE_MGR] VK8M page initialized
[MODULE_BASE] Active module set to: VK8M
```

But no UI rendered. Checked:
1. ❓ Was `draw_ui()` being called? 
2. ❓ Were buttons defined correctly?
3. ❓ Were dials created?

### The Real Culprit: rendering/renderer.py
Found the smoking gun in `renderer.py` line 89:

```python
elif ui_mode in ("mixer", "vibrato"):  # VK8M NOT IN THIS LIST!
    page["draw_ui"](self.screen, offset_y=offset_y)
```

**The renderer had a hardcoded list of page IDs** that use the `draw_ui()` calling convention. VK8M wasn't in it, so the page never got drawn!

### Solution 5: Add VK8M to Renderer Lists
**Change 1 - Drawing logic:**
```python
elif ui_mode in ("mixer", "vibrato", "vk8m_main"):
    page["draw_ui"](self.screen, offset_y=offset_y)
```

**Change 2 - Header theming:**
```python
themed_pages = ("dials", "presets", "mixer", "vibrato", "vk8m_main", "module_presets")
```

**This was the critical fix** that made the page visible!

## Challenge 6: Logging API Mismatch

### The Problem
VK8M used `import showlog as log` and called:
```python
log.warn("[VK8M] No MIDI sender bound; dropped %s", b)
```

But `showlog.warn()` only accepts one argument (the full message string), not Python's standard logging format with `%s` placeholders.

**Error:**
```
warn() takes 1 positional argument but 2 were given
```

### Solution 6: Use F-Strings
```python
import showlog  # Not 'as log'

showlog.warn(f"[VK8M] No MIDI sender bound; dropped {b}")
```

Applied throughout the VK8M plugin.

## Challenge 7: Button Layout Definition

### The Problem
VK8M initially defined buttons as a dict (wrong):
```python
BUTTONS = {
    "1": {"label": "VIB OFF", "action": "vibrato_mode"}
}
```

But `module_base` expects a **list** (like vibrato):
```python
BUTTONS = [
    {"id": "1", "label": "S", "behavior": "transient"},
    {"id": "2", "label": "L", "behavior": "state"},
    # ... 10 buttons total
]
```

### Solution 7: Standard 10-Button Layout
```python
BUTTONS = [
    {"id": "1", "label": "VIB OFF", "behavior": "state"},
    {"id": "2", "label": "2", "behavior": "transient"},
    {"id": "5", "label": "5", "behavior": "transient", "action": "bypass_toggle"},
    {"id": "6", "label": "6", "behavior": "nav", "action": "store_preset"},
    {"id": "7", "label": "P", "behavior": "nav", "action": "presets"},
    {"id": "8", "label": "8", "behavior": "transient", "action": "mute_toggle"},
    {"id": "9", "label": "S", "behavior": "nav", "action": "save_preset"},
    {"id": "10", "label": "10", "behavior": "nav", "action": "device_select"},
]
```

This provides the standard plugin UI with 10 buttons in the left column.

## Final Architecture: How It All Works

### 1. Plugin Discovery (Startup)
```
core/app.py:_init_plugins()
  → pkgutil walks plugins/ directory
  → Finds vk8m_plugin.py
  → Instantiates VK8MPlugin class
  → Calls plugin.on_load(app)
    → Registers "vk8m_main" page_id with PageRegistry
    → Links to module_base as the renderer
```

### 2. Navigation Flow
```
User clicks VK-8M button on device page
  ↓
pages/device_select.py:handle_click()
  → Detects "plugin": "vk8m_main" in button data
  → Sends message: ("ui_mode", "vk8m_main")
  ↓
managers/mode_manager.py:switch_mode()
  → Matches new_mode == "vk8m_main"
  → Calls _setup_vk8m()
    ↓
    → Imports module_base and vk8m_plugin
    → Calls module_base.set_active_module(vk8m_module)
      → Sets _ACTIVE_MODULE = vk8m_module
      → Sets _LOGTAG = "VK8M"
    → Calls cc_registry.load_from_device("vk8m")
    → Calls module_base.init_page()
      → Creates PresetSaveUI overlay
      → Links dials to StateManager
    → Calls unit_router.load_module("vk8m", module_base.handle_hw_dial)
      → Routes hardware dial input to VK8M page
  ↓
rendering/renderer.py:render_full_frame()
  → Checks ui_mode == "vk8m_main"
  → Finds it in ("mixer", "vibrato", "vk8m_main") list
  → Calls page["draw_ui"](screen, offset_y=0)
    ↓
    pages/module_base.py:draw_ui()
      → Uses _ACTIVE_MODULE (currently vk8m_plugin)
      → Calls _get_module_attr("BUTTONS") → VK8M.BUTTONS
      → Calls _get_module_attr("SLOT_TO_CTRL") → VK8M.SLOT_TO_CTRL
      → Renders 10 buttons in left column
      → Renders 2 dials (Distortion, Reverb) in main grid
```

### 3. Hardware Interaction
```
Physical dial turned
  ↓
Hardware input → MIDI/CV message
  ↓
unit_router dispatches to "vk8m" handler
  ↓
module_base.handle_hw_dial(dial_id, value)
  → Calls _get_mod_instance() → VK8M() singleton
  → Calls instance.on_dial_change(dial_id, value)
    ↓
    VK8M.on_dial_change()
      → Updates self.dial_values[dial_id]
      → Calls _apply_distortion() or _apply_reverb()
        → Sends MIDI CC via self._send_fn
```

### 4. Button Interaction
```
Button pressed (e.g., Button 1)
  ↓
module_base.handle_button_event(btn_id)
  → Calls _get_mod_instance() → VK8M() singleton
  → Calls instance.on_button(btn_id)
    ↓
    VK8M.on_button("1")
      → Cycles through VIB_LABELS: OFF → V1 → V2 → V3 → C1 → C2 → C3
      → Updates button_states["1"]
      → Calls _sync_vib_label() to update button label
      → Calls _apply_vib_state() to send MIDI
        → vk.set_vibrato_on() + vk.set_vibrato_type()
```

### 5. Module Switching
```
Navigate from VK8M page to Vibrato page
  ↓
mode_manager.switch_mode("vibrato")
  → Calls _setup_vibrato()
    → Calls module_base.set_active_module(vibrato_module)
      → _ACTIVE_MODULE = vibrato_module  # Switched!
      → _LOGTAG = "VIBRATO"
    → Calls module_base.init_page()
    
Next draw_ui() call uses vibrato data:
  → _get_module_attr("BUTTONS") → Vibrato.BUTTONS
  → _get_module_attr("MODULE_ID") → "vibrato"
```

## Key Architectural Insights

### 1. The Page-Module Split
- **Page (module_base.py)**: Generic renderer, handles UI layout and input routing
- **Module (vk8m_plugin.py)**: Specific logic, handles state and MIDI output
- **Binding**: `set_active_module()` connects them dynamically

### 2. Singleton Pattern for Module Instances
`module_base.py` maintains a single instance of each module class:
```python
_MOD_INSTANCE = None

def _get_mod_instance():
    global _MOD_INSTANCE
    if _MOD_INSTANCE is not None:
        return _MOD_INSTANCE
    # Create instance once, reuse forever
    _MOD_INSTANCE = ModuleClass()
    return _MOD_INSTANCE
```

**Why?** State persistence - dial values, button states preserved across page switches.

### 3. The Renderer Bottleneck
The renderer has **hardcoded page lists** in multiple places:
- Line 89: Draw method selection
- Line 118: Header theming

**Implication:** Every new module-based plugin must be added to these lists. Not truly dynamic!

**Better Solution (Future):** Use page metadata from PageRegistry:
```python
page_info = self.page_registry.get(ui_mode)
if page_info.get("type") == "module":
    page["draw_ui"](self.screen, offset_y=offset_y)
```

### 4. The ModuleBase Contract
For a plugin to work with `module_base.py`, it must provide:

**Required Class Attributes:**
- `MODULE_ID`: String identifier (e.g., "vk8m")
- `BUTTONS`: List of button definitions
- `REGISTRY`: Dict of CC mappings (can be empty)
- `SLOT_TO_CTRL`: Dict mapping dial slots to control IDs

**Required Methods:**
- `__init__(self)`: No parameters!
- `on_button(self, btn_id: str)`: Handle button press
- `on_dial_change(self, dial_index: int, value: int)`: Handle dial change

**Optional Methods:**
- `export_state(self) -> dict`: Return state for presets
- `import_state(self, state: dict)`: Restore state from presets
- `on_init(self)`: Called after instance creation

## Files Modified

### Core Changes
1. **pages/module_base.py** (1044 lines)
   - Removed hardcoded `from plugins import vibrato_plugin as mod`
   - Added `_ACTIVE_MODULE` global and `set_active_module()` function
   - Added `_get_module_attr()` helper for dynamic attribute access
   - Fixed 6 f-string syntax errors by extracting variables

2. **managers/mode_manager.py** (497 lines)
   - Added `_setup_vk8m()` function (lines 439-461)
   - Added `vk8m_main` to mode switch handler (line 133)
   - Added `vk8m_main` to navigator record list (line 161)

3. **rendering/renderer.py** (156 lines)
   - Added `vk8m_main` to draw method check (line 89)
   - Added `vk8m_main` to themed pages list (line 118)

4. **pages/device_select.py** (200+ lines)
   - Added plugin field capture in `load_buttons()` (line 55)
   - Added plugin check in `handle_click()` (lines 169-173)

### Plugin Implementation
5. **plugins/vk8m_plugin.py** (205 lines)
   - Created VK8M class extending ModuleBase
   - Defined MODULE_ID, BUTTONS, REGISTRY, SLOT_TO_CTRL
   - Implemented `__init__()`, `on_button()`, `on_dial_change()`
   - Implemented `export_state()`, `import_state()` for presets
   - Created VK8MPlugin class for plugin registration
   - Fixed all logging to use `showlog` with f-strings

### Configuration
6. **config/device_page_layout.json**
   - Added VK-8M button definition with `"plugin": "vk8m_main"`

## Lessons Learned

### 1. Don't Assume - Verify
Early assumption that plugin system was fully dynamic was wrong. Multiple hardcoded lists existed throughout the codebase.

### 2. Follow the Existing Pattern Exactly
VK8M's `__init__(self, app=None)` didn't match Vibrato's `__init__(self)`. This cost significant debugging time.

### 3. Renderer is the Final Gatekeeper
Even with perfect setup, if the renderer doesn't know about your page, nothing renders. Always check the renderer!

### 4. Logging APIs Vary
`showlog` is not Python's standard logging module. It has different function signatures (no format args).

### 5. Dynamic Systems Still Have Static Points
While `module_base` is now "generic," the renderer still has hardcoded page lists. True plugin architecture would eliminate these.

## Future Improvements

### 1. Make Renderer Truly Dynamic
```python
# Instead of hardcoded lists, use page metadata
page_info = self.page_registry.get(ui_mode)
if page_info and page_info.get("renderer") == "module_base":
    page["draw_ui"](self.screen, offset_y=offset_y)
```

### 2. Auto-Generate Device Page Buttons
Plugin `on_load()` could register device page buttons:
```python
def on_load(self, app):
    app.device_page.add_button({
        "label": "VK-8M",
        "icon": "vk8m.png",
        "plugin": self.page_id
    })
```

### 3. Plugin Metadata System
```python
class VK8MPlugin(PluginBase):
    metadata = {
        "type": "controller",
        "renderer": "module_base",
        "device_page_button": True,
        "icon": "vk8m.png"
    }
```

### 4. Mode Manager Plugin Registration
Instead of hardcoded `_setup_vk8m()`, use plugin metadata:
```python
def switch_mode(self, new_mode):
    plugin = self.plugin_registry.get(new_mode)
    if plugin and plugin.metadata["renderer"] == "module_base":
        self._setup_module_page(plugin)
```

## Conclusion

The VK8M plugin integration revealed that while the system has a plugin architecture, it's not fully abstracted. Multiple hardcoded references exist in:
- Renderer (page lists)
- Mode Manager (page setup functions)
- Device Page (JSON configuration)

However, the successful integration proves the architecture is **extensible**. By following the established patterns and understanding the rendering pipeline, new plugins can be added systematically.

The key insight: **The plugin system is a hybrid** - dynamic discovery and instantiation, but static integration points for rendering and navigation. Understanding where these integration points are is critical for successful plugin development.
