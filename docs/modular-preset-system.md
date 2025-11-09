# Fully Modular Preset System

## Overview
The preset system is now **completely self-contained** in each module. No external configuration needed!

## Three Approaches (Priority Order)

### 1. Explicit Declaration (PRESET_STATE) ⭐ Recommended
Define exactly what to save in your module file:

```python
class Vibrato(ModuleBase):
    MODULE_ID = "vibrato"
    
    PRESET_STATE = {
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
        "registry_slots": ["01", "02"]
    }
    
    REGISTRY = {
        "vibrato": {
            "type": "module",
            "01": {"label": "Division", ...},
            "02": {"label": "Depth", ...}
        }
    }
    
    def __init__(self):
        super().__init__()
        self.division_value = 4
        self.is_on = False
        self.current_hz = 0
```

**Pros:**
- Full control over what gets saved
- Explicit and clear
- Can exclude variables you don't want saved

**Cons:**
- Need to update PRESET_STATE when adding variables

---

### 2. Auto-Discovery (No Config Needed!) ✨ Easiest

Simply define your module - presets work automatically!

```python
class Tremolo(ModuleBase):
    MODULE_ID = "tremolo"
    
    REGISTRY = {
        "tremolo": {
            "type": "module",
            "01": {"label": "Rate", ...},
            "02": {"label": "Depth", ...},
            "03": {"label": "Shape", ...}
        }
    }
    
    def __init__(self):
        super().__init__()
        self.rate = 120
        self.depth = 50
        self.is_active = False
        # ALL these get auto-discovered and saved!
```

**The system automatically:**
- Finds all registry slots from REGISTRY
- Discovers all instance variables (non-private, non-method)
- Saves everything when you press button 9

**Pros:**
- Zero configuration needed
- Add new variables/dials - they're automatically saved
- Perfect for quick prototyping

**Cons:**
- Saves ALL instance variables (might include things you don't want)
- Cannot auto-discover widget state (must use PRESET_STATE for widgets)

---

### 3. JSON Fallback (Legacy)

Old approach via `config/save_state_vars.json`:

```json
{
  "tremolo": {
    "variables": ["rate", "depth"],
    "widget_state": [],
    "registry_slots": ["01", "02"]
  }
}
```

**Only use this for:**
- Pages without ModuleBase (like mixer, patchbay)
- When you need to override auto-discovery

---

## How It Works - Adding a New Dial

### Example: Adding "Shape" dial to Vibrato

**1. Add to REGISTRY:**
```python
REGISTRY = {
    "vibrato": {
        "type": "module",
        "01": {"label": "Division", "cc": 43, ...},
        "02": {"label": "Depth", "cc": 42, ...},
        "03": {"label": "Shape", "cc": 44, "range": [0, 3], ...}  # NEW
    }
}
```

**2. Add instance variable:**
```python
def __init__(self):
    super().__init__()
    self.division_value = 4
    self.is_on = False
    self.current_hz = 0
    self.shape_type = 0  # NEW - sine, square, saw, etc.
```

**3. Add handler:**
```python
def shape(self, value: int):
    """Handle shape dial changes."""
    self.shape_type = value
    showlog.debug(f"[Vibrato] Shape set to {value}")
```

**4. Update PRESET_STATE (if using explicit mode):**
```python
PRESET_STATE = {
    "variables": [
        "division_value",
        "is_on",
        "current_hz",
        "shape_type"  # NEW
    ],
    "widget_state": ["a_y", "b_x", "b_y"],
    "registry_slots": ["01", "02", "03"]  # NEW
}
```

**OR** just let auto-discovery handle it - no PRESET_STATE update needed!

---

## Complete Flow

```
┌─────────────────────────────────────────┐
│ User presses button 9 (Save Preset)    │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ PresetManager.get_page_config()         │
│ checks in priority order:              │
│ 1. Module's PRESET_STATE?              │
│ 2. Auto-discover from REGISTRY?        │
│ 3. save_state_vars.json?               │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ PresetManager.save_preset()             │
│ For each variable in config:           │
│   value = getattr(module, var_name)    │
│   preset_data[var_name] = value        │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ Save to:                                │
│ config/presets/vibrato/preset_name.json│
└─────────────────────────────────────────┘
```

---

## Real-World Examples

### Minimal Module (Auto-Discovery)
```python
class Chorus(ModuleBase):
    MODULE_ID = "chorus"
    
    REGISTRY = {
        "chorus": {
            "type": "module",
            "01": {"label": "Rate", ...},
            "02": {"label": "Depth", ...}
        }
    }
    
    def __init__(self):
        super().__init__()
        self.rate = 2.5
        self.depth = 30
        # Done! Presets work automatically
```

### With Custom Widget (Explicit)
```python
class ADSR(ModuleBase):
    MODULE_ID = "adsr"
    
    PRESET_STATE = {
        "variables": ["attack", "decay", "sustain", "release"],
        "widget_state": ["envelope_points"],  # From ADSRWidget
        "registry_slots": ["01", "02", "03", "04"]
    }
    
    REGISTRY = {...}
    
    def __init__(self):
        self.attack = 10
        self.decay = 20
        self.sustain = 70
        self.release = 50
```

---

## Benefits

✅ **Single Source of Truth** - Module file defines everything
✅ **Zero Duplication** - No separate config file to maintain
✅ **Auto-Discovery** - New dials/variables work automatically
✅ **Explicit Control** - Use PRESET_STATE when you need precision
✅ **Backwards Compatible** - JSON fallback still works

## Migration Guide

If you have existing modules using `save_state_vars.json`:

1. **Keep working as-is** (JSON fallback still supported)
2. **Migrate gradually** by adding PRESET_STATE to modules
3. **Or use auto-discovery** by removing JSON entries (system auto-detects)

No breaking changes - choose your approach per module!
