# Refactor Plan: `module_base.py`

This document details how to modularize the current **`/build/pages/module_base.py`** file, which has grown too large and serves multiple unrelated responsibilities. The goal is to make the system more maintainable, testable, and consistent with the existing `core/` and `pages/` architecture.

---

## ⚙️ Overview

### Current Size & Problem
The file currently:
- Manages dial banks (UI overlays)
- Handles module lifecycle and hooks
- Draws the module UI and widgets
- Deals with MIDI, hardware dials, and event handling
- Implements preset save/load overlays

This results in **tight coupling** between UI rendering, logic, and persistence.

---

## 🧩 Proposed Breakdown

### 1. `/core/ui/dial_bank_manager.py`
**Purpose:** Isolate all logic around dial banks and multi-bank overlay management.

#### Move these sections:
- `class DialBankManager`
- `_mark_widgets_dirty()`
- `request_custom_widget_redraw()`
- `configure_dial_banks()`
- All `set_dial_bank_*`, `get_dial_bank_*`, `clear_dial_banks()`
- `_register_active_bank_with_dialhandlers()`

#### Imports required:
```python
import pygame
import showlog
from widgets.dial_widget import DialWidget
from utils.grid_layout import get_grid_cell_rect, get_zone_rect_tight, get_grid_geometry
import dialhandlers
```

#### Will expose:
```python
class DialBankManager
configure_dial_banks()
get_dial_bank_manager()
set_dial_bank_values(), set_dial_bank_value(), ...
request_custom_widget_redraw()
```

---

### 2. `/core/module_runtime.py`
**Purpose:** Manage active module lifecycle, instantiation, hook dispatching, latch system, and MIDI handling.

#### Move these sections:
- `set_active_module()`
- `_get_mod_instance()`
- `_dispatch_hook()`
- `handle_midi_note()`
- `_check_dial_latch()`
- `apply_drumbo_instrument()`

#### Imports required:
```python
import showlog
from system.module_core import ModuleBase
from plugins import drumbo_instrument_service as service
```

#### Will expose:
```python
set_active_module()
get_active_module()
handle_midi_note()
_check_dial_latch()
apply_drumbo_instrument()
```

---

### 3. `/core/preset_controller.py`
**Purpose:** Centralize all preset operations: saving, loading, showing the Preset UI.

#### Move these sections:
- `save_current_preset()`
- `load_preset()`
- `show_preset_save_ui()`
- `is_preset_ui_active()`
- `handle_remote_input()`

#### Imports required:
```python
import showlog
import config as cfg
from preset_manager import get_preset_manager
from preset_ui import PresetSaveUI
from core.service_registry import ServiceRegistry
```

#### Will expose:
```python
save_current_preset()
load_preset()
show_preset_save_ui()
is_preset_ui_active()
handle_remote_input()
```

---

### 4. `/core/utils/module_meta_utils.py`
**Purpose:** Provide pure, stateless helpers for module metadata, state sync, and dial conversions.

#### Move these sections:
- `_ensure_meta()`
- `_get_owned_slots()`
- `_snap_for_meta_default()`
- `_module_value_to_raw()`
- `_apply_state_to_dials()`
- `_sync_module_state_to_dials()`

#### Imports required:
```python
import showlog
import custom_controls
from system import state_manager, dialhandlers
```

#### Will expose:
```python
_ensure_meta()
_get_owned_slots()
_apply_state_to_dials()
_sync_module_state_to_dials()
_module_value_to_raw()
```

---

### 5. `/pages/module_page.py` (new name for current file)
**Purpose:** Focus purely on rendering and input routing.

#### Keep these sections:
- `init_page()`
- `draw_ui()`
- `get_dirty_widgets()`
- `redraw_dirty_widgets()`
- `handle_event()`
- `handle_hw_dial()`
- `_process_dial_change()`
- `_apply_snap_and_dispatch()`

This file will import from the above new modules to access dial banks, presets, and runtime.

---

## 🔗 Inter-Module Dependencies

| From | Imports | Description |
|------|----------|-------------|
| `module_page.py` | `from core.module_runtime import set_active_module, handle_midi_note` | Lifecycle and MIDI hooks |
| `module_page.py` | `from core.ui.dial_bank_manager import configure_dial_banks, request_custom_widget_redraw` | Overlay dial system |
| `module_page.py` | `from core.preset_controller import show_preset_save_ui` | Preset overlay and save/load |
| `module_page.py` | `from core.utils.module_meta_utils import _ensure_meta, _get_owned_slots` | Metadata helpers |

---

## 🧱 Implementation Phases

### Phase 1 – Extraction (no logic changes)
1. Create the new files under `/core/` and `/core/ui/`.
2. Move code verbatim into their new homes.
3. Replace top-level globals in `module_base.py` with imports.

### Phase 2 – Adaptation
1. Update imports across `pages/` and `plugins/` to reflect new paths.
2. Test UI launch (ensure no circular imports).
3. Adjust any module-specific hooks referencing old functions.

### Phase 3 – Verification
1. Run regression test: `verify_sampler_phase2.py`
2. Confirm that:
   - UI loads all modules
   - Dials sync correctly
   - Presets save/load without errors
   - Hardware latch system still works

### Phase 4 – Cleanup
1. Rename original file to `/pages/module_page.py`.
2. Remove all legacy or duplicate code.
3. Add docstrings and type hints.

---

## ✅ Benefits
- **Readability:** File size reduced by ~80%.
- **Maintainability:** Each logical concern isolated.
- **Reusability:** DialBankManager and PresetController become reusable components.
- **Testability:** Easier to unit test module lifecycle, presets, and UI layers independently.

---

## 🧭 Summary of New Structure
```
/core/
├── module_core.py              # Base ModuleBase class
├── module_runtime.py           # Active module + latch logic
├── preset_controller.py        # Preset save/load management
├── utils/
│   └── module_meta_utils.py    # Meta & state helpers
└── ui/
    └── dial_bank_manager.py    # Dial bank overlay manager

/pages/
└── module_page.py              # UI drawing, events, and rendering
```

---

**Next step:** implement Phase 1 extraction by creating the five new files and copying code blocks directly (no logic changes yet).

