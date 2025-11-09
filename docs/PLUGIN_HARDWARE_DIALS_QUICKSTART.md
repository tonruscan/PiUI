# Plugin Hardware Dials Quick Start Guide

## Critical: You Need BOTH Systems Working Together

Adding hardware-controlled dials to a plugin requires **THREE components** working together. Missing ANY of these means dials won't work.

---

## ⚡ The 3 Required Components

### 1. REGISTRY (Hardware Dial Objects)
**Location:** Plugin class definition  
**Purpose:** Creates actual Dial objects that receive hardware CC messages

```python
class YourPlugin(ModuleBase):
    page_id = "your_plugin_main"
    
    # ✅ REGISTRY creates the hardware-connected Dial objects
    REGISTRY = {
        "your_plugin": {  # Family name
            "type": "module",
            "01": {  # Dial slot 1
                "label": "Control 1",
                "range": [0, 127],
                "type": "raw",
                "default_slot": 1,
                "family": "your_plugin",
                "variable": "control_1_value",
            },
            "02": {  # Dial slot 2
                "label": "Control 2",
                "range": [0, 127],
                "type": "raw",
                "default_slot": 2,
                "family": "your_plugin",
                "variable": "control_2_value",
            },
            # Add entries for each dial (up to 8: "01" through "08")
        }
    }
```

**Without this:** Hardware dials won't create Dial objects, events never fire.

---

### 2. SLOT_TO_CTRL (Routing Map)
**Location:** Plugin class definition  
**Purpose:** Maps hardware dial slots to control IDs for `on_dial_change()` routing

```python
class YourPlugin(ModuleBase):
    # ✅ SLOT_TO_CTRL maps dial slots to control names
    SLOT_TO_CTRL = {
        1: "control_1",  # Slot 1 → "Control 1" label in on_dial_change()
        2: "control_2",  # Slot 2 → "Control 2" label
        # Must match the number of REGISTRY entries
    }
```

**Without this:** `on_dial_change()` won't be called with proper labels.

---

### 3. on_dial_change() Handler
**Location:** Plugin class methods  
**Purpose:** Receives hardware dial events and updates your widget/state

```python
class YourPlugin(ModuleBase):
    def on_dial_change(self, dial_label: str, value: int):
        """Handle hardware dial changes."""
        showlog.debug(f"*[YourPlugin] Dial '{dial_label}' = {value}")
        
        # Update your widget's visual dials
        if self.widget and hasattr(self.widget, 'my_dials'):
            # Parse dial number from label
            if " " in dial_label:
                dial_num = int(dial_label.split()[-1])  # "Control 1" → 1
            else:
                dial_num = int(dial_label.split("_")[-1])  # "control_1" → 1
            
            dial_index = dial_num - 1  # Convert to 0-based index
            
            if 0 <= dial_index < len(self.widget.my_dials):
                self.widget.my_dials[dial_index].set_value(value)
                self.widget.mark_dirty()
                showlog.debug(f"*[YourPlugin] Updated dial {dial_num} to {value}")
```

**Without this:** Hardware events arrive but nothing happens visually.

---

## 🎨 Widget Integration (Optional Visual Dials)

If you want **mini dials rendered in your widget** (like Drumbo's 8 mic controls):

### Widget: Create Dial Objects

```python
class YourWidget:
    def __init__(self, rect, ...):
        from assets.dial import Dial
        
        # Create mini dials for visual display
        self.my_dials = []
        dial_radius = cfg.DIAL_SIZE // 2  # Half size = 25px
        
        for i in range(8):
            dial = Dial(x, y, radius=dial_radius)
            dial.id = i + 1
            dial.label = f"C{i+1}"
            dial.range = [0, 127]
            dial.value = 64  # Default center
            dial.set_visual_mode("hidden")  # Don't render via grid system
            self.my_dials.append(dial)
```

### Widget: Manual Drawing

```python
import pygame.gfxdraw
import math

def draw(self, surface, device_name=None, offset_y=0):
    for dial in self.my_dials:
        # Draw dial circle
        pygame.gfxdraw.filled_circle(surface, dial.cx, dial.cy, dial.radius, fill_color)
        pygame.gfxdraw.aacircle(surface, dial.cx, dial.cy, dial.radius, outline_color)
        
        # Draw pointer line
        rad = math.radians(dial.angle)
        x0 = dial.cx + (dial.radius * 0.4) * math.cos(rad)
        y0 = dial.cy - (dial.radius * 0.4) * math.sin(rad)
        x1 = dial.cx + (dial.radius * 0.85) * math.cos(rad)
        y1 = dial.cy - (dial.radius * 0.85) * math.sin(rad)
        pygame.draw.line(surface, text_color, (int(x0), int(y0)), (int(x1), int(y1)), 2)
```

### Widget: Mouse Interaction

```python
def handle_event(self, event):
    if event.type == pygame.MOUSEBUTTONDOWN:
        for dial in self.my_dials:
            if self._dial_hit(dial, event.pos):
                dial.dragging = True
                return True
    
    elif event.type == pygame.MOUSEBUTTONUP:
        for dial in self.my_dials:
            dial.dragging = False
    
    elif event.type == pygame.MOUSEMOTION:
        for dial in self.my_dials:
            if dial.dragging:
                old_value = dial.value
                dial.update_from_mouse(*event.pos)
                if dial.value != old_value:
                    # Notify plugin
                    if self._module:
                        self._module.on_dial_change(dial.label, int(dial.value))
                    self.mark_dirty()
                return True
    return False

def _dial_hit(self, dial, pos):
    dx = pos[0] - dial.cx
    dy = pos[1] - dial.cy
    return (dx * dx + dy * dy) <= (dial.radius * dial.radius)
```

---

## 📤 Module-Level Exports

At the **bottom** of your plugin file, export these for the system to discover:

```python
# Legacy exports (REQUIRED for module_base to find your config)
MODULE_ID = YourPlugin.MODULE_ID
REGISTRY = YourPlugin.REGISTRY
BUTTONS = YourPlugin.BUTTONS
SLOT_TO_CTRL = YourPlugin.SLOT_TO_CTRL
```

**Without these exports:** The module system won't find your REGISTRY/SLOT_TO_CTRL.

---

## 🐛 Debugging Checklist

If hardware dials don't work:

### 1. Check REGISTRY is loaded
```python
showlog.debug(f"*[{self.MODULE_ID}] REGISTRY = {self.REGISTRY}")
```

### 2. Check on_dial_change() is called
```python
def on_dial_change(self, dial_label: str, value: int):
    showlog.debug(f"*[{self.MODULE_ID}] on_dial_change() ENTRY: label='{dial_label}', value={value}")
```

### 3. Check widget updates
```python
if 0 <= dial_index < len(self.widget.my_dials):
    old_value = self.widget.my_dials[dial_index].value
    self.widget.my_dials[dial_index].set_value(value)
    showlog.debug(f"*[{self.MODULE_ID}] Updated dial: {old_value}→{value}")
```

### 4. Filter logs for debugging
```powershell
Get-Content ui_log.txt -Tail 100 | Select-String -Pattern "\*\[YourPlugin"
```

---

## 📋 Complete Minimal Example

```python
from system.module_core import ModuleBase

class MinimalPlugin(ModuleBase):
    MODULE_ID = "minimal"
    page_id = "minimal_main"
    
    # ✅ REQUIRED: Hardware dial objects
    REGISTRY = {
        "minimal": {
            "type": "module",
            "01": {
                "label": "Volume",
                "range": [0, 127],
                "type": "raw",
                "default_slot": 1,
                "family": "minimal",
                "variable": "volume",
            },
        }
    }
    
    # ✅ REQUIRED: Routing map
    SLOT_TO_CTRL = {
        1: "volume",
    }
    
    # ✅ REQUIRED: Event handler
    def on_dial_change(self, dial_label: str, value: int):
        showlog.info(f"[Minimal] {dial_label} = {value}")
        # Update widget here if needed

# ✅ REQUIRED: Module-level exports
MODULE_ID = MinimalPlugin.MODULE_ID
REGISTRY = MinimalPlugin.REGISTRY
SLOT_TO_CTRL = MinimalPlugin.SLOT_TO_CTRL
```

---

## ⚠️ Common Mistakes

### ❌ Forgot REGISTRY
**Symptom:** Other plugin's dials still show up  
**Fix:** Add REGISTRY dict with entries for each dial slot

### ❌ Forgot module-level exports
**Symptom:** `on_dial_change()` never called  
**Fix:** Add `REGISTRY = YourPlugin.REGISTRY` at bottom of file

### ❌ Mismatched slot numbers
**Symptom:** Wrong dials respond to hardware  
**Fix:** Ensure REGISTRY "01"-"08" matches SLOT_TO_CTRL 1-8

### ❌ Widget dials not updating
**Symptom:** Hardware events arrive but visuals don't change  
**Fix:** Call `widget.my_dials[i].set_value()` and `widget.mark_dirty()` in `on_dial_change()`

### ❌ Breaking module_base.py
**Symptom:** ALL plugins lose hardware dials  
**Fix:** Restore module_base.py from backup, don't modify core routing

---

## 📚 Reference Implementations

- **VK8M Plugin** (`plugins/vk8m_plugin.py`): 2 dials with custom drawbar widget
- **Drumbo Plugin** (`plugins/drumbo_plugin.py`): 8 mini dials for mic levels
- **Drawbar Widget** (`widgets/drawbar_widget.py`): Manual dial rendering example

---

## 🎯 Summary: The 3 Must-Haves

1. **REGISTRY** - Creates hardware Dial objects (01-08 entries)
2. **SLOT_TO_CTRL** - Routes slots to control names (1-8 mapping)
3. **on_dial_change()** - Handles events and updates widget

**All three required.** Missing one = dials don't work.

Add debug logging with `*` prefix for easy filtering: `showlog.debug(f"*[Plugin] message")`
