# Deprecation & Streamlining Guide
## UI Application V2 - Redundancy Analysis & Cleanup Roadmap

**Generated:** October 31, 2025  
**Purpose:** Identify duplicate code, redundant patterns, and streamlining opportunities

---

## Executive Summary

After comprehensive analysis of the codebase, the following major redundancies have been identified:

1. **Duplicate Driver Files** - LCD1602.py and ht16k33_seg8.py exist in both root and `drivers/`
2. **Duplicate Preset Management** - Two preset managers with overlapping functionality
3. **Legacy State Management** - Old `.old.py` files and deprecated state systems
4. **Redundant Device State Systems** - `device_states.py` vs `device_presets.py` overlap
5. **Multiple Init Functions** - Initialization scattered across multiple modules
6. **Duplicate Helper Functions** - Similar utility functions in multiple locations
7. **Inconsistent Import Patterns** - Same modules imported different ways

---

## 🔴 CRITICAL: Files to Delete Immediately

### Old/Backup Files (*.old.*)

These files are clearly deprecated backup versions:

#### `dial_router.old.py`
**Status:** ⚠️ DEPRECATED - Replace with new system  
**Used By:** None (legacy backup)  
**Replacement:** Custom dials now handled via `config/custom_dials.json` and device modules  
**Action:** ✅ **DELETE** after confirming no dependencies

**Original Purpose:**
- Loaded custom dial definitions from JSON
- Provided theme inheritance from devices

**Why Deprecated:**
- Functionality merged into device system
- No longer imported anywhere in codebase

---

#### `dial_state.old.py`
**Status:** ⚠️ DEPRECATED - Replaced by StateManager  
**Used By:** None (legacy backup)  
**Replacement:** `system/state_manager.py` (comprehensive state system)  
**Action:** ✅ **DELETE** after confirming migration complete

**Original Purpose:**
- Simple page/slot-based dial state storage
- JSON persistence for dial values
- Applied state to dial objects

**Why Deprecated:**
- `StateManager` provides much richer functionality:
  - Knob-level granularity (not just page/slot)
  - Source tracking (device/module)
  - Param IDs (4-digit hex hash)
  - Autosave thread
  - CC registry integration
  - Family/semantic support
- No imports found in active codebase

---

## 🟡 MEDIUM PRIORITY: Duplicate Files

### Duplicate Hardware Drivers

#### LCD1602.py (Root) vs drivers/LCD1602.py
**Status:** ⚠️ EXACT DUPLICATES  
**Lines:** 120 lines each (identical)  
**Used By:** 
- `network.py` imports from root
- `initialization/hardware_init.py` imports from root
- No imports from `drivers/` found

**Analysis:**
Both files are identical copies of the ST7032 I2C LCD driver for Raspberry Pi.

**Recommendation:**
1. ✅ **Keep:** `drivers/LCD1602.py` (proper location)
2. ❌ **Delete:** Root `LCD1602.py`
3. 🔧 **Update imports:**
   ```python
   # OLD (2 locations):
   import LCD1602
   
   # NEW (standardized):
   from drivers import LCD1602
   ```

**Migration Steps:**
```bash
# 1. Update imports in these files:
#    - network.py (line ~300)
#    - initialization/hardware_init.py (line ~25)

# 2. Delete root file:
rm LCD1602.py
```

---

#### ht16k33_seg8.py (Root) vs drivers/ht16k33_seg8.py
**Status:** ⚠️ NEARLY IDENTICAL (minor segment map differences)  
**Lines:** 
- Root: 50 lines
- Drivers: 54 lines (extended SEGMENTS dict with K, M, Q, V, W, X, Z)

**Used By:**
- `network.py` imports from root
- `initialization/hardware_init.py` imports from root
- No imports from `drivers/` found

**Analysis:**
The `drivers/` version has a more complete character set:
```python
# drivers/ version has these extras:
"K": 0x75, "M": 0x37, "Q": 0x67, "V": 0x3E, "W": 0x7E, "X": 0x76, "Z": 0x5B
```

**Recommendation:**
1. ✅ **Keep:** `drivers/ht16k33_seg8.py` (more complete)
2. ❌ **Delete:** Root `ht16k33_seg8.py`
3. 🔧 **Update imports:**
   ```python
   # OLD:
   import ht16k33_seg8
   
   # NEW:
   from drivers import ht16k33_seg8
   ```

---

## 🟠 OVERLAPPING SYSTEMS: Preset Management

### Two Preset Managers with Different Scopes

#### `preset_manager.py` (Root)
**Status:** 🟢 ACTIVE - Old System for Device Pages  
**Lines:** 580 lines  
**Purpose:** Manages device page presets (Quadraverb, etc.)  
**Features:**
- Save/load named presets for devices
- Autosave thread
- Legacy format support
- Device-specific presets

**Key Functions:**
```python
def get_page_config(page_id, module_instance)
def save_preset(page_id, preset_name, module_instance, widget)
def load_preset(page_id, preset_name, module_instance, widget)
def list_presets(page_id)
def delete_preset(page_id, preset_name)
```

---

#### `managers/preset_manager.py` (UnifiedPresetManager)
**Status:** 🟢 ACTIVE - New System for Module Pages  
**Lines:** 300 lines  
**Purpose:** Unified preset system for modules (Vibrato Maker, etc.)  
**Features:**
- Auto-discovery from REGISTRY
- Widget state management
- Button state tracking
- Unified UI handling

**Key Functions:**
```python
def init_for_page(module_id, module_instance, widget)
def handle_event(event)
def draw(screen, offset_y)
def get_current_type()
def get_current_name()
```

---

### Analysis: Merging Opportunity

**Problem:**
Two separate systems with significant overlap:
- Both save/load presets to JSON
- Both track button states
- Both handle widget state
- Both provide list/delete functionality
- Similar autosave logic

**Differences:**
| Feature | Root `preset_manager.py` | `managers/UnifiedPresetManager` |
|---------|-------------------------|-------------------------------|
| **Target** | Device pages | Module pages |
| **UI** | No built-in UI | Built-in preset browser UI |
| **Discovery** | Manual config | Auto from REGISTRY |
| **Widget** | Optional param | First-class support |
| **Location** | `config/presets/` | `config/presets/` |

**Recommendation:**
🔧 **MERGE INTO SINGLE SYSTEM**

**Proposed Architecture:**
```python
# New unified managers/preset_manager.py

class PresetManager:
    """Unified preset management for both devices and modules"""
    
    def __init__(self):
        self.device_handler = DevicePresetHandler()
        self.module_handler = ModulePresetHandler()
        self.ui = PresetBrowserUI()  # Optional UI component
    
    def save_preset(self, target_type: str, target_id: str, name: str, **kwargs):
        """
        target_type: "device" | "module"
        target_id: device_name or module_id
        """
        if target_type == "device":
            return self.device_handler.save(target_id, name, **kwargs)
        else:
            return self.module_handler.save(target_id, name, **kwargs)
    
    # Similar pattern for load, list, delete, etc.
```

**Migration Plan:**
1. Extract common functionality into base class
2. Specialize for device vs module
3. Add factory method to create appropriate handler
4. Update all callers to use unified interface
5. Delete old root `preset_manager.py`

---

## 🟡 OVERLAPPING SYSTEMS: Device State Management

### device_states.py vs device_presets.py

Both files manage device state but with different semantics:

#### `device_states.py`
**Purpose:** Manages INIT and CURRENT states  
**Storage:** `config/device_states.json`  
**Key Functions:**
```python
def store_init(device_name, page_id, values, button_states=None)
def get_init(device_name, page_id)
def get_page_state(device_name, page_id)  # CURRENT or fallback to INIT
def send_init_state(device_name)
```

**Use Cases:**
- Button 6: Save INIT preset
- First load: Send INIT to device
- State recall after page switch

---

#### `device_presets.py`
**Purpose:** Manages named presets separate from INIT  
**Storage:** `config/device_presets.json` + factory patches in `config/patches.json`  
**Key Functions:**
```python
def store_preset(device_name, page_id, preset_name, dial_values)
def get_preset(device_name, page_id, preset_name)
def list_presets(device_name, page_id=None)
def delete_preset(device_name, page_id, preset_name)
def get_patch(device_name, preset_name)  # Factory patches
```

**Use Cases:**
- Named preset save/load
- Preset browser page
- Factory patch recall

---

### Analysis: Semantic Overlap

**Problem:**
- INIT state is just a special preset named "INIT"
- Storing in separate files creates synchronization issues
- `get_preset()` already falls back between presets and patches
- Two different JSON files for essentially the same data

**Current Structure:**
```
config/
  device_states.json      # INIT + CURRENT states
  device_presets.json     # Named presets
  patches.json            # Factory presets
```

**Recommendation:**
🔧 **CONSOLIDATE INTO SINGLE FILE WITH SEMANTIC KEYS**

**Proposed Structure:**
```json
{
  "QUADRAVERB": {
    "01": {
      "__INIT__": {
        "dials": [0, 50, 100, ...],
        "buttons": {...}
      },
      "__CURRENT__": {
        "dials": [10, 60, 90, ...],
        "buttons": {...}
      },
      "My Preset 1": {
        "dials": [...],
        "buttons": {...}
      },
      "My Preset 2": { ... }
    }
  }
}
```

**Benefits:**
- Single source of truth
- No synchronization issues
- Easier to list all available states
- Clear semantic meaning with `__INIT__` and `__CURRENT__`
- Factory patches remain separate (read-only)

**Migration Plan:**
1. Create `system/device_state_manager.py` (unified)
2. Merge functions from both files
3. Add migration script to convert old JSON files
4. Update all imports
5. Delete `device_states.py` and `device_presets.py`

---

## 🟢 LOW PRIORITY: Scattered Initialization

### Multiple Init Functions Across Modules

**Problem:** Initialization logic scattered across many modules, each with its own `init()` function.

**Current Pattern:**
```python
# 15+ modules with init():
showlog.init(screen, font, size)
showheader.init(screen, font, size, spacing)
midiserver.init(dial_cb, sysex_cb)
cv_client.init()
dialhandlers.init(msg_queue)
devices.load()
device_states.load()
device_presets.load()
navigator.set_page("device_select")
# ... etc
```

**Partially Addressed:**
The new V2 architecture already improves this with:
- `initialization/hardware_init.py` - Hardware setup
- `initialization/registry_init.py` - Registry setup
- `initialization/device_loader.py` - Device loading
- `core/app.py::initialize()` - 8-phase orchestration

**Remaining Issues:**
1. Some modules still have global state requiring init
2. Init order dependencies not always clear
3. Some init functions return values, others mutate globals

**Recommendation:**
🔧 **CONTINUE REFACTORING TO DEPENDENCY INJECTION**

**Ideal Pattern:**
```python
# Instead of:
import showlog
showlog.init(screen, font, size)
showlog.log("message")

# Prefer:
from system import Logger
logger = Logger(screen, font, size)
logger.log("message")

# Or use ServiceRegistry:
services.register("logger", logger)
other_module_logger = services.get("logger")
```

**Already Done Well:**
- `DisplayManager` - Instantiated, not global
- `EventBus` - Instantiated
- `ServiceRegistry` - Instantiated
- `PageRegistry` - Instantiated
- Most managers - Instantiated

**Still Need Work:**
- `showlog` - Global state
- `showheader` - Global state
- `dialhandlers` - Global state
- `midiserver` - Global state
- `cv_client` - Global state
- `navigator` - Global state

---

## 🔵 CODE SMELL: Duplicate Helper Functions

### Multiple Places with Similar Utilities

#### Theme Resolution
**Found in:**
1. `helper.py::device_theme.get()` - Main implementation
2. `helper.py::theme_rgb()` - Wrapper
3. `showheader.py` - Local theme caching
4. `pages/page_dials.py` - Inline theme access
5. `rendering/renderer.py::_draw_header()` - Theme application

**Recommendation:**
✅ **Already mostly centralized in helper.py**  
Minor cleanup: Remove inline theme lookups in pages

---

#### Color Conversion
**Found in:**
1. `helper.py::hex_to_rgb()` - Main implementation
2. `utils/config_helpers.py::get_cfg_color()` - Wrapper with config access
3. Inline conversions in several pages

**Recommendation:**
🔧 **Standardize on helper.py**
- Move `get_cfg_color()` to `helper.py`
- Update all imports

---

#### Font Loading
**Found in:**
1. `utils/font_helper.py` - Dedicated module (not used?)
2. `pages/page_dials.py::_get_font()` - Cached loading
3. Inline `pygame.font.Font()` in 10+ files

**Recommendation:**
🔧 **CONSOLIDATE TO SINGLE FONT CACHE**

**Proposed:**
```python
# utils/font_cache.py
_cache = {}

def get_font(name: str, size: int) -> pygame.font.Font:
    key = f"{name}:{size}"
    if key not in _cache:
        _cache[key] = pygame.font.Font(name, size)
    return _cache[key]

def preload_fonts():
    """Preload commonly used fonts at startup"""
    get_font("Rasegard", 40)
    get_font("Courier", 14)
    # ...
```

---

## 🟣 ARCHITECTURAL IMPROVEMENTS

### 1. Service Locator Pattern for Global State

**Current Problem:**
Many modules maintain global state:

```python
# dialhandlers.py
current_device_id = None
current_device_name = None
current_page_id = "01"
live_states = {}
live_button_states = {}

# navigator.py
_history = []
_current = None
```

**Recommendation:**
🔧 **MIGRATE TO SERVICES**

**Proposed:**
```python
# Create service classes
class NavigationService:
    def __init__(self):
        self._history = []
        self._current = None
    
    def set_page(self, page_name, record=True):
        # Implementation
        pass

class DeviceContextService:
    def __init__(self):
        self.current_device_id = None
        self.current_device_name = None
        self.current_page_id = "01"
        self.live_states = {}

# Register in ServiceRegistry
services.register("navigation", NavigationService())
services.register("device_context", DeviceContextService())

# Access anywhere
nav = services.get("navigation")
nav.set_page("dials")
```

---

### 2. Event-Driven State Changes

**Current Problem:**
Direct function calls create tight coupling:

```python
# In dialhandlers.py
def on_dial_change(dial_id, value):
    # ... process ...
    state_manager.set_value(...)  # Direct call
    midiserver.send_cc(...)       # Direct call
```

**Recommendation:**
🔧 **USE EVENT BUS MORE EXTENSIVELY**

**Proposed:**
```python
# Publisher
def on_dial_change(dial_id, value):
    event_bus.publish("dial_changed", {
        "dial_id": dial_id,
        "value": value,
        "device": current_device_name,
        "page": current_page_id
    })

# Subscribers
state_manager.subscribe_to_dial_changes(event_bus)
midi_output.subscribe_to_dial_changes(event_bus)
ui_updater.subscribe_to_dial_changes(event_bus)
```

---

### 3. Configuration Management

**Current Problem:**
`config.py` is a 600+ line file with mixed concerns:

```python
# All in one file:
LOG_LEVEL = 0
MIDI_DEVICE = "MS1x1"
DIAL_RADIUS = 50
BUTTON_WIDTH = 95
MIXER_FADER_HEIGHT = 200
# ... 500 more lines
```

**Recommendation:**
🔧 **SPLIT INTO LOGICAL MODULES**

**Proposed Structure:**
```
config/
  __init__.py           # Exports all configs
  display.py            # Screen, FPS, visual settings
  midi.py               # MIDI devices, CC mappings
  network.py            # Network hosts, ports
  styling.py            # Colors, fonts, layouts
  paths.py              # File paths, directories
  logging.py            # Log levels, formats
```

**Usage:**
```python
from config import display, midi, styling

screen_width = display.WIDTH
dial_color = styling.DIAL_FILL_COLOR
midi_device = midi.DEVICE_NAME
```

---

### 4. Dependency Injection Completion

**Current Status:** Partially implemented

**Already Using DI:**
- Core modules (app, display, loop, etc.)
- Managers (dial, button, mode, etc.)
- Rendering components

**Still Direct Imports:**
- `config` - Imported everywhere
- `showlog` - Global functions
- `helper` - Utility functions
- `dialhandlers` - Global state functions

**Recommendation:**
🔧 **COMPLETE DI MIGRATION**

**Priority Order:**
1. ✅ **Core** - Already done
2. ✅ **Managers** - Already done
3. 🔧 **System Services** - In progress (StateManager, CCRegistry)
4. ⏳ **Utilities** - Next (showlog, helper)
5. ⏳ **Legacy Modules** - Last (dialhandlers, midiserver)

---

## 📊 REDUNDANCY METRICS

### Summary Statistics

| Category | Duplicate Items | Potential LOC Savings |
|----------|----------------|----------------------|
| **Old Files** | 2 files | ~150 lines |
| **Duplicate Drivers** | 2 files | ~170 lines |
| **Preset Systems** | 2 systems | ~300 lines (after merge) |
| **State Systems** | 2 systems | ~200 lines (after merge) |
| **Helper Functions** | ~15 duplicates | ~100 lines |
| **Init Functions** | ~20 scattered | ~50 lines (after consolidation) |
| **TOTAL** | **~40 items** | **~970 lines** |

**Current Codebase:** ~15,000 lines (excluding tests, docs, venv)  
**Potential Reduction:** ~6.5% with aggressive refactoring

---

## 🗺️ MIGRATION ROADMAP

### Phase 1: Safe Deletions (Low Risk)
**Timeline:** 1-2 hours  
**Impact:** Immediate cleanup, no code changes

- [ ] Delete `dial_router.old.py` (confirm no imports)
- [ ] Delete `dial_state.old.py` (confirm no imports)
- [ ] Delete root `LCD1602.py` (after updating 2 imports)
- [ ] Delete root `ht16k33_seg8.py` (after updating 2 imports)

**Verification:**
```bash
# Search for any imports
grep -r "import dial_router" .
grep -r "import dial_state" .
grep -r "^import LCD1602" .
grep -r "^import ht16k33_seg8" .
```

---

### Phase 2: Driver Consolidation (Low Risk)
**Timeline:** 30 minutes  
**Impact:** 2 file changes

- [ ] Update `network.py` line ~300: `from drivers import LCD1602`
- [ ] Update `initialization/hardware_init.py` line ~25: `from drivers import LCD1602`
- [ ] Update `network.py` line ~15: `from drivers import ht16k33_seg8`
- [ ] Update `initialization/hardware_init.py` line ~26: `from drivers import ht16k33_seg8`
- [ ] Test hardware initialization
- [ ] Delete root driver files

---

### Phase 3: State System Merge (Medium Risk)
**Timeline:** 4-8 hours  
**Impact:** Major refactor, touch ~10 files

- [ ] Design unified state schema
- [ ] Create `system/device_state_manager.py`
- [ ] Implement merged API
- [ ] Write migration script for JSON files
- [ ] Update `dialhandlers.py` (heavy user)
- [ ] Update `pages/presets.py`
- [ ] Update `control/mixer_control.py`
- [ ] Update `control/presets_control.py`
- [ ] Test all device state operations
- [ ] Delete old files after migration

---

### Phase 4: Preset System Unification (High Risk)
**Timeline:** 8-16 hours  
**Impact:** Major refactor, new architecture

- [ ] Design unified preset interface
- [ ] Extract common base class
- [ ] Implement device preset handler
- [ ] Implement module preset handler
- [ ] Create factory/router
- [ ] Update all preset callers (~15 locations)
- [ ] Migrate all presets to new format
- [ ] Extensive testing
- [ ] Delete old root `preset_manager.py`

---

### Phase 5: Global State Elimination (High Risk)
**Timeline:** 16-24 hours  
**Impact:** Architectural change, touch ~50 files

**Priority Order:**
1. [ ] `navigator` → `NavigationService`
2. [ ] `dialhandlers` → `DeviceContextService` + `DialRoutingService`
3. [ ] `showlog` → `LoggingService`
4. [ ] `showheader` → `HeaderService`
5. [ ] `midiserver` → `MIDIService`
6. [ ] `cv_client` → `CVService`

**For each module:**
- Create service class
- Register in ServiceRegistry
- Update all callers
- Remove global state
- Test thoroughly

---

### Phase 6: Configuration Split (Low Risk)
**Timeline:** 2-4 hours  
**Impact:** Better organization, ~100 file imports to update

- [ ] Create `config/` directory structure
- [ ] Split `config.py` into logical modules
- [ ] Update `config/__init__.py` to re-export everything
- [ ] Update imports (can be done gradually)
- [ ] Delete monolithic `config.py`

---

### Phase 7: Helper Consolidation (Low Risk)
**Timeline:** 2-3 hours  
**Impact:** Minor cleanup, ~20 files

- [ ] Create unified `utils/font_cache.py`
- [ ] Move `get_cfg_color()` to `helper.py`
- [ ] Remove duplicate theme lookups
- [ ] Standardize all helper imports
- [ ] Delete unused utility files

---

## ⚠️ RISK ASSESSMENT

### Low Risk (Can do immediately)
- ✅ Delete `.old.*` files
- ✅ Delete duplicate drivers
- ✅ Split config.py
- ✅ Consolidate helpers

### Medium Risk (Requires testing)
- ⚠️ Merge state systems (changes data format)
- ⚠️ Update driver imports (hardware dependent)

### High Risk (Major refactor)
- 🔴 Merge preset systems (changes API)
- 🔴 Eliminate global state (touches many files)
- 🔴 Complete DI migration (architectural change)

---

## 🧪 TESTING STRATEGY

### Before Any Changes
1. Create comprehensive test suite
2. Document current behavior
3. Take snapshots of JSON files
4. Record MIDI message logs

### After Each Phase
1. Run unit tests
2. Test hardware connections
3. Test all device pages
4. Test all preset operations
5. Test state persistence
6. Test MIDI/CV output
7. Visual regression testing

### Rollback Plan
1. Keep git commits small and atomic
2. Tag before each phase
3. Keep old files in `deprecated/` folder temporarily
4. Document migration in commit messages

---

## 📝 DECISION RECORD

### Why Not Delete Everything Now?

**Reasons for Phased Approach:**

1. **Risk Management**
   - Some modules have subtle dependencies
   - Hardware testing requires physical setup
   - Production system in use

2. **Time Investment**
   - Full refactor = 40-60 hours
   - Phased approach allows validation
   - Can stop if issues arise

3. **Backwards Compatibility**
   - Some JSON files in use
   - Hardware calibration data
   - User presets

4. **Learning Opportunity**
   - V2 architecture still being validated
   - May discover better patterns
   - Avoid premature optimization

---

## 📚 FURTHER READING

Related documentation:
- `COMPREHENSIVE_FUNCTION_REFERENCE.md` - Complete function catalog
- `ARCHITECTURE_DIAGRAM.md` - System architecture
- `REFACTORING_GUIDE.md` - General refactoring principles
- `MIGRATION_PLAN.md` - V1 to V2 migration details

---

## ✅ ACTION ITEMS FOR V2 RELEASE

### Must Do (Blocking V2)
- [ ] Delete `.old.*` files (30 min)
- [ ] Consolidate drivers (30 min)
- [ ] Document remaining duplicates

### Should Do (V2.1)
- [ ] Merge state systems (1 day)
- [ ] Consolidate helpers (2-3 hours)

### Nice to Have (V2.2+)
- [ ] Merge preset systems (2 days)
- [ ] Eliminate global state (3 days)
- [ ] Split config.py (3 hours)

---

**End of Deprecation Guide**

*This document will be updated as cleanup progresses.*
