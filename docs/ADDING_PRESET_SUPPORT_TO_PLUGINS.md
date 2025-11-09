# Adding Preset Save/Load Support to Plugins

## Quick Guide for Adding Presets to Module-Based Plugins

This guide explains how to add complete preset save/load functionality to any plugin using the `module_base` architecture, based on the VK8M implementation.

---

## Prerequisites

Your plugin must:
- Use `ModuleBase` as the base class
- Be rendered via `pages/module_base.py`
- Have a `MODULE_ID` defined (e.g., `"vk8m"`, `"vibrato"`)

---

## Step 1: Add Button Definitions

Add buttons 7 and 9 to your plugin's `BUTTONS` array:

```python
BUTTONS = [
    # ... your existing buttons ...
    
    {"id": "7", "label": "P", "behavior": "nav", "action": "presets"},    # Load preset
    {"id": "9", "label": "S", "behavior": "nav", "action": "save_preset"}, # Save preset
    {"id": "10", "label": "10", "behavior": "nav", "action": "device_select"}, # Optional
]
```

**Important:** Buttons 7 and 9 have special handling in `module_base.py` and are automatically routed to preset functions.

---

## Step 2: Add `self.button_states` Dict

Your module must maintain a `button_states` dict to track multi-state button positions:

```python
def __init__(self):
    super().__init__()
    
    # Initialize button states from INIT_STATE
    init = self.INIT_STATE
    buttons_init = init.get("buttons", {})
    self.button_states = buttons_init.copy() if buttons_init else {
        "1": 0, "2": 0, "3": 0, "4": 0, "5": 0, "8": 0
    }
```

### Update button_states in State Methods

Every state-change method must update `self.button_states`:

```python
def _set_reverb_type(self, rev_type: int):
    """Set reverb type. Updates button_states."""
    self.button_states["2"] = rev_type  # ← Update state
    vk.set_reverb_type(rev_type)        # ← Send to device
```

---

## Step 3: Add `on_preset_loaded()` Hook

This method is called by `preset_manager` after loading a preset:

```python
def on_preset_loaded(self, variables: dict):
    """Called by preset_manager after a preset is loaded."""
    showlog.info(f"[{self.MODULE_ID}] on_preset_loaded called")
    
    # Apply all button states to device
    self._apply_all_button_states()
    
    # Apply all dial values to device
    self._apply_distortion(self.dial_values[0])
    self._apply_reverb(self.dial_values[1])
    # ... etc for all dials
```

### Helper Method: `_apply_all_button_states()`

```python
def _apply_all_button_states(self):
    """Apply all button states to the device (called on init and preset load)."""
    # Button 1: Example
    vib_idx = self.button_states.get("1", 0)
    if vib_idx == 0:
        vk.set_vibrato_on(0)
    else:
        vk.set_vibrato_on(1)
        vk.set_vibrato_type(vib_idx - 1)
    
    # Button 2: Example
    rev_idx = self.button_states.get("2", 0)
    vk.set_reverb_type(rev_idx)
    
    # ... repeat for all buttons
```

---

## Step 4: Define `INIT_STATE` (Optional)

Define default state for buttons and dials:

```python
INIT_STATE = {
    "buttons": {
        "1": 0,  # Vibrato mode index (OFF)
        "2": 0,  # Reverb type index (R1)
        "3": 0,  # Distortion type index (D1)
        # ... etc
    },
    "dials": [64, 64],  # Default dial values
}
```

---

## How It Works

### **Saving a Preset (Button 9):**

1. User presses button 9
2. `module_base.py` intercepts (before multi-state handling)
3. `show_preset_save_ui()` creates/shows `PresetSaveUI` dialog
4. Remote keyboard is enabled (CC 119 = 127)
5. User types preset name
6. `preset_manager.save_preset()` is called:
   - Captures `self.button_states` from module instance
   - Captures `dial_values` if available
   - Captures widget state if widget exists
7. Saves to `config/presets/<MODULE_ID>/<preset_name>.json`

### **Loading a Preset (Button 7):**

1. User presses button 7
2. `module_base.py` navigates to `module_presets` page
3. `module_presets.py` loads preset list from `config/presets/<MODULE_ID>/`
4. User selects a preset
5. `preset_manager.load_preset()` is called:
   - Restores `module_instance.button_states`
   - Restores dial values
   - Restores widget state
6. Calls `module_instance.on_preset_loaded()`
7. Your `on_preset_loaded()` applies states to device hardware

---

## Folder Isolation

Presets are automatically isolated by `MODULE_ID`:
- **Vibrato presets**: `config/presets/vibrato/`
- **VK8M presets**: `config/presets/vk8m/`
- **Your plugin presets**: `config/presets/<your_module_id>/`

Each module only sees its own presets when button 7 is pressed.

---

## Debugging Tips

Add logging with `*` prefix for loupe mode visibility:

```python
showlog.info(f"[{self.MODULE_ID}] Button state updated: {self.button_states}")
showlog.info(f"[{self.MODULE_ID}] on_preset_loaded: applying states...")
```

### Common Issues:

**Dialog doesn't appear:**
- Check logs for `PresetSaveUI created on-demand successfully!`
- Verify `init_page()` is called when navigating to your page
- Added fallback: dialog now creates on-demand if missing

**Preset loads but device doesn't change:**
- Verify `on_preset_loaded()` is defined in your module
- Check that `_apply_all_button_states()` sends commands to device
- Add logging to confirm methods are called

**Wrong presets shown:**
- Check `MODULE_ID` matches your folder name
- Presets are in `config/presets/<MODULE_ID>/`

---

## Example: Complete VK8M Implementation

See `plugins/vk8m_plugin.py` for a complete working example with:
- ✅ Button state tracking
- ✅ Multi-state button handlers
- ✅ `on_preset_loaded()` hook
- ✅ State application methods
- ✅ Comprehensive debugging

---

## Summary Checklist

- [ ] Add buttons 7, 9 to `BUTTONS` array
- [ ] Add `self.button_states` dict to `__init__()`
- [ ] Update `button_states` in all state-change methods
- [ ] Add `on_preset_loaded(variables)` method
- [ ] Add `_apply_all_button_states()` helper
- [ ] Define `INIT_STATE` with default values
- [ ] Test save (button 9) and load (button 7)
- [ ] Verify presets stored in correct folder

**That's it!** The preset system handles everything else automatically.

---

## Problems Encountered & Solutions

### Problem 1: Button 9 Not Triggering Save Dialog

**Symptom:** Clicking button 9 did nothing, no dialog appeared.

**Root Cause:** Button 9 handling was placed AFTER the multi-state button check in `module_base.py`. When a button was detected as multi-state, it would `break` and never reach the button 9 check.

**Solution:** Moved buttons 7 and 9 special handling BEFORE the multi-state button logic:

```python
# In module_base.py handle_event()
for rect, name in button_rects:
    if rect.collidepoint(event.pos):
        # Check button 7 and 9 FIRST, before multi-state check
        if name == "7":
            # Navigate to presets page
        if name == "9":
            show_preset_save_ui()
            break
        
        # THEN check if it's a multi-state button
        if btn_meta and states:
            # Handle multi-state logic
```

**Key Learning:** Special navigation buttons (7, 9, 10) must be handled before generic multi-state logic.

---

### Problem 2: PresetSaveUI Not Initialized

**Symptom:** 
```
[WARN] PresetSaveUI not initialized - cannot show save dialog!
_PRESET_UI exists: False
```

**Root Cause:** The `_PRESET_UI` global was `None` because:
1. `init_page()` might not have been called yet
2. The module might have been reloaded, resetting globals
3. Timing issues during page initialization

**Solution:** Added fallback initialization in `show_preset_save_ui()`:

```python
def show_preset_save_ui():
    global _PRESET_UI
    
    # Fallback: Create on-demand if it doesn't exist
    if _PRESET_UI is None:
        try:
            screen_w = getattr(cfg, "SCREEN_WIDTH", 800)
            screen_h = getattr(cfg, "SCREEN_HEIGHT", 480)
            _PRESET_UI = PresetSaveUI((screen_w, screen_h))
            showlog.info(f"[...] PresetSaveUI created on-demand")
        except Exception as e:
            showlog.error(f"[...] Failed to create PresetSaveUI: {e}")
            return
    
    if _PRESET_UI:
        _PRESET_UI.show(on_save_callback=save_current_preset)
```

**Key Learning:** Don't rely solely on initialization at page load. Add defensive on-demand creation for critical UI components.

---

### Problem 3: Dialog Active But Not Visible

**Symptom:** Logs showed dialog was active, but nothing appeared on screen:
```
[INFO] PresetSaveUI Dialog is now active and visible
```
But no visual dialog appeared.

**Root Cause:** After setting `_PRESET_UI.active = True`, the screen wasn't being redrawn immediately. The dialog existed but the next frame hadn't rendered yet.

**Solution:** Added forced redraw after activating dialog:

```python
if name == "9":
    show_preset_save_ui()
    if msg_queue:
        msg_queue.put(("invalidate", None))
        msg_queue.put(("force_redraw", 10))  # Force immediate redraw
```

**Key Learning:** When showing modal dialogs or overlays, always force an immediate screen update with `("force_redraw", N)`.

---

### Problem 4: Conflicting State Method Names

**Symptom:** Multiple buttons had states like "OFF", "V1", "V2" causing Python method name conflicts:
- Button 1: OFF, V1, V2, V3 (vibrato)
- Button 4: OFF, 2ND, 3RD (percussion)
- Button 8: V1, V2, CLN (tonewheel)

**Root Cause:** Module_base tries to call methods named after state labels (e.g., `self.off()`, `self.v1()`), but Python can't have multiple methods with the same name.

**Solution:** Used the `on_button(btn_id, state_index, state_data)` fallback for conflicting buttons:

```python
def on_button(self, btn_id: str, state_index: int = 0, state_data: dict = None):
    """Handle button press for buttons without specific state methods."""
    
    if btn_id == "1":  # Vibrato
        if state_index == 0:
            self._set_vibrato(0)  # OFF
        elif 1 <= state_index <= 6:
            self._set_vibrato(1, state_index - 1)  # V1-C3
    
    elif btn_id == "4":  # Percussion
        self._set_percussion(state_index)
    
    elif btn_id == "8":  # Tonewheel
        self._set_tonewheel(state_index)
```

**Key Learning:** 
- Use direct state methods (e.g., `self.r1()`, `self.fst()`) for unique state names
- Use `on_button()` fallback with `btn_id` and `state_index` for conflicting names

---

### Problem 5: Preset Loaded But Device Didn't Change

**Symptom:** Preset loaded successfully, button_states restored, but VK8M hardware remained unchanged.

**Root Cause:** The `preset_manager` restores the `button_states` dict in memory, but doesn't automatically send commands to the hardware device. The module must explicitly apply states.

**Solution:** Implemented `on_preset_loaded()` hook:

```python
def on_preset_loaded(self, variables: dict):
    """Called by preset_manager after a preset is loaded."""
    
    # Apply all button states to device
    self._apply_all_button_states()
    
    # Apply dial values to device
    self._apply_distortion(self.dial_values[0])
    self._apply_reverb(self.dial_values[1])
```

**Key Learning:** `preset_manager` only restores module state (Python variables). You must implement `on_preset_loaded()` to translate that state into device commands (SysEx, CC, etc.).

---

### Problem 6: Insufficient Debugging Made Issues Hard to Track

**Symptom:** Couldn't tell where in the flow things were breaking without guessing.

**Root Cause:** Initial implementation lacked comprehensive logging at critical points.

**Solution:** Added extensive debug logging with `*` prefix for loupe mode highlighting:

```python
showlog.info(f"[{self.MODULE_ID}] Button {btn_id} clicked")
showlog.info(f"[PresetSaveUI] show() called - activating dialog")
showlog.info(f"[VK8M] _set_reverb_type: type={rev_type}, button_states[2]={self.button_states['2']}")
```

The `*` prefix makes critical messages stand out in loupe mode for easier debugging.

**Key Learning:** Add comprehensive logging FIRST when implementing complex features. It pays for itself immediately when troubleshooting.

---

### Problem 7: Understanding Preset Manager Auto-Discovery

**Symptom:** Initially unclear how `preset_manager` knew what to save/load.

**Root Cause:** The preset system has multiple discovery mechanisms that weren't documented clearly.

**Solution/Understanding:** The `preset_manager` auto-discovers what to save in this priority order:

1. **Explicit `PRESET_STATE` config** (highest priority)
2. **Auto-discovery from `REGISTRY`** - extracts variables via `"variable"` field
3. **`save_state_vars.json` config** (legacy fallback)

For button states specifically:
- Looks for `module_instance.button_states` dict
- Automatically saves entire dict to `preset_data["button_states"]`

**Key Learning:** You don't need explicit save/load methods if you follow conventions:
- Use `self.button_states` dict for button state
- Use `self.dial_values` list for dials
- Implement `on_preset_loaded()` to apply loaded state to hardware

---

## Debug Log Checklist

When testing preset save/load, look for these log messages:

**On Page Navigation:**
```
*[MODE_MGR] Calling vk8m_page.init_page()
*[module_base] init_page() called
*[module_base] PresetSaveUI successfully initialized!
```

**On Button 9 Press:**
```
*[module_base] Button 9 clicked
*[module_base] Button 9 (save preset) - showing save dialog
*[PresetSaveUI] show() called - activating dialog
*[PresetSaveUI] Sent CC 119 = 127 (enable remote keyboard)
*[module_base] Drawing preset UI overlay (active)
```

**On Preset Save:**
```
*[module_base] save_current_preset called with name: 'MyPreset'
*[PresetManager] Saved preset 'MyPreset' for vk8m
```

**On Preset Load:**
```
*[PresetManager] Restored button_states = {...}
*[VK8M] on_preset_loaded called
*[VK8M] _apply_all_button_states complete
```

If any of these messages are missing, you've found where the issue is!
