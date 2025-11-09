# Repository Alterations Log

**Purpose:** Track all modifications made to the codebase so they can be reverted if needed.

**Date Started:** November 4, 2025

---

## Change 1: None-Safe Dial Iteration in module_base.py

**Date:** November 4, 2025  
**File:** `pages/module_base.py`  
**Lines:** 620, 627  
**Issue:** VK8M fails to load with `AttributeError: 'NoneType' object has no attribute 'id'`

### Problem
When switching to VK8M (or other plugins with sparse dial usage), `init_page()` attempts to iterate over `dialhandlers.dials` which contains `None` entries for empty dial slots. The code tried to access `.id` and `._mod_init` attributes without checking if the dial object exists.

### Root Cause
- VK8M uses only slots 1, 2, 5 (3 of 8 dials)
- ASCII Animator uses no dials (0 of 8)
- Drumbo uses all 8 dials
- `dialhandlers.dials` is always 8 slots: `[None] * 8` (line 1161)
- Empty slots are intentionally `None` (by design)
- `init_page()` reads old dials array before new ones are created

### Original Code (BEFORE)

**Line 619-623:**
```python
# Clear first-load flags so new module state is recalled
try:
    for d in dials:
        if hasattr(d, "_mod_init"):
            delattr(d, "_mod_init")
except Exception:
    pass
```

**Line 626-628:**
```python
owned_slots = set(_get_owned_slots())
attached = sum(1 for d in dials if d.id in owned_slots and getattr(d, "sm_param_id", None))
_mod_id = _get_module_attr("MODULE_ID", "MODULE")
```

### Modified Code (AFTER)

**Line 619-623:**
```python
# Clear first-load flags so new module state is recalled
try:
    for d in dials:
        if d and hasattr(d, "_mod_init"):  # ← Added: d and
            delattr(d, "_mod_init")
except Exception:
    pass
```

**Line 626-628:**
```python
owned_slots = set(_get_owned_slots())
attached = sum(1 for d in dials if d and d.id in owned_slots and getattr(d, "sm_param_id", None))  # ← Added: d and
_mod_id = _get_module_attr("MODULE_ID", "MODULE")
```

### Changes Made
1. Line 620: Added `d and` before `hasattr(d, "_mod_init")` to skip `None` entries
2. Line 627: Added `d and` before `d.id in owned_slots` to skip `None` entries

### Reasoning
- This pattern already exists elsewhere in the code (e.g., `_dial_hit()` at line 633)
- The code comment at line 1161 explicitly states: `"(8 slots, some may be None for empty slots)"`
- This is defensive programming for an intentional design pattern
- Fixes crash when loading VK8M, ASCII Animator, and other sparse-dial plugins

### How to Revert
If this change causes issues, revert by removing the `d and` checks:

```bash
# Line 620: Remove "d and "
if d and hasattr(d, "_mod_init"):
# Change back to:
if hasattr(d, "_mod_init"):

# Line 627: Remove "d and "
attached = sum(1 for d in dials if d and d.id in owned_slots ...)
# Change back to:
attached = sum(1 for d in dials if d.id in owned_slots ...)
```

### Testing Checklist
- [ ] VK8M loads without error
- [ ] ASCII Animator loads without error
- [ ] Drumbo loads without error
- [ ] Vibrato still works (uses all 8 dials)
- [ ] Switching between plugins works correctly
- [ ] Dial state persistence works
- [ ] No errors in log when changing modes

---

## Change 2: Drumbo Plugin Integration

**Date:** November 4, 2025  
**Files Created:**
- `plugins/drumbo_plugin.py`
- `widgets/drumbo_widget.py`
- `docs/DRUMBO_IMPLEMENTATION_MANUAL.md`

**Files Modified:**
- `config/device_page_layout.json`
- `managers/mode_manager.py`
- `rendering/renderer.py`

### 2.1 Device Layout Config

**File:** `config/device_page_layout.json`

**Original:**
```json
{ "id": 6, "img": "icons/vk8m.png", "label": "VK-8M", "plugin": "vk8m_main" },
{ "id": 7, "img": "icons/ascii.png", "label": "ASCII Animator", "plugin": "ascii_animator" },
{ "id": 99, "img": "icons/patchbay.png", "label": "Patchbay" }
```

**Modified:**
```json
{ "id": 6, "img": "icons/vk8m.png", "label": "VK-8M", "plugin": "vk8m_main" },
{ "id": 7, "img": "icons/ascii.png", "label": "ASCII Animator", "plugin": "ascii_animator" },
{ "id": 8, "img": "icons/drumbo.png", "label": "Drumbo", "plugin": "drumbo" },
{ "id": 99, "img": "icons/patchbay.png", "label": "Patchbay" }
```

**Revert Command:**
```bash
# Remove the Drumbo line (id 8)
```

### 2.2 Mode Manager Integration

**File:** `managers/mode_manager.py`

**Location 1 - Line ~141:**

**Original:**
```python
elif new_mode == "ascii_animator":
    self._setup_ascii_animator()
elif new_mode == "module_presets":
    self._setup_module_presets()
```

**Modified:**
```python
elif new_mode == "ascii_animator":
    self._setup_ascii_animator()
elif new_mode == "drumbo":
    self._setup_drumbo()
elif new_mode == "module_presets":
    self._setup_module_presets()
```

**Location 2 - Line ~170:**

**Original:**
```python
elif new_mode in ("patchbay", "text_input", "mixer", "vibrato", "vk8m_main", "ascii_animator", "module_presets"):
    record = True
```

**Modified:**
```python
elif new_mode in ("patchbay", "text_input", "mixer", "vibrato", "vk8m_main", "ascii_animator", "drumbo", "module_presets"):
    record = True
```

**Location 3 - Line ~505 (New function added after `_setup_ascii_animator`):**

**Added:**
```python
def _setup_drumbo(self):
    """Setup for Drumbo drum machine mode."""
    self.header_text = "Drumbo"
    showlog.debug("[MODE_MGR] Switched to Drumbo")
    
    try:
        from pages import module_base as page
        from plugins.drumbo_plugin import DrumboModule
        
        # Set the active module for module_base BEFORE init_page
        page.set_active_module(DrumboModule)
        
        # Initialize page
        if hasattr(page, "init_page"):
            page.init_page()
        
        showlog.debug("[MODE_MGR] Drumbo module active")
        
    except Exception as e:
        showlog.error(f"[MODE_MGR] Failed to activate Drumbo: {e}")
        import traceback
        showlog.error(traceback.format_exc())
```

**Revert Commands:**
```bash
# Remove "drumbo" from line ~143
# Remove "drumbo" from line ~170
# Delete entire _setup_drumbo() function (lines ~505-524)
```

### 2.3 Renderer Integration

**File:** `rendering/renderer.py`

**Location 1 - Line ~89:**

**Original:**
```python
elif ui_mode in ("mixer", "vibrato", "vk8m_main", "ascii_animator"):
    page["draw_ui"](self.screen, offset_y=offset_y)
```

**Modified:**
```python
elif ui_mode in ("mixer", "vibrato", "vk8m_main", "ascii_animator", "drumbo"):
    page["draw_ui"](self.screen, offset_y=offset_y)
```

**Location 2 - Line ~118:**

**Original:**
```python
themed_pages = ("dials", "presets", "mixer", "vibrato", "vk8m_main", "module_presets", "ascii_animator")
```

**Modified:**
```python
themed_pages = ("dials", "presets", "mixer", "vibrato", "vk8m_main", "module_presets", "ascii_animator", "drumbo")
```

**Revert Commands:**
```bash
# Remove "drumbo" from line ~89
# Remove "drumbo" from line ~118
```

### 2.4 New Files Created

To completely remove Drumbo integration:
```bash
rm plugins/drumbo_plugin.py
rm widgets/drumbo_widget.py
rm docs/DRUMBO_IMPLEMENTATION_MANUAL.md
```

---

## Testing After Changes

After any modifications or reversions:

1. **Start Application:**
   ```bash
   python ui.py
   ```

2. **Test Each Plugin:**
   - [ ] Device Select loads
   - [ ] VK8M loads and displays correctly
   - [ ] ASCII Animator loads and displays correctly
   - [ ] Drumbo loads and displays correctly (if integrated)
   - [ ] Vibrato loads and displays correctly
   - [ ] Switching between plugins works

3. **Check Logs:**
   ```bash
   tail -f ui_log.txt
   ```
   Look for any `AttributeError` or `NoneType` errors

4. **Test Dial Interactions:**
   - [ ] Dials respond to mouse input
   - [ ] Dial values persist when switching pages
   - [ ] MIDI CC controls work (if applicable)

---

## Notes

- All changes follow the patterns established in `PLUGIN_CREATION_MANUAL_COMPLETE.md`
- Changes are minimal and follow existing code style
- No core architecture modifications, only additions and safety checks
- If unsure about any change, check git history: `git diff HEAD~1`

---

## Change History

| Date | Change | Files | Reason | Status |
|------|--------|-------|--------|--------|
| 2025-11-04 | None-safe dial iteration | module_base.py | Fix VK8M crash | Active |
| 2025-11-04 | Drumbo plugin integration | 7 files | Add drum machine | Active |

---

**Last Updated:** November 4, 2025
