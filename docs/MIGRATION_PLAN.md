# Migration Plan: From Monolithic to Modular UI

## 🎯 Current Status

✅ **Phase 1 Complete** - New modular structure created
- All folders created (core/, managers/, rendering/, initialization/, handlers/)
- All base modules implemented
- Original ui.py still intact and working

---

## 📋 Remaining Work

### **Step 1: Complete UIApplication Integration**

The `core/app.py` needs to be completed with full integration:

**Tasks:**
1. Wire up all managers in `_init_managers()`
2. Implement `_update()` callback with queue processing
3. Implement `_render()` callback with proper rendering
4. Add event routing in the event loop
5. Connect all callbacks between managers

**Estimated Time:** 2-3 hours

---

### **Step 2: Test New Architecture**

Create test script to verify functionality:

```python
# test_refactored.py
from core.app import UIApplication

app = UIApplication()
app.initialize()
# Test individual components
```

**Tasks:**
1. Test display initialization
2. Test hardware initialization
3. Test manager creation
4. Test mode switching
5. Test dial creation
6. Test event handling

**Estimated Time:** 1-2 hours

---

### **Step 3: Incremental Feature Migration**

Move features from old ui.py to new architecture one at a time:

#### **Feature 1: Basic Event Loop**
- Migrate pygame event handling
- Test with minimal page rendering

#### **Feature 2: Device Selection**
- Migrate device_select page
- Test device selection flow

#### **Feature 3: Dials Page**
- Migrate dials page logic
- Test dial interaction
- Test button behavior

#### **Feature 4: Mode Switching**
- Migrate full mode switching
- Test all page transitions
- Test state persistence

#### **Feature 5: Message Queue**
- Migrate queue processing
- Test message routing
- Test control module integration

#### **Feature 6: Rendering Pipeline**
- Migrate dirty rect logic
- Test frame rate control
- Test burst mode

**Estimated Time:** 4-6 hours (depending on issues found)

---

### **Step 4: Side-by-Side Testing**

Run both versions simultaneously to compare:

```bash
# Terminal 1
python ui.py

# Terminal 2
python ui_new.py
```

**Compare:**
- Visual output
- Performance (FPS)
- Memory usage
- Behavior correctness

**Estimated Time:** 1 hour

---

### **Step 5: Replace Original**

Once new version is fully tested:

```bash
# Backup original
cp ui.py ui_old_backup.py

# Replace with new
cp ui_new.py ui.py
```

**Estimated Time:** 10 minutes

---

## 🔧 Integration Checklist

### **Core Application**
- [ ] Complete `_init_managers()` in app.py
- [ ] Implement `_update()` callback
- [ ] Implement `_render()` callback
- [ ] Wire up event loop handlers
- [ ] Test initialization sequence

### **Managers**
- [ ] Test DialManager independently
- [ ] Test ButtonManager independently
- [ ] Test ModeManager independently
- [ ] Test MessageQueueProcessor independently

### **Rendering**
- [ ] Test Renderer independently
- [ ] Test DirtyRectManager independently
- [ ] Test FrameController independently
- [ ] Verify FPS targeting works

### **Hardware**
- [ ] Test MIDI initialization
- [ ] Test CV initialization
- [ ] Test network initialization
- [ ] Verify callbacks work

### **Event Handling**
- [ ] Test GlobalEventHandler
- [ ] Test DialsEventHandler
- [ ] Test DeviceSelectEventHandler
- [ ] Verify routing works

---

## 🐛 Common Issues & Solutions

### **Issue: Circular Imports**
**Solution:** Use dependency injection, pass instances not modules

### **Issue: Global State Access**
**Solution:** Pass state through context dictionaries

### **Issue: Missing References**
**Solution:** Update imports, use explicit dependencies

### **Issue: Callback Hell**
**Solution:** Use event system or observer pattern

---

## 📊 Success Criteria

✅ All pages render correctly  
✅ All interactions work (dials, buttons, navigation)  
✅ FPS matches or exceeds original  
✅ No visual glitches  
✅ State persists correctly  
✅ Hardware connections work  
✅ Message queue processes correctly  
✅ No memory leaks  

---

## 🚀 Quick Start for Next Session

To continue the refactoring:

1. **Open `core/app.py`**
2. **Complete `_init_managers()`:**
   ```python
   def _init_managers(self):
       from managers import DialManager, ButtonManager, ModeManager
       from managers.message_queue import MessageQueueProcessor
       
       self.dial_manager = DialManager()
       self.button_manager = ButtonManager()
       self.mode_manager = ModeManager(self.dial_manager, self.button_manager)
       self.msg_processor = MessageQueueProcessor(self.msg_queue)
       # ... etc
   ```

3. **Complete `_update()`:**
   ```python
   def _update(self):
       # Process message queue
       ui_context = {
           "ui_mode": self.mode_manager.get_current_mode(),
           "screen": self.screen,
           # ... etc
       }
       self.msg_processor.process_all(ui_context)
       
       # Update animations
       showheader.update()
   ```

4. **Complete `_render()`:**
   ```python
   def _render(self):
       offset_y = showheader.get_offset()
       self.renderer.draw_current_page(
           self.mode_manager.get_current_mode(),
           self.mode_manager.get_header_text(),
           self.dial_manager.get_dials(),
           60,  # radius
           self.button_manager.get_pressed_button(),
           offset_y=offset_y
       )
       self.renderer.present_frame()
   ```

5. **Test with:** `python ui_new.py`

---

## 📝 Notes

- Keep old ui.py until new version is 100% verified
- Test each feature incrementally
- Don't try to migrate everything at once
- Use git branches for safety
- Document any issues found

---

## 🎓 Learning Resources

**Python Best Practices:**
- Type hints: https://docs.python.org/3/library/typing.html
- Docstrings: PEP 257
- Code style: PEP 8

**Design Patterns:**
- Manager pattern
- Observer pattern
- Dependency injection

**Testing:**
- pytest for unit tests
- Mock for dependencies
- Coverage for test coverage

---

**Next Milestone:** Complete core/app.py integration (2-3 hours)
