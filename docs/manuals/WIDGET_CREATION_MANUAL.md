# Widget Creation Manual

**Complete Guide to Building Custom Widgets for the Modular UI System**

Version 1.2 | Last Updated: November 3, 2025 | **Dual grid layout pattern added**

---

## Table of Contents

1. [Introduction](#introduction)
2. [Widget Architecture Overview](#widget-architecture-overview)
3. [Grid System & Measurements](#grid-system--measurements)
4. [Core Widget Requirements](#core-widget-requirements)
5. [Step-by-Step Widget Creation](#step-by-step-widget-creation)
6. [Complete Working Example](#complete-working-example)
7. [Integration with Plugins](#integration-with-plugins)
8. [Advanced Features](#advanced-features)
9. [Testing & Debugging](#testing--debugging)
10. [Common Patterns & Best Practices](#common-patterns--best-practices)

---

## Introduction

This manual provides everything you need to create custom widgets for the modular synthesizer UI system. Widgets are interactive UI components that can range from simple controls (knobs, sliders) to complex visualizations (ADSR envelopes, drawbars, waveform displays).

### What You'll Learn

- How to calculate precise widget dimensions for different grid sizes
- How to implement the dirty rect rendering system for performance
- How to handle mouse/touch events properly
- How to integrate widgets with the plugin system
- How to save/restore widget state with presets

### Prerequisites

- Basic Python programming knowledge
- Familiarity with Pygame
- Understanding of the plugin architecture (see `PLUGIN_CREATION_MANUAL_COMPLETE.md`)

---

## Widget Architecture Overview

### Widget Hierarchy

```
DirtyWidgetMixin (widgets/dirty_mixin.py)
    │
    ├── DialWidget (assets/dial.py)
    ├── DrawBarWidget (widgets/drawbar_widget.py)
    ├── VibratoField (widgets/adsr_widget.py)
    └── Your Custom Widget
```

### Key Components

1. **DirtyWidgetMixin**: Base class providing dirty rect optimization
2. **Grid System**: Standardized positioning across the UI
3. **Event System**: Mouse/touch event handling
4. **State Management**: Saving/loading widget state with presets
5. **Theme Integration**: Automatic color scheme adaptation

---

## Grid System & Measurements

### Understanding the Grid

The UI uses a **4-column × 2-row grid** for dial placement. Widgets occupy one or more grid cells.

#### Base Grid Parameters

```python
# From config/styling.py and utils/grid_layout.py
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 480

GRID_WIDTH = 586        # Total grid width (for calculations)
GRID_HEIGHT = 360       # Total grid height (for calculations)
GRID_TOP_PADDING = 10   # Vertical offset for fine-tuning

DIAL_SIZE = 50          # Dial radius (from config)
DIAL_DIAMETER = 100     # Full dial size (DIAL_SIZE * 2)
PANEL_SIZE = 120        # Dial panel (DIAL_DIAMETER + 20px padding)

# Actual usable grid space (with panel padding):
USABLE_GRID_WIDTH = 560    # 4 cols × 140px each = 560px
USABLE_GRID_HEIGHT = 300   # 2 rows × 150px each = 300px
```

#### Grid Cell Dimensions

```python
# Calculated per cell
cell_width = GRID_WIDTH / 4 = 586 / 4 = 146.5 pixels
cell_height = GRID_HEIGHT / 2 = 360 / 2 = 180 pixels
```

### Widget Size Calculations

Widgets are sized in **grid units** (e.g., "3×2" means 3 columns wide, 2 rows tall).

#### Formula for Widget Dimensions

Given a widget of size `(w_cells, h_cells)` at position `(col, row)`:

```python
# Import the grid system
from utils.grid_layout import get_zone_rect_tight, get_grid_geometry

# Calculate widget rect (this handles all the math for you!)
rect = get_zone_rect_tight(row, col, w_cells, h_cells)
```

#### Manual Calculation (for understanding)

If you need to calculate manually:

```python
# Screen parameters
screen_w = 800
screen_h = 480
GRID_W = 586
GRID_H = 360
GRID_TOP_PADDING = 10

# Cell dimensions
cell_w = GRID_W / 4  # 146.5px
cell_h = GRID_H / 2  # 180px

# Dial panel dimensions
DIAL_DIAMETER = 100
PANEL_SIZE = DIAL_DIAMETER + 20  # 120px
PANEL_HALF = PANEL_SIZE / 2.0    # 60px

# Grid origin (centered on screen)
orig_GRID_X = (screen_w - GRID_W) / 2  # 107px
orig_GRID_Y = (screen_h - GRID_H) / 2 + GRID_TOP_PADDING  # 70px

# For a widget at (row, col) spanning (w_cells, h_cells):
# Calculate start/end dial centers
start_center_x = orig_GRID_X + (col + 0.5) * cell_w
start_center_y = orig_GRID_Y + (row + 0.5) * cell_h
end_center_x = orig_GRID_X + (col + w_cells - 0.5) * cell_w
end_center_y = orig_GRID_Y + (row + h_cells - 0.5) * cell_h

# Calculate bounding box from panel edges
x = start_center_x - PANEL_HALF
y = start_center_y - PANEL_HALF
width = (end_center_x + PANEL_HALF) - x
height = (end_center_y + PANEL_HALF) - y

rect = pygame.Rect(int(round(x)), int(round(y)), 
                   int(round(width)), int(round(height)))
```

### Common Widget Sizes

Here are the calculated dimensions for common widget configurations:

#### 1×1 Widget (Single Dial Space)
```python
grid_size = [1, 1]
grid_pos = [0, 0]  # row 0, col 0
# Result: Rect(120, 100, 120, 120)
# Width: 120px, Height: 120px
```

#### 3×2 Widget (Drawbar Size)
```python
grid_size = [3, 2]
grid_pos = [0, 1]  # row 0, col 1 (skip first column for buttons)
# Result: Rect(267, 100, 413, 300)
# Width: 413px, Height: 300px
```

#### 4×2 Widget (Full Grid Width)
```python
grid_size = [4, 2]
grid_pos = [0, 0]  # spans entire width
# Result: Rect(120, 100, 560, 300)
# Width: 560px, Height: 300px
```

#### 2×1 Widget (Horizontal Strip)
```python
grid_size = [2, 1]
grid_pos = [0, 0]  # top row, first two columns
# Result: Rect(120, 100, 266, 120)
# Width: 266px, Height: 120px
```

#### 1×2 Widget (Vertical Strip)
```python
grid_size = [1, 2]
grid_pos = [0, 0]  # first column, both rows
# Result: Rect(120, 100, 120, 300)
# Width: 120px, Height: 300px
```

### Grid Position Reference

```
Grid Layout (4 cols × 2 rows):

     Col 0    Col 1    Col 2    Col 3
   ┌────────┬────────┬────────┬────────┐
R0 │ (0,0)  │ (0,1)  │ (0,2)  │ (0,3)  │
   │ 120×120│ 120×120│ 120×120│ 120×120│
   ├────────┼────────┼────────┼────────┤
R1 │ (1,0)  │ (1,1)  │ (1,2)  │ (1,3)  │
   │ 120×120│ 120×120│ 120×120│ 120×120│
   └────────┴────────┴────────┴────────┘
```

**Note**: Row/Column are **0-indexed**. Position `[row, col]` or `[0, 1]` = Row 0, Column 1.

---

## Core Widget Requirements

Every widget must implement these key components:

### 1. Inherit from DirtyWidgetMixin

```python
from widgets.dirty_mixin import DirtyWidgetMixin

class MyWidget(DirtyWidgetMixin):
    def __init__(self, rect, on_change=None, theme=None):
        super().__init__()  # Initialize dirty tracking
        # ... your init code
```

### 2. Required Methods

```python
def __init__(self, rect, on_change=None, theme=None):
    """Initialize widget with rect, optional callback, and theme."""
    
def draw(self, surface, device_name=None, offset_y=0):
    """Draw the widget. Returns dirty rect or None."""
    
def handle_event(self, event) -> bool:
    """Handle pygame events. Return True if event was consumed."""
    
def get_state(self) -> Dict:
    """Return serializable state for preset saving."""
    
def set_from_state(self, **kwargs):
    """Restore widget from saved state."""
```

### 3. Essential Attributes

```python
self.rect = pygame.Rect(rect)      # Widget bounding box
self.on_change = on_change          # Callback for value changes
```

### ⚠️ CRITICAL: __init__ Signature Must Match Exactly

**The widget's `__init__` signature MUST accept `rect`, `on_change`, and `theme` as the first three parameters.**

This is **not optional**. The `module_base.py` system instantiates all custom widgets with this exact call:

```python
widget = cls(rect, on_change=None, theme=theme)
```

#### ❌ Wrong - Widget Won't Load (Blank Screen)
```python
def __init__(self, rect, grid_rows=9, grid_cols=9):
    # Missing on_change and theme parameters!
    # This will cause TypeError when module_base tries to instantiate it
    super().__init__()
    self.rect = pygame.Rect(rect)
```

#### ✅ Correct - Required Pattern
```python
def __init__(self, rect, on_change=None, theme=None, grid_rows=9, grid_cols=9):
    super().__init__()
    self.rect = pygame.Rect(rect)
    self.on_change = on_change  # REQUIRED: Store callback
    self.theme = theme or {}    # REQUIRED: Store theme dict
    # ... your custom parameters
```

**What happens if you get this wrong:**
- Plugin loads successfully (no errors)
- Buttons appear and work correctly
- **Widget area shows completely black** (widget never instantiates)
- No error message in logs (silent failure until deep exception trace)
- `TypeError: __init__() got an unexpected keyword argument 'on_change'`

**Always put `rect`, `on_change`, `theme` first, then add your custom parameters after.**

---

## Step-by-Step Widget Creation

### Step 1: Create Widget File

Create a new file in `widgets/` directory:

```
widgets/
├── my_widget.py          # Your new widget
├── drawbar_widget.py     # Example: Complex animated widget
├── adsr_widget.py        # Example: Interactive envelope
├── dial_widget.py        # Example: Rotary control
└── dirty_mixin.py        # Base class (don't modify)
```

### Step 2: Define Widget Class

```python
# widgets/my_widget.py
import pygame
import config as cfg
import showlog
import helper
from widgets.dirty_mixin import DirtyWidgetMixin
from typing import Optional, Callable, Dict, Tuple

class MyWidget(DirtyWidgetMixin):
    """
    Brief description of what your widget does.
    """
    
    def __init__(
        self,
        rect: pygame.Rect,
        on_change: Optional[Callable[[Dict], None]] = None,
        theme: Optional[Dict[str, Tuple[int, int, int]]] = None,
    ):
        super().__init__()
        self.rect = pygame.Rect(rect)
        self.on_change = on_change
        
        # Parse theme colors with fallbacks
        th = theme or {}
        self.col_bg = th.get("bg", helper.hex_to_rgb(cfg.DIAL_PANEL_COLOR))
        self.col_fill = th.get("fill", helper.hex_to_rgb(cfg.DIAL_FILL_COLOR))
        self.col_outline = th.get("outline", helper.hex_to_rgb(cfg.DIAL_OUTLINE_COLOR))
        
        # Your initialization code here
        self.value = 0
        self.dragging = False
```

### Step 3: Implement Draw Method

```python
def draw(self, surface: pygame.Surface, device_name=None, offset_y=0):
    """
    Draw the widget.
    
    Args:
        surface: Pygame surface to draw on
        device_name: Current device name (for theme lookups)
        offset_y: Vertical scroll offset (for scrollable pages)
        
    Returns:
        pygame.Rect: Dirty rect that needs redrawing, or None
    """
    try:
        # Apply offset if provided (important for scrolling pages)
        draw_rect = self.rect.copy()
        draw_rect.y += offset_y
        
        # Clear previous drawing (use page background color)
        from helper import theme_rgb
        bg_color = theme_rgb(device_name, "PAGE_BG_COLOR", default=(0, 0, 0))
        pygame.draw.rect(surface, bg_color, draw_rect)
        
        # Draw your widget components here
        pygame.draw.rect(surface, self.col_bg, draw_rect, border_radius=12)
        
        # Example: Draw a filled circle
        center_x = draw_rect.centerx
        center_y = draw_rect.centery
        pygame.draw.circle(surface, self.col_fill, (center_x, center_y), 20)
        pygame.draw.circle(surface, self.col_outline, (center_x, center_y), 20, 2)
        
        # Return the dirty rect for the rendering system
        return draw_rect
        
    except Exception as e:
        showlog.warn(f"[MyWidget] Draw failed: {e}")
        import traceback
        showlog.warn(traceback.format_exc())
        return None
```

### Step 4: Implement Event Handling

```python
def handle_event(self, event) -> bool:
    """
    Handle pygame events (mouse, touch, etc.).
    
    Returns:
        bool: True if event was consumed, False otherwise
    """
    if event.type == pygame.MOUSEBUTTONDOWN and hasattr(event, "pos"):
        # Check if click is inside widget bounds
        if self.rect.collidepoint(event.pos):
            self.dragging = True
            self._update_from_mouse(event.pos)
            return True  # Event consumed
            
    elif event.type == pygame.MOUSEBUTTONUP:
        if self.dragging:
            self.dragging = False
            return True
            
    elif event.type == pygame.MOUSEMOTION and hasattr(event, "pos"):
        if self.dragging:
            self._update_from_mouse(event.pos)
            return True
            
    return False  # Event not consumed

def _update_from_mouse(self, pos):
    """Update widget state from mouse position."""
    # Calculate new value from mouse position
    relative_x = pos[0] - self.rect.left
    t = relative_x / self.rect.width
    new_value = int(t * 127)
    
    # Only update if value changed
    if new_value != self.value:
        self.value = new_value
        self.mark_dirty()  # Tell system to redraw
        
        # Call on_change callback if provided
        if self.on_change:
            self.on_change({"value": new_value})
```

### Step 5: Implement State Management

```python
def get_state(self) -> Dict:
    """
    Return current widget state for preset saving.
    
    Returns:
        Dict containing all state that should be saved
    """
    return {
        "value": self.value,
        # Add any other state variables here
    }

def set_from_state(self, **kwargs):
    """
    Restore widget state from saved data.
    
    Args:
        **kwargs: State dictionary (keys match get_state() output)
    """
    if "value" in kwargs:
        self.value = kwargs["value"]
        self.mark_dirty()  # Redraw with new state
```

### Step 6: Optimize with Dirty Rect System

```python
def is_dirty(self) -> bool:
    """
    Override to keep widget dirty during animations or continuous updates.
    """
    # For animated widgets, always return True during animation
    if hasattr(self, 'animating') and self.animating:
        return True
    # Otherwise use parent's dirty flag
    return super().is_dirty()

def clear_dirty(self):
    """
    Override to prevent clearing dirty flag during animations.
    """
    # Don't clear if animating (keeps redrawing)
    if hasattr(self, 'animating') and self.animating:
        return
    # Otherwise clear normally
    super().clear_dirty()
```

---

## Complete Working Example

Here's a complete, functional slider widget you can use as a template:

```python
# widgets/slider_widget.py
"""
Horizontal Slider Widget - Complete Example
A simple horizontal slider control with visual feedback.
"""

import pygame
import config as cfg
import showlog
import helper
from widgets.dirty_mixin import DirtyWidgetMixin
from typing import Optional, Callable, Dict, Tuple


class SliderWidget(DirtyWidgetMixin):
    """
    A horizontal slider widget with configurable range.
    
    Features:
    - Smooth dragging interaction
    - Visual feedback (hover, active states)
    - Theme color integration
    - Preset state saving/loading
    - Dirty rect optimization
    
    Usage:
        def on_slider_change(data):
            print(f"Slider value: {data['value']}")
        
        slider = SliderWidget(
            rect=pygame.Rect(100, 100, 300, 40),
            on_change=on_slider_change,
            value_range=(0, 127)
        )
    """
    
    def __init__(
        self,
        rect: pygame.Rect,
        on_change: Optional[Callable[[Dict], None]] = None,
        theme: Optional[Dict[str, Tuple[int, int, int]]] = None,
        value_range: Tuple[int, int] = (0, 127),
        initial_value: int = 64,
    ):
        super().__init__()
        self.rect = pygame.Rect(rect)
        self.on_change = on_change
        self.min_val, self.max_val = value_range
        self.value = initial_value
        
        # Theme colors with fallbacks
        th = theme or {}
        self.col_bg = th.get("bg", helper.hex_to_rgb(cfg.DIAL_PANEL_COLOR))
        self.col_fill = th.get("fill", helper.hex_to_rgb(cfg.DIAL_FILL_COLOR))
        self.col_outline = th.get("outline", helper.hex_to_rgb(cfg.DIAL_OUTLINE_COLOR))
        
        # Interaction state
        self.dragging = False
        self.hovering = False
        
        # Visual parameters
        self.track_height = 8
        self.handle_width = 20
        self.handle_height = 30
        self.border_radius = 6
        
        showlog.info(f"[SliderWidget] Created at {rect} with range {value_range}")
    
    def draw(self, surface: pygame.Surface, device_name=None, offset_y=0):
        """Draw the slider widget."""
        try:
            # Apply offset
            draw_rect = self.rect.copy()
            draw_rect.y += offset_y
            
            # Clear background
            from helper import theme_rgb
            bg_color = theme_rgb(device_name, "PAGE_BG_COLOR", default=(0, 0, 0))
            pygame.draw.rect(surface, bg_color, draw_rect)
            
            # Draw track background (centered vertically in rect)
            track_y = draw_rect.centery - self.track_height // 2
            track_rect = pygame.Rect(
                draw_rect.left,
                track_y,
                draw_rect.width,
                self.track_height
            )
            pygame.draw.rect(surface, self.col_bg, track_rect, border_radius=4)
            
            # Calculate handle position based on value
            t = (self.value - self.min_val) / max(1, self.max_val - self.min_val)
            handle_x = draw_rect.left + int(t * (draw_rect.width - self.handle_width))
            handle_y = draw_rect.centery - self.handle_height // 2
            handle_rect = pygame.Rect(
                handle_x,
                handle_y,
                self.handle_width,
                self.handle_height
            )
            
            # Draw filled portion of track
            if t > 0:
                filled_rect = pygame.Rect(
                    draw_rect.left,
                    track_y,
                    handle_x + self.handle_width // 2 - draw_rect.left,
                    self.track_height
                )
                pygame.draw.rect(surface, self.col_fill, filled_rect, border_radius=4)
            
            # Draw handle with state-based colors
            handle_color = self.col_fill
            if self.dragging:
                # Brighten when dragging
                handle_color = tuple(min(255, c + 40) for c in self.col_fill)
            elif self.hovering:
                # Slightly brighten when hovering
                handle_color = tuple(min(255, c + 20) for c in self.col_fill)
            
            pygame.draw.rect(
                surface,
                handle_color,
                handle_rect,
                border_radius=self.border_radius
            )
            pygame.draw.rect(
                surface,
                self.col_outline,
                handle_rect,
                width=2,
                border_radius=self.border_radius
            )
            
            # Draw value text
            import utils.font_helper as font_helper
            font_path = font_helper.main_font("Bold")
            font = pygame.font.Font(font_path, 16)
            value_text = font.render(str(self.value), True, (255, 255, 255))
            text_rect = value_text.get_rect(center=handle_rect.center)
            surface.blit(value_text, text_rect)
            
            return draw_rect
            
        except Exception as e:
            showlog.warn(f"[SliderWidget] Draw failed: {e}")
            import traceback
            showlog.warn(traceback.format_exc())
            return None
    
    def handle_event(self, event) -> bool:
        """Handle mouse events."""
        if event.type == pygame.MOUSEBUTTONDOWN and hasattr(event, "pos"):
            if self.rect.collidepoint(event.pos):
                self.dragging = True
                self._update_from_mouse(event.pos[0])
                self.mark_dirty()
                return True
                
        elif event.type == pygame.MOUSEBUTTONUP:
            if self.dragging:
                self.dragging = False
                self.mark_dirty()
                return True
                
        elif event.type == pygame.MOUSEMOTION and hasattr(event, "pos"):
            # Update hover state
            was_hovering = self.hovering
            self.hovering = self.rect.collidepoint(event.pos)
            
            if self.dragging:
                self._update_from_mouse(event.pos[0])
                self.mark_dirty()
                return True
            elif was_hovering != self.hovering:
                self.mark_dirty()  # Redraw for hover effect
                
        return False
    
    def _update_from_mouse(self, mouse_x: int):
        """Update slider value from mouse X position."""
        # Calculate position relative to track
        relative_x = mouse_x - self.rect.left - self.handle_width // 2
        track_width = self.rect.width - self.handle_width
        
        # Clamp and normalize
        t = max(0.0, min(1.0, relative_x / max(1, track_width)))
        
        # Map to value range
        new_value = int(self.min_val + t * (self.max_val - self.min_val))
        
        # Only update if changed
        if new_value != self.value:
            self.value = new_value
            showlog.debug(f"[SliderWidget] Value changed to {new_value}")
            
            # Trigger callback
            if self.on_change:
                self.on_change({
                    "value": new_value,
                    "normalized": t,
                })
    
    def get_state(self) -> Dict:
        """Return state for preset saving."""
        return {"value": self.value}
    
    def set_from_state(self, **kwargs):
        """Restore state from preset."""
        if "value" in kwargs:
            self.value = max(self.min_val, min(self.max_val, int(kwargs["value"])))
            self.mark_dirty()
```

### Testing the Example Widget

Create a test file to verify your widget works:

```python
# test_slider_widget.py
import pygame
import sys
from widgets.slider_widget import SliderWidget

pygame.init()
screen = pygame.display.set_mode((800, 480))
clock = pygame.time.Clock()

def on_change(data):
    print(f"Slider value: {data['value']}")

# Create slider at 3×2 size (using drawbar dimensions)
rect = pygame.Rect(267, 100, 413, 300)
slider = SliderWidget(rect, on_change=on_change)

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        slider.handle_event(event)
    
    screen.fill((0, 0, 0))
    slider.draw(screen)
    pygame.display.flip()
    clock.tick(60)

pygame.quit()
```

---

## Integration with Plugins

### Step 1: Define Widget in Plugin

```python
# plugins/my_device_plugin.py
from system.module_core import ModuleBase

class MyDevice(ModuleBase):
    MODULE_ID = "mydevice"
    
    # Define custom widget
    CUSTOM_WIDGET = {
        "class": "SliderWidget",           # Widget class name
        "path": "widgets.slider_widget",   # Import path
        "grid_size": [3, 2],               # 3 cols wide, 2 rows tall
        "grid_pos": [0, 1],                # Position at row 0, col 1
    }
    
    # Grid layout for dials (remaining space)
    GRID_LAYOUT = {
        "rows": 2,
        "cols": 4
    }
    
    # ... rest of plugin code
```

### Step 2: Wire Widget to Plugin Logic

```python
class MyDevice(ModuleBase):
    # ... (previous code)
    
    def __init__(self):
        super().__init__()
        self.slider_value = 64  # Initial state
    
    def attach_widget(self, widget):
        """
        Called by module_base after widget is created.
        Wire the widget's on_change callback to your logic.
        """
        def on_slider_change(data):
            self.slider_value = data["value"]
            # Send to hardware
            self._send_slider_value(data["value"])
        
        widget.on_change = on_slider_change
        showlog.info(f"[MyDevice] Widget attached and wired")
    
    def _send_slider_value(self, value):
        """Send slider value to hardware."""
        # Your MIDI/SysEx code here
        pass
```

### Step 3: Handle Preset Save/Load

The system automatically handles widget state if you implement `get_state()` and `set_from_state()`. The plugin receives the widget state via `on_preset_loaded()`:

```python
class MyDevice(ModuleBase):
    # ... (previous code)
    
    def on_preset_loaded(self, variables: dict, widget_state: dict = None):
        """Called when a preset is loaded."""
        showlog.info(f"[MyDevice] Preset loaded")
        
        # Restore widget state if provided
        if widget_state and "value" in widget_state:
            slider_value = widget_state["value"]
            self.slider_value = slider_value
            # Send to hardware
            self._send_slider_value(slider_value)
```

---

## Advanced Features

### Animation System

For widgets that need continuous animation (like the DrawBarWidget):

```python
class AnimatedWidget(DirtyWidgetMixin):
    def __init__(self, rect, on_change=None, theme=None):
        super().__init__()
        self.rect = pygame.Rect(rect)
        self.on_change = on_change
        
        # Animation state
        self.animation_enabled = False
        self.animation_frame = 0
    
    def start_animation(self):
        """Start the animation."""
        self.animation_enabled = True
        self.mark_dirty()
    
    def stop_animation(self):
        """Stop the animation."""
        self.animation_enabled = False
    
    def update_animation(self):
        """Called each frame to update animation state."""
        if not self.animation_enabled:
            return
        
        self.animation_frame += 1
        # Update visual state based on frame
        # ...
    
    def is_dirty(self) -> bool:
        """Keep dirty during animation."""
        if self.animation_enabled:
            return True
        return super().is_dirty()
    
    def clear_dirty(self):
        """Don't clear dirty flag during animation."""
        if self.animation_enabled:
            return
        super().clear_dirty()
```

### Multi-Part Widgets

For widgets with multiple interactive regions (like ADSR envelope):

```python
class MultiPartWidget(DirtyWidgetMixin):
    def __init__(self, rect, on_change=None, theme=None):
        super().__init__()
        self.rect = pygame.Rect(rect)
        self.on_change = on_change
        
        # Define sub-regions
        self.handle_a = {"x": 100, "y": 100, "dragging": False}
        self.handle_b = {"x": 200, "y": 150, "dragging": False}
    
    def _hit_handle(self, pos, handle_name):
        """Test if position hits a specific handle."""
        handle = getattr(self, handle_name)
        dist = ((pos[0] - handle["x"])**2 + (pos[1] - handle["y"])**2)**0.5
        return dist < 20  # Hit radius
    
    def handle_event(self, event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and hasattr(event, "pos"):
            # Check each handle
            if self._hit_handle(event.pos, "handle_a"):
                self.handle_a["dragging"] = True
                return True
            elif self._hit_handle(event.pos, "handle_b"):
                self.handle_b["dragging"] = True
                return True
        
        elif event.type == pygame.MOUSEMOTION and hasattr(event, "pos"):
            if self.handle_a["dragging"]:
                self.handle_a["x"], self.handle_a["y"] = event.pos
                self.mark_dirty()
                return True
            # ... handle B motion
        
        # ... handle MOUSEBUTTONUP
        return False
```

### Dual Grid Layout (Internal Widget Subdivision)

**Advanced Technique**: Split a single widget into multiple visual sections that look like separate dial panels.

This is useful when you want a large widget (e.g., 4×2) to appear as multiple distinct panels (e.g., 1×2 + 3×2) with proper spacing and styling to match dial panels exactly.

#### Use Case

The ASCII Animator widget demonstrates this pattern:
- Single `CUSTOM_WIDGET` occupying 4×2 grid space (560×300px)
- Internally split into two visual panels:
  - **Left panel**: 1×2 grid cells (120×300px) for frame list
  - **Right panel**: 3×2 grid cells (413×27px) for ASCII grid editor
- Both panels styled exactly like dial panels with proper spacing

#### Implementation Pattern

```python
from utils.grid_layout import get_zone_rect_tight
from helper import theme_rgb
import config as cfg

class DualPanelWidget(DirtyWidgetMixin):
    """
    Widget that internally subdivides into two dial-panel-styled sections.
    """
    
    def __init__(self, rect, on_change=None, theme=None):
        super().__init__()
        self.rect = pygame.Rect(rect)
        self.on_change = on_change
        
        # Parse theme colors
        from helper import theme_rgb
        # (theme color setup...)
    
    def draw(self, surface, device_name=None, offset_y=0):
        """Draw with internal dual-panel layout."""
        try:
            # Apply vertical offset
            draw_rect = self.rect.copy()
            draw_rect.y += offset_y
            
            # Get theme color for dial panel background
            bg_color = theme_rgb(device_name, "DIAL_PANEL_COLOR", default="#0A2F65")
            
            # Calculate internal layout using grid system
            # Left panel: 1×2 at position (0, 0)
            left_rect = get_zone_rect_tight(row=0, col=0, w=1, h=2)
            left_rect.y += offset_y  # Apply offset
            
            # Right panel: 3×2 at position (0, 1) 
            right_rect = get_zone_rect_tight(row=0, col=1, w=3, h=2)
            right_rect.y += offset_y  # Apply offset
            
            # Draw left panel background with dial panel styling
            pygame.draw.rect(surface, bg_color, left_rect, border_radius=15)
            
            # Draw right panel background with dial panel styling
            pygame.draw.rect(surface, bg_color, right_rect, border_radius=15)
            
            # Draw left panel content
            self._draw_left_section(surface, left_rect, device_name)
            
            # Draw right panel content
            self._draw_right_section(surface, right_rect, device_name)
            
            # Return the full widget rect as dirty area
            return draw_rect
            
        except Exception as e:
            import showlog, traceback
            showlog.warn(f"[DualPanelWidget] Draw failed: {e}")
            showlog.warn(traceback.format_exc())
            
            # Fallback: try without grid system
            try:
                # Simple subdivision without grid calculations
                left_width = self.rect.width // 4  # 25% width
                right_width = self.rect.width - left_width - 20  # Remaining with gap
                
                left_rect = pygame.Rect(
                    draw_rect.x, draw_rect.y,
                    left_width, draw_rect.height
                )
                right_rect = pygame.Rect(
                    draw_rect.x + left_width + 20, draw_rect.y,
                    right_width, draw_rect.height
                )
                
                pygame.draw.rect(surface, bg_color, left_rect, border_radius=15)
                pygame.draw.rect(surface, bg_color, right_rect, border_radius=15)
                
                return draw_rect
            except:
                return None
    
    def _draw_left_section(self, surface, rect, device_name):
        """Draw content for left panel."""
        # Your left panel drawing code here
        pass
    
    def _draw_right_section(self, surface, rect, device_name):
        """Draw content for right panel."""
        # Your right panel drawing code here
        pass
```

#### Key Points for Dual Grid Layout

1. **Use Grid System for Positioning**: Call `get_zone_rect_tight(row, col, w, h)` to calculate each internal panel's position
   - This ensures exact dial spacing and sizing
   - Automatic gap calculation between panels
   - Consistent with rest of the UI

2. **Match Dial Panel Styling**:
   ```python
   # Use dial panel background color
   bg_color = theme_rgb(device_name, "DIAL_PANEL_COLOR", default="#0A2F65")
   
   # Use dial panel border radius (15px, not 6px!)
   pygame.draw.rect(surface, bg_color, panel_rect, border_radius=15)
   ```

3. **Apply Offset to All Rects**:
   ```python
   # When using grid system, apply offset after calculation
   left_rect = get_zone_rect_tight(row=0, col=0, w=1, h=2)
   left_rect.y += offset_y  # Don't forget this!
   ```

4. **Provide Fallback**:
   ```python
   try:
       # Grid system approach
       rect = get_zone_rect_tight(row, col, w, h)
   except Exception:
       # Manual calculation fallback
       rect = pygame.Rect(...)
   ```

5. **Organize Drawing Logic**:
   - Separate methods for each panel (`_draw_left_section`, `_draw_right_section`)
   - Keeps code organized and maintainable
   - Each method receives its specific rect

#### Visual Example

```
CUSTOM_WIDGET Config in Plugin:
┌────────────────────────────────────────────────────┐
│ grid_size: [4, 2]                                  │
│ grid_pos: [0, 0]                                   │
│ Single 560×300px widget                            │
└────────────────────────────────────────────────────┘

Internal Layout in draw() method:
┌──────────┬─────────────────────────────────────────┐
│          │                                         │
│  Left    │           Right Panel                   │
│  Panel   │           (3×2 grid)                    │
│  (1×2)   │           413×300px                     │
│ 120×300px│                                         │
│          │                                         │
└──────────┴─────────────────────────────────────────┘
  ↑ 20px gap between panels (automatic from grid system)
```

#### Complete Dual Layout Example

See `widgets/ascii_animator_widget.py` for a real-world implementation:
- Left panel (1×2): Displays frame list with scrolling
- Right panel (3×2): 9×9 ASCII grid editor with box-drawing borders
- Both panels use `theme_rgb()` for all colors
- Proper error handling with fallback positioning
- Exact dial panel styling match

#### Common Pitfalls

❌ **Wrong border radius**
```python
pygame.draw.rect(surface, bg_color, rect, border_radius=6)  # Too small!
```

✅ **Correct border radius**
```python
pygame.draw.rect(surface, bg_color, rect, border_radius=15)  # Matches dials
```

❌ **Forgetting offset**
```python
left_rect = get_zone_rect_tight(row=0, col=0, w=1, h=2)
# Missing: left_rect.y += offset_y
```

✅ **Applying offset**
```python
left_rect = get_zone_rect_tight(row=0, col=0, w=1, h=2)
left_rect.y += offset_y  # Required for scrolling pages
```

❌ **Hardcoded colors**
```python
bg_color = (10, 47, 101)  # Won't adapt to other devices
```

✅ **Theme colors**
```python
bg_color = theme_rgb(device_name, "DIAL_PANEL_COLOR", default="#0A2F65")
```

### Background Caching

For complex backgrounds that don't change often:

```python
class CachedBackgroundWidget(DirtyWidgetMixin):
    def __init__(self, rect, on_change=None, theme=None):
        super().__init__()
        self.rect = pygame.Rect(rect)
        self.on_change = on_change
        
        # Cache for background
        self._background_cache = None
        self._background_cache_rect = None
    
    def draw(self, surface, device_name=None, offset_y=0):
        offset_rect = self.rect.copy()
        offset_rect.y += offset_y
        
        # Check if cache is valid
        cache_invalid = (
            self._background_cache is None
            or self._background_cache_rect != offset_rect
        )
        
        if cache_invalid:
            # Capture background once
            try:
                self._background_cache = surface.subsurface(offset_rect).copy()
                self._background_cache_rect = offset_rect.copy()
            except ValueError:
                self._background_cache = None
        
        # Restore background
        if self._background_cache:
            surface.blit(self._background_cache, offset_rect)
        
        # Draw dynamic elements on top
        # ...
        
        return offset_rect
```

---

## Testing & Debugging

### Debug Drawing

Add debug visualization to understand hit testing and layout:

```python
def draw(self, surface, device_name=None, offset_y=0):
    # ... normal drawing ...
    
    # Debug mode: Show hit regions
    if getattr(self, "debug_mode", False):
        # Draw bounding box
        pygame.draw.rect(surface, (255, 0, 0), draw_rect, 2)
        
        # Draw center crosshair
        center = draw_rect.center
        pygame.draw.line(surface, (0, 255, 0), 
                        (center[0] - 10, center[1]), 
                        (center[0] + 10, center[1]), 2)
        pygame.draw.line(surface, (0, 255, 0),
                        (center[0], center[1] - 10),
                        (center[0], center[1] + 10), 2)
    
    return draw_rect
```

### Logging Best Practices

```python
import showlog

# Use appropriate log levels
showlog.verbose(f"[MyWidget] Frame update {self.frame}")  # High-frequency
showlog.debug(f"[MyWidget] Mouse position: {pos}")        # Debugging info
showlog.info(f"[MyWidget] Value changed to {value}")      # Important events
showlog.warn(f"[MyWidget] Invalid input: {input}")        # Warnings
showlog.error(f"[MyWidget] Failed to load: {e}")          # Errors

# Include context in log messages
showlog.info(f"[MyWidget] Initialized at rect={self.rect}, theme={theme}")
```

### Common Issues & Solutions

#### Issue: Widget shows black screen / Widget not instantiated

**Symptom:** Plugin loads, buttons appear, but widget area is completely black.

**Cause:** Widget's `__init__` signature doesn't match the required pattern.

```python
# ❌ WRONG - Missing required parameters
def __init__(self, rect, my_param=10):
    # This will fail when module_base tries: cls(rect, on_change=None, theme=theme)
    
# ✅ CORRECT - Must accept rect, on_change, theme first
def __init__(self, rect, on_change=None, theme=None, my_param=10):
    super().__init__()
    self.rect = pygame.Rect(rect)
    self.on_change = on_change  # Required!
    self.theme = theme or {}    # Required!
```

**Solution:** Always define `__init__` with `rect`, `on_change`, `theme` as first three parameters. Custom parameters come after.

#### Issue: Widget not appearing (rect problems)

```python
# Solution 1: Check rect dimensions
showlog.info(f"[MyWidget] rect={self.rect}")  # Should not be (0,0,0,0)

# Solution 2: Verify draw method returns dirty rect
return draw_rect  # Don't forget this!

# Solution 3: Check grid position is valid
# grid_pos should be [row, col] where row ∈ [0,1], col ∈ [0,3]
```

#### Issue: Events not working

```python
# Solution 1: Return True when consuming event
if self.rect.collidepoint(event.pos):
    self.dragging = True
    return True  # ← Must return True!

# Solution 2: Check rect collision correctly
if self.rect.collidepoint(event.pos):  # Not self.rect.contains()

# Solution 3: Mark dirty after state change
self.value = new_value
self.mark_dirty()  # ← Don't forget!
```

#### Issue: Widget not redrawing

```python
# Solution: Call mark_dirty() after any visual state change
self.value = new_value
self.mark_dirty()  # Tells system to redraw

# For animations: Override is_dirty()
def is_dirty(self):
    if self.animating:
        return True  # Always dirty during animation
    return super().is_dirty()
```

---

## Common Patterns & Best Practices

### Pattern 1: Value Mapping

Map between different coordinate systems:

```python
def _pos_to_value(self, pos):
    """Map screen position to value range."""
    # Clamp to widget bounds
    x = max(self.rect.left, min(self.rect.right, pos[0]))
    
    # Normalize to 0..1
    t = (x - self.rect.left) / self.rect.width
    
    # Map to value range
    return int(self.min_val + t * (self.max_val - self.min_val))

def _value_to_pos(self, value):
    """Map value to screen position."""
    # Normalize value to 0..1
    t = (value - self.min_val) / (self.max_val - self.min_val)
    
    # Map to pixel position
    return int(self.rect.left + t * self.rect.width)
```

### Pattern 2: Snapping & Quantization

For discrete values (like MIDI notes):

```python
def _update_from_mouse(self, pos):
    """Update value with snapping."""
    # Calculate continuous value
    t = (pos[0] - self.rect.left) / self.rect.width
    raw_value = self.min_val + t * (self.max_val - self.min_val)
    
    # Snap to nearest integer
    new_value = int(round(raw_value))
    
    # Or snap to specific increments
    snap_size = 12  # Snap to semitones
    new_value = int(round(raw_value / snap_size) * snap_size)
    
    if new_value != self.value:
        self.value = new_value
        self.mark_dirty()
        if self.on_change:
            self.on_change({"value": new_value})
```

### Pattern 3: Constrained Movement

For handles that must respect constraints:

```python
def _apply_constraints(self):
    """Enforce widget-specific constraints."""
    # Clamp to bounds
    self.handle_x = max(self.rect.left, min(self.rect.right, self.handle_x))
    self.handle_y = max(self.rect.top, min(self.rect.bottom, self.handle_y))
    
    # Enforce ordering (e.g., handle A must be left of handle B)
    if self.handle_a_x > self.handle_b_x:
        self.handle_a_x = self.handle_b_x
    
    # Maintain minimum gap
    min_gap = 20
    if self.handle_b_x - self.handle_a_x < min_gap:
        self.handle_b_x = self.handle_a_x + min_gap
```

### Pattern 4: Theme Color Parsing

Robust theme color handling:

```python
def _parse_theme_color(self, theme, key, fallback):
    """Safely parse theme color with fallback."""
    if key not in theme:
        return helper.hex_to_rgb(fallback)
    
    color = theme[key]
    
    # Handle different formats
    if isinstance(color, str) and color.startswith("#"):
        return helper.hex_to_rgb(color)
    elif isinstance(color, (list, tuple)):
        # Ensure RGB (no alpha)
        return tuple(color[:3])
    else:
        return helper.hex_to_rgb(fallback)

# Usage in __init__:
self.col_bg = self._parse_theme_color(theme, "bg", cfg.DIAL_PANEL_COLOR)
```

### Pattern 5: Callback Data Structure

Consistent callback data format:

```python
def _notify_change(self):
    """Trigger on_change callback with standardized data."""
    if not self.on_change:
        return
    
    data = {
        "value": self.value,           # Raw value
        "normalized": self._normalize(self.value),  # 0..1
        "widget": self,                 # Reference to widget
        "timestamp": time.time(),       # When it changed
    }
    
    self.on_change(data)

def _normalize(self, value):
    """Normalize value to 0..1 range."""
    return (value - self.min_val) / max(1, self.max_val - self.min_val)
```

---

## Widget Size Reference Chart

Quick reference for common widget configurations:

| Size | Grid Cells | Dimensions (px) | Use Case |
|------|-----------|----------------|----------|
| 1×1 | 1 col × 1 row | 120 × 120 | Single knob replacement |
| 2×1 | 2 cols × 1 row | 266 × 120 | Horizontal slider |
| 1×2 | 1 col × 2 rows | 120 × 300 | Vertical slider/meter |
| 3×1 | 3 cols × 1 row | 413 × 120 | Wide visualization |
| 3×2 | 3 cols × 2 rows | 413 × 300 | Drawbar array, complex controls |
| 4×1 | 4 cols × 1 row | 560 × 120 | Full-width strip |
| 4×2 | 4 cols × 2 rows | 560 × 300 | Full grid widget |

### Position Reference

Common starting positions when column 0 is reserved for buttons:

- **[0, 1]**: Top-left of dial area (skipping button column)
- **[0, 0]**: True top-left (includes button column)
- **[1, 0]**: Bottom-left (second row)
- **[0, 2]**: Top-right area

---

## Checklist for New Widgets

Use this checklist when creating a new widget:

### Design Phase
- [ ] Define widget purpose and interaction model
- [ ] Choose appropriate grid size (e.g., 3×2)
- [ ] Sketch visual design and states
- [ ] Plan state variables needed for presets

### Implementation Phase
- [ ] Create widget file in `widgets/` directory
- [ ] Inherit from `DirtyWidgetMixin`
- [ ] **⚠️ CRITICAL: Implement `__init__` with `rect`, `on_change`, `theme` as first 3 params**
- [ ] Store `self.on_change` and `self.theme` in `__init__`
- [ ] Implement `draw()` method
- [ ] Implement `handle_event()` method
- [ ] Implement `get_state()` method
- [ ] Implement `set_from_state()` method
- [ ] Add proper logging statements
- [ ] Handle theme colors with fallbacks

### Integration Phase
- [ ] Define `CUSTOM_WIDGET` in plugin
- [ ] Implement `attach_widget()` in plugin
- [ ] Handle widget state in `on_preset_loaded()`
- [ ] Test widget in isolation
- [ ] Test widget with plugin
- [ ] Test preset save/load

### Polish Phase
- [ ] Add debug visualization (optional)
- [ ] Optimize drawing performance
- [ ] Add hover/active state visuals
- [ ] Test on different screen sizes
- [ ] Document widget usage

---

## Summary

Creating widgets for the modular UI system involves:

1. **Understanding the grid system**: Widgets are sized in grid cells (4×2 grid)
2. **Using the dirty rect system**: Optimize rendering by only redrawing when needed
3. **Implementing core methods**: `__init__`, `draw`, `handle_event`, `get_state`, `set_from_state`
4. **Integrating with plugins**: Use `CUSTOM_WIDGET` config and `attach_widget()` hook
5. **Following patterns**: Use established patterns for event handling, theme colors, and state management

### Key Takeaways

- **⚠️ CRITICAL: `__init__` signature**: MUST be `(self, rect, on_change=None, theme=None, ...)`. Missing these causes silent failure (black screen).
- **Grid calculations are handled for you**: Use `get_zone_rect_tight()` from `utils.grid_layout`
- **Always mark dirty**: Call `self.mark_dirty()` after any visual state change
- **Return True when consuming events**: This prevents event bubbling
- **Use theme colors**: Make widgets adapt to different device color schemes
- **Test incrementally**: Build and test in small steps

### Most Common Mistake

**Forgetting `on_change` and `theme` parameters in `__init__`**

This causes the widget to fail instantiation silently. You'll see:
- ✅ Plugin loads
- ✅ Buttons appear
- ❌ Widget area is black
- ❌ No error in logs (unless you dig deep)

Always start your widget with:
```python
def __init__(self, rect, on_change=None, theme=None, ...your params...):
    super().__init__()
    self.rect = pygame.Rect(rect)
    self.on_change = on_change
    self.theme = theme or {}
```

### Further Reading

- `PLUGIN_CREATION_MANUAL_COMPLETE.md`: Full plugin system documentation
- `ARCHITECTURE_DIAGRAM.md`: System architecture overview
- `widgets/drawbar_widget.py`: Complex animated widget example
- `widgets/adsr_widget.py`: Multi-handle interactive widget example

---

**Happy Widget Building!** 🎛️

For questions or issues, check the existing widgets in `widgets/` for reference implementations, or consult the plugin examples in `plugins/`.
