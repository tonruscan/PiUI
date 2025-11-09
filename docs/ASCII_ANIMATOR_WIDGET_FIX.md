# ASCII Animator Widget Fix - November 3, 2025

## Problem Summary

ASCII Animator plugin loaded successfully with visible buttons, but the widget area showed completely black (no widget displayed).

## Root Cause

**Widget's `__init__` signature didn't match the required pattern.**

The widget was defined as:
```python
def __init__(self, rect, grid_rows=9, grid_cols=9, border_style="double", fps=24):
```

But `module_base.py` instantiates ALL custom widgets with:
```python
widget = cls(rect, on_change=None, theme=theme)
```

This caused a `TypeError` when trying to pass `on_change` and `theme` as keyword arguments that didn't exist in the widget's signature.

## Why It Was Silent

- No error appeared in normal logs
- Plugin loaded successfully
- Buttons rendered correctly (handled separately from widget)
- Widget instantiation failure was swallowed by exception handler
- Only deep exception traces showed the `TypeError`

## Solution

Updated widget signature to match required pattern:

```python
# BEFORE (wrong)
def __init__(self, rect, grid_rows=9, grid_cols=9, border_style="double", fps=24):

# AFTER (correct)
def __init__(self, rect, on_change=None, theme=None, grid_rows=9, grid_cols=9, border_style="double", fps=24):
    super().__init__()
    self.rect = pygame.Rect(rect)
    self.on_change = on_change  # Required by system
    self.theme = theme or {}    # Required by system
```

## Key Rule

**ALL custom widgets MUST accept these first three parameters:**
1. `rect` - Widget bounding box
2. `on_change` - Callback for value changes (optional but must exist)
3. `theme` - Theme color dictionary (optional but must exist)

Any custom parameters must come AFTER these three.

## Manual Updates

Updated `WIDGET_CREATION_MANUAL.md` v1.1 with:

1. **Critical warning section** after "Core Widget Requirements"
2. **New "Common Issue"** entry for blank screen / missing parameters
3. **Enhanced checklist** highlighting the critical `__init__` signature
4. **Updated Key Takeaways** emphasizing this as the most common mistake
5. **"Most Common Mistake"** callout box with example

## Files Changed

- `widgets/ascii_animator_widget.py` - Fixed `__init__` signature
- `docs/WIDGET_CREATION_MANUAL.md` - Added comprehensive warnings and examples

## Prevention

Future widgets should use this template:

```python
from widgets.dirty_mixin import DirtyWidgetMixin
import pygame

class MyWidget(DirtyWidgetMixin):
    def __init__(self, rect, on_change=None, theme=None, **your_params):
        super().__init__()
        self.rect = pygame.Rect(rect)
        self.on_change = on_change  # REQUIRED
        self.theme = theme or {}    # REQUIRED
        # ... your custom initialization
    
    def draw(self, surface, device_name=None, offset_y=0):
        # ... drawing code
        return self.rect.copy()
    
    def handle_event(self, event):
        # ... event handling
        return False
    
    def get_state(self):
        return {}  # Serializable state
    
    def set_from_state(self, **kwargs):
        pass  # Restore from state
```

## Testing Checklist

When creating a new widget, verify:

- [ ] `__init__` signature: `(self, rect, on_change=None, theme=None, ...)`
- [ ] Stores `self.on_change` and `self.theme`
- [ ] Widget area displays (not black)
- [ ] Buttons work alongside widget
- [ ] No `TypeError` in exception traces

## Result

ASCII Animator widget now displays correctly with:
- ✅ 9×9 ASCII grid visible
- ✅ Frame counter overlay
- ✅ Side buttons functional
- ✅ Proper theme colors applied
- ✅ Mouse events working

The issue was purely a signature mismatch - the widget code itself was already correct.
