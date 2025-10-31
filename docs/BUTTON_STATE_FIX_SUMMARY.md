# Button State Fix Summary

## What Was Broken
1. **Button states changed from list to dict** but preset_manager still expected lists
2. **INIT_STATE not being loaded** - vibrato was starting with all zeros
3. **Rotating button not updating label** - stereo mode wasn't syncing properly

## What Was Fixed

### 1. vibrato_mod.py `__init__()` (lines ~104-134)
**Now initializes from INIT_STATE:**
```python
# Initialize from INIT_STATE
init_state = self.INIT_STATE

# Load division_value from init
self.division_value = init_state.get("dials", [4])[0] if isinstance(init_state.get("dials"), list) else 4

# Load button_states from init (dict format)
self.button_states = init_state.get("buttons", {"1": 0, "2": 0}).copy()

# Sync stereo_mode with button state
if "2" in self.button_states:
    self.stereo_mode.set_index(self.button_states["2"])
```

**Result:** Module starts with division=4 (1/8 note), button 1=off, button 2=L mode

### 2. preset_manager.py save_preset() (lines ~240-250)
**Now saves button_states as dict:**
```python
# Save button states from module instance
if hasattr(module_instance, 'button_states'):
    preset_data["button_states"] = module_instance.button_states.copy() if isinstance(module_instance.button_states, dict) else {}
```

**Old:** `[False, False, False, False, False]`  
**New:** `{"1": 0, "2": 1}` (actual button state values)

### 3. preset_manager.py load_preset() (lines ~295-310)
**Now restores button_states as dict AND syncs stereo_mode:**
```python
# Restore to module instance
if hasattr(module_instance, 'button_states'):
    module_instance.button_states = button_states.copy() if isinstance(button_states, dict) else {}
    
    # Sync rotating state (button 2) if module has stereo_mode
    if hasattr(module_instance, 'stereo_mode') and "2" in button_states:
        module_instance.stereo_mode.set_index(button_states["2"])

# Check vibrato on/off state correctly
was_vibrato_on = button_states.get("1", 0) == 1 if isinstance(button_states, dict) else False
```

**Result:** Loading preset properly restores button 2's L/R/LR state AND the label

## Expected Behavior Now

### First Load (No Preset)
- Dial 1: Division = 4 (1/8 note) ✅
- Button 1: OFF (vibrato stopped) ✅
- Button 2: "L" (left channel only) ✅

### Press Button 1
- Toggles 0 → 1
- Vibrato turns ON ✅
- Press again: 1 → 0, vibrato OFF ✅

### Press Button 2
- Cycles: L (0) → R (1) → LR (2) → L (0)
- Label updates: "L" → "R" → "LR" → "L" ✅
- Channels update: [17] → [16] → [17,16] → [17] ✅

### Load Preset with button_states = {"1": 1, "2": 2}
- Button 1: ON (vibrato active) ✅
- Button 2: "LR" label showing ✅
- stereo_mode.index = 2 ✅
- Channels = [17, 16] ✅

## Files Changed
1. `modules/vibrato_mod.py` - Fixed `__init__()` to load INIT_STATE
2. `preset_manager.py` - Fixed save/load to use dict format for button_states
