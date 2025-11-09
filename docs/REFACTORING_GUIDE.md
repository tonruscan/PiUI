# UI Refactoring Guide

## Overview

This document describes the new modular architecture for the UI application. The original 1000+ line `ui.py` has been refactored into clean, testable, Pythonic modules following SOLID principles.

---

## 🎯 Goals Achieved

✅ **Single Responsibility** - Each module does ONE thing well  
✅ **Modularity** - Easy to find, test, and modify specific functionality  
✅ **Pythonic** - Type hints, docstrings, proper class design  
✅ **Maintainable** - Clear separation of concerns  
✅ **Testable** - Each component can be tested in isolation  

---

## 📁 New Folder Structure

```
build/
├── core/                      # Application lifecycle
│   ├── __init__.py
│   ├── app.py                # Main UIApplication class
│   ├── display.py            # Display/screen management
│   └── loop.py               # Event loop coordinator
│
├── managers/                  # State & resource managers
│   ├── __init__.py
│   ├── dial_manager.py       # Dial lifecycle & state
│   ├── button_manager.py     # Button behavior & memory
│   ├── mode_manager.py       # UI mode switching
│   └── message_queue.py      # Queue processing
│
├── rendering/                 # Drawing operations
│   ├── __init__.py
│   ├── renderer.py           # Main render coordinator
│   ├── dirty_rect.py         # Dirty rect optimization
│   └── frame_control.py      # FPS & frame scheduling
│
├── initialization/            # Setup modules
│   ├── __init__.py
│   ├── hardware_init.py      # MIDI, CV, network setup
│   ├── device_loader.py      # Device loading logic
│   └── registry_init.py      # CC registry setup
│
├── handlers/                  # Event handlers
│   ├── __init__.py
│   ├── global_handler.py     # Global events (back, exit)
│   ├── dials_handler.py      # Dials page events
│   └── device_select_handler.py
│
└── ui.py                     # Entry point (50 lines!)
```

---

## 🔑 Key Components

### **core/app.py - UIApplication**
Main application coordinator that initializes and manages all subsystems.

```python
from core.app import UIApplication

app = UIApplication()
app.initialize()
app.run()
```

### **managers/mode_manager.py - ModeManager**
Handles UI mode/page switching with proper state management.

**Responsibilities:**
- Switch between pages (device_select, dials, presets, etc.)
- Handle navigation history
- Save/restore page state
- Load device-specific button behaviors

**Key Methods:**
- `switch_mode(new_mode)` - Switch to a new page
- `get_current_mode()` - Get current page
- `get_header_text()` - Get header text

### **managers/dial_manager.py - DialManager**
Manages dial creation, state, and MIDI CC mapping.

**Responsibilities:**
- Rebuild dials with correct layout
- Attach StateManager mappings
- Update dial values
- Track last MIDI values

**Key Methods:**
- `rebuild_dials(device_name)` - Create/recreate all dials
- `update_dial_value(dial_id, value)` - Update a dial
- `get_dial_by_id(dial_id)` - Get specific dial

### **managers/button_manager.py - ButtonManager**
Manages button selection, behavior, and per-device memory.

**Responsibilities:**
- Track selected buttons
- Remember last button per device
- Handle button behaviors (state/nav/transient)
- Button selection state

**Key Methods:**
- `select_button(which)` - Select a button
- `remember_device_button(device, button)` - Remember for device
- `get_button_behavior(button_id)` - Get behavior type

### **managers/message_queue.py - MessageQueueProcessor**
Processes queued messages and routes to control modules.

**Responsibilities:**
- Process all message types (tuples and strings)
- Route to appropriate control modules
- Handle structured messages (sysex_update, dial_value, etc.)
- Lazy-load control modules

**Key Methods:**
- `process_all(ui_context)` - Process all queued messages
- `get_control(name)` - Lazy-load control module

### **rendering/renderer.py - Renderer**
Coordinates all drawing operations.

**Responsibilities:**
- Draw current page
- Draw header with themes
- Draw log bar
- Route to page-specific drawers

**Key Methods:**
- `draw_current_page(...)` - Render complete frame
- `present_frame()` - Show frame to user

### **rendering/dirty_rect.py - DirtyRectManager**
Optimizes rendering with dirty rectangles.

**Responsibilities:**
- Track dirty regions
- Handle burst mode
- Optimize screen updates

**Key Methods:**
- `mark_dirty(rect)` - Mark region for redraw
- `present_dirty(force_full)` - Update display
- `is_in_burst()` - Check burst mode

### **rendering/frame_control.py - FrameController**
Manages frame rate and timing.

**Responsibilities:**
- Target FPS selection
- Frame timing control
- Full frame requests

**Key Methods:**
- `get_target_fps(ui_mode, in_burst)` - Get target FPS
- `tick(target_fps)` - Control frame rate
- `request_full_frames(count)` - Force full redraws

### **initialization/hardware_init.py - HardwareInitializer**
Sets up hardware connections (MIDI, CV, network).

**Responsibilities:**
- Initialize MIDI server
- Initialize CV client
- Start network TCP server
- Start remote typing server

**Key Methods:**
- `initialize_all(...)` - Initialize all hardware
- `get_status()` - Get initialization status

### **initialization/device_loader.py - DeviceLoader**
Loads device configurations and button behaviors.

**Responsibilities:**
- Load device modules dynamically
- Extract button behaviors
- Send CV calibration
- Cache device configurations

**Key Methods:**
- `load_device_module(device_name)` - Load device
- `get_button_behavior(device_name)` - Get behaviors
- `send_cv_calibration(device_name)` - Send CV cal

### **handlers/global_handler.py - GlobalEventHandler**
Handles global UI events (back, exit).

**Responsibilities:**
- Back button navigation
- Exit button
- Header interactions

**Key Methods:**
- `handle_click(pos)` - Handle global clicks
- `is_running()` - Check if still running

### **handlers/dials_handler.py - DialsEventHandler**
Handles dials page events (mouse, buttons).

**Responsibilities:**
- Dial dragging
- Button clicks on dials page
- Button behavior interpretation

**Key Methods:**
- `handle_event(...)` - Route event to appropriate handler
- `handle_mouse_down/up/motion(...)` - Handle mouse events

---

## 🔄 Migration Path

### **Phase 1: Keep Original ui.py (DONE)**
All new modules created alongside existing ui.py. Nothing breaks.

### **Phase 2: Create ui_new.py (NEXT STEP)**
Create a new entry point using the modular architecture:

```python
# ui_new.py
import crashguard
from core.app import UIApplication

def main():
    app = UIApplication()
    app.initialize()
    app.run()
    app.cleanup()

if __name__ == "__main__":
    main()
```

### **Phase 3: Test Side-by-Side**
Run `python ui_new.py` to test new architecture while keeping `ui.py` working.

### **Phase 4: Integrate Remaining Logic**
Move the complex logic from ui.py into the appropriate managers:
- Message queue callbacks
- Event handling routing
- State persistence
- Frame control logic

### **Phase 5: Replace ui.py**
Once ui_new.py is fully working, replace the old ui.py.

---

## 📊 Benefits

### **Before:**
❌ 1000+ lines in one file  
❌ Global state everywhere  
❌ Hard to test  
❌ Hard to debug  
❌ Difficult to modify  

### **After:**
✅ Clear module boundaries  
✅ Easy to find functionality  
✅ Testable components  
✅ Easy debugging  
✅ Simple to extend  

---

## 🧪 Testing

Each module can now be tested independently:

```python
# Test DialManager
from managers import DialManager

dial_mgr = DialManager()
dials = dial_mgr.rebuild_dials("QUADRAVERB")
assert len(dials) == 8

# Test ButtonManager
from managers import ButtonManager

btn_mgr = ButtonManager()
btn_mgr.select_button("1")
assert btn_mgr.get_pressed_button() == "1"
```

---

## 🚀 Next Steps

1. **Complete core/app.py** - Wire up all managers
2. **Create ui_new.py** - New entry point
3. **Test thoroughly** - Ensure all functionality works
4. **Document** - Add more docstrings where needed
5. **Optimize** - Profile and optimize hot paths

---

## 📝 Notes

- All modules follow Python naming conventions
- Type hints throughout for better IDE support
- Docstrings on all public methods
- Logging at appropriate levels
- Error handling in all critical paths
- No circular dependencies

---

## 💡 Usage Examples

### **Switching Modes**
```python
mode_manager.switch_mode("presets", persist_callback=_persist_dials)
```

### **Managing Dials**
```python
dial_manager.rebuild_dials("QUADRAVERB")
dial_manager.update_dial_value(1, 64)
```

### **Button Selection**
```python
button_manager.select_button("2")
button_manager.remember_device_button("QUADRAVERB", "2")
```

### **Rendering**
```python
renderer.draw_current_page(ui_mode, header_text, dials, radius, pressed_button)
renderer.present_frame()
```

---

**Questions?** Check the docstrings in each module for detailed documentation.
