# Preset Variables Defined in REGISTRY

## Concept
Variables are declared directly in the REGISTRY, just like `options`, `range`, `family`, etc.

## Example: Complete Module

```python
class Vibrato(ModuleBase):
    MODULE_ID = "vibrato"
    FAMILY = "vibrato"

    REGISTRY = {
        "vibrato": {
            "type": "module",
            "01": {
                "label": "Division",
                "cc": 43,
                "range": [0, 5],
                "options": ["1", "1/2", "1/4", "1/8", "1/16", "1/32"],
                "family": "vibrato",
                "variable": "division_value",  # ← Links to instance var
            },
            "02": {
                "label": "Depth",
                "cc": 42,
                "range": [0, 100],
                "family": "vibrato",
                "variable": "depth_value",  # ← Links to instance var
            },
        }
    }
    
    # Widget state (for custom widgets like vibrato field)
    WIDGET_STATE = ["a_y", "b_x", "b_y"]
    
    # Additional variables not tied to dials
    PRESET_VARS = ["is_on", "current_hz"]
    
    def __init__(self):
        super().__init__()
        self.division_value = 4  # Slot "01"
        self.depth_value = 50    # Slot "02"
        self.is_on = False       # PRESET_VARS
        self.current_hz = 0      # PRESET_VARS
```

## How It Works

### 1. Registry Slots with Variables
Each dial slot can declare a `"variable"` field:
```python
"01": {
    "label": "Division",
    "variable": "division_value"  # ← This instance var gets saved
}
```

### 2. Widget State (Optional)
For custom widgets, declare their state attributes:
```python
WIDGET_STATE = ["a_y", "b_x", "b_y"]
```

### 3. Extra Variables (Optional)
For variables not tied to dials:
```python
PRESET_VARS = ["is_on", "current_hz", "mode"]
```

## Auto-Discovery Process

The PresetManager scans your module and builds the preset config:

```
1. Scan REGISTRY → Find all slots with "variable" field
   └─> Collects: ["division_value", "depth_value"]

2. Check PRESET_VARS → Add extra variables
   └─> Adds: ["is_on", "current_hz"]

3. Check WIDGET_STATE → Add widget properties
   └─> Adds: ["a_y", "b_x", "b_y"]

4. Build config:
   {
     "variables": ["division_value", "depth_value", "is_on", "current_hz"],
     "widget_state": ["a_y", "b_x", "b_y"],
     "registry_slots": ["01", "02"]
   }
```

## Adding a New Dial

**Example: Adding "Shape" dial**

### Step 1: Add to REGISTRY
```python
REGISTRY = {
    "vibrato": {
        "type": "module",
        "01": {"label": "Division", "variable": "division_value", ...},
        "02": {"label": "Depth", "variable": "depth_value", ...},
        "03": {  # NEW
            "label": "Shape",
            "cc": 44,
            "range": [0, 3],
            "options": ["Sine", "Square", "Saw", "Triangle"],
            "family": "vibrato",
            "variable": "shape_type"  # ← Declare the variable
        }
    }
}
```

### Step 2: Add instance variable
```python
def __init__(self):
    super().__init__()
    self.division_value = 4
    self.depth_value = 50
    self.shape_type = 0  # NEW - linked to slot "03"
    self.is_on = False
    self.current_hz = 0
```

### Step 3: Add handler method
```python
def shape(self, value: int):
    """Handle shape dial changes."""
    self.shape_type = value
    options = ["Sine", "Square", "Saw", "Triangle"]
    showlog.debug(f"[Vibrato] Shape set to {options[value]}")
```

**That's it!** The preset system automatically:
- Detects slot "03" has `"variable": "shape_type"`
- Saves `shape_type` when you save a preset
- Restores it when you load a preset

## Complete Example: Tremolo Module

```python
class Tremolo(ModuleBase):
    MODULE_ID = "tremolo"
    FAMILY = "tremolo"
    
    REGISTRY = {
        "tremolo": {
            "type": "module",
            "01": {
                "label": "Rate",
                "cc": 50,
                "range": [1, 20],
                "variable": "rate_hz"
            },
            "02": {
                "label": "Depth",
                "cc": 51,
                "range": [0, 100],
                "variable": "depth_percent"
            },
            "03": {
                "label": "Shape",
                "cc": 52,
                "range": [0, 2],
                "options": ["Sine", "Square", "Triangle"],
                "variable": "waveform"
            }
        }
    }
    
    PRESET_VARS = ["is_active", "sync_to_tempo"]
    
    def __init__(self):
        super().__init__()
        # These match the registry "variable" fields
        self.rate_hz = 5
        self.depth_percent = 50
        self.waveform = 0
        # These are in PRESET_VARS
        self.is_active = False
        self.sync_to_tempo = True
    
    def rate(self, value: int):
        self.rate_hz = value
        # Apply to hardware...
    
    def depth(self, value: int):
        self.depth_percent = value
        # Apply to hardware...
    
    def shape(self, value: int):
        self.waveform = value
        # Apply to hardware...
```

## Benefits

✅ **Single Source of Truth** - Registry defines everything
✅ **Self-Documenting** - Variable name right next to dial definition
✅ **Zero External Config** - No save_state_vars.json needed
✅ **Automatic** - Add dial → add variable → presets work
✅ **Clear Linking** - Easy to see which variable controls which dial

## What Gets Saved

**Preset file example (`config/presets/vibrato/my_preset.json`):**
```json
{
  "page_id": "vibrato",
  "preset_name": "my_preset",
  "variables": {
    "division_value": 4,
    "depth_value": 75,
    "is_on": true,
    "current_hz": 120
  },
  "widget_state": {
    "a_y": 0.25,
    "b_x": 0.5,
    "b_y": 0.75
  },
  "registry_values": {
    "01": 4,
    "02": 75
  }
}
```

## Optional: Backward Compatibility

If you don't want to add `"variable"` fields yet, the old PRESET_STATE still works:

```python
PRESET_STATE = {
    "variables": ["division_value", "depth_value"],
    "widget_state": ["a_y", "b_x"],
    "registry_slots": ["01", "02"]
}
```

Priority order:
1. PRESET_STATE (if defined)
2. Auto-discovery from REGISTRY (variable fields)
3. save_state_vars.json fallback
