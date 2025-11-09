# Dirty Rect Optimization Guide

**Date:** November 5, 2025  
**Issue:** Mini dial performance degradation (100 FPS → 30 FPS)  
**Root Cause:** Excessive dirty rect regions causing unnecessary redraws

---

## Problem Summary

When implementing mini dials (radius < 50px) with transparent backgrounds for the Drumbo plugin, performance degraded significantly:

- **Symptom:** FPS dropped from 100 → 30 when turning mini dials
- **Expected:** Mini dials should perform identically to normal dials (maintain 100 FPS)
- **CPU Usage:** Spiked during mini dial interaction vs. normal dials staying low

### Root Causes Discovered

1. **Widget returned full rect instead of dial-specific rect**
   - `DrumboMainWidget.get_dirty_rect()` returned entire widget (560x240px)
   - Should have returned only changed dial area (~54x54px + label ≈ 100x100px)
   - **Impact:** 134,400 pixels updated → should be ~10,000 pixels (93% reduction)

2. **Widget draw() always redrawed full background**
   - `DrumboMainWidget.draw()` drew entire widget every call
   - No check for partial updates (specific dial changes)
   - **Impact:** Forced full widget repaint even for single dial changes

3. **All overlay dials redrawn when widget marked dirty**
   - `module_base.py` redrawed all 16 overlay dials when custom widget dirty
   - Didn't check if only specific dial changed
   - **Impact:** 16x unnecessary dial redraws (16 dials × ~10k pixels each = 160k pixels)

---

## The Dirty Rect System Flow

Understanding how the system works prevents future issues:

### 1. Change Detection
```python
# Entry: MIDI message arrives
dialhandlers.py:693 → msg_queue.put(("update_dial_value", dial_id, value))

# Processing
core/app.py:758 → dial.dirty = True  # Flag for redraw
```

### 2. Collection Phase
```python
# module_base.py:1450-1488
get_dirty_widgets() → checks ALL widgets for:
  - widget.is_dirty() method (custom widgets)
  - widget.dirty attribute (simple dials)
  
Returns: [list of only changed widgets]
```

### 3. Selective Redraw
```python
# module_base.py:1506-1561
redraw_dirty_widgets():
  for each dirty widget:
    1. Call widget.draw() → returns pygame.Rect
    2. If None, call widget.get_dirty_rect()
    3. Collect all rects → [rect1, rect2, ...]
    4. Clear dirty flags
```

### 4. Display Update
```python
# rendering/dirty_rect.py
DirtyRectManager.mark_dirty(rect) → accumulate rects
DirtyRectManager.present_dirty() → pygame.display.update(self._dirty)
  
CRITICAL: Only updates changed screen regions, NOT full flip()
```

---

## Solution Implementation

### Fix #1: Track Specific Dirty Dial

**File:** `widgets/drumbo_main_widget.py`

```python
# Add tracking field in __init__
self._dirty = True
self._dirty_dial = None  # Track which specific dial changed

# Update mark_dirty to accept dial parameter
def mark_dirty(self, dial=None):
    """Mark widget as needing redraw. If dial provided, track it for minimal dirty rect."""
    self._dirty = True
    if dial is not None:
        self._dirty_dial = dial  # Store the specific dial
```

**File:** `plugins/drumbo_plugin.py`

```python
# Pass the changed dial when marking dirty
changed_dial = target_row[mic_index]
self.widget.mark_dirty(dial=changed_dial)  # Not just mark_dirty()
```

### Fix #2: Return Minimal Dirty Rect

**File:** `widgets/drumbo_main_widget.py`

```python
def get_dirty_rect(self) -> Optional[pygame.Rect]:
    """Get the rectangle that needs redrawing - just the changed dial if possible."""
    if not self._dirty:
        return None
    
    # If we have a specific dial that changed, return just its area
    if self._dirty_dial is not None:
        try:
            dial = self._dirty_dial
            radius = getattr(dial, 'radius', 25)
            cx = int(getattr(dial, 'cx', 0))
            cy = int(getattr(dial, 'cy', 0))
            
            # Dial circle area
            dial_rect = pygame.Rect(cx - radius - 2, cy - radius - 2, 
                                   radius * 2 + 4, radius * 2 + 4)
            
            # Add label area below
            label_rect = pygame.Rect(cx - 40, cy + radius + 5, 80, 60)
            
            return dial_rect.union(label_rect)
        except Exception as e:
            showlog.warn(f"[Widget] Failed to calculate dial dirty rect: {e}")
    
    # Fallback: return full widget rect
    return self.rect
```

### Fix #3: Smart Widget Draw

**File:** `widgets/drumbo_main_widget.py`

```python
def draw(self, surface: pygame.Surface, device_name=None, offset_y=0):
    """Draw the widget - only if full redraw needed, otherwise return minimal dirty rect."""
    
    # If we only have a specific dial dirty, don't redraw the widget background
    # Just return the dial's dirty rect so the dial can be redrawn over existing background
    if self._dirty_dial is not None:
        # Calculate minimal dial rect
        dial = self._dirty_dial
        radius = getattr(dial, 'radius', 25)
        cx = int(getattr(dial, 'cx', 0))
        cy = int(getattr(dial, 'cy', 0))
        
        dial_rect = pygame.Rect(cx - radius - 2, cy - radius - 2, 
                               radius * 2 + 4, radius * 2 + 4)
        label_rect = pygame.Rect(cx - 40, cy + radius + 5, 80, 60)
        
        dial_rect.y += offset_y
        label_rect.y += offset_y
        
        # Return minimal rect WITHOUT redrawing widget background
        return dial_rect.union(label_rect)
    
    # Full widget redraw (instrument change, bank change, initial draw)
    draw_rect = self.rect.copy()
    draw_rect.y += offset_y
    # ... draw full widget background, borders, text, etc.
```

### Fix #4: Selective Overlay Dial Redraw

**File:** `pages/module_base.py` (lines ~1529-1559)

```python
# If this is the custom widget, redraw grid dials on top of it
if widget == _CUSTOM_WIDGET_INSTANCE:
    try:
        # Check if widget has a specific dirty dial - if so, only redraw that one
        has_specific_dirty = hasattr(widget, '_dirty_dial') and widget._dirty_dial is not None
        
        if has_specific_dirty:
            # Only redraw the specific dial that changed
            dirty_dial = widget._dirty_dial
            overlay_widgets = _DIAL_BANK_MANAGER.get_all_widgets() if _DIAL_BANK_MANAGER else _ACTIVE_WIDGETS
            for w in overlay_widgets:
                if hasattr(w, 'dial') and w.dial == dirty_dial:
                    dial_rect = w.draw(screen, device_name=device_name, offset_y=offset_y)
                    if dial_rect:
                        dirty_rects.append(dial_rect)
                    break  # Found it, stop searching
        else:
            # Full redraw - redraw all overlay dials
            overlay_widgets = _DIAL_BANK_MANAGER.get_all_widgets() if _DIAL_BANK_MANAGER else _ACTIVE_WIDGETS
            for w in overlay_widgets:
                w.draw(screen, device_name=device_name, offset_y=offset_y)
    except Exception as e:
        showlog.warn(f"[MODULE_BASE] Failed to redraw dials on top: {e}")
```

---

## Performance Impact

### Before Fixes
- **Dial Turn:** 560x240px widget + 16 dials redrawn = ~160,000 pixels
- **FPS:** 100 → 30 during interaction
- **CPU:** High spike during dial movement

### After Fixes
- **Dial Turn:** ~100x100px (one dial + label) = ~10,000 pixels
- **FPS:** Stable 100 during interaction
- **CPU:** Low, matches normal dial performance
- **Improvement:** 94% reduction in pixel updates

---

## Best Practices for Custom Widgets

### ✅ DO: Implement Granular Dirty Tracking

```python
class CustomWidget:
    def __init__(self):
        self._dirty = False
        self._dirty_region = None  # Track what changed
    
    def mark_dirty(self, region=None):
        self._dirty = True
        self._dirty_region = region  # Store what changed
    
    def get_dirty_rect(self):
        if self._dirty_region:
            return self._dirty_region  # Return minimal rect
        return self.rect  # Fallback to full widget
```

### ✅ DO: Return Early from draw() for Partial Updates

```python
def draw(self, surface, device_name=None, offset_y=0):
    # Check if partial update possible
    if self._dirty_region:
        # Don't redraw background, just return the region
        # The specific component will be redrawn by caller
        return self._dirty_region
    
    # Full redraw
    # ... draw everything ...
    return self.rect
```

### ✅ DO: Clear Dirty Tracking After Draw

```python
def clear_dirty(self):
    self._dirty = False
    self._dirty_region = None  # Clear the region tracking
```

### ❌ DON'T: Always Redraw Full Widget

```python
# BAD - always redraws everything
def draw(self, surface, device_name=None, offset_y=0):
    pygame.draw.rect(surface, self.bg_color, self.rect)  # Always draws full bg
    # ... draw all components ...
    return self.rect  # Always returns full rect
```

### ❌ DON'T: Return Full Widget Rect for Small Changes

```python
# BAD - returns massive rect for tiny change
def get_dirty_rect(self):
    return self.rect if self._dirty else None  # Always full widget!
```

### ❌ DON'T: Redraw All Children When Parent Dirty

```python
# BAD - redraws all children even if only one changed
if widget_is_dirty:
    for child in all_children:
        child.draw()  # Wasteful!
        
# GOOD - only redraw changed children
if widget_is_dirty:
    changed_child = widget.get_dirty_child()
    if changed_child:
        changed_child.draw()  # Minimal!
```

---

## Debugging Dirty Rects

### Enable Debug Overlay

**File:** `config/performance.py`

```python
DEBUG_DIRTY_OVERLAY = True  # Draw magenta boxes around dirty regions
```

**File:** `core/app.py` (add before present_dirty())

```python
# Debug overlay: Draw magenta boxes around dirty regions
self.dirty_rect_manager.debug_overlay(self.screen)
self.dirty_rect_manager.present_dirty(force_full=False)
```

### What to Look For

- ✅ **Good:** Small magenta boxes around only changed elements
- ❌ **Bad:** Large magenta box covering entire widget/screen
- ❌ **Bad:** Multiple boxes when only one element changed
- ❌ **Bad:** Full-screen box (indicates no dirty rect optimization)

### Measuring Impact

```python
# Add logging to see rect sizes
rect = widget.get_dirty_rect()
if rect:
    pixel_count = rect.width * rect.height
    showlog.debug(f"Dirty rect: {rect.width}x{rect.height} = {pixel_count:,} pixels")
```

---

## Common Pitfalls

### 1. Forgetting to Clear Dirty Region
**Symptom:** Widget always returns same dirty rect, even after clearing `_dirty`  
**Fix:** Clear `_dirty_region` in `clear_dirty()`

### 2. Calculating Rect After draw() Modifies State
**Symptom:** Dirty rect doesn't match drawn region  
**Fix:** Calculate rect before drawing, or store calculated rect

### 3. Not Accounting for offset_y
**Symptom:** Dirty rect doesn't align with actual drawn position  
**Fix:** Always apply `offset_y` to returned rects

### 4. Overlay Components Not Redrawn
**Symptom:** Dials/widgets disappear after partial update  
**Fix:** Ensure overlay components redrawn within dirty region

### 5. Label Area Not Included in Dirty Rect
**Symptom:** Old label text remains visible  
**Fix:** Include label bounds in dirty rect calculation

---

## Testing Checklist

When implementing custom widgets with dirty rect optimization:

- [ ] Enable `DEBUG_DIRTY_OVERLAY = True`
- [ ] Turn dial - verify small magenta box (not full widget)
- [ ] Check FPS stays at target (100 for high-FPS pages)
- [ ] Verify CPU usage matches normal dial performance
- [ ] Test rapid dial changes (burst mode)
- [ ] Verify labels update correctly
- [ ] Check overlay components don't disappear
- [ ] Test full widget updates (button presses, mode changes)
- [ ] Confirm no visual artifacts (ghost images, missing components)
- [ ] Verify `offset_y` applied correctly for scrolling pages

---

## Related Files

- `rendering/dirty_rect.py` - DirtyRectManager implementation
- `config/performance.py` - Dirty rect settings and debug flags
- `core/app.py` - Main render loop with dirty rect handling
- `pages/module_base.py` - Module-based page dirty rect collection
- `pages/page_dials.py` - Individual dial redraw function
- `docs/PLUGIN_RENDERING_ARCHITECTURE.md` - Overall rendering system

---

## Key Takeaway

**Always track WHAT changed, not just THAT something changed.**

The dirty rect system is optimized to update only changed screen regions. Custom widgets must participate correctly by:

1. **Tracking** which specific component changed
2. **Returning** minimal rects covering only changed areas
3. **Avoiding** unnecessary redraws of unchanged components
4. **Clearing** tracking state after successful draw

When done correctly, the system can maintain high FPS (100+) even with complex layouts containing many interactive elements.
