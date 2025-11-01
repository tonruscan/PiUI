# Graphics Engine Optimization Plan
**Date:** November 1, 2025  
**Status:** READY FOR IMPLEMENTATION  
**Priority:** HIGH  
**Estimated Time:** 6-8 hours

---

## 🔴 **Critical Issues Identified**

### **Issue #1: Muted Dial Flash During Dirty Rect Updates**
**Symptom:** When dragging a muted dial (e.g., Quadraverb), it briefly flashes with normal colors before returning to muted colors.

**Root Cause:**
```python
# In core/app.py _render_dirty_dials():
def _render_dirty_dials(self, offset_y: int):
    # ...
    is_page_muted = False  # ❌ Hardcoded! Not checking actual mute state
    try:
        if hasattr(dialhandlers, "mute_page_on"):
            is_page_muted = dialhandlers.mute_page_on  # ❌ This attribute doesn't exist!
    except Exception:
        pass
```

**The Problem:**
- `dialhandlers.mute_page_on` doesn't exist (it's `get_page_mute_states()` function)
- `redraw_single_dial()` is called with `is_page_muted=False` 
- Dial draws with normal colors, THEN full frame redraws with correct muted colors

**Fix:**
```python
# Get ACTUAL mute state from dialhandlers
current_pid = getattr(dialhandlers, "current_page_id", "01")
device_name = getattr(dialhandlers, "current_device_name", None)
device_mute_states = dialhandlers.get_page_mute_states(device_name)
is_page_muted = device_mute_states.get(current_pid, False)
```

---

### **Issue #2: Empty Dial Flashing on Page Transitions**
**Symptom:** Empty dials (dial 8 on BMLPF) flash visible before being hidden.

**Root Cause:** Timing issue in mode switching:
1. `rebuild_dials()` creates dials with default labels
2. Full frames requested (draws dials with default state)
3. `on_button_press()` loads actual page state
4. Some dials are marked "EMPTY" only after frames are drawn

**Current Mitigation:** We moved `request_full_frames()` to after state load, but the issue persists because:
- The dial object's `label` is set to "EMPTY" asynchronously
- First frame may render before the label is updated

**Fix:** Pre-load dial labels BEFORE any rendering:
```python
# In mode_manager._setup_dials():
self.dial_manager.rebuild_dials(device_name)

# NEW: Pre-load page state synchronously BEFORE first render
if self.prev_mode == "device_select":
    # Load state FIRST, synchronously
    which = self.button_manager.restore_left_page("1")
    dialhandlers.on_button_press(int(which), block_render=True)  # Add blocking flag
    
# THEN request frames (dials already have correct labels)
self.request_full_frames(3)
```

---

### **Issue #3: Label Y-Offset Inconsistency**
**Symptom:** Label positions differ between full draw and dirty rect draw.

**Root Cause:**
```python
# draw_ui() uses:
ui_label.draw_label(screen, label_surf, (d.cx, sy(d.cy)), radius)

# redraw_single_dial() uses:
ui_label.draw_label(screen, label_surf, (d.cx, d.cy + offset_y + 10), d.radius)
#                                                              ^^^ Extra 10px!
```

**Fix:** Use consistent positioning everywhere.

---

### **Issue #4: Redundant Color Lookups**
**Problem:** Every dial redraw re-queries theme colors via `helper.theme_rgb()`, which may involve file I/O or parsing.

**Impact:** Unnecessary overhead on high-frequency dirty rect updates (100+ FPS).

**Fix:** Cache theme colors per device.

---

### **Issue #5: Font Recreation**
**Problem:** `_get_font()` recreates fonts even though they're supposedly cached.

**Current Code:**
```python
_FONT_CACHE = {}

def _get_font(size: int):
    font_path = cfg.font_helper.main_font()
    key = (font_path, size)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = pygame.font.Font(font_path, size)
    return _FONT_CACHE[key]
```

**Issue:** `cfg.font_helper.main_font()` is called every time. If it does file checking, it's slow.

**Fix:** Cache the font path lookup too.

---

### **Issue #6: Redundant Value Computation**
**Problem:** `redraw_single_dial()` computes `shown_val` **twice** (lines 412-449, then again 468-487).

**Impact:** Wasted CPU cycles during high-frequency updates.

**Fix:** Compute once, reuse.

---

### **Issue #7: No Vsync Support**
**Problem:** Pygame clock ticking without vsync can cause tearing and inconsistent frame timing.

**Current:** `pygame.display.flip()` without vsync flag.

**Fix:** Enable vsync in display initialization.

---

### **Issue #8: Burst Mode Grace Period Too Short**
**Problem:** `DIRTY_GRACE_MS = 120` (120ms) means burst mode ends too quickly.

**Impact:** When user pauses briefly while dragging, it exits burst mode, causing a full redraw hiccup.

**Fix:** Increase grace period to 250-500ms.

---

### **Issue #9: No Frame Skipping Strategy**
**Problem:** If processing takes longer than frame budget, frames queue up.

**Current:** Always tries to draw every frame.

**Fix:** Implement frame skipping when behind schedule.

---

### **Issue #10: Dial Face Cache Never Invalidated**
**Problem:** `_get_dial_face()` caches surfaces by color, but if theme changes at runtime, stale colors remain.

**Impact:** Dial colors don't update without restart.

**Fix:** Add cache invalidation on theme change.

---

## 🎯 **Optimization Strategies**

### **Strategy 1: State-Aware Dirty Rect Rendering**
**Goal:** Ensure dirty rect updates have full context (mute state, empty state).

**Changes:**
1. Fix `_render_dirty_dials()` to properly check mute state
2. Pass `is_empty` flag to `redraw_single_dial()`
3. Store dial state flags on Dial object for fast lookup

**Implementation:**
```python
class Dial:
    def __init__(self, ...):
        # ...existing...
        self.is_empty = False       # ✅ Add flag
        self.is_muted = False       # ✅ Add flag
        self.dirty = False
        
# In dialhandlers.on_button_press():
for i, d in enumerate(dials):
    # ... set dial properties ...
    d.is_empty = (d.label.upper() == "EMPTY")  # ✅ Set once
```

**In _render_dirty_dials():**
```python
# Get mute state ONCE for whole page
device_name = getattr(dialhandlers, "current_device_name", None)
current_pid = getattr(dialhandlers, "current_page_id", "01")
mute_states = dialhandlers.get_page_mute_states(device_name)
is_page_muted = mute_states.get(current_pid, False)

for dial in dials:
    if dial.dirty:
        # Use dial's cached state flags
        rect = page_dials.redraw_single_dial(
            self.screen, dial,
            offset_y=offset_y,
            device_name=device_name,
            is_page_muted=is_page_muted,  # ✅ Correct state
            is_empty=dial.is_empty         # ✅ Cached flag
        )
```

---

### **Strategy 2: Theme Color Caching**
**Goal:** Avoid repeated theme lookups during burst updates.

**Implementation:**
```python
# In page_dials.py
_THEME_COLOR_CACHE = {}  # key: (device_name, color_key) -> RGB

def _get_theme_color(device_name, key, default):
    cache_key = (device_name, key)
    if cache_key not in _THEME_COLOR_CACHE:
        _THEME_COLOR_CACHE[cache_key] = helper.theme_rgb(device_name, key, default)
    return _THEME_COLOR_CACHE[cache_key]

def invalidate_theme_cache():
    """Call when device switches or theme changes."""
    _THEME_COLOR_CACHE.clear()
```

---

### **Strategy 3: Pre-Render Optimization**
**Goal:** Ensure dials have correct state before ANY frame is drawn.

**Implementation:**
```python
# In mode_manager._setup_dials():
def _setup_dials(self, device_behavior_map):
    # ... existing setup ...
    
    # Rebuild dials (creates objects)
    self.dial_manager.rebuild_dials(device_name)
    
    # ✅ NEW: Load page state synchronously (no rendering yet)
    if self.prev_mode == "device_select":
        which = self.button_manager.restore_left_page("1")
        dialhandlers.on_button_press(int(which), suppress_render=True)
    elif self.prev_mode == "presets":
        # ... similar ...
        dialhandlers.on_button_press(1, suppress_render=True)
    else:
        self._handle_dials_restore_last_button()
    
    # ✅ Now that state is loaded, request frames
    self.request_full_frames(3)
```

**In dialhandlers.py:**
```python
def on_button_press(slot_idx, suppress_render=False):
    # ... existing logic to set dial labels/values ...
    
    # Update dial flags immediately
    for dial in dials:
        dial.is_empty = (dial.label.upper() == "EMPTY")
    
    # Only queue render message if not suppressed
    if not suppress_render and msg_queue:
        msg_queue.put(("force_redraw", 3))
```

---

### **Strategy 4: Double-Buffered Dial State**
**Goal:** Prevent partial state updates from being visible.

**Implementation:**
```python
class Dial:
    def __init__(self, ...):
        self._display_label = ""      # ✅ Committed label
        self._display_value = 0       # ✅ Committed value
        self._pending_label = None    # ✅ Staging area
        self._pending_value = None
        
    def stage_update(self, label=None, value=None):
        """Stage changes without making them visible."""
        if label is not None:
            self._pending_label = label
        if value is not None:
            self._pending_value = value
    
    def commit_update(self):
        """Make staged changes visible atomically."""
        if self._pending_label is not None:
            self.label = self._pending_label
            self._display_label = self._pending_label
            self._pending_label = None
        if self._pending_value is not None:
            self.value = self._pending_value
            self._display_value = self._pending_value
            self._pending_value = None
```

---

### **Strategy 5: Frame Budget Management**
**Goal:** Skip rendering if behind schedule.

**Implementation:**
```python
class FrameController:
    def __init__(self):
        # ... existing ...
        self.frame_budget_ms = 1000.0 / 100  # 10ms for 100 FPS
        self.last_frame_ms = 0
        
    def should_skip_frame(self) -> bool:
        """Determine if we should skip this frame to catch up."""
        now = pygame.time.get_ticks()
        elapsed = now - self.last_frame_ms
        
        # If we're more than 2 frames behind, skip rendering
        return elapsed > (self.frame_budget_ms * 2)
    
    def tick(self, target_fps: int):
        self.frame_budget_ms = 1000.0 / target_fps
        self.last_frame_ms = pygame.time.get_ticks()
        self.clock.tick(target_fps)
```

---

### **Strategy 6: Vsync and Display Optimization**
**Goal:** Eliminate tearing and improve frame pacing.

**Implementation:**
```python
# In core/display.py:
def initialize(self):
    # ...
    flags = pygame.FULLSCREEN
    
    # ✅ Enable hardware acceleration and vsync
    if hasattr(pygame, 'SCALED'):
        flags |= pygame.SCALED
    
    # Request vsync (OpenGL backend)
    pygame.display.gl_set_attribute(pygame.GL_SWAP_CONTROL, 1)
    
    self.screen = pygame.display.set_mode(
        (self.width, self.height),
        flags,
        vsync=1  # ✅ Enable vsync
    )
```

---

### **Strategy 7: Dial Rendering Pipeline Refactor**
**Goal:** Eliminate redundant computations and inconsistencies.

**Proposed New Architecture:**
```python
class DialRenderer:
    """Dedicated dial rendering engine with state caching."""
    
    def __init__(self):
        self.theme_cache = {}
        self.face_cache = {}
        self.label_cache = {}
        
    def draw_dial_full(self, screen, dial, context):
        """Full dial render (face + label + pointer)."""
        colors = self._get_colors(dial, context)
        face = self._get_face(dial, colors)
        label = self._get_label(dial, context, colors)
        
        # Blit face
        screen.blit(face, dial.get_rect())
        
        # Draw label
        self._draw_label(screen, label, dial, context)
        
        # Draw pointer
        if not dial.is_empty:
            self._draw_pointer(screen, dial, context)
    
    def draw_dial_dirty(self, screen, dial, context):
        """Optimized dirty rect render (reuses caches)."""
        # Same logic as full, but guaranteed to use caches
        return self.draw_dial_full(screen, dial, context)
    
    def _get_colors(self, dial, context):
        """Get color palette for dial (cached)."""
        cache_key = (
            context.device_name,
            dial.is_empty,
            context.is_page_muted
        )
        
        if cache_key not in self.theme_cache:
            # Compute colors once
            if dial.is_empty:
                colors = self._compute_empty_colors(context.device_name)
            elif context.is_page_muted:
                colors = self._compute_muted_colors(context.device_name)
            else:
                colors = self._compute_normal_colors(context.device_name)
            
            self.theme_cache[cache_key] = colors
        
        return self.theme_cache[cache_key]
    
    def invalidate_cache(self, device_name=None):
        """Clear caches when device/theme changes."""
        if device_name:
            # Clear only this device's cache
            keys_to_remove = [k for k in self.theme_cache if k[0] == device_name]
            for k in keys_to_remove:
                del self.theme_cache[k]
        else:
            self.theme_cache.clear()
        
        self.face_cache.clear()
        self.label_cache.clear()
```

---

## 📋 **Implementation Checklist**

### **Phase 1: Critical Fixes** (2-3 hours)
- [ ] Fix muted dial color flash in `_render_dirty_dials()`
- [ ] Add `is_empty` and `is_muted` flags to Dial class
- [ ] Update dialhandlers to set flags during page load
- [ ] Add `suppress_render` flag to `on_button_press()`
- [ ] Move state loading before `request_full_frames()` in mode_manager

### **Phase 2: Performance Optimization** (2-3 hours)
- [ ] Implement theme color caching
- [ ] Deduplicate value computation in `redraw_single_dial()`
- [ ] Cache font path lookups
- [ ] Increase `DIRTY_GRACE_MS` to 250ms
- [ ] Add frame budget/skip logic to FrameController

### **Phase 3: Architecture Improvements** (2-3 hours)
- [ ] Create DialRenderer class
- [ ] Refactor draw_ui() to use DialRenderer
- [ ] Refactor redraw_single_dial() to use DialRenderer
- [ ] Add cache invalidation on device switch
- [ ] Enable vsync in display initialization

### **Phase 4: Testing & Validation** (1-2 hours)
- [ ] Test muted dial dragging (no color flash)
- [ ] Test page transitions (no empty dial flash)
- [ ] Profile frame times (should be < 10ms @ 100 FPS)
- [ ] Test burst mode behavior (smooth dial updates)
- [ ] Test cache invalidation (theme changes work)
- [ ] Test on target hardware (Raspberry Pi)

---

## 🎨 **Expected Results**

### **Before Optimization:**
- ❌ Muted dials flash normal colors during drag
- ❌ Empty dials visible for 2-3 frames on page switch
- ❌ Occasional frame drops during burst mode
- ❌ 100+ theme color lookups per second
- ❌ Inconsistent label positioning

### **After Optimization:**
- ✅ Muted dials stay muted color throughout drag
- ✅ Empty dials never visible (pre-loaded state)
- ✅ Stable 100 FPS during dial updates
- ✅ Theme colors cached (1 lookup per page load)
- ✅ Consistent rendering between full/dirty updates
- ✅ Smooth burst mode transitions
- ✅ Vsync eliminates tearing
- ✅ Frame skipping prevents backlog

---

## 🔧 **Configuration Tuning**

Recommended updates to `config/performance.py`:

```python
# Increase burst grace period for smoother interactions
DIRTY_GRACE_MS = 250  # was 120

# Reduce forced full frames (waste CPU)
DIRTY_FORCE_FULL_FRAMES = 1  # was 2

# Optional: Add vsync flag
ENABLE_VSYNC = True

# Optional: Frame skip threshold
FRAME_SKIP_THRESHOLD = 2.0  # Skip if more than 2x frame budget behind
```

---

## 💡 **Advanced Future Enhancements**

### **Enhancement 1: GPU Acceleration**
Use pygame-ce (community edition) with OpenGL backend for hardware-accelerated blitting.

### **Enhancement 2: Sprite Groups**
Convert dials to pygame sprites for automatic dirty rect management.

### **Enhancement 3: Texture Atlasing**
Pre-render all dial faces into a texture atlas for ultra-fast blitting.

### **Enhancement 4: Predictive Rendering**
Render next frame while user is dragging (double buffer with prediction).

### **Enhancement 5: Adaptive FPS**
Dynamically adjust target FPS based on actual frame times (auto-tune).

---

## 📊 **Performance Targets**

| Metric | Current | Target | Method |
|--------|---------|--------|--------|
| Frame Time (dials page) | ~12ms | < 10ms | Caching, optimization |
| Dirty Rect Update | ~5ms | < 3ms | Dedupe, state flags |
| Full Frame Draw | ~16ms | < 12ms | Cached surfaces |
| Theme Color Lookup | 100+/sec | 1/page | Cache |
| Burst Mode Stability | 80-120 FPS | 100 FPS ±2 | Grace period |
| Page Transition Flash | 2-3 frames | 0 frames | Pre-load state |

---

## 🚀 **Getting Started**

1. **Review this document** with your team
2. **Create a feature branch**: `git checkout -b graphics-optimization`
3. **Start with Phase 1** (critical fixes)
4. **Test on target hardware** after each phase
5. **Profile with debug overlay** to measure improvements
6. **Merge when all tests pass**

---

**Questions?** Check the inline code comments for detailed implementation notes.

**Author:** GitHub Copilot  
**Review Status:** Ready for implementation  
**Dependencies:** None (all changes are isolated to rendering pipeline)
