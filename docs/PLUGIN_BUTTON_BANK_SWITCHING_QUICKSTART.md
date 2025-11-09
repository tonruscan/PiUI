# Plugin Button Bank Switching Quick-Start Guide

**Created:** November 4, 2025  
**Purpose:** Add hardware button-controlled bank switching to toggle which visual elements hardware dials control

---

## Overview

This guide shows how to implement button-controlled bank switching where one set of hardware dials can control different sets of visual dials/parameters by pressing a button. Based on the Drumbo plugin implementation.

**Use Case:** You have 8 hardware dials but 16+ visual controls. Button press toggles which "bank" (set of 8) the hardware controls.

---

## Three-Part Implementation

### Part 1: Widget State & Toggle Method

**File:** `widgets/your_widget.py`

#### 1.1 Add Bank State to `__init__()`

```python
def __init__(self, app, surface):
    super().__init__()
    self.app = app
    self.surface = surface
    
    # Bank switching state
    self.active_bank = "A"  # or "1", "primary", etc.
    
    # Create your visual controls (all visible at once)
    self.controls_bank_a = []  # First 8 controls
    self.controls_bank_b = []  # Second 8 controls
```

#### 1.2 Add Toggle Method

```python
def toggle_bank(self):
    """Toggle between banks for hardware dial routing."""
    self.active_bank = "B" if self.active_bank == "A" else "A"
    showlog.info(f"[YourWidget] Hardware dials now control Bank {self.active_bank}")
    self.mark_dirty()  # Trigger redraw if you have visual indicator
```

#### 1.3 Add Visual Indicator (Optional but Recommended)

```python
def draw(self, surface):
    """Draw widget with bank indicator."""
    # ... your existing drawing code ...
    
    # Show which bank is active (top-right corner example)
    bank_text = f"HW→BANK {self.active_bank}"
    font = pygame.font.Font(None, 20)
    text_surf = font.render(bank_text, True, (0, 255, 0))
    surface.blit(text_surf, (self.rect.width - 80, 10))
```

---

### Part 2: Plugin Button Definition

**File:** `plugins/your_plugin.py`

#### 2.1 Add Button to BUTTONS Array

```python
class YourModule(ModuleBase):
    # ... existing code ...
    
    BUTTONS = [
        # Your existing buttons...
        {
            "id": "2",  # Or any available button number
            "behavior": "multi",  # Multi-state button
            "states": ["A", "B"]  # Button cycles through these states
        },
        # ... other buttons ...
    ]
```

**Button Behavior Options:**
- `"multi"` - Cycles through states on each press (what we want)
- `"momentary"` - Only active while held
- `"nav"` - Navigation action (presets, save, etc.)

---

### Part 3: Plugin Button Handler

**File:** `plugins/your_plugin.py`

#### 3.1 Handle Button Press in `on_button()`

```python
def on_button(self, btn_id: str, state_index: int = 0, state_data: dict = None):
    """Handle button presses."""
    showlog.info(f"[YourPlugin] Button {btn_id} pressed, state={state_index}")
    
    # Update button states
    self.button_states[btn_id] = state_index
    
    if btn_id == "2":  # Match the button ID from BUTTONS array
        # Toggle bank A/B
        if self.widget:
            self.widget.toggle_bank()
            showlog.info(f"[YourPlugin] Switched to Bank {self.widget.active_bank}")
```

---

### Part 4: Dial Routing Based on Bank

**File:** `plugins/your_plugin.py`

#### 4.1 Update `on_dial_change()` to Route by Bank

```python
def on_dial_change(self, dial_label: str, value: int):
    """Handle dial changes with bank-aware routing."""
    if not self.widget:
        return
    
    try:
        # Parse dial number from label (e.g., "Control 1" or "ctrl_1")
        if " " in dial_label:
            dial_num = int(dial_label.split()[-1])
        else:
            dial_num = int(dial_label.split("_")[-1])
        
        # Hardware dials 1-8 route to different targets based on bank
        if 1 <= dial_num <= 8:
            if self.widget.active_bank == "B":
                # Bank B: Hardware dials control second set (9-16)
                target_controls = self.widget.controls_bank_b
                control_index = dial_num - 1
                actual_control = dial_num + 8  # For logging
            else:
                # Bank A: Hardware dials control first set (1-8)
                target_controls = self.widget.controls_bank_a
                control_index = dial_num - 1
                actual_control = dial_num
            
            # Update the target control
            if 0 <= control_index < len(target_controls):
                target_controls[control_index].set_value(value)
                showlog.debug(f"[YourPlugin] Bank {self.widget.active_bank}: Dial {dial_num} → Control {actual_control} = {value}")
                self.widget.mark_dirty()
        
        # Handle mouse-controlled dials (9-16) - always route directly
        elif 9 <= dial_num <= 16:
            control_index = dial_num - 9
            self.widget.controls_bank_b[control_index].set_value(value)
            self.widget.mark_dirty()
            
    except Exception as e:
        showlog.error(f"[YourPlugin] Dial routing error: {e}")
```

---

## Complete Example: Minimal Plugin

```python
# plugins/bank_example_plugin.py

from pages.module_base import ModuleBase
import showlog

class BankExample(ModuleBase):
    """Example plugin with bank switching."""
    
    page_id = "bank_example"
    
    # Define button with bank states
    BUTTONS = [
        {"id": "2", "behavior": "multi", "states": ["A", "B"]},
    ]
    
    # Define 8 hardware dials (will control 16 visual dials via banking)
    REGISTRY = {
        f"0{i}": {
            "label": f"Control {i}",
            "min": 0,
            "max": 127,
            "default": 64
        }
        for i in range(1, 9)  # Hardware dials 1-8
    }
    
    SLOT_TO_CTRL = {i: f"control_{i}" for i in range(1, 9)}
    
    def on_button(self, btn_id: str, state_index: int = 0, state_data: dict = None):
        """Handle button press for bank switching."""
        if btn_id == "2" and self.widget:
            self.widget.toggle_bank()
            showlog.info(f"[BankExample] Now controlling Bank {self.widget.active_bank}")
    
    def on_dial_change(self, dial_label: str, value: int):
        """Route dial changes based on active bank."""
        if not self.widget:
            return
        
        dial_num = int(dial_label.split()[-1])
        
        if 1 <= dial_num <= 8:
            # Route to bank A or B controls
            if self.widget.active_bank == "B":
                target = self.widget.bank_b_controls[dial_num - 1]
            else:
                target = self.widget.bank_a_controls[dial_num - 1]
            
            target.set_value(value)
            self.widget.mark_dirty()
```

---

## Testing Checklist

- [ ] **Button Definition:** Button appears in BUTTONS array with `"multi"` behavior
- [ ] **Widget State:** `active_bank` variable exists in widget `__init__()`
- [ ] **Toggle Method:** `toggle_bank()` method switches bank and logs change
- [ ] **Button Handler:** `on_button()` calls `widget.toggle_bank()` for correct button ID
- [ ] **Dial Routing:** `on_dial_change()` checks `widget.active_bank` before routing
- [ ] **Visual Indicator:** Bank state visible on screen (optional but helpful)
- [ ] **Test Bank A:** Press button, confirm "Bank A" indicator, turn hardware dial 1, verify first control moves
- [ ] **Test Bank B:** Press button again, confirm "Bank B" indicator, turn hardware dial 1, verify second control moves
- [ ] **Mouse Test:** Mouse control still works on all visual controls regardless of bank

---

## Common Mistakes

❌ **Forgot button behavior:** Using `"behavior": "momentary"` instead of `"behavior": "multi"`  
✅ **Fix:** Multi-state buttons MUST have `"behavior": "multi"` and `"states": [...]` array

❌ **Wrong button ID:** `on_button()` checks for wrong button number  
✅ **Fix:** Match the `"id"` in BUTTONS array with the `if btn_id ==` check

❌ **No bank check in dial routing:** `on_dial_change()` doesn't check `active_bank`  
✅ **Fix:** Always check `self.widget.active_bank` before routing hardware dials 1-8

❌ **Mouse dials also banked:** Mouse control broken when bank switched  
✅ **Fix:** Only apply bank routing to hardware dials (1-8), not mouse-controlled dials (9+)

❌ **No visual feedback:** User can't tell which bank is active  
✅ **Fix:** Draw bank indicator text in widget's `draw()` method

---

## Advanced: More Than 2 Banks

To add 3+ banks (e.g., A/B/C):

1. Change button states: `"states": ["A", "B", "C"]`
2. Update toggle method to cycle through all states:
   ```python
   def toggle_bank(self):
       banks = ["A", "B", "C"]
       current_idx = banks.index(self.active_bank)
       self.active_bank = banks[(current_idx + 1) % len(banks)]
   ```
3. Add more routing cases in `on_dial_change()`:
   ```python
   if self.widget.active_bank == "C":
       target = self.widget.bank_c_controls[dial_num - 1]
   elif self.widget.active_bank == "B":
       target = self.widget.bank_b_controls[dial_num - 1]
   else:
       target = self.widget.bank_a_controls[dial_num - 1]
   ```

---

## Pattern Summary

**Widget Side:**
1. Add `self.active_bank = "A"` state variable
2. Create `toggle_bank()` method to cycle state
3. Optionally draw bank indicator

**Plugin Side:**
1. Add button to BUTTONS with `"multi"` behavior and states array
2. Handle button press → call `widget.toggle_bank()`
3. Check `widget.active_bank` in `on_dial_change()` to route hardware dials

**Result:** 8 hardware dials can control 16+ visual parameters via button toggle!

---

## Related Documentation

- `PLUGIN_HARDWARE_DIALS_QUICKSTART.md` - Basic dial integration (prerequisite)
- `PLUGIN_BUTTON_REFERENCE.md` - Complete button system documentation
- Example: `plugins/drumbo_plugin.py` - Full working implementation

---

**Questions?** This pattern works for any widget that needs hardware dial multiplexing via button-controlled banking.
