# VK8M Preset Implementation Postmortem
## Complete Issue Log and Analysis

**Date:** November 2, 2025  
**Duration:** ~7 hours  
**Goal:** Add preset save/load functionality to VK8M plugin  
**Outcome:** Eventually successful, but unnecessarily complex

---

## Executive Summary

What should have been a 15-minute task to add preset support to a new plugin turned into a 7-hour debugging nightmare due to:
1. **Inconsistent plugin architecture** - Multiple ways to do the same thing
2. **Hidden dependencies** - Critical initialization order not documented
3. **Complex preset system** - 620-line preset_manager.py with edge cases
4. **Lack of examples** - No simple reference implementation
5. **Silent failures** - Code failing without clear error messages

---

## Issue Timeline and Root Cause Analysis

### Issue #1: Text Input Not Working in VK8M Preset Save Dialog

**Symptom:** When pressing button 9 to save a preset in VK8M, the text input dialog appeared but keyboard input did nothing. The same dialog worked perfectly in Vibrato Maker.

**Investigation:**
- Vibrato Maker preset save dialog accepted keyboard input normally
- VK8M preset save dialog displayed but was unresponsive to typing
- Both used the same `PresetSaveUI` component

**Root Cause:**
File: `core/app.py` line 787

```python
if ui_mode in ("vibrato",):  # Only "vibrato" checked
    page_obj.on_keyboard_input(event)
```

The remote keyboard input routing was hardcoded to only check for "vibrato" mode. VK8M's page_id is "vk8m_main", which was never added to this check.

**Fix Applied:**
```python
if ui_mode in ("vibrato", "vk8m_main"):
    page_obj.on_keyboard_input(event)
```

**Why This Is Hacky:**
- **Hardcoded mode list**: Every new plugin requires manually updating this list
- **No centralized registry**: No way for plugins to declare "I need keyboard input"
- **Easy to forget**: Plugin authors won't know to add their page_id here
- **Breaks encapsulation**: Core app code shouldn't know about specific plugins

**Proper Solution:**
1. Create a plugin capability registry system:
```python
# In Plugin base class
class Plugin:
    capabilities = {
        "keyboard_input": False,
        "preset_support": False,
        "custom_widget": False
    }
```

2. In app.py, check capabilities dynamically:
```python
if page_obj and hasattr(page_obj, 'supports_keyboard_input') and page_obj.supports_keyboard_input():
    page_obj.on_keyboard_input(event)
```

3. Plugins declare capabilities in their metadata:
```python
class VK8MPlugin(Plugin):
    supports_keyboard_input = True
```

---

### Issue #2: Presets Saved But Didn't Appear in List

**Symptom:** After fixing text input, presets could be saved (JSON files created), but pressing button 7 to load presets showed an empty list. Button state indicated success (green LED), but no presets visible.

**Investigation:**
- Files existed in `config/presets/vk8m/*.json`
- `save_preset()` returned `True`
- `get_page_config()` was returning `None` for VK8M
- Auto-discovery was being skipped

**Root Cause:**
File: `preset_manager.py` line 86

```python
registry = getattr(module_instance, 'REGISTRY', {}) or {}
if registry:  # Empty dict {} is falsy in Python!
    # Auto-discovery happens here
    result = self._auto_discover_from_registry(module_instance, registry)
```

VK8M had `REGISTRY = {}` (empty dict). The check `if registry:` treated empty dict as `False`, so auto-discovery never ran. This meant `get_page_config()` returned `None`, so `save_preset()` returned `False`.

**Why Empty REGISTRY:**
VK8M uses direct SysEx commands rather than the CV/DAC system that other plugins use. The REGISTRY was meant for CV routing, so VK8M left it empty. But the preset system incorrectly assumed empty REGISTRY = no preset support.

**Fix Applied:**
```python
# Remove the truthiness check - let it run even with empty dict
result = self._auto_discover_from_registry(module_instance, registry)
```

Added `PRESET_VARS` class attribute to VK8M:
```python
PRESET_VARS = ["button_states", "dial_values"]
```

Modified `_auto_discover_from_registry()` to check `PRESET_VARS` as fallback when REGISTRY is empty.

**Why This Is Hacky:**
- **Falsy check bug**: Using `if registry:` for empty dict is a Python gotcha
- **Dual systems**: REGISTRY for CV routing AND PRESET_VARS for presets creates confusion
- **Not discoverable**: How would a plugin author know to add PRESET_VARS?
- **Documentation gap**: No docs explaining when to use REGISTRY vs PRESET_VARS

**Proper Solution:**
1. Separate preset configuration from REGISTRY:
```python
class ModuleBase:
    PRESET_CONFIG = {
        "variables": ["var1", "var2"],  # Explicit list
        "widget_state": True,  # Auto-detect widget state
        "button_states": True  # Auto-save button states
    }
```

2. Make it required and validated:
```python
def __init_subclass__(cls):
    if not hasattr(cls, 'PRESET_CONFIG'):
        raise AttributeError(f"{cls.__name__} must define PRESET_CONFIG")
```

3. Update documentation with clear examples for each use case

---

### Issue #3: Presets Loaded But Were Immediately Cleared

**Symptom:** After fixing auto-discovery, presets would load (logs showed variables being restored), but immediately upon returning to the VK8M page, all state was reset to defaults.

**Investigation:**
- `load_preset()` successfully restored `button_states` and `dial_values`
- `on_preset_loaded()` was called
- But when navigating back to VK8M page, everything was reset
- The module instance was being cleared

**Root Cause:**
File: `pages/module_base.py` line 54

```python
def set_active_module(new_module_class):
    global _ACTIVE_MODULE, _MOD_INSTANCE
    
    # ALWAYS clear the instance, even if same module!
    _MOD_INSTANCE = None
    _ACTIVE_MODULE = new_module_class
```

Every call to `set_active_module()` cleared `_MOD_INSTANCE`, even when returning to the same module. The flow was:
1. Load preset (module instance has loaded state)
2. Return from preset page → `set_active_module(VK8M)` called
3. Instance cleared
4. New instance created with INIT_STATE defaults
5. Loaded preset state lost

**Fix Applied:**
```python
def set_active_module(new_module_class):
    global _ACTIVE_MODULE, _MOD_INSTANCE
    
    # Get current module ID
    new_module_id = getattr(new_module_class, 'MODULE_ID', None)
    current_module_id = getattr(_ACTIVE_MODULE, 'MODULE_ID', None) if _ACTIVE_MODULE else None
    
    # Only clear if switching to a DIFFERENT module
    if new_module_id != current_module_id:
        _MOD_INSTANCE = None
        showlog.info(f"[MODULE_BASE] Switching modules, clearing instance")
    else:
        showlog.info(f"[MODULE_BASE] Same module ({new_module_id}), preserving instance")
    
    _ACTIVE_MODULE = new_module_class
```

**Why This Is Hacky:**
- **Over-aggressive clearing**: No reason to clear instance when staying in same module
- **State management confusion**: Multiple places track module state (_MOD_INSTANCE, _ACTIVE_MODULE, _BUTTON_STATES)
- **Navigation side effects**: Page navigation shouldn't destroy state
- **No state lifecycle**: No clear pattern for when state should persist vs reset

**Proper Solution:**
1. Implement proper state lifecycle:
```python
class ModuleStateManager:
    def __init__(self):
        self._instances = {}  # module_id -> instance
        self._state_snapshots = {}  # module_id -> state
    
    def get_or_create(self, module_class):
        module_id = module_class.MODULE_ID
        if module_id not in self._instances:
            self._instances[module_id] = module_class()
        return self._instances[module_id]
    
    def clear_module(self, module_id):
        # Explicitly clear when needed
        if module_id in self._instances:
            del self._instances[module_id]
```

2. Make state persistence explicit:
```python
@property
def should_persist_on_navigation(self):
    return True  # Override per module
```

3. Add state snapshot/restore:
```python
def save_state_snapshot(self):
    return {"button_states": self.button_states, ...}

def restore_state_snapshot(self, snapshot):
    self.button_states = snapshot.get("button_states", {})
```

---

### Issue #4: _BUTTON_STATES Not Syncing After Preset Load

**Symptom:** After preset loaded, hardware state was correct (VK-8M responded to loaded settings), but UI still showed old button labels and states.

**Investigation:**
- `module_instance.button_states` was correctly restored from preset
- Hardware commands were sent successfully
- But UI buttons still showed old labels (e.g., "OFF" instead of "V2")
- Module has `button_states` dict, but rendering reads from `module_base._BUTTON_STATES`

**Root Cause:**
File: `pages/module_base.py` line 43 (global variable)

```python
_BUTTON_STATES = {}  # Global UI state tracking
```

There are TWO separate button state dictionaries:
1. `module_instance.button_states` - The module's internal state
2. `module_base._BUTTON_STATES` - Global UI rendering state

When preset loaded, it only updated #1. The UI rendering code reads from #2, which was never updated.

**Why Two Dictionaries Exist:**
- `_BUTTON_STATES` is global and persists across module switches
- `module_instance.button_states` is instance-specific
- No synchronization between them after preset load

**Fix Applied:**
Added sync method to VK8M plugin:
```python
def _sync_button_states_to_ui(self):
    """Sync module's button_states to module_base's _BUTTON_STATES for UI rendering."""
    from pages import module_base
    for btn_id, state_idx in self.button_states.items():
        module_base._BUTTON_STATES[btn_id] = state_idx
```

Called in `on_preset_loaded()`:
```python
def on_preset_loaded(self, variables: dict):
    self._sync_button_states_to_ui()  # Sync to UI
    self._apply_all_button_states()   # Send to hardware
```

**Why This Is Hacky:**
- **Dual state tracking**: Two sources of truth for same data
- **Manual sync required**: Easy to forget to sync after state changes
- **Import from submodule**: Plugins shouldn't import from pages/module_base
- **Global state pollution**: _BUTTON_STATES is shared across all modules
- **No automatic sync**: System doesn't ensure consistency

**Proper Solution:**
1. Eliminate dual state - single source of truth:
```python
class ModuleBase:
    @property
    def button_states(self):
        # UI always reads from module instance
        return self._button_states
    
    @button_states.setter
    def button_states(self, value):
        self._button_states = value
        self._mark_ui_dirty()  # Trigger redraw
```

2. Use observer pattern for state changes:
```python
class ButtonStateManager:
    def __init__(self):
        self._observers = []
    
    def set_button_state(self, btn_id, state):
        self._states[btn_id] = state
        self._notify_observers(btn_id, state)
```

3. Make rendering read directly from module:
```python
def render_button(btn_id):
    module = get_active_module()
    state_idx = module.button_states.get(btn_id, 0)
    label = get_button_label(btn_id, state_idx)
```

---

### Issue #5: Dial Positions Not Updating After Preset Load

**Symptom:** After preset loaded, dials on screen didn't move to show loaded values. Hardware received correct values, but visual dials stayed in old positions.

**Investigation:**
- `on_preset_loaded()` tried to call `_sync_ui_dials()` to update dial positions
- But `dialhandlers.dials` was `None` during preset load
- Dials only exist when the VK8M page is actively rendered
- Preset loads while still on preset selection page

**Root Cause:**
Timing issue - trying to update UI elements that don't exist yet:

```python
def on_preset_loaded(self):
    self._sync_ui_dials()  # Tries to update dials
    # But we're on preset page, not VK8M page!
    # dialhandlers.dials doesn't exist yet
```

The dial objects are created during `module_base.draw_ui()`, not during module initialization. When preset loads, you're still viewing the preset list page, so VK8M's dials haven't been created yet.

**Initial Wrong Fix Attempt:**
Tried to manually update dial positions in `on_preset_loaded()`:
```python
def _sync_ui_dials(self):
    dials = dialhandlers.dials
    dials[0].set_value(self.dial_values[0])  # FAILS - dials is None
```

**Why This Failed:**
- Dials don't exist until page is drawn
- Can't update UI from preset load callback
- Wrong architectural layer - preset loading shouldn't touch UI

**Actual Root Cause - Deeper Issue:**
VK8M was using raw arrays (`dial_values = [64, 64]`) instead of the REGISTRY system that other plugins use. The REGISTRY system has built-in dial synchronization via `_sync_module_state_to_dials()` which runs AFTER returning to the page when dials exist.

**Proper Fix Applied:**
Changed VK8M to use REGISTRY like Vibrato:

```python
# Before - manual array tracking
REGISTRY = {}
PRESET_VARS = ["button_states", "dial_values"]

def __init__(self):
    self.dial_values = [64, 64]

def on_dial_change(self, label, value):
    self.dial_values[0] = value  # Manual indexing

# After - REGISTRY system
REGISTRY = {
    "vk8m": {
        "type": "module",
        "01": {
            "label": "Distortion",
            "range": [0, 127],
            "type": "raw",
            "default_slot": 1,
            "variable": "distortion_value",
        },
        "05": {
            "label": "Reverb",
            "range": [0, 127],
            "type": "raw",
            "default_slot": 5,
            "variable": "reverb_value",
        }
    }
}

def __init__(self):
    self.distortion_value = 64
    self.reverb_value = 64

def on_dial_change(self, label, value):
    if label == "Distortion":
        self.distortion_value = value
```

Now `preset_manager` auto-discovers `distortion_value` and `reverb_value` from REGISTRY, and `module_base._sync_module_state_to_dials()` automatically syncs dials when returning to page.

**Why This Is Hacky:**
- **Not documented**: No guidance on when to use REGISTRY vs manual arrays
- **Easy to do wrong**: VK8M initially took the manual approach
- **Hidden magic**: `_sync_module_state_to_dials()` only works with REGISTRY
- **Inconsistent examples**: Different plugins use different approaches
- **No validation**: System doesn't warn if you're doing it wrong

**Proper Solution:**
1. Make REGISTRY mandatory and validated:
```python
class ModuleBase:
    def __init_subclass__(cls):
        if not hasattr(cls, 'REGISTRY') or not cls.REGISTRY:
            raise ValueError(f"{cls.__name__} must define REGISTRY")
        
        # Validate structure
        cls._validate_registry()
```

2. Document the pattern clearly:
```markdown
# Plugin Dial Variables - REQUIRED PATTERN

Every dial MUST be linked to an instance variable via REGISTRY:

```python
REGISTRY = {
    "module_name": {
        "type": "module",
        "01": {  # Slot number
            "label": "Parameter Name",
            "variable": "instance_variable_name",  # REQUIRED
            "range": [min, max],
            "type": "raw"
        }
    }
}

def __init__(self):
    # Initialize the variable
    self.instance_variable_name = default_value
```

This pattern ensures:
- Automatic preset save/load
- Automatic dial synchronization
- State persistence across navigation
```

3. Add auto-sync hook that's always called:
```python
def return_to_module_page(module_class):
    # After dials are created, always sync
    instance = get_module_instance(module_class)
    if hasattr(instance, 'on_page_shown'):
        instance.on_page_shown()  # Hook for post-navigation sync
```

---

### Issue #6: Widget (DrawBar) State Not Restoring

**Symptom:** After preset load, button states and dial positions restored correctly, but the DrawBar widget sliders didn't move to saved positions.

**Investigation:**
- Preset JSON contained `"widget_state": {"bar_values": [0,0,0,0,0,3,2,1,0]}`
- `preset_manager.load_preset()` read widget_state successfully
- But DrawBar sliders stayed in old positions

**Root Cause:**
File: `preset_manager.py` line 466

```python
if hasattr(widget, 'set_from_state') and callable(widget.set_from_state):
    # VibratoField expects: set_from_state(low_norm, high_norm, fade_ms, emit=True)
    if 'low_norm' in widget_state_data and 'high_norm' in widget_state_data:
        widget.set_from_state(...)  # Only called for VibratoField
        # DrawBarWidget has set_from_state() but it's never called!
```

The code checked if widget has `set_from_state()`, but then ONLY called it if the data matched VibratoField's specific structure (`low_norm`, `high_norm`, `fade_ms`). 

DrawBarWidget has `set_from_state(**kwargs)` that takes `bar_values`, but since the data didn't have VibratoField's keys, the method was never called.

The fallback was `setattr()`:
```python
else:
    for state_name, value in widget_state_data.items():
        setattr(widget, state_name, value)
```

But `setattr(widget, "bar_values", [...])` doesn't trigger the widget's internal update logic. You need to call `set_from_state()` which updates the internal `bars` array and marks dirty.

**Fix Applied:**
```python
if hasattr(widget, 'set_from_state') and callable(widget.set_from_state):
    # VibratoField expects specific positional args
    if 'low_norm' in widget_state_data and 'high_norm' in widget_state_data:
        widget.set_from_state(
            widget_state_data['low_norm'],
            widget_state_data['high_norm'],
            widget_state_data['fade_ms'],
            emit=False
        )
    else:
        # Other widgets (like DrawBarWidget) use **kwargs
        widget.set_from_state(**widget_state_data)
```

**Why This Is Hacky:**
- **Hardcoded widget types**: Code assumes only VibratoField exists
- **Positional vs kwargs**: VibratoField uses positional args, DrawBar uses kwargs
- **No interface contract**: No defined interface for widget state methods
- **Easy to break**: Adding new widget type requires modifying preset_manager
- **Not extensible**: Widget authors must study preset_manager code to understand requirements

**Proper Solution:**
1. Define widget interface protocol:
```python
class WidgetProtocol(Protocol):
    def get_state(self) -> dict:
        """Return widget state as dict."""
        ...
    
    def set_state(self, state: dict) -> None:
        """Restore widget state from dict."""
        ...
```

2. Standardize on dict-based state:
```python
# VibratoField should use dict too
def get_state(self) -> dict:
    return {
        "low_norm": self.low_norm,
        "high_norm": self.high_norm,
        "fade_ms": self.fade_ms
    }

def set_state(self, state: dict) -> None:
    self.low_norm = state.get("low_norm", 0.0)
    self.high_norm = state.get("high_norm", 1.0)
    self.fade_ms = state.get("fade_ms", 0)
    self._apply_changes()
```

3. Preset manager uses standardized interface:
```python
if hasattr(widget, 'set_state'):
    widget.set_state(widget_state_data)
else:
    # Fallback for legacy widgets
    for key, value in widget_state_data.items():
        setattr(widget, key, value)
```

4. Add validation:
```python
def __init_subclass__(cls):
    if cls.is_custom_widget:
        required_methods = ['get_state', 'set_state']
        for method in required_methods:
            if not hasattr(cls, method):
                raise NotImplementedError(
                    f"{cls.__name__} must implement {method}()"
                )
```

---

## Systemic Problems Identified

### 1. Lack of Plugin Development Documentation

**Problem:** No comprehensive guide explaining the plugin architecture, required patterns, or common pitfalls.

**Evidence:**
- VK8M initially used manual array tracking instead of REGISTRY
- No documentation explaining PRESET_VARS vs REGISTRY
- No examples showing correct implementation patterns
- Plugin authors left to reverse-engineer from existing code

**Impact:** 7-hour implementation for what should be a 15-minute task

**Solution:**
Create comprehensive plugin development guide:

```markdown
# Plugin Development Guide

## Required Components

### 1. REGISTRY (REQUIRED)
Every module MUST define REGISTRY linking dial slots to instance variables:

```python
REGISTRY = {
    "module_id": {
        "type": "module",
        "01": {  # Slot number (1-8)
            "label": "Display Name",
            "variable": "instance_var",  # Links to self.instance_var
            "range": [0, 127],
            "type": "raw"
        }
    }
}
```

### 2. Instance Variables (REQUIRED)
Initialize all variables referenced in REGISTRY:

```python
def __init__(self):
    super().__init__()
    self.instance_var = default_value
```

### 3. Preset Support (AUTOMATIC)
Presets work automatically if you follow REGISTRY pattern:
- Variables auto-discovered from REGISTRY
- Save/load handled by preset_manager
- Dial sync happens automatically

### 4. Custom Widget (OPTIONAL)
If your module has a custom widget:

```python
CUSTOM_WIDGET = {
    "class": "WidgetClassName",
    "path": "widgets.widget_file",
    "grid_size": [width, height]
}

class YourWidget:
    def get_state(self) -> dict:
        return {"key": self.value}
    
    def set_state(self, state: dict) -> None:
        self.value = state.get("key", default)
        self.mark_dirty()
```

### 5. Button States
Multi-state buttons require button_states dict:

```python
def __init__(self):
    self.button_states = {
        "1": 0,  # Button ID -> state index
        "2": 0
    }

BUTTONS = [
    {
        "id": "1",
        "label": "BTN1",
        "states": ["OFF", "ON", "HIGH"]  # State 0, 1, 2
    }
]
```

## Common Pitfalls

### ❌ DON'T: Use manual arrays
```python
self.dial_values = [64, 64]  # Hard to maintain
```

### ✅ DO: Use REGISTRY variables
```python
self.distortion_value = 64
self.reverb_value = 64
```

### ❌ DON'T: Hardcode plugin names in core
```python
if ui_mode in ("vibrato",):  # Breaks for new plugins
```

### ✅ DO: Use capability flags
```python
class Plugin:
    supports_keyboard_input = True
```

## Testing Checklist

Before submitting a plugin:
- [ ] REGISTRY defined with all dial slots
- [ ] Instance variables initialized
- [ ] Save preset works (creates JSON file)
- [ ] Load preset works (restores all state)
- [ ] Dials update after preset load
- [ ] Button labels update after preset load
- [ ] Widget state restores (if applicable)
- [ ] Hardware responds to loaded settings
```

### 2. Complex Preset System

**Problem:** `preset_manager.py` is 620 lines with multiple code paths, edge cases, and special handling for different widget types.

**Evidence:**
- Different handling for VibratoField vs other widgets
- Auto-discovery from REGISTRY OR PRESET_VARS
- Button state syncing logic scattered across files
- Special cases for vibrato start/stop
- Dual save paths (variables + button_states)

**Impact:**
- Hard to understand
- Easy to break
- Difficult to extend
- Requires deep knowledge to debug

**Solution:**
Refactor into smaller, focused components:

```python
# preset_config.py - Configuration discovery
class PresetConfigDiscovery:
    def discover(self, module_instance) -> PresetConfig:
        """Single path to discover preset configuration."""
        pass

# preset_serializer.py - Save/load logic
class PresetSerializer:
    def serialize(self, module_instance) -> dict:
        """Serialize module state to dict."""
        pass
    
    def deserialize(self, data: dict, module_instance) -> None:
        """Restore module state from dict."""
        pass

# widget_state_handler.py - Widget-specific logic
class WidgetStateHandler:
    def save_widget_state(self, widget) -> dict:
        pass
    
    def restore_widget_state(self, widget, state: dict) -> None:
        pass

# preset_manager.py - Orchestration only
class PresetManager:
    def __init__(self):
        self.config_discovery = PresetConfigDiscovery()
        self.serializer = PresetSerializer()
        self.widget_handler = WidgetStateHandler()
    
    def save_preset(self, name: str, module) -> bool:
        config = self.config_discovery.discover(module)
        data = self.serializer.serialize(module, config)
        return self._write_file(name, data)
```

### 3. Global State Management

**Problem:** Multiple global variables tracking module state:
- `_ACTIVE_MODULE` - Current module class
- `_MOD_INSTANCE` - Current module instance
- `_BUTTON_STATES` - UI button states
- `_ACTIVE_WIDGETS` - Widget instances
- `_SLOT_META` - Dial metadata

**Evidence:**
- State scattered across module_base.py globals
- No clear ownership or lifecycle
- Manual synchronization required
- Easy to get out of sync

**Impact:**
- State corruption bugs (like button states not syncing)
- Memory leaks (old instances not cleaned up)
- Navigation bugs (state cleared unexpectedly)
- Hard to test (global state)

**Solution:**
Centralized state manager:

```python
class ModuleStateManager:
    def __init__(self):
        self._instances: Dict[str, ModuleBase] = {}
        self._button_states: Dict[str, Dict[str, int]] = {}
        self._active_module_id: Optional[str] = None
    
    def get_instance(self, module_class) -> ModuleBase:
        """Get or create module instance."""
        module_id = module_class.MODULE_ID
        if module_id not in self._instances:
            self._instances[module_id] = module_class()
        return self._instances[module_id]
    
    def switch_to(self, module_class) -> ModuleBase:
        """Switch active module, preserving old instance."""
        old_id = self._active_module_id
        new_id = module_class.MODULE_ID
        
        if old_id and old_id != new_id:
            # Save snapshot of old module
            old_instance = self._instances.get(old_id)
            if old_instance:
                self._save_state_snapshot(old_id, old_instance)
        
        self._active_module_id = new_id
        return self.get_instance(module_class)
    
    def get_button_states(self, module_id: str) -> Dict[str, int]:
        """Get button states for module (single source of truth)."""
        return self._button_states.get(module_id, {})
    
    def set_button_state(self, module_id: str, btn_id: str, state: int):
        """Update button state (triggers UI update)."""
        if module_id not in self._button_states:
            self._button_states[module_id] = {}
        self._button_states[module_id][btn_id] = state
        self._notify_ui_update(module_id, btn_id, state)

# Usage
state_manager = ModuleStateManager()

def switch_page(module_class):
    instance = state_manager.switch_to(module_class)
    render_module_page(instance)
```

### 4. No Plugin Validation

**Problem:** Plugins can be loaded with missing or incorrect configuration, leading to runtime errors instead of startup errors.

**Evidence:**
- VK8M worked with empty REGISTRY (wrong approach)
- No validation that variables in REGISTRY exist on instance
- No check that CUSTOM_WIDGET class exists
- Widget state methods not verified

**Impact:**
- Bugs discovered during use, not at startup
- Silent failures (missing methods just skip)
- Hard to debug (error far from cause)

**Solution:**
Add plugin validation on load:

```python
class PluginValidator:
    def validate(self, plugin_class) -> List[ValidationError]:
        errors = []
        
        # Check required attributes
        required = ['MODULE_ID', 'REGISTRY', 'BUTTONS']
        for attr in required:
            if not hasattr(plugin_class, attr):
                errors.append(f"Missing required attribute: {attr}")
        
        # Validate REGISTRY structure
        registry = getattr(plugin_class, 'REGISTRY', {})
        if not registry:
            errors.append("REGISTRY cannot be empty")
        
        for slot_key, slot_data in self._get_registry_slots(registry):
            var_name = slot_data.get('variable')
            if not var_name:
                errors.append(f"Slot {slot_key} missing 'variable' field")
        
        # Validate instance can be created
        try:
            instance = plugin_class()
        except Exception as e:
            errors.append(f"Cannot instantiate: {e}")
            return errors
        
        # Validate variables exist
        for slot_key, slot_data in self._get_registry_slots(registry):
            var_name = slot_data.get('variable')
            if var_name and not hasattr(instance, var_name):
                errors.append(
                    f"Slot {slot_key} references undefined variable '{var_name}'"
                )
        
        # Validate widget if defined
        widget_config = getattr(plugin_class, 'CUSTOM_WIDGET', None)
        if widget_config:
            widget_class = self._load_widget_class(widget_config)
            if not widget_class:
                errors.append(f"Cannot load widget: {widget_config}")
            elif not hasattr(widget_class, 'get_state'):
                errors.append(f"Widget missing get_state() method")
        
        return errors

# In plugin loader
validator = PluginValidator()
errors = validator.validate(VK8M)
if errors:
    raise PluginValidationError(
        f"Plugin {VK8M.MODULE_ID} validation failed:\n" + 
        "\n".join(f"  - {e}" for e in errors)
    )
```

### 5. Inconsistent Naming and Patterns

**Problem:** Different plugins use different patterns for the same functionality.

**Evidence:**
- Vibrato uses REGISTRY with variables
- VK8M initially used dial_values array
- Some use on_dial_change, others use property setters
- Button handling varies (methods vs on_button callback)
- Widget state: get_state vs set_from_state vs set_state

**Impact:**
- No "one way" to do things
- Copy-paste from wrong example
- Maintenance nightmare
- Steeper learning curve

**Solution:**
Standardize and enforce patterns:

```python
# Standard plugin template
class StandardModulePlugin(ModuleBase):
    """
    Standard module template - copy this to create new plugins.
    """
    
    # Required: Unique module identifier
    MODULE_ID = "module_name"
    
    # Required: Registry linking dials to variables
    REGISTRY = {
        "module_name": {
            "type": "module",
            "01": {
                "label": "Parameter 1",
                "variable": "param1_value",
                "range": [0, 127],
                "type": "raw"
            }
        }
    }
    
    # Required: Initial state
    INIT_STATE = {
        "dials": [64, 0, 0, 0, 0, 0, 0, 0],
        "buttons": {"1": 0, "2": 0}
    }
    
    # Required: Button definitions
    BUTTONS = [
        {"id": "1", "label": "BTN1", "states": ["OFF", "ON"]},
        {"id": "7", "label": "P", "behavior": "nav", "action": "presets"}
    ]
    
    def __init__(self):
        super().__init__()
        # Initialize all REGISTRY variables
        self.param1_value = 64
        
        # Initialize button states
        self.button_states = {"1": 0, "2": 0}
    
    # Required: Dial change handler
    def on_dial_change(self, label: str, value: int):
        """Handle dial changes."""
        if label == "Parameter 1":
            self.param1_value = value
            self._apply_param1(value)
    
    # Required: Button handler (if multi-state buttons)
    def on_button(self, btn_id: str, state_index: int, state_data: dict):
        """Handle button press."""
        self.button_states[btn_id] = state_index
        if btn_id == "1":
            self._apply_button1_state(state_index)
    
    # Optional: Preset load hook
    def on_preset_loaded(self, variables: dict):
        """Called after preset restored - apply to hardware."""
        self._sync_button_states_to_ui()
        self._apply_all_button_states()
        self._apply_param1(self.param1_value)
    
    # Private: Hardware control methods
    def _apply_param1(self, value: int):
        # Send to hardware
        pass
    
    def _apply_button1_state(self, state: int):
        # Send to hardware
        pass
    
    def _apply_all_button_states(self):
        # Send all button states to hardware
        pass
    
    def _sync_button_states_to_ui(self):
        # Sync to module_base._BUTTON_STATES
        from pages import module_base
        for btn_id, state in self.button_states.items():
            module_base._BUTTON_STATES[btn_id] = state

# Enforce with linter
# plugin_linter.py
def check_plugin_structure(plugin_class):
    required_methods = [
        'on_dial_change',
        'on_button',
        'on_preset_loaded'
    ]
    for method in required_methods:
        if not hasattr(plugin_class, method):
            raise StructureError(f"Missing required method: {method}")
```

---

## Recommendations

### Immediate Actions (Fix Current System)

1. **Add Plugin Development Guide**
   - Document REGISTRY pattern
   - Provide working examples
   - Explain common pitfalls
   - Create checklist for new plugins

2. **Fix preset_manager.py**
   - Remove hardcoded widget type checks
   - Standardize on dict-based widget state
   - Add better error messages
   - Log what's being saved/restored

3. **Add Validation**
   - Validate plugins on load
   - Check REGISTRY completeness
   - Verify variables exist
   - Test widget state methods

4. **Eliminate Dual State**
   - Merge _BUTTON_STATES into module instances
   - Make rendering read from module
   - Remove global state variables
   - Use proper state manager

5. **Document core/app.py Requirements**
   - Explain keyboard input routing
   - Document how to add new page types
   - Make it discoverable from plugin metadata

### Long-term Refactoring (Fix Architecture)

1. **Plugin System v2.0**
   - Capability-based plugin registration
   - Standardized interfaces (Protocol classes)
   - Automatic validation on load
   - Template generator for new plugins

2. **State Management Refactor**
   - Centralized ModuleStateManager
   - Single source of truth for all state
   - Proper lifecycle management
   - State snapshots for undo/redo

3. **Preset System Refactor**
   - Break apart preset_manager.py
   - Plugin-defined serialization
   - Versioned preset format
   - Migration system for format changes

4. **Widget System Standardization**
   - Required interface (get_state/set_state)
   - Base widget class with defaults
   - Widget validation on registration
   - Better widget lifecycle hooks

5. **Testing Infrastructure**
   - Unit tests for each plugin
   - Integration tests for preset system
   - Mock hardware for testing
   - Plugin validation in CI/CD

---

## Lessons Learned

### What Went Wrong

1. **Assumed REGISTRY was optional** - Led to empty dict approach
2. **No documentation** - Had to reverse-engineer from Vibrato
3. **Silent failures** - Code returned False without explanation
4. **Complex codebase** - 620-line preset_manager with many code paths
5. **Global state** - Multiple sources of truth caused sync issues
6. **No validation** - Errors discovered at runtime, not startup
7. **Hardcoded logic** - Core code knew about specific plugins

### What Worked

1. **REGISTRY pattern** - Once properly implemented, everything just worked
2. **_sync_module_state_to_dials()** - Automatic dial sync after preset load
3. **Widget get_state/set_state** - Clean interface for widget persistence
4. **Preset JSON format** - Clear, debuggable, version-controllable

### Key Insights

1. **Documentation is critical** - Save 7 hours with 30 minutes of docs
2. **Validation saves time** - Catch errors at startup, not during use
3. **Single source of truth** - Dual state tracking caused 2+ hours of bugs
4. **Explicit is better** - Auto-discovery is clever but hard to debug
5. **Fail loudly** - Silent failures waste hours of debugging time

---

## Action Items

### For Next Plugin (Immediate)

- [ ] Copy Vibrato plugin as template
- [ ] Define REGISTRY with all dial variables
- [ ] Initialize instance variables in __init__
- [ ] Test preset save immediately
- [ ] Test preset load before implementing features
- [ ] Verify dial sync after preset load
- [ ] Test widget state if applicable

### For Plugin System (Short-term)

- [ ] Write comprehensive plugin guide
- [ ] Create plugin template file
- [ ] Add validation on plugin load
- [ ] Fix preset_manager widget handling
- [ ] Document keyboard input routing
- [ ] Add error messages to preset_manager

### For Architecture (Long-term)

- [ ] Design Plugin System v2.0
- [ ] Implement ModuleStateManager
- [ ] Refactor preset_manager
- [ ] Standardize widget interface
- [ ] Add plugin testing framework
- [ ] Create plugin validation tool

---

## Conclusion

What should have been a simple "add REGISTRY and test" became a 7-hour debugging session due to:
- Lack of documentation
- Complex, undocumented systems
- Silent failures
- Dual state tracking
- No validation

**The core issue:** The plugin system was designed for flexibility but lacks guardrails, documentation, and validation to guide developers toward the correct patterns.

**The solution:** Standardize, document, validate, and simplify. Make the "right way" the "easy way" and make the "wrong way" fail loudly at startup with clear error messages.

**Estimated time savings for future plugins:** 6.5 hours per plugin if recommendations are implemented.

---

## Appendix: Files Modified

### Session Changes

1. `core/app.py` (line 787)
   - Added "vk8m_main" to keyboard input routing

2. `preset_manager.py` (line 86)
   - Removed `if registry:` check
   - Added PRESET_VARS fallback in auto-discovery
   - Fixed widget state restoration (line 466)

3. `plugins/vk8m_plugin.py`
   - Changed from dial_values array to REGISTRY pattern
   - Added distortion_value and reverb_value instance variables
   - Implemented on_preset_loaded with button state sync
   - Updated on_dial_change to use instance variables

4. `pages/module_base.py` (line 54)
   - Modified set_active_module to preserve instance on same module
   - Fixed init_page to preserve _BUTTON_STATES if populated

### Recommended Changes (Not Yet Implemented)

1. `docs/PLUGIN_DEVELOPMENT_GUIDE.md` (new)
2. `plugins/plugin_template.py` (new)
3. `validation/plugin_validator.py` (new)
4. `core/module_state_manager.py` (new)
5. `preset/preset_config_discovery.py` (new)
6. `preset/preset_serializer.py` (new)
7. `preset/widget_state_handler.py` (new)

---

## Post-Session Issue: Drawbar SysEx Not Sent on Preset Load

### Issue #7: Drawbar Values Not Applied to Hardware on Preset Load

**Discovered:** After the main session concluded

**Symptom:** When loading a preset from the preset page, buttons and dials updated on the hardware (audible change), but the 9 drawbar sliders did not send their SysEx commands to the VK-8M, so the organ sound didn't match the preset.

**Investigation:**
- Widget state was being saved correctly in preset JSON: `"widget_state": {"bar_values": [0,0,0,0,0,3,2,1,0]}`
- Widget state was being restored to the DrawBarWidget (visual sliders moved correctly)
- But no SysEx was being sent to the hardware

**Root Cause:**
The `on_preset_loaded()` callback only applied button states and dial values to hardware, but didn't apply widget state. The widget restoration happened AFTER the callback, and the DrawBarWidget's `set_from_state()` method only updates visual state without triggering the `on_change` callback that sends SysEx.

Flow was:
1. `preset_manager.load_preset()` restores variables
2. Calls `module.on_preset_loaded(variables)` → applies button/dial SysEx
3. Later restores widget state → visual only, no SysEx
4. User hears buttons/dials change but drawbars are silent

**Fix Applied:**

1. Modified `preset_manager.py` to pass widget_state to the hook:
```python
# preset_manager.py line 426
if hasattr(module_instance, 'on_preset_loaded'):
    module_instance.on_preset_loaded(
        preset_data.get("variables", {}),
        widget_state=preset_data.get("widget_state", {})  # Added
    )
```

2. Updated VK8M's `on_preset_loaded()` to accept and apply widget_state:
```python
def on_preset_loaded(self, variables: dict, widget_state: dict = None):
    # ... existing button/dial code ...
    
    # Apply drawbar state to hardware
    if widget_state and "bar_values" in widget_state:
        bar_values = widget_state["bar_values"]
        for i, value in enumerate(bar_values):
            vk.set_drawbar(i + 1, int(value))  # Send SysEx for each bar
```

**Why This Was Missed:**
- Widget state restoration happens separately from variable restoration
- No visual feedback that SysEx wasn't being sent (sliders moved correctly)
- Only noticeable when listening to the hardware output
- Widget callback (`on_change`) is designed for user interaction, not programmatic updates

**Why This Is Hacky:**
- **Manual widget state handling**: Module has to know about widget internals
- **Inconsistent with dials**: Dials auto-sync via REGISTRY, widgets require manual code
- **Module-specific logic**: Each module with a custom widget needs custom hook code
- **No abstraction**: Direct calls to `vk.set_drawbar()` in preset callback

**Proper Solution:**

1. **Widget Protocol with Hardware Sync**:
```python
class HardwareSyncWidget(Protocol):
    def get_state(self) -> dict:
        """Return widget state."""
        ...
    
    def set_state(self, state: dict) -> None:
        """Restore visual state."""
        ...
    
    def apply_to_hardware(self) -> None:
        """Send current state to hardware."""
        ...

class DrawBarWidget:
    def apply_to_hardware(self):
        """Send all bar values to hardware."""
        for i, bar in enumerate(self.bars):
            vk.set_drawbar(i + 1, bar["value"])
```

2. **Automatic Hardware Sync in preset_manager**:
```python
# After restoring widget state
if hasattr(widget, 'apply_to_hardware'):
    widget.apply_to_hardware()
    showlog.debug("[PresetManager] Applied widget state to hardware")
```

3. **Or Use Widget's on_change Callback**:
```python
# DrawBarWidget.set_from_state()
def set_from_state(self, **kwargs):
    bar_values = kwargs.get("bar_values", None)
    if bar_values and len(bar_values) == self.num_bars:
        for i, value in enumerate(bar_values):
            self.bars[i]["value"] = max(0, min(8, int(value)))
            # Trigger callback for each bar
            if self.on_change:
                self.on_change({"bar_index": i, "value": value})
        self.mark_dirty()
```

4. **Unified Hardware Sync Hook**:
```python
class ModuleBase:
    def on_preset_loaded(self, preset_data: dict):
        """Called after ALL state is restored (variables + widgets)."""
        # Default implementation applies everything
        self.apply_to_hardware()
    
    def apply_to_hardware(self):
        """Apply current module state to hardware."""
        # Override in subclass to send SysEx
        pass

# VK8M
def apply_to_hardware(self):
    self._apply_all_button_states()
    self._apply_distortion(self.distortion_value)
    self._apply_reverb(self.reverb_value)
    # Widget handled automatically by preset_manager
```

**Lesson Learned:**
When implementing preset support, test with **audio output**, not just visual state. Widget restoration is separate from variable restoration and requires explicit hardware sync.

**Added to Action Items:**
- [ ] Add `apply_to_hardware()` method to widget protocol
- [ ] Modify preset_manager to call widget hardware sync
- [ ] Update DrawBarWidget to support hardware sync
- [ ] Add audio output testing to preset validation checklist

---

## Updated Appendix: Files Modified

### Session Changes (Updated)

1. `core/app.py` (line 787)
   - Added "vk8m_main" to keyboard input routing

2. `preset_manager.py` 
   - (line 86) Removed `if registry:` check
   - (line 86) Added PRESET_VARS fallback in auto-discovery
   - (line 466) Fixed widget state restoration
   - (line 426) **NEW:** Pass widget_state to on_preset_loaded hook

3. `plugins/vk8m_plugin.py`
   - Changed from dial_values array to REGISTRY pattern
   - Added distortion_value and reverb_value instance variables
   - Implemented on_preset_loaded with button state sync
   - Updated on_dial_change to use instance variables
   - **NEW:** Added widget_state parameter to on_preset_loaded
   - **NEW:** Added drawbar SysEx sending in on_preset_loaded

4. `pages/module_base.py` (line 54)
   - Modified set_active_module to preserve instance on same module
   - Fixed init_page to preserve _BUTTON_STATES if populated

### Recommended Changes (Not Yet Implemented)

1. `docs/PLUGIN_DEVELOPMENT_GUIDE.md` (new)
2. `plugins/plugin_template.py` (new)
3. `validation/plugin_validator.py` (new)
4. `core/module_state_manager.py` (new)
5. `preset/preset_config_discovery.py` (new)
6. `preset/preset_serializer.py` (new)
7. `preset/widget_state_handler.py` (new)
8. **NEW:** `widgets/hardware_sync_protocol.py` (new) - Widget hardware sync interface
