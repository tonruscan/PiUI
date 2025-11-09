# Plugin Quick Start Guide

**How to create a high-performance 100 FPS plugin from scratch in minutes**

This guide shows the exact steps we used to create the Drumbo drum machine plugin, achieving 100 FPS performance with 6% CPU usage.

---

## The Secret: Start with a Proven Baseline

**DON'T** start from scratch or copy a complex plugin. **DO** start with `test_minimal_plugin.py` - a clean, verified 100 FPS baseline.

---

## Step 1: Copy the Minimal Plugin Template

```powershell
cd plugins
cp test_minimal_plugin.py my_plugin.py
```

The minimal plugin template contains:
- Clean ModuleBase structure
- Correct PLUGIN_METADATA with `fps_mode="high"`
- Simple widget integration
- Button handling
- Theme support

**This template is PROVEN to run at 100 FPS with 6% CPU.**

---

## Step 2: Rename Everything in Your New Plugin

In `my_plugin.py`, find and replace:

1. **Class name**: `TestMinimal` → `MyPlugin`
   ```python
   class MyPlugin(ModuleBase):
   ```

2. **page_id**: `"test_minimal_main"` → `"my_plugin_main"`
   ```python
   page_id = "my_plugin_main"
   ```

3. **MODULE_ID and PLUGIN_ID**: `"test_minimal"` → `"my_plugin"`
   ```python
   MODULE_ID = "my_plugin"
   PLUGIN_ID = "my_plugin"
   ```

4. **Plugin class name**: `TestMinimalPlugin` → `MyPluginPlugin`
   ```python
   class MyPluginPlugin(PluginBase):
       name = "My Plugin"
       page_id = MyPlugin.page_id
   ```

5. **Log messages**: Update showlog messages to use your plugin name
   ```python
   showlog.info("[MyPlugin] Module initialized")
   ```

---

## Step 3: Create Your Widget (Optional)

If you need a custom widget:

```powershell
cd widgets
# Create new widget file
notepad my_plugin_main_widget.py
```

**Widget Requirements:**
- `__init__(self, rect, on_change=None, theme=None, init_state=None)`
- `draw(surface, device_name=None, offset_y=0)` - Returns dirty rect
- `is_dirty()` - Returns True if needs redraw
- `clear_dirty()` - Called after draw
- `mark_dirty()` - Call when state changes

**Important:** Use the widget from another working plugin as a template (e.g., `drumbo_main_widget.py`).

---

## Step 4: Update config/device_page_layout.json

Add your plugin to a button (choose 8 or 9 for test plugins):

```json
{
  "button": "8",
  "plugin": "my_plugin_main"
}
```

**Note:** Use the `page_id` value, NOT the MODULE_ID!

---

## Step 5: Update managers/mode_manager.py

Add handling for your plugin's page_id:

```python
# Around line 142, add to the mode switching logic:
elif new_mode == "my_plugin_main":
    self._setup_my_plugin()

# Add the setup method (around line 200):
def _setup_my_plugin(self):
    """Setup My Plugin module."""
    try:
        from plugins.my_plugin import MyPlugin
        page = self.app.ui_ctx.page_manager.get_page("module")
        if page:
            page.set_active_module(MyPlugin)
    except Exception as e:
        showlog.error(f"Failed to load My Plugin: {e}")

# Add to navigation recording tuple (around line 171):
if new_mode in ("dials", "presets", "mixer", "vibrato", "vk8m_main", "module_presets", "ascii_animator", "drumbo", "drumbo_main", "test_minimal_main", "my_plugin_main"):
```

---

## Step 6: Update rendering/renderer.py

Add your plugin to themed pages:

```python
# Around line 118, add to themed_pages tuple:
themed_pages = ("dials", "presets", "mixer", "vibrato", "vk8m_main", "module_presets", "ascii_animator", "drumbo", "drumbo_main", "test_minimal_main", "my_plugin_main")

# Around line 89, add to ui_mode check:
elif ui_mode in ("dials", "presets", "mixer", "vibrato", "vk8m_main", "module_presets", "ascii_animator", "drumbo", "drumbo_main", "test_minimal_main", "my_plugin_main"):
```

---

## Step 7: Test Your Barebones Plugin

```powershell
cd ..
python ui.py
```

**Expected results:**
- ✅ 100 FPS displayed in top-right corner
- ✅ ~6% CPU usage (same as vibrato/vk8m)
- ✅ Plugin loads when you press the button
- ✅ Widget displays (if you added one)
- ✅ Clean logs with no errors

**If FPS is below 100:** Something is wrong. Go back and check you copied from `test_minimal_plugin.py` correctly.

---

## Step 8: Add Features Incrementally

**CRITICAL:** Add features ONE AT A TIME and test FPS after each addition!

### Example: Adding Audio (from Drumbo)

**Step 8.1 - Add pygame.mixer initialization:**

```python
def __init__(self):
    super().__init__()
    self.widget = None
    # ... existing code ...
    
    # Audio initialization
    self._init_audio()
    self.loaded_sounds = {}

def _init_audio(self):
    """Initialize pygame mixer for audio playback."""
    try:
        import pygame
        import os
        
        os.environ['SDL_AUDIODRIVER'] = 'alsa'
        devices = ['sysdefault:CARD=sndrpijustboomd', 'plughw:2,0', 'hw:2,0', 'default']
        
        for device in devices:
            try:
                os.environ['AUDIODEV'] = device
                pygame.mixer.init(frequency=48000, size=-16, channels=2, buffer=128)
                
                if pygame.mixer.get_init():
                    showlog.info(f"*[MyPlugin] Audio initialized on {device}")
                    pygame.mixer.set_num_channels(16)
                    return
                else:
                    pygame.mixer.quit()
            except:
                pass
        
        showlog.error("*[MyPlugin] All audio device options failed!")
        
    except Exception as e:
        showlog.error(f"*[MyPlugin] Failed to initialize audio: {e}")
```

**Test:** Restart app, check FPS still 100, check logs for audio init success.

---

**Step 8.2 - Add sample loading:**

```python
def _load_samples(self, instrument):
    """Load samples for the specified instrument."""
    if instrument in self.loaded_sounds:
        return
    
    try:
        import pygame
        import os
        
        sample_dir = os.path.join("assets", "samples", "drums", instrument)
        
        if not os.path.exists(sample_dir):
            showlog.error(f"*[MyPlugin] Sample directory not found: {sample_dir}")
            return
        
        samples = []
        for filename in sorted(os.listdir(sample_dir)):
            if filename.endswith('.wav'):
                filepath = os.path.join(sample_dir, filename)
                try:
                    sound = pygame.mixer.Sound(filepath)
                    samples.append(sound)
                    showlog.info(f"*[MyPlugin] Loaded {filename}")
                except Exception as e:
                    showlog.error(f"*[MyPlugin] Failed to load {filename}: {e}")
        
        self.loaded_sounds[instrument] = samples
        showlog.info(f"*[MyPlugin] Loaded {len(samples)} {instrument} samples")
        
    except Exception as e:
        showlog.error(f"*[MyPlugin] Sample loading error: {e}")

def attach_widget(self, widget):
    """Called by module_base after widget is instantiated."""
    self.widget = widget
    if widget:
        widget._module = self
    
    # Load initial samples
    self._load_samples("snare")
```

**Test:** Restart, check FPS still 100, check logs show samples loaded.

---

**Step 8.3 - Add MIDI listener:**

```python
def attach_widget(self, widget):
    """Called by module_base after widget is instantiated."""
    self.widget = widget
    if widget:
        widget._module = self
    
    self._load_samples("snare")
    self._register_midi_listener()

def _register_midi_listener(self):
    """Register to receive MIDI note events."""
    try:
        from core.service_registry import ServiceRegistry
        registry = ServiceRegistry()
        midi_server = registry.get('midi_server')
        
        if midi_server and midi_server.inport:
            original_callback = midi_server._on_midi_in
            
            def my_plugin_midi_callback(msg):
                if msg.type == 'note_on' and msg.velocity > 0:
                    self._on_midi_note(msg.note, msg.velocity)
                original_callback(msg)
            
            midi_server.inport.callback = my_plugin_midi_callback
            showlog.info("*[MyPlugin] MIDI listener registered")
        else:
            showlog.warning("*[MyPlugin] MIDI server not available")
            
    except Exception as e:
        showlog.error(f"*[MyPlugin] Failed to register MIDI listener: {e}")

def _on_midi_note(self, note, velocity):
    """Handle incoming MIDI note events."""
    if note == 38:  # Snare
        self._play_sample("snare", velocity)
    
    if self.widget:
        self.widget.on_midi_note(note, velocity)

def _play_sample(self, instrument, velocity):
    """Play a sample for the specified instrument."""
    try:
        if instrument not in self.loaded_sounds:
            self._load_samples(instrument)
        
        samples = self.loaded_sounds.get(instrument, [])
        if not samples:
            showlog.warning(f"*[MyPlugin] No samples loaded for {instrument}")
            return
        
        sound = samples[0]
        volume = velocity / 127.0
        sound.set_volume(volume)
        sound.play()
        showlog.info(f"*[MyPlugin] Playing {instrument}, vel={velocity}")
        
    except Exception as e:
        showlog.error(f"*[MyPlugin] Playback error: {e}")
```

**Test:** Restart, check FPS still 100, send MIDI note, verify audio plays.

---

## Critical Success Factors

### ✅ DO:
- Start with `test_minimal_plugin.py` as your baseline
- Test FPS after EVERY feature addition
- Use asterisk prefix `*[PluginName]` in logs for loupe mode visibility
- Copy the PLUGIN_METADATA exactly from the template
- Keep `__init__()` lightweight - no heavy operations

### ❌ DON'T:
- Don't copy from complex plugins with lots of features
- Don't add multiple features before testing
- Don't skip the FPS test between additions
- Don't modify class structure during debugging
- Don't use deprecated `FPS_HIGH_PAGES` in config/performance.py (use PLUGIN_METADATA instead)

---

## Troubleshooting

### Plugin runs at 36 FPS instead of 100:
- ❌ **Wrong!** File corruption or bad structure
- ✅ **Fix:** Delete plugin, start over from `test_minimal_plugin.py`
- Don't try to debug incrementally - rebuild from clean baseline

### Widget doesn't display:
- Check widget path in CUSTOM_WIDGET matches actual file
- Check widget has correct `draw()` signature: `draw(surface, device_name=None, offset_y=0)`
- Check widget is in `widgets/` directory

### Plugin doesn't load:
- Check button mapping in `config/device_page_layout.json` uses correct `page_id`
- Check `mode_manager.py` has case for your `page_id` (not MODULE_ID)
- Check import statement matches your class name exactly

### MIDI listener errors:
- Must import from `core.service_registry` not `system`
- Must wrap original callback, don't replace completely
- Check `midi_server.inport` exists before registering

---

## Summary: The 10-Minute Plugin

Time breakdown for Drumbo drum machine:

1. **Copy template:** 30 seconds
2. **Rename classes/IDs:** 2 minutes
3. **Update mode_manager.py:** 1 minute
4. **Update renderer.py:** 1 minute
5. **Update device_page_layout.json:** 30 seconds
6. **Test barebones (100 FPS confirmed):** 1 minute
7. **Add pygame.mixer init + test:** 2 minutes
8. **Add sample loading + test:** 1 minute
9. **Add MIDI listener + test:** 1 minute

**Total: ~10 minutes to working drum machine with 100 FPS performance**

The key is starting with a proven template and testing after each small addition. If you ever drop below 100 FPS, you know exactly which feature caused it.

---

## Files Modified Checklist

For every new plugin, you must update exactly 3 files:

- [ ] `config/device_page_layout.json` - Add button mapping
- [ ] `managers/mode_manager.py` - Add mode case and setup method
- [ ] `rendering/renderer.py` - Add to themed_pages and ui_mode check

That's it! Everything else is in your plugin file.

---

## The Drumbo Success Story

Drumbo was rebuilt from scratch using this exact process after the original implementation became corrupted and ran at 36 FPS. By following this guide:

- ✅ 100 FPS with 6% CPU (same as vibrato/vk8m)
- ✅ Working widget with theme integration
- ✅ Audio playback with pygame.mixer
- ✅ MIDI note triggering
- ✅ Sample loading system
- ✅ Clean, maintainable code

**Time to rebuild from scratch: 10 minutes**

**Time spent debugging the old corrupted version: 2+ hours**

**Lesson: Always start clean with test_minimal_plugin.py!**



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
