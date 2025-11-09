# 🧩 UI-Midi-Pi Plugin Creation Manual (Complete Faulty Towers Edition)
### Complete Developer Guide for Creating Stable, Compatible Plugins
**Date:** November 3, 2025  
**Version:** 2.1 - Mode Manager & Renderer Integration Added  
**Scope:** All `ModuleBase`-based plugins (Vibrato, VK8M, ASCII Animator, etc.)

---

## 📖 Overview

This manual provides **everything a new GPT or developer needs** to build a fully working plugin in the UI‑Midi‑Pi ecosystem **without repeating any of the bugs, confusion, or pitfalls** encountered in earlier modules (VK8M, Vibrato Maker, etc.).

It summarizes real-world problems, their root causes, and the permanent remedies implemented in 2025.

---

## 🎯 Goals of This Manual

✅ Ensure every new plugin loads and renders correctly  
✅ Enable preset save/load out of the box  
✅ Guarantee button and dial states sync between UI and hardware  
✅ Prevent hardcoded dependencies in core code  
✅ Standardize widget and overlay behavior  
✅ Document every required attribute and pattern clearly  
✅ Handle theme inheritance correctly for standalone vs child modules  

---

## 🚀 Quick Start: 5-Step Plugin Integration

Every ModuleBase plugin requires **5 integration points** to function:

1. **Plugin File** (`plugins/your_plugin.py`) - Define ModuleBase class with config
2. **Device Layout** (`config/device_page_layout.json`) - Add navigation button
3. **Plugin Registration** (`plugins/your_plugin.py`) - Add Plugin class for auto-discovery
4. **Mode Manager** (`managers/mode_manager.py`) - Add mode switch handler **⚠️ CRITICAL**
5. **Renderer** (`rendering/renderer.py`) - Add to render and theme lists **⚠️ CRITICAL**

**Steps 4 & 5 are REQUIRED** but often forgotten. Without them:
- ❌ Plugin loads but shows blank screen (no `set_active_module()` called)
- ❌ Widget doesn't render (renderer doesn't know about the mode)
- ❌ Theme doesn't apply (mode not in themed_pages list)

See sections below for complete implementation details.

---

## 1️⃣ Plugin Fundamentals

Each plugin is a **Python class** that inherits from `ModuleBase`.

It must:
- Live under `/plugins/`
- Be referenced in `config/device_page_layout.json`
- Define all configuration **as class attributes**, not module-level variables

**Basic Structure:**

```python
from pages.module_base import ModuleBase

class YourPlugin(ModuleBase):
    MODULE_ID = "your_plugin"
    FAMILY = "your_plugin"
    STANDALONE = True  # or False for child modules
    REGISTRY = {...}
    BUTTONS = [...]
    INIT_STATE = {...}
```

---

## 2️⃣ Step-by-Step Integration Guide

### Step 1: Create Plugin File

**Location:** `plugins/your_plugin.py`

```python
from system.module_core import ModuleBase

class YourPluginModule(ModuleBase):
    MODULE_ID = "your_plugin"
    FAMILY = "your_plugin"
    STANDALONE = True  # Set False if augments a device
    
    REGISTRY = {
        "your_plugin": {
            "type": "module",
            "01": {"label": "Param1", "variable": "param1", "range": [0, 127], "type": "raw"},
        }
    }
    
    BUTTONS = [
        {"id": "1", "label": "Mode", "states": ["OFF", "ON"]},
        {"id": "7", "label": "P", "behavior": "nav", "action": "presets"},
        {"id": "9", "label": "S", "behavior": "nav", "action": "save_preset"},
    ]
    
    # Optional: Custom widget
    CUSTOM_WIDGET = {
        "class": "YourWidget",
        "path": "widgets.your_widget",
        "grid_size": [4, 2],  # Width, height in grid cells
        "grid_pos": [0, 0]    # Optional: X, Y position
    }
    
    def __init__(self):
        super().__init__()
        self.param1 = 64
        self.button_states = {"1": 0}
    
    def on_dial_change(self, label, value):
        if label == "Param1":
            self.param1 = value
    
    def on_button(self, btn_id, state_index, state_data):
        self.button_states[btn_id] = state_index
    
    def on_preset_loaded(self, variables: dict):
        """Called after preset load - apply hardware state"""
        pass

# Legacy exports (required for backwards compatibility)
MODULE_ID = YourPluginModule.MODULE_ID
FAMILY = YourPluginModule.FAMILY
REGISTRY = YourPluginModule.REGISTRY
BUTTONS = YourPluginModule.BUTTONS

# Auto-discovery registration
from core.plugin import Plugin

class YourPluginPlugin(Plugin):
    def register(self, app):
        app.page_registry.register(
            name=YourPluginModule.MODULE_ID,
            page_class="pages.module_base",
            module_class=YourPluginModule
        )
```

### Step 2: Add to Device Layout

**Location:** `config/device_page_layout.json`

```json
{
  "device_selection": {
    "buttons": [
      {
        "id": "1",
        "action": "your_plugin",
        "label": "Your Plugin",
        "device": "your_plugin"
      }
    ]
  }
}
```

### Step 3: Plugin Registration (Already in Step 1)

The `YourPluginPlugin` class at the bottom of your plugin file handles auto-discovery. The system will automatically:
- Load the plugin on startup
- Call `register()` to add it to PageRegistry
- Make it available for navigation

### Step 4: Mode Manager Integration ⚠️ CRITICAL

**Location:** `managers/mode_manager.py`

**Required:** Without this, `set_active_module()` is never called and you get a blank screen.

#### 4A: Add mode switch handler

Find the `switch_mode()` method (around line 100-150) and add:

```python
def switch_mode(self, new_mode: str):
    # ... existing code ...
    
    elif new_mode == "your_plugin":
        self._setup_your_plugin()
```

#### 4B: Add to navigation history

In the same `switch_mode()` method, find the navigation history list (around line 167):

```python
elif new_mode in ("patchbay", "text_input", "mixer", "vibrato", "vk8m_main", "your_plugin", "module_presets"):
    self._nav_history.append((new_mode, None))
```

#### 4C: Create setup function

Add at the end of the file (around line 480+):

```python
def _setup_your_plugin(self):
    """Initialize Your Plugin module."""
    try:
        from pages import module_base
        page = self.app.page_registry.get("your_plugin")
        if page and page.get("page_ref"):
            from plugins.your_plugin_plugin import YourPluginModule
            page["page_ref"].set_active_module(YourPluginModule)
            page["page_ref"].init_page()
            showlog.info("[MODE] Your Plugin initialized")
    except Exception as e:
        showlog.error(f"[MODE] Failed to setup Your Plugin: {e}")
```

**Why this is critical:**
- `set_active_module(YourPluginModule)` instantiates your module class
- Creates the custom widget if `CUSTOM_WIDGET` is defined
- `init_page()` draws the initial UI state
- Without this, the page handler has no module to render → blank screen

### Step 5: Renderer Integration ⚠️ CRITICAL

**Location:** `rendering/renderer.py`

**Required:** Without this, the renderer doesn't know how to draw your module.

#### 5A: Add to draw method check

Find the `elif ui_mode in (...)` line (around line 89):

```python
elif ui_mode in ("mixer", "vibrato", "vk8m_main", "your_plugin"):
    page["draw_ui"](self.screen, offset_y=offset_y)
```

#### 5B: Add to themed pages list

Find the `themed_pages` tuple (around line 118):

```python
themed_pages = ("dials", "presets", "mixer", "vibrato", "vk8m_main", "module_presets", "your_plugin")
```

**Why this is critical:**
- First edit ensures `draw_ui()` is called with correct signature
- Second edit enables theme system (proper header colors, device name display)
- Without these, widget doesn't render or shows default grey theme

### Step 6: Performance Configuration ⚠️ IMPORTANT

**Location:** `config/performance.py`

Your plugin's performance characteristics determine how the renderer handles it. This is especially critical for plugins with animations or custom widgets.

#### 6A: Configure Dirty Rendering Exclusion

Find the `EXCLUDE_DIRTY` list (around line 45-60):

```python
# Pages that don't support dirty rect rendering (full redraw always)
EXCLUDE_DIRTY = [
    "device_select",
    "patchbay",
    "presets",
    "module_presets",
    "text_input",
    "your_plugin",  # Add your plugin if it has animations or complex widgets
]
```

**When to add your plugin to EXCLUDE_DIRTY:**
- ✅ Plugin has animations (drawbar animations, visualizers, etc.)
- ✅ Custom widget updates frequently (100 FPS)
- ✅ Multiple moving parts that need to stay synchronized
- ❌ Static dial/button page (dirty rendering works fine)

**Why this matters:**
- Dirty rendering = only redraw changed areas (efficient for static pages)
- Full redraw = redraw entire page each frame (needed for animations)
- Wrong setting = animations flicker, tear, or don't update properly

#### 6B: Configure Rendering Metadata (Optional)

In your plugin class, add rendering metadata:

```python
class YourPlugin(ModuleBase):
    # Standard attributes...
    MODULE_ID = "your_plugin"
    
    # Rendering configuration (optional but recommended)
    PLUGIN_METADATA = {
        "rendering": {
            "fps_mode": "high",              # "high" (100 FPS) or "low" (20 FPS)
            "supports_dirty_rect": False,    # False if animations, True if static
            "burst_multiplier": 1.0,         # 1.0 = standard, >1.0 = more aggressive
        }
    }
```

**fps_mode values:**
- `"high"` (100 FPS): For animations, visualizers, smooth interactions
- `"low"` (20 FPS): For static pages with just buttons/dials

**supports_dirty_rect values:**
- `True`: Page can use dirty rect optimization (static content)
- `False`: Page needs full redraws (animations, moving content)

**Example from real plugins:**

```python
# VK8M with DrawBar animations (from plugins/vk8m_plugin.py)
PLUGIN_METADATA = {
    "rendering": {
        "fps_mode": "high",              # 100 FPS for smooth animations
        "supports_dirty_rect": True,     # Widgets use dirty rect optimization
        "burst_multiplier": 1.0,
    }
}

# ASCII Animator (from pages/module_base.py)
PLUGIN_METADATA = {
    "rendering": {
        "fps_mode": "high",              # 100 FPS for animation playback
        "supports_dirty_rect": True,     # Uses dirty rect system
        "burst_multiplier": 1.0,
    }
}
```

**Common mistake:** Not adding animated plugin to `EXCLUDE_DIRTY`:
```
❌ Plugin has drawbar animation
❌ Not in EXCLUDE_DIRTY list
❌ Renderer uses dirty rect optimization
❌ Animation updates set widget dirty flag
❌ Only widget area redraws
❌ Preset UI overlay doesn't clear properly
❌ Visual artifacts appear
```

**Correct configuration:**
```
✅ Plugin has drawbar animation
✅ Added to EXCLUDE_DIRTY list
✅ Renderer does full redraw each frame
✅ Animation updates entire screen
✅ Preset UI overlay clears properly
✅ No visual artifacts
```

---

## 3️⃣ Attribute Placement — The Vibrato Lesson

### ❌ Wrong (module-level attributes)
```python
# DO NOT DO THIS
SLOT_TO_CTRL = {...}
CUSTOM_WIDGET = {...}
```

### ✅ Correct (inside the class)
```python
class Vibrato(ModuleBase):
    MODULE_ID = "vibrato"
    SLOT_TO_CTRL = {...}
    CUSTOM_WIDGET = {...}
```

When attributes are outside the class, the rendering system (`getattr(_ACTIVE_MODULE, "SLOT_TO_CTRL")`) cannot see them, leading to "empty dial slot" or "widget=False" errors.

---

## 4️⃣ REGISTRY Pattern — The Heart of Plugin Integration

Every plugin must define a **REGISTRY** mapping dial slots (1–8) to variables and metadata.

### ✅ Correct Pattern
```python
REGISTRY = {
    "your_plugin": {
        "type": "module",
        "01": {"label": "Reverb", "variable": "reverb_value", "range": [0, 127], "type": "raw"},
        "05": {"label": "Distortion", "variable": "distortion_value", "range": [0, 127], "type": "raw"}
    }
}
```

### ✅ Initialize variables in `__init__`
```python
def __init__(self):
    super().__init__()
    self.reverb_value = 64
    self.distortion_value = 64
```

### ❌ Don't do this
```python
self.dial_values = [64, 64]  # Obsolete array-based tracking
```

### ✅ Benefits
- Preset system auto-discovers variables
- Dials sync automatically after preset load
- Consistent save/load behavior across all modules

---

## 5️⃣ Buttons — State and Behavior

Each plugin defines button layout via `BUTTONS` and tracks states in `self.button_states`.

### ✅ Example
```python
BUTTONS = [
    {"id": "1", "label": "VIB", "states": ["OFF", "V1", "V2", "V3"]},
    {"id": "7", "label": "P", "behavior": "nav", "action": "presets"},
    {"id": "9", "label": "S", "behavior": "nav", "action": "save_preset"},
]

def __init__(self):
    super().__init__()
    self.button_states = {"1": 0, "2": 0}
```

### ✅ Update button states in logic
```python
def on_button(self, btn_id, state_index, state_data):
    self.button_states[btn_id] = state_index
    if btn_id == "1":
        self._apply_vibrato(state_index)
```

### ❌ Don't maintain a separate `_BUTTON_STATES` global
The system now uses a unified `button_states` dict per module instance.

---

## 6️⃣ Preset Integration — The VK8M Fixes

### Preset Buttons
- **Button 7** → Load Preset  
- **Button 9** → Save Preset  

### Required Hook
```python
def on_preset_loaded(self, variables: dict):
    """Called after preset restored from file."""
    self._apply_all_button_states()
    self._apply_all_dial_values()
```

### Folder Isolation
Presets are saved to `config/presets/<MODULE_ID>/` automatically.

### Common Pitfall
- Empty `REGISTRY` prevents preset auto-discovery  
- Fix: define at least one valid dial variable or add `PRESET_VARS = ["button_states"]`

---

## 7️⃣ Custom Widgets — The DrawBar & VibratoField Fix

Custom widgets must declare `CUSTOM_WIDGET` inside the plugin class:

```python
CUSTOM_WIDGET = {
    "class": "DrawBarWidget",
    "path": "widgets.drawbar_widget",
    "grid_size": [3, 2],
}
```

### Widget Constructor Requirements

All custom widgets **must** accept these parameters:
```python
def __init__(self, rect, on_change=None, theme=None):
    # Minimum required signature
```

**Optional:** To support INIT_STATE initialization, add `init_state` parameter:
```python
def __init__(self, rect, on_change=None, theme=None, init_state=None):
    # Widget with init_state support
    widget_init = init_state or {}
    self.bar_values = widget_init.get("drawbars", [8, 7, 6, 5, 4, 3, 2, 1, 0])
```

**Important:** The module system uses signature inspection to detect `init_state` support:
- If widget accepts `init_state` → Passes `INIT_STATE["widget"]` from plugin
- If widget doesn't accept it → Skips parameter (backward compatible)

This means **old widgets without `init_state` continue working** without modification.

### State Persistence Methods

Each widget **must** implement for preset save/load:

```python
def get_state(self) -> dict:
    """Return widget state for preset saving."""
    return {"bar_values": self.bar_values, "speed_dial_value": int(self.speed_dial.value)}

def set_from_state(self, **kwargs) -> None:
    """Restore widget state from preset (uses **kwargs pattern)."""
    if "bar_values" in kwargs:
        self.bar_values = kwargs["bar_values"]
    if "speed_dial_value" in kwargs:
        self.speed_dial.set_value(kwargs["speed_dial_value"])
    self.mark_dirty()  # Request redraw
```

**Critical:** Method is `set_from_state()` not `set_state()` — uses `**kwargs` pattern for flexibility.

### ❌ Don't rely on `setattr()` in preset_manager
This bypasses internal redraw logic. Always use `get_state()` / `set_from_state()` pair.

---

## 8️⃣ Overlay Rendering (Preset Dialogs, etc.)

Overlays (like PresetSaveUI) are **not part of the widget dirty-rect system**.  
They must manually request full-frame redraws.

### ✅ Correct Implementation
```python
def _request_full_frames(self, count=2):
    if self.msg_queue:
        self.msg_queue.put(("force_redraw", count))
```

Called whenever:
- Typing in the dialog
- Cursor blinks
- Dialog opens/closes

This guarantees immediate visual updates.

---

## 9️⃣ Keyboard Input Handling — **FIXED: Preset Dialog Support**

### 🚨 Critical Bug: Hardcoded UI Mode List

The `app.py` remote character handler was hardcoded to only work with specific plugins:

### ❌ Wrong (Old Implementation)
```python
# In app.py _handle_remote_char()
if ui_mode in ("vibrato", "vk8m_main"):  # ❌ Breaks for new plugins!
    from pages import module_base
    if module_base.is_preset_ui_active():
        module_base.handle_remote_input(char)
```

**Problem:** Adding a new plugin (like `ascii_animator`) meant preset dialogs couldn't receive keyboard input.

### ✅ Correct (Fixed Implementation)
```python
# In app.py _handle_remote_char()
# Check if module_base has an active preset UI (works for ALL plugins)
try:
    from pages import module_base
    if hasattr(module_base, "is_preset_ui_active") and module_base.is_preset_ui_active():
        module_base.handle_remote_input(char)
        return
except Exception as e:
    showlog.debug(f"Could not check module_base: {e}")

# Legacy: specific page handlers
if ui_mode == "patchbay":
    from pages import patchbay
    patchbay.handle_remote_input(char)
```

**Solution:** Check `module_base.is_preset_ui_active()` instead of hardcoding plugin names.

### Impact
- ✅ All ModuleBase plugins now support preset dialogs automatically
- ✅ No need to modify `app.py` when adding new plugins
- ✅ Keyboard input works for vibrato, vk8m, ascii_animator, and future plugins

---

## 🔟 Theme System — **NEW: The VK8M Standalone vs Inheritance Problem**

### 🚨 Critical Issue: Theme Inheritance vs Standalone Modules

The theme system has a **global caching problem** where modules inherit the previous device's theme instead of using config defaults.

### Problem Chain
1. User loads **BMLPF** device → theme cache loads orange/amber colors
2. User switches to **VK8M** (standalone module with no device file)
3. VK8M **incorrectly inherits BMLPF's orange theme** instead of default blue
4. Only the custom widget uses correct defaults (different code path)

### Root Causes
- `dialhandlers.current_device_name` never gets updated when loading standalone modules
- `showheader.py` caches theme globally without invalidation
- `devices.get_theme()` returns parent device theme for modules without checking if they're standalone

### Solution: The STANDALONE Flag

**Every plugin must declare** if it's standalone or inherits from parent device:

```python
class VK8M(ModuleBase):
    MODULE_ID = "vk8m"
    STANDALONE = True  # ⚠️ CRITICAL: This module has its own identity
```

```python
class Vibrato(ModuleBase):
    MODULE_ID = "vibrato"
    # No STANDALONE flag = defaults to False
    # Inherits theme from active device (BMLPF, Quadraverb, etc.)
```

### What STANDALONE=True Does
1. Updates `dialhandlers.current_device_name` to module ID
2. Clears `showheader` theme cache
3. Forces `devices.get_theme()` to return empty dict `{}`
4. All theme lookups fall back to `config/styling.py` defaults

### What STANDALONE=False Does (default)
1. Preserves parent device name in `dialhandlers.current_device_name`
2. Keeps theme cache intact
3. Inherits parent device's custom theme colors
4. Vibrato on BMLPF shows orange, on Quadraverb shows pink, etc.

### Implementation Details

**In set_active_module():**
```python
is_standalone = getattr(module_ref, "STANDALONE", False)
if new_module_id and is_standalone:
    dialhandlers.current_device_name = new_module_id
    showheader.clear_theme_cache()
```

**In devices.get_theme():**
```python
if devname_lower not in dev_files:
    parent_dev = getattr(dialhandlers, "current_device_name", None)
    if isinstance(parent_dev, str) and parent_dev.strip() and parent_dev.lower() != devname_lower:
        # Inherit parent theme
        device_name = parent_dev
    else:
        # No parent or standalone - return empty for config defaults
        return {}
```

### 📋 Decision Tree: Standalone or Not?

**Use STANDALONE=True when:**
- Module is a complete instrument (VK8M, Pogolab, etc.)
- Has its own branding/identity
- Should always look the same regardless of context
- Examples: VK8M, standalone synthesizers, drum machines

**Use STANDALONE=False (omit flag) when:**
- Module augments an existing device (Vibrato Maker, Tremolo, etc.)
- Should visually match the parent device
- Acts as an "effect page" for device
- Examples: Vibrato Maker on BMLPF, Tremolo on Quadraverb

---

## 1️⃣1️⃣ Config Defaults vs Theme Overrides — **NEW: The Inline Default Problem**

### 🚨 Critical Issue: Mismatched Inline Defaults

When theme lookups fail, they fall back to **inline default values**. If these don't match `config/styling.py`, you get inconsistent colors.

### Problem Example
```python
# In showheader.py (WRONG!)
bg_rgb = helper.theme_rgb(device_name, "HEADER_BG_COLOR", "#000000")  # Black
text_rgb = helper.theme_rgb(device_name, "HEADER_TEXT_COLOR", "#FFFFFF")  # White

# But config/styling.py says:
HEADER_BG_COLOR = "#0B1C34"  # Dark blue
HEADER_TEXT_COLOR = "#BCBCBC"  # Light grey
```

Result: VK8M shows **black header with white text** instead of proper blue theme.

### ✅ Solution: Always Match Config Defaults

**Every theme_rgb() call must use the same default as config/styling.py:**

```python
# In any rendering code
btn_fill = helper.theme_rgb(device_name, "BUTTON_FILL", "#071C3C")  # ✅ Matches config
btn_outline = helper.theme_rgb(device_name, "BUTTON_OUTLINE", "#0D3A7A")  # ✅ Matches config

# In config/styling.py
BUTTON_FILL = "#071C3C"  # ✅ Same value
BUTTON_OUTLINE = "#0D3A7A"  # ✅ Same value
```

### Complete Audit Required

Check these files for correct inline defaults:
- `showheader.py` - header colors
- `pages/page_dials.py` - dial and button colors
- `pages/module_base.py` - button colors
- `pages/presets.py` - preset page colors
- `pages/module_presets.py` - module preset colors
- Any widget files using `theme_rgb()`

### Naming Consistency

**Config constants** must match **theme keys** (lowercased):
- `BUTTON_FILL` in config → `button_fill` in device themes
- `DIAL_PANEL_COLOR` in config → `dial_panel_color` in device themes
- `HEADER_BG_COLOR` in config → `header_bg_color` in device themes

---

## 1️⃣2️⃣ Device Theme Files — What Can Be Customized

### Location
`device/<device_name>.py` (e.g., `device/quadraverb.py`, `device/bmlpf.py`)

### Structure
```python
THEME = {
    # Header
    "header_bg_color": "#DC00B3",
    "header_text_color": "#FFC4C4",
    
    # Normal dials
    "dial_panel_color": "#301020",
    "dial_fill_color": "#FF0090",
    "dial_outline_color": "#FFB0D0",
    "dial_text_color": "#FFFFFF",
    
    # Muted dials
    "dial_mute_panel": "#100010",
    "dial_mute_fill": "#4A004A",
    "dial_mute_outline": "#804080",
    "dial_mute_text": "#B088B0",
    
    # Offline/empty dials (can differ per device!)
    "dial_offline_panel": "#101010",
    "dial_offline_fill": "#303030",
    "dial_offline_outline": "#505050",
    "dial_offline_text": "#707070",
    
    # Buttons
    "button_fill": "#FF0090",
    "button_outline": "#FFB0D0",
    "button_text": "#FFFFFF",
    "button_disabled_fill": "#3A003A",
    "button_disabled_text": "#703070",
    "button_active_fill": "#FF33AA",
    "button_active_text": "#FFFFFF",
    
    # Preset page
    "preset_button_color": "#351530",
    "preset_text_color": "#FFC4C4",
    "preset_label_highlight": "#FF00AA",
    "preset_font_highlight": "#FFFFFF",
    "scroll_bar_color": "#FF66CC",
    
    # Mixer page
    "mixer_panel_color": "#301020",
    "mixer_knob_color": "#FF00AA",
    # ... etc
}
```

### ⚠️ Important: Offline Dial Colors Are Device-Specific

**Don't force all devices to use the same offline colors!** Each device has its own aesthetic:
- **Quadraverb**: Grey offline dials `#101010`, `#303030`
- **BMLPF**: Brownish offline dials `#1C0C00`, `#2C1A0A` (matches sunset theme)
- **PSR-36**: Dark grey `#0A0A0A`, `#1C1C1C` (matches teal theme)

Only the **default fallback** in `config/styling.py` should be consistent.

---

## 1️⃣3️⃣ Logging Standards

Use `showlog.info()` with module identifiers for loupe mode visibility.

```python
showlog.info(f"*[{self.MODULE_ID}] Button 1 pressed, state={self.button_states['1']}")
showlog.info(f"*[{self.MODULE_ID}] on_preset_loaded → reverb={self.reverb_value}")
```

Prefix with `*` for messages that should appear in debug loupe overlay.

---

## 🔍 Complete Pitfalls & Fixes Summary

| # | Problem | Symptom | Correct Fix |
|---|----------|----------|--------------|
| 1 | Attributes outside class | Plugin loads but renders nothing | Move all config inside class |
| 2 | Empty REGISTRY | Presets fail to save/load | Always define REGISTRY with at least one dial |
| 3 | Dual button states | UI buttons not syncing | Use only `self.button_states` |
| 4 | Dials not updating | Dial widgets stay static | Use REGISTRY pattern; no arrays |
| 5 | Widget state not restoring | DrawBar sliders don't move | Implement `set_state()` method |
| 6 | Typing invisible | PresetSaveUI text not updating | Force full-frame redraws via msg_queue |
| 7 | Hardcoded mode checks | Plugin ignored keyboard | Use `supports_keyboard_input` flag |
| 8 | Silent preset fails | Files created but not loaded | Add `on_preset_loaded()` hook |
| 9 | **Wrong theme inherited** | Standalone module shows BMLPF colors | Add `STANDALONE = True` attribute |
| 10 | **Theme cache not cleared** | Colors don't update when switching | Use `showheader.clear_theme_cache()` in `set_active_module()` |
| 11 | **Mismatched inline defaults** | VK8M shows black header not blue | Match all `theme_rgb()` defaults to `config/styling.py` |
| 12 | **Config constants missing** | Fallback uses hardcoded grey | Add all `BUTTON_*`, `DIAL_*` constants to config |
| 13 | **⚠️ Missing mode_manager setup** | **Blank screen, widget never loads** | **Add Step 4: mode switch handler + setup function** |
| 14 | **⚠️ Missing renderer integration** | **Widget doesn't render or theme** | **Add Step 5: ui_mode check + themed_pages list** |

---

## 🧪 Validation & Testing

Run validation before deployment:

```bash
python tools/validate_plugins.py
```

Validation checks:
- REGISTRY completeness
- Instance variable existence
- Widget method compliance
- Missing required attributes (MODULE_ID, BUTTONS, INIT_STATE)
- **STANDALONE flag present for standalone modules**
- **Inline defaults match config/styling.py**

---

## 🧱 Full Example Plugin (Copy & Rename)

```python
# plugins/example_plugin.py

from pages.module_base import ModuleBase

class ExamplePlugin(ModuleBase):
    MODULE_ID = "example_plugin"
    FAMILY = "example_plugin"
    STANDALONE = True  # ⚠️ CRITICAL: Set to False if this augments a device
    supports_keyboard_input = True

    REGISTRY = {
        "example_plugin": {
            "type": "module",
            "01": {"label": "Depth", "variable": "depth", "range": [0, 127], "type": "raw"},
            "05": {"label": "Speed", "variable": "speed", "range": [0, 127], "type": "raw"},
        }
    }

    BUTTONS = [
        {"id": "1", "label": "Mode", "states": ["OFF", "V1", "V2"]},
        {"id": "7", "label": "P", "behavior": "nav", "action": "presets"},
        {"id": "9", "label": "S", "behavior": "nav", "action": "save_preset"},
    ]

    INIT_STATE = {
        "buttons": {"1": 0},
        "dials": [64, 64, 0, 0, 0, 0, 0, 0]
    }

    def __init__(self):
        super().__init__()
        self.depth = 64
        self.speed = 64
        self.button_states = {"1": 0}

    def on_dial_change(self, label, value):
        if label == "Depth":
            self.depth = value
        elif label == "Speed":
            self.speed = value
        self._apply_to_hardware(label, value)

    def on_button(self, btn_id, state_index, state_data):
        self.button_states[btn_id] = state_index
        self._apply_button_state(btn_id, state_index)

    def on_preset_loaded(self, variables: dict):
        self._apply_all_button_states()
        self._apply_to_hardware("Depth", self.depth)
        self._apply_to_hardware("Speed", self.speed)

    def _apply_to_hardware(self, label, value):
        showlog.info(f"*[{self.MODULE_ID}] {label} -> {value} (send to device)")

    def _apply_button_state(self, btn_id, state_index):
        showlog.info(f"*[{self.MODULE_ID}] Button {btn_id} set to state {state_index}")

    def _apply_all_button_states(self):
        for btn_id, idx in self.button_states.items():
            self._apply_button_state(btn_id, idx)
```

---

## 🎨 Performance Debugging: The Theme Checking Every Frame Problem

### Problem: Device Select Page Checking Themes 100 Times Per Second

**What we discovered:** The device_select page was calling `helper.device_theme.get()` in its render loop, causing expensive theme lookups every frame at 100 FPS.

#### Initial Investigation
```
User: "can you check why select device checks themes every frame?"
Observation: Device select page consuming excessive CPU
Root cause: Theme lookups in hot path (render loop)
```

#### The Bug Pattern

```python
# ❌ WRONG: Theme lookup in render loop (called 100x/second)
def draw_button(screen, rect, label, ...):
    for each button:
        # This gets called 100 times per second!
        color = helper.device_theme.get(device_name, "button_fill", default)
        pygame.draw.rect(screen, color, rect)
```

**Why this is bad:**
- `device_theme.get()` does dictionary lookups, file parsing, color conversion
- Called inside nested loops during rendering
- At 100 FPS, this means 100+ theme lookups per second
- Causes frame drops, stuttering, excessive CPU usage

#### The Solution: Dirty Rendering Hook

**Step 1: Add dirty rendering support to the page**

```python
# In pages/device_select.py
_is_dirty = False

def mark_dirty():
    """Mark page as needing redraw."""
    global _is_dirty
    _is_dirty = True

def is_dirty():
    """Check if page needs redraw."""
    return _is_dirty

def clear_dirty():
    """Clear dirty flag after redraw."""
    global _is_dirty
    _is_dirty = False

def get_dirty_rect():
    """Return area that needs redrawing (or None for full page)."""
    return None  # Full page redraw
```

**Step 2: Only redraw when actually dirty**

```python
# In rendering/renderer.py
if ui_mode == "device_select":
    # Check if page is dirty before redrawing
    if device_select.is_dirty():
        device_select.draw_ui(self.screen)
        device_select.clear_dirty()
    # Otherwise skip redraw entirely
```

**Step 3: Mark page dirty when state changes**

```python
# In device_select.py handle_event()
if button_clicked:
    # Change state
    selected_device = new_device
    # Mark dirty so next frame redraws
    mark_dirty()
```

#### Results
- ✅ Theme lookups only happen when buttons actually change
- ✅ Static pages don't redraw every frame
- ✅ CPU usage drops dramatically for device_select
- ✅ No visual impact (page still updates when needed)

#### When to Use Dirty Rendering

**Use dirty rendering for:**
- ✅ Static pages (device_select, preset lists, etc.)
- ✅ Button/menu pages with infrequent updates
- ✅ Pages where user interacts occasionally

**Don't use dirty rendering for:**
- ❌ Animation pages (drawbar animations, visualizers)
- ❌ Pages with continuously updating content
- ❌ Real-time displays (VU meters, waveforms)

For animated pages, add to `EXCLUDE_DIRTY` in `config/performance.py` (see Step 6 above).

#### Implementation Pattern

```python
# Standard dirty rendering pattern for static pages
class MyStaticPage:
    _dirty = False
    
    def mark_dirty(self):
        self._dirty = True
    
    def is_dirty(self):
        return self._dirty
    
    def clear_dirty(self):
        self._dirty = False
    
    def draw_ui(self, screen):
        # Expensive rendering code
        # Theme lookups, font rendering, etc.
        pass
    
    def handle_event(self, event):
        if state_changed:
            self.mark_dirty()  # Trigger next redraw
```

Then in renderer:
```python
if page.is_dirty():
    page.draw_ui(screen)
    page.clear_dirty()
```

**Key insight:** Don't perform expensive operations (theme lookups, file I/O, calculations) in render loops. Cache them or only compute when state actually changes.

---

## 📨 Message Queue & UI Invalidation System

### Understanding the Message Queue Architecture

The UI uses a message queue system to coordinate between event handlers, preset loaders, and the rendering pipeline. This is critical for triggering UI updates after programmatic state changes.

#### Core Concept

```python
# Message queue pattern
msg_queue.put(("invalidate", None))  # Request UI redraw
msg_queue.put(("burst", duration))    # Request burst rendering mode
```

**Why this exists:**
- Event handlers and preset loaders run outside the main render loop
- They can't directly call `draw_ui()` (would cause race conditions)
- Message queue lets them request a redraw on the next frame
- Renderer checks queue each frame and responds accordingly

#### The Invalidate Message

**When to send `("invalidate", None)`:**
- ✅ After loading a preset programmatically
- ✅ After changing button states in code
- ✅ After loading an animation preset
- ✅ After any state change that should be visible immediately
- ❌ NOT needed for user clicks/drags (handle_event marks dirty automatically)
- ❌ NOT needed during animations (render loop already running)

**Example from preset loading:**
```python
# In pages/module_presets.py
def handle_event(self, event):
    if preset_selected:
        # Load preset data
        preset_mgr.load_preset(page_id, preset_name, module_instance, widget)
        
        # CRITICAL: Tell renderer to redraw
        if self.msg_queue:
            self.msg_queue.put(("invalidate", None))
        
        # Hide preset selection page
        self.active = False
```

**What happens next:**
1. Message sits in queue
2. Main render loop calls `msg_queue.get_nowait()` on next frame
3. Sees `("invalidate", None)` message
4. Sets page dirty flag
5. Renderer redraws page on that frame
6. User sees updated state immediately

#### The Burst Message

Burst mode temporarily increases frame rate for smooth interactions:

```python
# Request 0.5 seconds of high-FPS rendering
msg_queue.put(("burst", 0.5))
```

**When widgets use burst:**
- User starts dragging a dial
- Widget detects `MOUSEBUTTONDOWN`
- Requests burst mode
- Renderer switches to 100 FPS for smooth dragging
- After 0.5s of no input, returns to normal FPS

**Example from DirtyWidgetMixin:**
```python
class DirtyWidgetMixin:
    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self._hit_test(event.pos):
                self.mark_dirty()
                # Request burst mode for smooth interaction
                if self.msg_queue:
                    self.msg_queue.put(("burst", 0.5))
                return True
```

#### Getting the Message Queue Reference

**From ServiceRegistry (preferred):**
```python
from core.service_registry import ServiceRegistry
services = ServiceRegistry()
msg_queue = services.get('msg_queue')
```

**Passed to constructors:**
```python
# In module_base init_page()
_PRESET_UI = PresetSaveUI((screen_w, screen_h), msg_queue=msg_queue)

# Widget stores reference
self.msg_queue = msg_queue
```

**In page handlers:**
```python
def handle_event(self, event, msg_queue):
    # msg_queue passed as parameter
    if state_changed:
        msg_queue.put(("invalidate", None))
```

#### Common Mistake: Forgetting Invalidate

❌ **Wrong:**
```python
# Load preset
preset_mgr.load_preset(page_id, preset_name, module_instance, widget)
# User sees old state until they move a dial
```

✅ **Right:**
```python
# Load preset
preset_mgr.load_preset(page_id, preset_name, module_instance, widget)
# Immediately tell renderer to update
msg_queue.put(("invalidate", None))
# User sees new state on next frame
```

#### Message Queue vs Direct Marking

**Message Queue (for external events):**
```python
# Preset loading, remote commands, MIDI events
msg_queue.put(("invalidate", None))
```

**Direct Dirty Flag (for UI events):**
```python
# User clicks button, drags dial
widget.mark_dirty()  # Widget sets its own dirty flag
# Renderer detects dirty widgets automatically
```

**Why the difference:**
- Message queue = cross-thread communication, async events
- Dirty flags = same-thread UI interactions, immediate response
- Both eventually trigger renderer, but different timing/safety

#### Testing Message Queue Flow

```python
# Add debug logging to verify invalidate messages work
def handle_event(self, event):
    if preset_selected:
        showlog.debug("Loading preset...")
        load_preset()
        showlog.debug("Pushing invalidate message...")
        msg_queue.put(("invalidate", None))
        showlog.debug("Invalidate message sent")

# In renderer.py
while True:
    try:
        msg = msg_queue.get_nowait()
        showlog.debug(f"Renderer received message: {msg}")
        if msg[0] == "invalidate":
            showlog.debug("Processing invalidate - marking page dirty")
    except queue.Empty:
        pass
```

If you see "Pushing invalidate message" but never "Renderer received message", the queue isn't being processed. Check that:
1. msg_queue is the same object (not recreated)
2. Renderer is running its message processing loop
3. No exceptions are swallowing the messages

---

## ✅ Final Developer Checklist

### Plugin File (Step 1)
- [ ] All attributes defined inside class  
- [ ] REGISTRY correctly maps dials to variables  
- [ ] Instance variables initialized in `__init__`  
- [ ] Button states tracked in `self.button_states`  
- [ ] `on_preset_loaded()` applies hardware state  
- [ ] Widget implements `get_state()` / `set_from_state(**kwargs)` if using CUSTOM_WIDGET
- [ ] Widget constructor accepts `init_state=None` parameter (optional, for INIT_STATE support)
- [ ] Widget dials registered via `register_widget_dial(slot, dial_obj, visual_mode="hidden")`
- [ ] Uses `supports_keyboard_input` if needed  
- [ ] Logging follows `*[MODULE_ID]` pattern  
- [ ] **INIT_STATE defined with 8 dial values, button states, and optional widget state**
- [ ] **STANDALONE flag set correctly (True for instruments, False/omit for effects)**  
- [ ] Plugin class at bottom for auto-discovery
- [ ] Legacy exports defined (MODULE_ID, FAMILY, REGISTRY, BUTTONS)

### Config Integration (Step 2)
- [ ] Button added to `config/device_page_layout.json`
- [ ] Action matches MODULE_ID
- [ ] Label is user-friendly

### Mode Manager (Step 4) ⚠️ CRITICAL
- [ ] **`elif new_mode == "your_plugin":` added to switch_mode()**
- [ ] **Mode added to navigation history list**
- [ ] **`_setup_your_plugin()` function created**
- [ ] **Setup function calls `set_active_module(YourPluginModule)`**
- [ ] **Setup function calls `init_page()`**

### Renderer (Step 5) ⚠️ CRITICAL
- [ ] **Mode added to `ui_mode in (...)` check**
- [ ] **Mode added to `themed_pages` tuple**

### Testing
- [ ] **All `theme_rgb()` inline defaults match `config/styling.py`**  
- [ ] Validation passes with no warnings  
- [ ] Plugin loads from device select screen
- [ ] Widget displays correctly
- [ ] Buttons respond to clicks
- [ ] Dials update values
- [ ] Presets save and load  

---

## 💬 Final Note

> *"Make the right way the easy way."*  

This manual ensures every future plugin works cleanly, integrates instantly, and passes all validation without the hours of debugging that plagued earlier modules.

**New Issues Documented in v2.1 (Nov 3, 2025):**
- Theme inheritance vs standalone module problem (#9)
- Global theme cache invalidation (#10)
- Mismatched inline defaults causing wrong colors (#11)
- Missing config constants forcing hardcoded fallbacks (#12)
- **⚠️ Missing mode_manager integration causing blank screens (#13)**
- **⚠️ Missing renderer integration preventing widget render (#14)**

**Critical Learning from ASCII Animator Plugin:**
The most common plugin failure mode is **forgetting Steps 4 & 5** (mode_manager and renderer integration). These are REQUIRED but easy to overlook because:
- Plugin file loads successfully (no errors)
- Device button appears and is clickable
- Navigation seems to work (no crashes)
- BUT: Screen goes blank because `set_active_module()` never gets called
- AND: Widget doesn't render because renderer doesn't know about the mode

**Always complete all 5 steps** in the integration guide. Steps 4 & 5 are not optional.

Following this guide guarantees that **new GPT instances can build fully working plugins independently** — consistent, predictable, and stable every time.

---

## 🔄 State Persistence & Initialization System (INIT_STATE)

### The Three-Tier State Priority System

The plugin system uses a **sophisticated 3-tier priority system** for initializing dials and buttons, matching the proven pattern from device pages (BMLPF, Quadraverb, etc.):

```
Priority 1: LIVE State (user modifications) → Highest
Priority 2: INIT State (first visit defaults) → Medium
Priority 3: Zero defaults (fallback) → Lowest
```

### How It Works

**First Visit to Plugin:**
1. System checks `dialhandlers.visited_pages` for `"plugin_id:main"`
2. Not found → Applies `INIT_STATE` values to all dials and buttons
3. Marks page as visited in `dialhandlers.visited_pages`
4. User sees configured starting positions (e.g., dial 1 at 64, button 2 in "ON" state)

**User Modifies Controls:**
1. Any dial change triggers `_apply_snap_and_dispatch()`
2. Current dial values captured to `dialhandlers.live_states[plugin_id]["main"]["dials"]`
3. Button changes update `dialhandlers.live_states[plugin_id]["main"]["buttons"]`
4. Widget state captured to `dialhandlers.live_states[plugin_id]["main"]["widget"]`

**User Switches Away and Returns:**
1. System checks for LIVE state first
2. Found → Restores exact positions user left them in
3. Skips INIT_STATE (page already visited)
4. User sees their modifications preserved

**App Restart:**
1. `dialhandlers.visited_pages` cleared (in-memory only)
2. `dialhandlers.live_states` cleared
3. Next visit applies INIT_STATE again (fresh start)

### Defining INIT_STATE

Every plugin should define starting positions for all controls:

```python
class YourPlugin(ModuleBase):
    MODULE_ID = "your_plugin"
    
    INIT_STATE = {
        # Dial positions (0-127 for each of 8 slots)
        "dials": [64, 64, 0, 0, 64, 0, 0, 0],
        
        # Button states (button_id: state_index)
        "buttons": {
            "1": 0,  # First state
            "2": 1   # Second state
        },
        
        # Custom widget state (optional)
        "widget": {
            "drawbars": [8, 7, 6, 5, 4, 3, 2, 1, 0],
            "speed": 100
        }
    }
```

### Dial Initialization Details

**Standard Grid Dials (Slots 1-8):**
- Created as `DialWidget` objects in `draw_ui()`
- Populated into `dialhandlers.dials` array for MIDI routing
- INIT_STATE applied automatically on first visit
- System handles:
  - Value application via `dial.set_value()`
  - Visual update (dial angle)
  - Display text (`"Label: 64"`)

**Widget-Owned Dials (e.g., Speed Dial):**
- Special dials created inside custom widgets (DrawBarWidget, etc.)
- Must be registered via `register_widget_dial(slot, dial_obj, visual_mode="hidden")`
- Registered AFTER `dialhandlers.dials` exists
- INIT_STATE applied separately in widget dial initialization block
- System handles same as grid dials, but timing is different

### Critical Timing: Why Widget Dials Needed Special Handling

**The Problem:**
1. Grid dials created first → `dialhandlers.dials` populated
2. Grid dials initialized from INIT_STATE → Page marked as visited ❌
3. Custom widget loaded (has speed dial)
4. Widget dial registered, but page already visited
5. INIT_STATE check fails → Widget dial stuck at 0

**The Solution:**
1. Grid dials created → `dialhandlers.dials` populated ✅
2. Grid dials initialized from INIT_STATE → DON'T mark visited yet ✅
3. Custom widget loaded ✅
4. Widget dial registered successfully (dials exist) ✅
5. Widget dial INIT_STATE applied ✅
6. NOW mark page as visited ✅

**Implementation in module_base.py:**
```python
# After grid dial creation (line ~1150)
if dial_vals:
    _apply_state_to_dials(dial_vals, "INIT")
    # DON'T mark as visited here - widget dials not registered yet!

# After widget dial registration (line ~1320)
if _WIDGET_SLOT_DIALS and state_type == "INIT":
    # Apply INIT state to widget dials
    for slot, dial_obj in _WIDGET_SLOT_DIALS.items():
        dial_obj.set_value(dial_vals[slot - 1])
    
    # NOW mark as visited (after widget dials initialized)
    dialhandlers.visited_pages.add(page_key)
```

### Button Initialization

Buttons follow the same 3-tier priority but with simpler state:

```python
INIT_STATE = {
    "buttons": {
        "1": 0,  # Button 1 starts in first state
        "2": 2   # Button 2 starts in third state
    }
}
```

**Multi-State Buttons:**
```python
BUTTONS = [
    {
        "id": "1",
        "states": ["OFF", "V1", "V2", "V3"]  # 4 states
    }
]

INIT_STATE = {
    "buttons": {
        "1": 2  # Start in "V2" state (index 2)
    }
}
```

Button states persist in `dialhandlers.live_states[plugin_id]["main"]["buttons"]` and restore automatically.

### Widget State (Custom Widgets)

Custom widgets can define their own INIT_STATE section:

**In Widget Class:**
```python
class DrawBarWidget:
    INIT_STATE = {
        "drawbars": [8, 7, 6, 5, 4, 3, 2, 1, 0]  # Class default
    }
    
    def __init__(self, rect, on_change=None, theme=None, init_state=None):
        # Use passed init_state or fall back to class default
        widget_init = init_state or self.INIT_STATE
        self.bar_values = widget_init.get("drawbars", [8, 7, 6, 5, 4, 3, 2, 1, 0])
```

**In Plugin Class:**
```python
class VK8M(ModuleBase):
    INIT_STATE = {
        "dials": [64, 64, 0, 0, 64, 0, 0, 0],
        "buttons": {"1": 0, "2": 0},
        "widget": {
            "drawbars": [8, 7, 6, 5, 4, 3, 2, 1, 0],  # Override widget default
            "speed": 100
        }
    }
    
    CUSTOM_WIDGET = {
        "class": "DrawBarWidget",
        "path": "widgets.drawbar_widget",
        "grid_size": [3, 2]
    }
```

Module system passes `INIT_STATE["widget"]` to widget constructor automatically.

### State Capture Flow

**When User Changes Dial:**
```
User drags dial
  ↓
DialWidget.handle_event() → dial.set_value()
  ↓
_process_dial_change()
  ↓
_apply_snap_and_dispatch()
  ↓
Capture to dialhandlers.live_states:
  live_states[plugin_id]["main"]["dials"] = [current values for all 8 dials]
  live_states[plugin_id]["main"]["buttons"] = {button states}
```

**When User Changes Button:**
```
User clicks button
  ↓
handle_event() detects button rect
  ↓
Cycle to next state
  ↓
_dispatch_hook("on_button", btn_id, state_index)
  ↓
Update live_states[plugin_id]["main"]["buttons"][btn_id] = new_index
```

### Widget Dial Registration API

For custom widgets with internal dials (speed controls, parameter knobs):

```python
# In _load_custom_widget() after widget creation
if hasattr(widget, 'get_speed_dial'):
    speed_dial = widget.get_speed_dial()
    slot = getattr(speed_dial, "id", None)
    if slot:
        # This replaces dialhandlers.dials[slot-1] with widget's dial
        register_widget_dial(slot, speed_dial, visual_mode="hidden")
        showlog.verbose(f"Registered widget dial in slot {slot}")
```

**What register_widget_dial() does:**
1. Saves original dial from `dialhandlers.dials[idx]`
2. Replaces it with widget's dial object
3. Stores in `_WIDGET_SLOT_DIALS[slot]` for init tracking
4. Sets `visual_mode="hidden"` so grid rendering skips it
5. Widget renders the dial itself in `widget.draw()`

**Benefits:**
- Widget dial receives MIDI CC messages (via dialhandlers.dials array position)
- INIT_STATE applies correctly (via _WIDGET_SLOT_DIALS iteration)
- LIVE state persistence works (captured in _apply_snap_and_dispatch)
- Widget has full visual control (hidden from grid renderer)

### Testing State Persistence

**Manual Test Procedure:**
1. Navigate to plugin
2. Verify all controls at INIT_STATE positions
3. Change dial 1 to 100, dial 5 to 20, button 1 to second state
4. Switch to different page (Patchbay, Mixer, etc.)
5. Return to plugin
6. Verify dials show 100, 20 and button shows second state ✅
7. Close app completely
8. Restart app
9. Navigate to plugin
10. Verify controls reset to INIT_STATE ✅

### Common Pitfalls

❌ **Forgetting INIT_STATE** - Controls start at 0, confusing users  
❌ **Wrong dial count** - Must be exactly 8 values, one per slot  
❌ **Button state out of range** - If button has 3 states, max index is 2  
❌ **Widget init_state not passed** - Widget ignores plugin's INIT_STATE  
❌ **Marking visited too early** - Widget dials don't get initialized  
❌ **Missing dialhandlers.dials** - Widget dial registration fails silently  

### Empty Dial Slots & None Handling

**Key Implementation Detail:** `dialhandlers.dials` can contain `None` entries for empty slots.

When a plugin doesn't use all 8 dial slots (e.g., ASCII Animator has no dials), the system creates:
```python
dialhandlers.dials = [None, None, None, None, None, None, None, None]
```

**What this means for your code:**
- ✅ **module_base.py handles None automatically** - All mouse/event handlers check `if d and getattr(d, 'cx', None)` before accessing dial properties
- ✅ **Your plugin can safely ignore empty slots** - Define only the slots you need in SLOT_TO_CTRL
- ✅ **Widget dial registration still works** - Replaces None with widget dial when needed
- ❌ **Direct dial access needs null checks** - If manually accessing `dialhandlers.dials[idx]`, always check `if dial:` first

**Example - Plugin with Partial Dial Usage:**
```python
SLOT_TO_CTRL = {
    1: "frequency",  # Dial 1 active
    2: "resonance",  # Dial 2 active
    # Slots 3-8 empty (will be None in dialhandlers.dials)
}
```

Result: `dialhandlers.dials = [dial_obj, dial_obj, None, None, None, None, None, None]`  

### Best Practices

✅ **Always define INIT_STATE** - Even if all zeros, be explicit  
✅ **Use meaningful defaults** - 64 (center) for parameters, 0 (off) for FX  
✅ **Match button count** - Define initial state for every button  
✅ **Test state persistence** - Verify both INIT and LIVE paths work  
✅ **Document widget state** - Comment what each widget field means  
✅ **Use PLUGIN_ID attribute** - Required for state key (alongside MODULE_ID)  

### Advanced: Multi-Page Plugins

If your plugin has multiple pages (rare), state keys include page ID:

```python
page_key = f"{plugin_id}:{page_id}"  # e.g., "vk8m:main", "vk8m:settings"

# Separate state per page
live_states["vk8m"]["main"] = {...}
live_states["vk8m"]["settings"] = {...}
visited_pages.add("vk8m:main")
visited_pages.add("vk8m:settings")
```

Current system assumes single "main" page per plugin.

---

## �️ Advanced Topic: External MIDI Controller Integration for Widget Dials

### The Problem
Custom widgets (like DrawBarWidget) may have internal controls (speed dials, parameter knobs) that need to respond to external MIDI controllers. The challenge is integrating widget-owned dials into the system's dial handling infrastructure.

### How the Dial System Works
Understanding the architecture is critical:

1. **MIDI CC → Dial ID Mapping**: External controller sends CC messages (CC1-CC8). System maps CC number to dial_id (1-8).

2. **Dial Array Position = Dial ID**: The `dialhandlers.dials` array uses **position** to determine routing:
   - `dialhandlers.dials[0]` = dial 1 (receives CC1)
   - `dialhandlers.dials[1]` = dial 2 (receives CC2)
   - Position in array IS the dial ID, not a property

3. **Module System Flow**: 
   ```
   MIDI CC → dialhandlers.on_midi_cc(dial_id, value)
   → module_base.handle_hw_dial(dial_id, value)
   → _SLOT_META.get(dial_id) → gets metadata from custom_dials.json
   → _apply_snap_and_dispatch() → scales value using range
   → Module.on_dial_change(label, scaled_value)
   ```

4. **SLOT_TO_CTRL Mapping**: Module defines which dial positions it owns:
   ```python
   SLOT_TO_CTRL = {
       1: "distortion",      # Slot 1 → "distortion" control in custom_dials.json
       2: "drawbar_speed",   # Slot 2 → "drawbar_speed" control
       5: "reverb_level",    # Slot 5 → "reverb_level" control
   }
   ```

5. **custom_dials.json Metadata**: Defines control parameters:
   ```json
   "drawbar_speed": {
       "label": "Speed",
       "range": [10, 200],    // This is the PARAMETER range, not dial range
       "type": "raw",
       "page": 0,
       "description": "Drawbar animation speed (10-200 ms per frame)"
   }
   ```

### Critical Misunderstandings to Avoid

❌ **WRONG**: Dial objects have a `.cc` property that determines which CC they respond to  
✅ **RIGHT**: Position in `dialhandlers.dials` array determines CC routing

❌ **WRONG**: `range: [10, 200]` means the dial sends 10-200 values  
✅ **RIGHT**: Dial always sends 0-127 (MIDI standard). Range defines the PARAMETER's scale. System maps 0-127 → 10-200 automatically.

❌ **WRONG**: Need to manually scale dial values in the widget  
✅ **RIGHT**: `_apply_snap_and_dispatch()` handles all scaling. Module receives pre-scaled values.

❌ **WRONG**: Widget dial needs special registration code  
✅ **RIGHT**: Just replace `dialhandlers.dials[N]` with widget's dial object. System handles the rest.

### Widget Dial Initialization Timing Issue & Solution

**CRITICAL**: When a widget has an internal dial that needs to honor INIT_STATE values, you must initialize derived state AFTER the dial's initial value is set.

#### The Problem We Encountered
```python
# DrawBarWidget.__init__()
self.speed_dial.value = 2  # Set from INIT_STATE by module_base later
self.preset_frame_ms = 2.0  # Hardcoded default - WRONG!
# Result: Animation speed stuck at 2ms until user touches the dial
```

**Why this happened:**
1. Widget `__init__()` runs first, creates speed dial with default value
2. Widget hardcodes `preset_frame_ms = 2.0` based on that default
3. module_base later sets dial to INIT_STATE value (e.g., 64 for medium speed)
4. Widget's `preset_frame_ms` never updates because `_update_speed_from_dial()` wasn't called
5. Animation runs at wrong speed until user manually moves the dial

#### The Solution: Call Sync After Dial Init

```python
class DrawBarWidget:
    def __init__(self, rect, on_change=None, theme=None, init_state=None):
        # ... create all controls ...
        
        # Speed dial (gets value from INIT_STATE later via module_base)
        self.speed_dial = Dial(speed_dial_x, speed_dial_y, radius=speed_dial_radius)
        self.speed_dial.id = 2
        self.speed_dial.label = "SPEED"
        self.speed_dial.range = [0, 127]
        self.speed_dial.value = 2  # Default (will be overridden by INIT_STATE)
        self.speed_dial.set_visual_mode("hidden")
        
        # CRITICAL: Initialize derived state from dial's initial value
        # This ensures preset_frame_ms syncs whether we use default OR INIT_STATE
        self._update_speed_from_dial()  # ← Must be AFTER dial creation
    
    def _update_speed_from_dial(self):
        """Convert dial value (0-127) to animation frame timing (200ms to 10ms)."""
        # Invert: dial 0 = slow (200ms), dial 127 = fast (10ms)
        t = self.speed_dial.value / 127.0
        self.preset_frame_ms = 200.0 - (t * 190.0)  # 200 - (0→190) = 200→10
        showlog.info(f"[DrawBarWidget] Speed updated to {self.preset_frame_ms:.1f}ms per frame")
```

#### Why This Works
1. Widget creates dial with default value (2)
2. Widget calls `_update_speed_from_dial()` → `preset_frame_ms` syncs to default
3. module_base loads widget
4. module_base registers widget dial in slot 2
5. module_base applies INIT_STATE: `speed_dial.set_value(64)`
6. Dial value updates to 64
7. **Widget ALREADY has sync method**, so derived state is correct after first call
8. When user later moves dial, `on_mouse_up()` calls `_update_speed_from_dial()` again

**Key Insight:** Don't hardcode derived state - always compute it from the dial's current value, even if that value is just the initial default. This way INIT_STATE updates "just work" without special hooks.

#### Anti-Pattern to Avoid

❌ **Don't do this:**
```python
# Hardcoded derived state that never updates
self.speed_dial.value = 2
self.preset_frame_ms = 2.0  # WRONG - won't sync when dial updates

# Later trying to fix it with complicated hooks
def on_dial_updated(self, dial_obj):
    if dial_obj is self.speed_dial:
        self._update_speed_from_dial()
```

✅ **Do this instead:**
```python
# Compute derived state from dial immediately
self.speed_dial.value = 2
self._update_speed_from_dial()  # RIGHT - syncs now and forever
```

#### General Pattern for Widget Dials

For any widget with internal dials that drive derived state:

```python
def __init__(self, ...):
    # 1. Create dial
    self.control_dial = Dial(...)
    self.control_dial.value = default_value
    
    # 2. Initialize any state derived from the dial
    self._sync_state_from_dial()  # ← Always call this in __init__
    
def _sync_state_from_dial(self):
    """Compute all derived state from dial's current value."""
    # Map dial value to whatever your widget needs
    self.some_internal_parameter = self._map_dial_to_param(self.control_dial.value)
    
def handle_event(self, event):
    # ... dial interaction code ...
    if dial_released:
        self._sync_state_from_dial()  # Call again when user changes it
```

This pattern ensures:
- ✅ Default values work
- ✅ INIT_STATE values work
- ✅ User changes work
- ✅ Preset loads work
- ✅ No hardcoded state
- ✅ No special hooks needed

---

## 🎮 Animation Preset Loading & Widget State Restoration

### The Challenge: Animation Presets vs Regular Presets

Animation presets (like drawbar animations) require special handling because they:
1. Start playing automatically when loaded
2. Override the widget's live state temporarily
3. Need to restore preset state when animation stops
4. Must update button state to reflect animation ON

### Problem: Stopping Animation Restored Wrong Values

**What we encountered:**
```
1. Load regular preset → Drawbars set to [5, 4, 3, 2, 1, 0, 0, 0, 0]
2. Load animation preset → Animation starts, drawbars animate
3. User clicks button to stop animation
4. Drawbars restore to [0, 0, 0, 0, 0, 0, 0, 0, 0] ❌ WRONG!
```

**Root cause:** Widget saved drawbar state when animation started, but at that moment the preset's values hadn't been applied yet.

#### Solution: Save State Only When Animation Active

```python
# DrawBarWidget
def start_animation(self):
    """Start the animation sequence."""
    if not self.animation_enabled:
        # Save current bar values BEFORE starting animation
        self.saved_bar_values = [bar["value"] for bar in self.bars]
        self.animation_enabled = True
        showlog.info(f"Animation started! saved_values={self.saved_bar_values}")

def stop_animation(self):
    """Stop the animation and restore original values."""
    if self.animation_enabled:
        self.animation_enabled = False
        # Restore saved values
        if self.saved_bar_values:
            for i, value in enumerate(self.saved_bar_values):
                self.bars[i]["value"] = value
            showlog.info(f"Restored values: {self.saved_bar_values}")
            self.saved_bar_values = None

def set_from_state(self, bar_values):
    """Called by preset manager to restore drawbar positions."""
    for i, value in enumerate(bar_values):
        if i < len(self.bars):
            self.bars[i]["value"] = value
    
    # CRITICAL: If animation is running, update saved state too
    # So when user stops animation, it restores to THIS preset, not old values
    if self.animation_enabled and self.saved_bar_values:
        self.saved_bar_values = bar_values.copy()
        showlog.info(f"[DrawBarWidget] Updated saved_bar_values during animation: {self.saved_bar_values}")
```

**Why this works:**
1. Regular preset loads → `set_from_state()` sets bar values directly
2. Animation preset loads → `set_from_state()` sets bar values, then `start_animation()` saves them
3. Animation runs, overwriting bar values each frame
4. User stops animation → `stop_animation()` restores the saved preset values ✅

### Problem: Animation Button Didn't Show ON State

**What we encountered:**
```
1. Load animation preset
2. Animation starts playing ✅
3. Button 6 still shows "OFF" ❌
4. Preset UI disappears (expected) ✅
```

**Root cause:** Loading animation preset updated `module_instance.button_states["6"] = 1` but never synced to `module_base._BUTTON_STATES`, which drives UI rendering.

#### Solution: Sync Button States to UI After Load

**In vk8m_plugin.py:**
```python
def load_animation_preset(self, filename: str):
    """Load a drawbar animation from ASCII animator preset."""
    # ... load frames and start animation ...
    
    if hasattr(widget, 'start_animation'):
        widget.start_animation()
        showlog.info("[VK8M] Animation started")
        
        # Update button 6 state to ON (state_index=1)
        self.button_states["6"] = 1
        showlog.debug("[VK8M] Button 6 state updated to ON (1)")
        
        # CRITICAL: Sync to UI immediately so button shows correct state
        self._sync_button_states_to_ui()

def _sync_button_states_to_ui(self):
    """Sync module's button_states to module_base's _BUTTON_STATES for UI rendering."""
    try:
        from pages import module_base
        for btn_id, state_idx in self.button_states.items():
            module_base._BUTTON_STATES[btn_id] = state_idx
        showlog.info(f"[VK8M] Synced _BUTTON_STATES: {module_base._BUTTON_STATES}")
    except Exception as e:
        showlog.error(f"[VK8M] Failed to sync button states: {e}")
```

**In pages/module_presets.py (animation preset handler):**
```python
# After loading animation preset
if filename.endswith('.drawbar.json'):
    module_instance.load_animation_preset(filename)
    # Push invalidate message to trigger UI redraw
    if msg_queue:
        msg_queue.put(("invalidate", None))
    return True
```

**Why this works:**
1. Animation preset loads and calls `load_animation_preset()`
2. Method starts animation AND updates button_states
3. Method syncs button_states → `_BUTTON_STATES` (UI state)
4. Invalidate message triggers redraw
5. Button renders with new state ✅

### Key Architectural Points

**Dual State Systems:**
- `module_instance.button_states` = Module's logical state (what hardware knows)
- `module_base._BUTTON_STATES` = UI rendering state (what screen shows)
- Must sync when programmatically changing state (presets, automation)
- User clicks automatically sync both (via `handle_event()`)

**When to Sync:**
- ✅ After loading preset programmatically
- ✅ After loading animation preset
- ✅ After any code that changes button_states dictionary
- ❌ NOT needed for user clicks (handle_event does it)
- ❌ NOT needed for INIT_STATE (init_page does it)

**Message Queue Invalidation:**
```python
# Always push invalidate after programmatic state changes
if msg_queue:
    msg_queue.put(("invalidate", None))
```

This triggers the rendering system to redraw the page, showing updated button labels/states.

### Complete Animation Preset Flow

```
1. User selects animation preset from preset list
   ↓
2. module_presets.handle_event() detects animation preset
   ↓
3. Calls module_instance.load_animation_preset(filename)
   ↓
4. Plugin loads frames into widget.preset_frames
   ↓
5. Plugin calls widget.start_animation()
   ↓
6. Widget saves current bar_values → saved_bar_values
   ↓
7. Widget sets animation_enabled = True
   ↓
8. Plugin updates button_states["6"] = 1 (ON)
   ↓
9. Plugin calls _sync_button_states_to_ui()
   ↓
10. module_base._BUTTON_STATES["6"] = 1
   ↓
11. module_presets pushes ("invalidate", None) to msg_queue
   ↓
12. Renderer redraws page, button shows "ON" ✅
   ↓
13. Widget.update_animation() runs each frame (100 FPS)
   ↓
14. User clicks button 6 to stop
   ↓
15. handle_event() cycles button state 1 → 0
   ↓
16. on_button(btn_id=6, state_index=0) called
   ↓
17. _toggle_drawbar_animation(enable=False) called
   ↓
18. widget.stop_animation() called
   ↓
19. Widget restores saved_bar_values to bars ✅
   ↓
20. Widget sets animation_enabled = False
```

### Testing Checklist

Test animation preset behavior:
- [ ] Load regular preset → Verify drawbar positions
- [ ] Load animation preset → Animation starts, button shows ON
- [ ] Stop animation → Drawbars restore to preset values (not zeros)
- [ ] Load different preset during animation → Stop restores NEW preset
- [ ] Switch pages during animation → Animation stops, state persists
- [ ] Reload app → Animation OFF, button shows OFF

### Implementation Pattern

```python
# In your plugin (VK8M, etc.)
class YourPlugin(ModuleBase):
    def load_animation_preset(self, filename: str):
        """Load animation from file and start playback."""
        # 1. Load animation data
        frames = load_animation_data(filename)
        if not frames:
            return
        
        # 2. Get widget reference
        from pages import module_base
        widget = module_base._CUSTOM_WIDGET_INSTANCE
        if not widget:
            return
        
        # 3. Load into widget
        if hasattr(widget, 'load_animation'):
            widget.load_animation(frames)
        
        # 4. Start animation
        if hasattr(widget, 'start_animation'):
            widget.start_animation()
        
        # 5. Update button state
        self.button_states["animation_toggle_btn"] = 1  # ON
        
        # 6. CRITICAL: Sync to UI
        self._sync_button_states_to_ui()
    
    def _sync_button_states_to_ui(self):
        """Sync module button_states to module_base._BUTTON_STATES."""
        from pages import module_base
        for btn_id, state_idx in self.button_states.items():
            module_base._BUTTON_STATES[btn_id] = state_idx
```

```python
# In your widget (DrawBarWidget, etc.)
class YourWidget:
    def start_animation(self):
        """Start animation, saving current state."""
        if not self.animation_enabled:
            # Save CURRENT state before animation
            self.saved_state = self._capture_current_state()
            self.animation_enabled = True
    
    def stop_animation(self):
        """Stop animation, restoring saved state."""
        if self.animation_enabled:
            self.animation_enabled = False
            # Restore saved state
            if self.saved_state:
                self._restore_state(self.saved_state)
                self.saved_state = None
    
    def set_from_state(self, state_data):
        """Called by preset manager to apply preset."""
        self._restore_state(state_data)
        
        # CRITICAL: If animation running, update saved state
        # so stop() restores THIS preset, not old values
        if self.animation_enabled and self.saved_state:
            self.saved_state = state_data.copy()
```

### Implementation Pattern

**Step 1: Widget Creates Its Own Dial**
```python
# In widget __init__
from assets.dial import Dial
self.speed_dial = Dial(x, y, radius=25)  # Custom position/size
self.speed_dial.id = 2  # Must match slot number
self.speed_dial.label = "SPEED"
self.speed_dial.range = [0, 127]  # Always standard MIDI range
self.speed_dial.value = 0  # Initial value
```

**Step 2: Module Defines SLOT_TO_CTRL**
```python
SLOT_TO_CTRL = {
    2: "drawbar_speed",  # Slot 2 maps to this control ID
}
```

**Step 3: Add Metadata to custom_dials.json**
```json
"drawbar_speed": {
    "label": "Speed",
    "range": [10, 200],  // Parameter range (not dial range!)
    "type": "raw"
}
```

**Step 4: Register Widget Dial in module_base**
```python
# In _load_custom_widget(), after widget creation:
if hasattr(widget, 'get_speed_dial'):
    speed_dial = widget.get_speed_dial()
    if speed_dial and dialhandlers.dials and len(dialhandlers.dials) > 1:
        dialhandlers.dials[1] = speed_dial  # Position 1 = dial 2
        showlog.info(f"Registered widget speed dial at dialhandlers.dials[1]")
```

**Step 5: Module Handles Scaled Values**
```python
def on_dial_change(self, dial_label: str, value: int):
    if dial_label.lower() in ("speed", "drawbar_speed"):
        # Value is ALREADY scaled to 10-200 by system
        self._update_drawbar_speed(value)

def _update_drawbar_speed(self, val: int):
    widget = module_base._CUSTOM_WIDGET_INSTANCE
    # Value is 10-200, use it directly
    widget.preset_frame_ms = float(val)
    
    # Update dial visual position (convert back to 0-127 for display)
    if hasattr(widget, 'speed_dial') and widget.speed_dial:
        t = (val - 10.0) / (200.0 - 10.0)  # Normalize to 0-1
        dial_value = int(t * 127)           # Scale to 0-127
        widget.speed_dial.set_value(dial_value)
    
    widget.mark_dirty()
```

**Step 6: Hide Dial from Normal Grid Rendering**
```python
# In module_base draw_ui(), skip widget's dial:
for w in _ACTIVE_WIDGETS:
    if _CUSTOM_WIDGET_INSTANCE and hasattr(_CUSTOM_WIDGET_INSTANCE, 'background_rect'):
        if hasattr(w, 'dial') and getattr(w.dial, 'id', None) == 2:
            continue  # Skip dial 2, widget will render it
    w.draw(screen, device_name=device_name, offset_y=offset_y)
```

**Step 7: Widget Renders Dial Itself**
```python
def draw(self, surface, device_name=None, offset_y=0):
    if self.animation_enabled:  # Or whatever condition
        # Draw dial at custom position with custom size
        dial_cx = self.speed_dial.cx
        dial_cy = self.speed_dial.cy + offset_y
        dial_r = self.speed_dial.radius
        
        # Standard dial rendering (panel, circle, pointer)
        pygame.gfxdraw.filled_circle(surface, dial_cx, dial_cy, dial_r, fill_color)
        # ... draw pointer, etc.
```

### Data Flow Summary

```
External Controller (0-127)
    ↓
dialhandlers.on_midi_cc(dial_id=2, value)
    ↓
module_base.handle_hw_dial(dial_id=2, value)
    ↓
meta = _SLOT_META.get(2)  → {"label": "Speed", "range": [10, 200]}
    ↓
_apply_snap_and_dispatch() → scales 0-127 to 10-200
    ↓
Module.on_dial_change("Speed", 10-200)
    ↓
widget.preset_frame_ms = scaled_value (10-200)
widget.speed_dial.set_value(back_to_0_127_for_visual)
```

### Special Dial Visual Overrides (v2.2)

Sometimes a widget needs total ownership of a dial slot—including rendering—while the rest of the module framework still handles MIDI routing, snapping, scaling, dirty rects, etc. The `visual_mode` flag on `assets.dial.Dial` exists for exactly this situation.

**Key concept:** mark any widget-owned dial as `visual_mode: "hidden"`. The dial remains in the routing array so CC messages, state persistence, and module callbacks continue to work, but the standard dial renderer (grid panel, label, pointer) never draws. Your widget can then place a completely custom control in that slot without double-rendering or label artifacts.

#### How it works under the hood

1. **Metadata** – Set the control’s metadata in `config/custom_dials.json`:
   ```json
   "drawbar_speed": {
       "label": "Speed",
       "range": [10, 200],
       "page": 0,
       "description": "Drawbar animation speed (10-200 ms per frame)",
       "visual_mode": "hidden"
   }
   ```
   When `module_base` builds `_SLOT_META`, the `visual_mode` value is copied into each dial widget’s config.

2. **DialWidget propagation** – `DialWidget` copies `visual_mode` onto the underlying `assets.dial.Dial`. During draw and event handling it simply returns if the mode is `hidden`, so no panel, label, or pointer is produced and it ignores mouse input.

3. **Renderer guard rails** – `page_dials.draw_ui()` and `page_dials.redraw_single_dial()` both check the dial’s `visual_mode`. If it is `hidden`, the renderer exits early, meaning dirty-draw bursts never touch that slot. Dirty list management, burst scheduling, and label caching stay intact for the rest of the dials.

4. **Widget registration** – Custom widgets can still replace entries in `dialhandlers.dials` with their own dial instances (e.g., `DrawBarWidget.speed_dial`). As long as the injected dial keeps `visual_mode="hidden"`, it participates in MIDI routing but avoids the legacy visuals. The widget renders its bespoke control inside `widget.draw()` and can still call `dial.set_value()` to keep hardware feedback in sync.

5. **Dirty rect compatibility** – Because hidden dials bail out before drawing, dirty rect calculations never allocate rectangles for them. The widget remains responsible for calling `mark_dirty()` and returning the correct rect from its own `draw()` so the dirty rect manager knows what area changed.

This pattern lets you layer free-form UI on top of the slot grid without breaking the workflow that the module system expects. Think of `visual_mode="hidden"` as a “silent participant”: the dial stays wired into MIDI/state lifecycles, but you take over the paintbrush.

#### Switching between widget visuals and stock dials at runtime

- Use `pages.module_base.register_widget_dial(slot, dial_obj, visual_mode="hidden")` when your widget wants to take control of a dial slot. The helper records the original dial, swaps in your widget dial for routing, and applies the hidden mode to both instances.
- Call `pages.module_base.set_dial_visibility(slot, visible)` to toggle between the grid-rendered dial (`visible=True`) and the fully custom look (`visible=False`). The helper normalizes values (`visible`/`default`) and marks every relevant dial dirty so the next burst reflects the change immediately.
- If you ever need the system dial back permanently (for example when removing the widget), call `pages.module_base.unregister_widget_dial(slot)` to restore the original object in `dialhandlers.dials` and reset its visual mode.

Inside your widget you can mirror the state with a thin wrapper, e.g.:

```python
def set_speed_dial_visible(self, visible: bool):
    mode = "visible" if visible else "hidden"
    self.speed_dial.set_visual_mode(mode)
    module_base.set_dial_visibility(self.speed_dial.id, visible)
    self.mark_dirty()
```

That way a “Hide Widget” toggle can simply hide your canvas and set the slot visible, revealing the stock dial underneath without any hacks.

### Key Takeaways

1. **Let the system handle scaling** - Don't do manual conversion, `_apply_snap_and_dispatch` does it
2. **Range is for parameters, not dials** - Dials always use 0-127 internally
3. **Position in array = routing** - No magic properties, just array index
4. **Widget owns rendering** - Standard grid skips the dial, widget draws it
5. **Two-way sync required** - Controller → value (system does) AND value → visual (you do)

### Common Pitfalls

🔴 **Trying to set dial.cc = 2** - This property doesn't exist and does nothing  
🔴 **Manually mapping 0-127 to range** - System already did this, you'll double-convert  
🔴 **Setting range = [0, 127] in JSON** - Use actual parameter range, system handles MIDI  
🔴 **Forgetting visual update** - Dial value changes but angle doesn't update  
🔴 **Not registering in dialhandlers.dials** - Controller sends values but nothing happens

---

## 🎬 Widget Animation System — **CRITICAL: Frame Rate Requirements**

### 🚨 The Animation Update Loop Bug (November 2025)

**Problem:** When implementing widget animations (like `DrawBarWidget` frame playback), animations would freeze for 400-500ms before starting, creating a jarring "jolt" effect.

**Root Cause:** The rendering system only called `widget.update_animation()` during **burst mode** (when widgets were marked dirty). After the first frame was drawn, the widget exited burst mode and `update_animation()` stopped being called, causing massive frame gaps.

**Timeline of the Bug:**
```
T+0ms:   start_animation() called
T+29ms:  First draw (frame_index=0)
T+469ms: First update_animation() call! ⚠️ 469ms gap!
T+540ms: Second frame drawn (frame_index=1)
```

The widget was being drawn 10+ times but `update_animation()` was only called TWICE in 540ms, creating the freeze effect.

### ✅ The Fix: Update Animations Every Frame

**Solution:** Move `update_animation()` calls from the rendering phase to the **`_update()` phase**, which runs every frame regardless of dirty state or burst mode.

**Implementation in `core/app.py`:**

```python
def _update(self):
    """Update application state each frame (lightweight - messages processed async)."""
    # Update header animation
    showheader.update()
    
    # Update widget animations EVERY FRAME (not just when in burst mode)
    # This ensures smooth animation playback at full framerate
    ui_mode = self.mode_manager.get_current_mode()
    page_info = self.page_registry.get(ui_mode)
    if page_info and hasattr(page_info.get("module"), "get_all_widgets"):
        module = page_info["module"]
        for widget in module.get_all_widgets():
            if hasattr(widget, "update_animation"):
                widget.update_animation()
    
    # ... rest of update logic
```

**Why This Works:**
- `_update()` is called **every frame** by the main event loop (60-100 FPS)
- It runs **before** `_render()`, so animation state is updated before drawing
- It's **independent of burst mode**, dirty state, or rendering optimization
- Widgets can now advance frames at consistent intervals (e.g., 197ms per frame)

### Required Module Function: `get_all_widgets()`

**Implementation in `pages/module_base.py`:**

```python
def get_all_widgets():
    """Return all active widgets for animation updates.
    
    This is called every frame by core/app.py to update animations,
    regardless of dirty state or burst mode.
    """
    global _ACTIVE_WIDGETS, _CUSTOM_WIDGET_INSTANCE
    all_widgets = list(_ACTIVE_WIDGETS)
    if _CUSTOM_WIDGET_INSTANCE:
        all_widgets.append(_CUSTOM_WIDGET_INSTANCE)
    return all_widgets
```

**Purpose:**
- Provides a complete list of widgets that need animation updates
- Includes both dial widgets (`_ACTIVE_WIDGETS`) and custom widgets
- Called every frame, ensuring no animation updates are missed

### Widget Animation Requirements

For widgets that support animation, implement these methods:

```python
class AnimatedWidget:
    def __init__(self, ...):
        self.animation_enabled = False
        self.animation_frames = []
        self.frame_index = 0
        self.last_advance_ms = 0
        self.frame_duration_ms = 197  # ~5 FPS animation
    
    def update_animation(self):
        """Called every frame (60-100 FPS) to advance animation state.
        
        This method MUST be lightweight - it's called constantly!
        Only advance frames when enough time has elapsed.
        """
        if not self.animation_enabled or not self.animation_frames:
            return
        
        current_time_ms = time.time() * 1000.0
        elapsed = current_time_ms - self.last_advance_ms
        
        # Advance to next frame if duration elapsed
        if elapsed >= self.frame_duration_ms:
            self.frame_index = (self.frame_index + 1) % len(self.animation_frames)
            self.last_advance_ms = current_time_ms
            self.mark_dirty()  # Request redraw with new frame
    
    def start_animation(self):
        """Start animation playback."""
        if not self.animation_enabled:
            self.animation_enabled = True
            # CRITICAL: Initialize timing to allow immediate first frame
            current_time_ms = time.time() * 1000.0
            self.last_advance_ms = current_time_ms - self.frame_duration_ms
            self.frame_index = 0
            self.mark_dirty()
    
    def stop_animation(self):
        """Stop animation playback."""
        self.animation_enabled = False
        self.mark_dirty()
    
    def is_dirty(self) -> bool:
        """Widget is dirty while animating."""
        if self.animation_enabled:
            return True
        return self._other_dirty_checks()
```

### Critical Timing Details

**Initialization Pattern:**
```python
# ❌ WRONG: Causes 500ms delay before first frame
self.last_advance_ms = 0.0

# ✅ CORRECT: Allows immediate first frame advance
current_time_ms = time.time() * 1000.0
self.last_advance_ms = current_time_ms - self.frame_duration_ms
```

**Frame Advance Logic:**
```python
# Only advance when enough time elapsed
elapsed = current_time_ms - self.last_advance_ms
if elapsed >= self.frame_duration_ms:
    self.frame_index = (self.frame_index + 1) % len(self.animation_frames)
    self.last_advance_ms = current_time_ms  # Record advance time
    self.mark_dirty()  # Trigger redraw
```

### Performance Considerations

**`update_animation()` Performance:**
- Called 60-100 times per second (every frame)
- Must be **extremely lightweight** - no heavy computation
- Only advance frames based on elapsed time
- Don't perform drawing or complex logic here

**Typical Execution Time:**
```
update_animation(): < 0.1ms per call
- Check animation_enabled flag
- Calculate elapsed time
- Maybe advance frame index
- Maybe call mark_dirty()
```

**Frame Rate Independence:**
- Animation speed controlled by `frame_duration_ms`, not frame rate
- Widget draws at 60-100 FPS (smooth)
- Animation advances at slower rate (e.g., 197ms = ~5 FPS)
- Decouples rendering speed from animation speed

### Testing Animation Performance

**Add timing logs to verify fix:**
```python
def start_animation(self):
    self.start_time_ms = time.time() * 1000.0
    showlog.info(f"[TIMER 1] Animation start_animation() called at {self.start_time_ms}ms")
    # ... rest of start logic

def update_animation(self):
    if self.first_update:
        elapsed = (time.time() * 1000.0) - self.start_time_ms
        showlog.info(f"[TIMER 1.5] First update_animation()! Elapsed: {elapsed:.2f}ms")
        self.first_update = False
    # ... rest of update logic

def draw(self, ...):
    if self.frame_index == 1 and not self.second_frame_drawn:
        elapsed = (time.time() * 1000.0) - self.start_time_ms
        showlog.info(f"[TIMER 2] Second frame displayed! Elapsed: {elapsed:.2f}ms")
        self.second_frame_drawn = True
```

**Expected Results After Fix:**
```
[TIMER 1] Animation start_animation() at T+0ms
[TIMER 1.5] First update_animation() at T+16ms  ✅ (~16ms = one frame at 60 FPS)
[TIMER 2] Second frame displayed at T+213ms     ✅ (~197ms frame duration)
```

### Key Takeaways

1. **`update_animation()` must run every frame** - Not just when dirty or in burst mode
2. **Place animation updates in `_update()` phase** - Runs before rendering, every frame
3. **Module must provide `get_all_widgets()`** - Returns complete list for animation updates
4. **Initialize timing correctly** - Allow immediate first frame advance
5. **Keep `update_animation()` lightweight** - Called 60-100 times per second
6. **Separate animation speed from frame rate** - Use time-based frame advancement

### Common Pitfalls

🔴 **Calling update_animation() only on dirty widgets** - Creates frame gaps during burst exit  
🔴 **Initializing last_advance_ms = 0** - Causes 500ms delay before first frame  
🔴 **Heavy computation in update_animation()** - Kills frame rate, should be < 0.1ms  
🔴 **Not implementing get_all_widgets()** - System can't find widgets for updates  
🔴 **Forgetting to call mark_dirty()** - Frame advances but widget doesn't redraw

---

## �🏗️ Future Overhaul Roadmap

When the system is redesigned properly, these issues should be eliminated:

1. **Explicit theme resolution** - No global caches, always resolve per-frame
2. **Config as single source of truth** - No inline defaults, only config references
3. **Proper plugin typing** - Replace attribute introspection with interfaces/protocols
4. **Dedicated theme service** - Centralized theme management with proper invalidation
5. **Module registration system** - Explicit declaration instead of dynamic discovery
6. **Widget dial registration API** - Declarative system for widget-owned controls instead of manual array replacement

