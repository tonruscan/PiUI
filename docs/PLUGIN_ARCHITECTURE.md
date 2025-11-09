# Plugin Architecture: Standalone vs Module Plugins

## Overview

The plugin system supports two distinct types of plugins, differentiated by the `standalone` flag:

### Visual Architecture

```
┌─────────────────────────────────────────────────────┐
│              Device Selection Page                   │
├─────────────────────────────────────────────────────┤
│  [Quadraverb]  [PogoLab]  [PSR-36]                  │
│  [CT-660]      [BMLPF]    [VK-8M] ← Plugin!         │
│                           [Patchbay]                 │
└─────────────────────────────────────────────────────┘
                      ↓
         ┌────────────┴───────────┐
         ↓                        ↓
    Traditional Device      Standalone Plugin
    (devices.json)         (standalone=True)
         ↓                        ↓
    Has device/ file       Has plugin file only
    Fixed in JSON          Modular & extensible
```

When a device is active, **both** device and plugin can access modules:
```
┌─────────────────────────────────────────┐
│        Active Device: BMLPF             │
├─────────────────────────────────────────┤
│  Main Controls                          │
│  ├─ Cutoff, Resonance, Mix...          │
│                                         │
│  Modules (standalone=False)             │
│  ├─ [Vibrato] ← Modulates device CVs   │
│  ├─ [Tremolo] (future)                  │
│  └─ [LFO] (future)                      │
└─────────────────────────────────────────┘
```

---

### 1. **Standalone Plugins** (`standalone = True`)
- **Purpose**: Control external MIDI devices or synthesizers
- **Behavior**: Appear in the device selection page alongside traditional devices
- **Examples**: Roland VK-8M, future synth controllers
- **Characteristics**:
  - Generate their own MIDI output
  - Act as device controllers
  - Can be selected as the primary device
  - Show up in device select grid

### 2. **Module Plugins** (`standalone = False`)
- **Purpose**: Modulate or enhance existing device parameters
- **Behavior**: Operate on the currently selected device
- **Examples**: Vibrato, LFO, Envelope followers
- **Characteristics**:
  - Require a parent device to be active
  - Modify device CV/MIDI parameters
  - Don't appear in device selection
  - Accessible as secondary pages/modules

---

## Implementation Guide

### Creating a Standalone Plugin (Device Controller)

```python
# plugins/my_device_plugin.py
from core.plugin import Plugin as PluginBase
from system.module_core import ModuleBase
import showlog

class MyDevice(ModuleBase):
    page_id = "my_device"
    page_label = "My Device"
    
    def __init__(self, app, *args, **kwargs):
        super().__init__(app, *args, **kwargs)
        # Your device initialization
    
    def on_dial_change(self, dial_index: int, value: int):
        # Send MIDI to your device
        pass
    
    def on_button(self, button_id: str):
        # Handle button presses
        pass

class MyDevicePlugin(PluginBase):
    name = "My Device"
    version = "1.0.0"
    category = "synth"
    author = "Your Name"
    description = "Controls the My Device synthesizer"
    page_id = MyDevice.page_id
    standalone = True  # ← KEY: This makes it a device controller
    
    def on_load(self, app):
        app.page_registry.register(
            self.page_id,
            MyDevice,
            label=MyDevice.page_label,
            meta={"rendering": {"fps_mode": "high", "supports_dirty_rect": True}}
        )
        showlog.info(f"[MyDevice] Registered page '{self.page_id}'")

# Export for auto-discovery
Plugin = MyDevicePlugin
```

**Then add to device selection:**
```json
// config/device_page_layout.json
{
  "device_select": {
    "buttons": [
      ...
      { "id": 6, "img": "icons/my_device.png", "label": "My Device", "plugin": true }
    ]
  }
}
```

---

### Creating a Module Plugin (Device Modulator)

```python
# plugins/my_module_plugin.py
from core.plugin import Plugin as PluginBase
from system.module_core import ModuleBase
import showlog

class MyModule(ModuleBase):
    MODULE_ID = "my_module"
    FAMILY = "modulation"
    page_id = "my_module"
    page_label = "My Module"
    
    def __init__(self):
        super().__init__()
        # Your module initialization
    
    def on_dial_change(self, dial_label: str, value: int):
        # Modulate the current device's parameters
        pass

class MyModulePlugin(PluginBase):
    name = "My Module"
    version = "1.0.0"
    category = "modulation"
    author = "Your Name"
    description = "Modulates device parameters"
    page_id = MyModule.page_id
    standalone = False  # ← KEY: This makes it a device-dependent module
    
    def on_load(self, app):
        app.page_registry.register(
            self.page_id,
            MyModule,
            label=MyModule.page_label,
            meta={"rendering": {"fps_mode": "high", "supports_dirty_rect": True}}
        )
        showlog.info(f"[MyModule] Registered page '{self.page_id}'")

# Export for auto-discovery
Plugin = MyModulePlugin
```

**Module plugins don't need device_page_layout.json entries** - they're accessed via navigation buttons or module select.

---

## Plugin Discovery Flow

```
1. App starts → PluginManager.discover("plugins")
2. Scans plugins/*_plugin.py files
3. Imports and instantiates Plugin class
4. Calls plugin.on_load(app)
5. Plugin registers its page with PageRegistry
6. Metadata stored in ModuleRegistry

For Standalone Plugins:
7. Device select page loads device_page_layout.json
8. Buttons with "plugin": true are recognized
9. Clicking plugin button triggers standard device flow
10. Plugin page becomes the active device page

For Module Plugins:
7. Module accessible via navigation when device is active
8. Operates on current device's CV/MIDI channels
9. Can be toggled on/off independently
```

---

## Key Differences Summary

### Quick Reference Table

| Plugin Type | `standalone` | Appears in Device Select | Requires Parent Device | Example |
|-------------|--------------|-------------------------|------------------------|---------|
| **Device Controller** | `True` | ✅ Yes | ❌ No | VK-8M organ |
| **Device Module** | `False` | ❌ No | ✅ Yes | Vibrato LFO |

### Detailed Comparison

| Aspect | Standalone Plugin | Module Plugin |
|--------|------------------|---------------|
| **`standalone` flag** | `True` | `False` |
| **Device Select** | ✅ Appears | ❌ Hidden |
| **Requires Parent Device** | ❌ No | ✅ Yes |
| **MIDI Output** | Direct to hardware | Via parent device |
| **Navigation** | Primary device | Secondary module |
| **JSON Config** | device_page_layout.json | Not needed |
| **Example** | VK-8M, Synth Controllers | Vibrato, LFO, Effects |

---

## PluginManager API Extensions

```python
# Get all standalone plugins (device controllers)
standalone_plugins = app.plugin_manager.list_standalone_plugins()

# Get all module plugins (device modulators)
module_plugins = app.plugin_manager.list_module_plugins()

# Check if a plugin is standalone
plugin = app.plugin_manager.get_by_name("Roland VK-8M")
is_standalone = plugin.standalone  # True

# Get metadata including standalone flag
metadata = plugin.get_metadata()
# Returns: {..., "standalone": True}
```

---

## Migration Guide for Existing Code

### Converting a Device to Standalone Plugin

1. **Move device logic to plugin:**
   - Create `plugins/device_name_plugin.py`
   - Define module class (from ModuleBase)
   - Define plugin class (from Plugin)
   - Set `standalone = True`

2. **Update device_page_layout.json:**
   - Add button with `"plugin": true`

3. **Optional: Keep device/ file for backwards compatibility**
   - Or move entirely to plugin-only

### Converting a Module to Plugin

1. **Create plugin file:**
   - Create `plugins/module_name_plugin.py`
   - Define module class (from ModuleBase)
   - Define plugin class (from Plugin)
   - Set `standalone = False`

2. **No JSON changes needed** - modules don't appear in device select

---

## Best Practices

### When to Use Standalone Plugins
- ✅ Controlling a physical MIDI device
- ✅ Software synthesizer controllers
- ✅ External hardware interfaces
- ✅ Anything that can be "selected" as a device

### When to Use Module Plugins
- ✅ LFOs that modulate device parameters
- ✅ Envelope followers
- ✅ Effects processors that layer on devices
- ✅ Vibrato/tremolo/modulation
- ✅ Anything that "enhances" an existing device

---

## Future Enhancements

Potential future additions to the plugin system:

1. **Hybrid Plugins**: `standalone = "both"` for plugins that work standalone OR as modules
2. **Plugin Dependencies**: Declare required plugins in metadata
3. **Hot Reload**: Reload plugins without restarting app
4. **Plugin Marketplace**: Download and install plugins dynamically
5. **Plugin Categories in UI**: Group plugins by category in device select
6. **Plugin Chaining**: Route module plugins in series

---

## Troubleshooting

### Plugin Not Appearing in Device Select
- ✅ Check `standalone = True` in plugin class
- ✅ Verify entry in `device_page_layout.json` with `"plugin": true`
- ✅ Check plugin loads successfully in logs: `[PluginManager] Loading: PluginName`

### Module Not Working with Device
- ✅ Check `standalone = False` in plugin class
- ✅ Verify device is active before activating module
- ✅ Check CV/MIDI channel routing

### Plugin Not Loading
- ✅ Filename must match pattern: `*_plugin.py`
- ✅ Must have `Plugin = PluginClassName` export at bottom
- ✅ Check logs for import errors

---

## Examples in Codebase

### Standalone Plugin Example
- **File**: `plugins/vk8m_plugin.py`
- **Purpose**: Controls Roland VK-8M organ module
- **Flag**: `standalone = True`
- **Config**: Entry in `device_page_layout.json`

### Module Plugin Example
- **File**: `plugins/vibrato_plugin.py`
- **Purpose**: Adds vibrato modulation to any device
- **Flag**: `standalone = False`
- **Config**: No device select entry needed

---

## See Also

- `core/plugin.py` - Plugin base classes and manager
- `system/module_core.py` - ModuleBase for plugin logic
- `docs/upgrades/Phase3_Plugin_System.md` - Plugin system migration
- `pages/device_select.py` - Device selection handler
