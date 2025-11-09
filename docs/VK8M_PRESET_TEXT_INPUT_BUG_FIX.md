# Bug Report: VK8M Save Preset Dialog - Text Input Not Working

**Date:** November 2, 2025  
**Severity:** High  
**Status:** Fixed  
**Affected Versions:** Pre-fix  
**Fixed In:** Current version  

## Problem Summary
The save preset dialog appeared correctly in VK8M mode, but typed characters did not appear on screen. The same functionality worked perfectly in Vibrato mode.

## Root Cause
The `_handle_remote_char()` method in `core/app.py` (line 780-791) only handled text input routing for `"vibrato"` mode and `"patchbay"` mode, but **did not include `"vk8m_main"`** in its mode check.

### Broken Code
```python
# BROKEN CODE (lines 785-791 in core/app.py):
if ui_mode == "vibrato":
    from pages import module_base as vibrato
    if hasattr(vibrato, "is_preset_ui_active") and vibrato.is_preset_ui_active():
        vibrato.handle_remote_input(char)
elif ui_mode == "patchbay":
    from pages import patchbay
    patchbay.handle_remote_input(char)
```

### What Was Happening
When a user typed in VK8M mode:
1. ✅ Remote typing server received keystrokes
2. ✅ Message queue received `("remote_char", char)` messages
3. ✅ `_handle_remote_char()` was called with `ui_mode="vk8m_main"`
4. ❌ **But the ui_mode check failed** because `"vk8m_main"` wasn't in the if statement
5. ❌ Text was never routed to the preset UI handler
6. ❌ Characters appeared to vanish into the void

## The Fix
Changed the mode check to use a tuple that includes both module-based modes:

```python
# FIXED CODE (lines 785-797 in core/app.py):
if ui_mode in ("vibrato", "vk8m_main"):
    showlog.debug(f"*[APP._handle_remote_char] Module mode detected!")
    from pages import module_base
    if hasattr(module_base, "is_preset_ui_active") and module_base.is_preset_ui_active():
        showlog.debug(f"*[APP._handle_remote_char] Preset UI is active, routing to module_base")
        module_base.handle_remote_input(char)
    else:
        showlog.debug(f"*[APP._handle_remote_char] Preset UI not active")
elif ui_mode == "patchbay":
    showlog.debug(f"*[APP._handle_remote_char] Patchbay mode, routing to patchbay")
    from pages import patchbay
    patchbay.handle_remote_input(char)
else:
    showlog.debug(f"*[APP._handle_remote_char] Unhandled ui_mode '{ui_mode}'")
```

### Key Changes
1. Changed `if ui_mode == "vibrato"` to `if ui_mode in ("vibrato", "vk8m_main")`
2. Added comprehensive debug logging with `*` prefix for easy filtering
3. Unified the import to use `module_base` directly (not aliased as `vibrato`)

## Why This Bug Occurred

### 1. Hard-coded Mode List
The handler explicitly listed modes instead of using a pattern or registry. When new modes are added, developers must remember to update multiple locations.

### 2. No Centralization
Multiple places in the codebase check for module modes:
- `core/app.py` line 787: `if ui_mode in ("vibrato", "vk8m_main")`
- `core/mixins/message_mixin.py` line 125: `if ui_mode in ("vibrato", "vk8m_main")`

### 3. Copy-Paste Errors
When VK8M was added, developers updated `message_mixin.py` but missed `app.py`.

### 4. Duplicate Logic
Both `app.py` and `message_mixin.py` had `_handle_remote_char()` methods. The one in `app.py` takes precedence due to how callbacks are registered in `_connect_message_callbacks()`.

## Prevention Strategy: Streamline Text Input Handling

### 1. Centralize Module Mode Detection
Create a single source of truth for which modes support text input:

```python
# In core/ui_context.py or config/pages.py:
MODULE_MODES_WITH_TEXT_INPUT = ("vibrato", "vk8m_main", "tremolo", "reverb")

def supports_text_input(ui_mode: str) -> bool:
    """Check if a UI mode supports text input (preset save, patchbay labels, etc.)"""
    return ui_mode in MODULE_MODES_WITH_TEXT_INPUT or ui_mode == "patchbay"
```

**Usage:**
```python
# In app.py:
from core.ui_context import supports_text_input

def _handle_remote_char(self, msg: tuple, ui_context: dict):
    _, char = msg
    ui_mode = ui_context.get("ui_mode")
    
    if supports_text_input(ui_mode):
        # Route to appropriate handler
```

### 2. Use Page Registry Metadata
Leverage the existing page registry to declare text input support:

```python
# When registering pages:
self.page_registry.register("vk8m_main", vk8m_page, "VK8M",
    meta={
        "themed": True, 
        "supports_text_input": True, 
        "has_preset_ui": True
    })

# In _handle_remote_char:
def _handle_remote_char(self, msg: tuple, ui_context: dict):
    _, char = msg
    ui_mode = ui_context.get("ui_mode")
    
    page_info = self.page_registry.get(ui_mode)
    if page_info and page_info.get("meta", {}).get("supports_text_input"):
        # Route to appropriate handler
        if page_info.get("meta", {}).get("has_preset_ui"):
            from pages import module_base
            if module_base.is_preset_ui_active():
                module_base.handle_remote_input(char)
        elif ui_mode == "patchbay":
            from pages import patchbay
            patchbay.handle_remote_input(char)
```

### 3. Eliminate Duplicate Handlers
Remove `_handle_remote_char()` from `app.py` and use only the message_mixin.py version:

```python
# In app.py _connect_message_callbacks():
# Instead of:
# self.msg_processor.on_remote_char = self._handle_remote_char

# Use mixin version:
from core.mixins.message_mixin import MessageMixin
self.msg_processor.on_remote_char = lambda msg, ctx: MessageMixin._handle_remote_char(self, msg, ctx)
```

### 4. Auto-Detection via Module Base
Any module using `module_base` automatically gets text input support:

```python
def _handle_remote_char(self, msg: tuple, ui_context: dict):
    """Handle remote character input with auto-detection."""
    _, char = msg
    ui_mode = ui_context.get("ui_mode")
    
    # Check if current page uses module_base
    page_info = self.page_registry.get(ui_mode)
    if page_info:
        module = page_info.get("module")
        # If page imports from module_base, it supports preset UI
        if hasattr(module, "is_preset_ui_active"):
            if module.is_preset_ui_active():
                module.handle_remote_input(char)
                return
    
    # Fallback to special cases
    if ui_mode == "patchbay":
        from pages import patchbay
        patchbay.handle_remote_input(char)
```

### 5. Add Registration Validation
When a new module is registered, validate text input routing:

```python
def validate_module_registration(module_id: str, module):
    """Ensure new modules are properly configured for text input."""
    warnings = []
    
    # Check if module has preset support but isn't in text input handlers
    if hasattr(module, "BUTTONS"):
        for btn in module.BUTTONS:
            if btn.get("action") == "save_preset":
                # This module needs text input!
                page_id = getattr(module, "page_id", module_id)
                if page_id not in MODULE_MODES_WITH_TEXT_INPUT:
                    warnings.append(
                        f"⚠️  Module {module_id} has save_preset button "
                        f"but page_id '{page_id}' is not in text input handlers!"
                    )
    
    for warning in warnings:
        showlog.warn(warning)
    
    return warnings
```

## Recommended Implementation Order

### ✅ Phase 1: Immediate (DONE)
- [x] Add `"vk8m_main"` to app.py handler
- [x] Add comprehensive debug logging
- [x] Test fix in both VK8M and Vibrato

### 📋 Phase 2: Short-term (Next Sprint)
- [ ] Verify message_mixin.py has same fix
- [ ] Create `supports_text_input()` utility function
- [ ] Add to both app.py and message_mixin.py

### 🔧 Phase 3: Medium-term (Next Quarter)
- [ ] Add `supports_text_input` metadata to page registry
- [ ] Update all module registrations with metadata
- [ ] Refactor handlers to use page registry

### 🏗️ Phase 4: Long-term (Architectural)
- [ ] Eliminate duplicate _handle_remote_char implementations
- [ ] Consolidate all text input routing in one place
- [ ] Add automated validation on module registration

## Testing Checklist for Future Modules

When adding a new module with preset save functionality:

- [ ] Test save preset button shows dialog
- [ ] Test typing characters appear on screen  
- [ ] Test backspace removes characters
- [ ] Test Enter key saves preset
- [ ] Test Escape key cancels dialog
- [ ] Verify ui_mode is in text input handler checks (both app.py and message_mixin.py)
- [ ] Verify remote typing server receives keystrokes (check logs with `grep "*[REMOTE_TYPING]"`)
- [ ] Test in both the new module AND vibrato to ensure nothing broke
- [ ] Test with PC keyboard client connected to port 8765
- [ ] Verify CC 119 is sent when dialog opens (enables keyboard)

## Debugging Process Used

### Tools Added
1. **Comprehensive Debug Logging**: Added `*` prefix to all debug messages for easy filtering
   ```bash
   grep "*\[" ui_log.txt  # Filter only debug messages
   ```

2. **Flow Tracing**: Added logs at every step:
   - Remote typing server receives keystroke
   - Message queue processes message
   - Handler routing decision
   - Module base receives character
   - Preset UI processes character
   - Draw method renders text

### Key Discovery Points
1. Dialog was showing (✅ visual rendering worked)
2. Remote server was receiving keystrokes (✅ network layer worked)  
3. Message queue was processing messages (✅ async processing worked)
4. But no MESSAGE_MIXIN logs appeared (❌ routing failed)
5. Found duplicate handler in app.py that took precedence
6. Handler didn't include vk8m_main in mode check

## Files Modified

### Core Changes
- ✅ `core/app.py` - Added `"vk8m_main"` to mode check (line 787)
- ✅ `core/app.py` - Added debug logging (lines 789-797)

### Already Correct
- 🔍 `core/mixins/message_mixin.py` - Already had correct check (line 125)
- 🔍 `pages/module_base.py` - Handler was correct
- 🔍 `preset_ui.py` - UI implementation was correct

### Debug Instrumentation Added
- 📝 `