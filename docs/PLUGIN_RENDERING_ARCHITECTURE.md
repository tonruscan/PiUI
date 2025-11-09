# Plugin Rendering Architecture Plan (v2)

**Status:** Updated with review feedback  
**Last Updated:** 2025-11-01

## Current Problem

The dirty rect optimization is causing update issues with vibrato maker, and the current implementation has several hardcoded assumptions that don't scale well for plugins.

**Issues identified:**
1. `EXCLUDE_DIRTY` tuple requires manually listing pages that can't use dirty rects
2. `FPS_HIGH_PAGES` tuple requires manually listing MIDI/CV pages
3. Dirty rect system assumes dial widgets - doesn't work for custom plugin widgets
4. No clear contract for plugin authors on how to integrate with rendering system

---

## Design Goals

### 1. All plugins should default to 100 FPS
- MIDI/CV interaction requires consistent 100 FPS baseline
- No manual configuration - plugins auto-detect as "interactive"

### 2. All plugins should use dirty rect optimization
- Only redraw changed regions
- No hardcoded widget types - plugin declares what changed
- Fallback to full frame if dirty rects aren't working

### 3. Burst mode available for future expansion
- Currently 100 FPS (same as HIGH)
- Reserved for potential per-plugin performance boost
- Could scale to 120+ FPS if needed for specific plugins

---

## Proposed Architecture

### A. Plugin Capability Declaration

Each plugin declares its rendering capabilities in metadata:

```python
# In plugin file (e.g., vibrato_plugin.py)
PLUGIN_METADATA = {
    "name": "vibrato",
    "schema_version": 1,  # For future compatibility
    "rendering": {
        "fps_mode": "high",           # "low" | "normal" | "high"
        "supports_dirty_rect": True,  # Can mark regions dirty
        "requires_full_frame": False, # Forces full frame every render
        "burst_multiplier": 1.0,      # Future: 1.2 = 20% faster in burst
        "render_layer": "plugin",     # "header" | "plugin" | "overlay" (for compositing)
        "hardware_accel": False       # Future: GPU-aware flag for Pi 5
    }
}
```

**Defaults for plugins without metadata:**
- `fps_mode: "high"` (assume MIDI/CV interaction)
- `supports_dirty_rect: True` (assume modern plugin)
- `requires_full_frame: False`
- `burst_multiplier: 1.0`
- `render_layer: "plugin"`
- `hardware_accel: False`

---

### B. Page Registry Enhancement

Extend the existing `PageRegistry` to store plugin capabilities with normalization:

```python
# In core/page_registry.py

DEFAULT_RENDERING = {
    "fps_mode": "high",
    "supports_dirty_rect": True,
    "requires_full_frame": False,
    "burst_multiplier": 1.0,
    "render_layer": "plugin",
    "hardware_accel": False,
    "schema_version": 1
}

class PageRegistry:
    def __init__(self):
        self._pages = {}
        self._fps_cache = {}  # Cache computed FPS per page
    
    def register(self, page_key, draw_func, metadata=None):
        """
        Register a page with optional rendering metadata.
        
        Args:
            page_key: Unique page identifier
            draw_func: Drawing function
            metadata: Optional rendering hints from plugin
        """
        # Normalize metadata at registration time
        md = {**DEFAULT_RENDERING, **(metadata or {})}
        
        self._pages[page_key] = {
            "draw_ui": draw_func,
            **md
        }
    
    def get_capabilities(self, page_key):
        """Get normalized capabilities for a page."""
        return self._pages.get(page_key, DEFAULT_RENDERING)
    
    def invalidate_fps_cache(self, page_key=None):
        """Invalidate FPS cache when metadata changes."""
        if page_key:
            self._fps_cache.pop(page_key, None)
        else:
            self._fps_cache.clear()
```

---

### C. Dynamic FPS Selection with Caching

Replace hardcoded tuples with capability queries:

```python
# In rendering/frame_control.py
def get_target_fps(self, ui_mode: str, in_burst: bool = False) -> int:
    """Get target FPS based on page capabilities."""
    
    # Check cache first (avoid recomputation)
    cache_key = (ui_mode, in_burst)
    if cache_key in self._fps_cache:
        return self._fps_cache[cache_key]
    
    # Get page capabilities from registry
    capabilities = self.page_registry.get_capabilities(ui_mode)
    
    # Burst mode
    if in_burst:
        base_burst = int(getattr(cfg, "FPS_BURST", 100))
        multiplier = capabilities.get("burst_multiplier", 1.0)
        target_fps = int(base_burst * multiplier)
    else:
        # Non-burst: use declared fps_mode
        fps_mode = capabilities.get("fps_mode", "normal")
        
        if fps_mode == "low":
            target_fps = int(getattr(cfg, "FPS_LOW", 12))
        elif fps_mode == "high":
            target_fps = int(getattr(cfg, "FPS_HIGH", 100))
        else:
            target_fps = int(getattr(cfg, "FPS_NORMAL", 60))
    
    # Cache result
    self._fps_cache[cache_key] = target_fps
    return target_fps

def supports_dynamic_fps_scaling(self) -> bool:
    """Check if dynamic FPS downscaling is enabled."""
    return getattr(cfg, "DYNAMIC_FPS_SCALING", True)

def get_scaled_fps(self, base_fps: int, idle_frames: int) -> int:
    """
    Scale FPS down when page is idle.
    
    Args:
        base_fps: Base FPS for the page
        idle_frames: Number of consecutive idle frames
    
    Returns:
        Scaled FPS (lower when idle)
    """
    if not self.supports_dynamic_fps_scaling():
        return base_fps
    
    idle_threshold = getattr(cfg, "IDLE_FPS_THRESHOLD", 30)  # 30 frames (~0.5s at 60 FPS)
    
    if idle_frames > idle_threshold:
        return max(int(base_fps * 0.5), 12)  # Half FPS, minimum 12
    
    return base_fps
```

---

### D. Enhanced Dirty Rect Protocol

Define clear protocol with context manager and auto-timeout:

```python
# In rendering/dirty_rect.py

class DirtyRectManager:
    def __init__(self):
        self._dirty = []
        self._burst_active = False
        self._burst_last_ms = 0
        self._full_frame_count = {}  # Track consecutive full frames per page
        self._disabled_pages = set()  # Pages with auto-disabled dirty rects
    
    def track(self, rect):
        """
        Context manager for tracking dirty regions.
        
        Usage:
            with dirty_manager.track(widget.rect):
                widget.draw(screen)
        """
        return DirtyRectContext(self, rect)
    
    def mark_dirty(self, rect):
        """Mark a rectangular region as needing redraw."""
        if rect and rect.width > 0 and rect.height > 0:
            self._dirty.append(rect)
    
    def request_full_frame(self):
        """Request a full frame redraw."""
        self._dirty.clear()
        self._full_frame_needed = True
    
    def check_silent_plugin(self, page_key: str, frame_count: int):
        """
        Check if plugin is silently failing to mark dirty rects.
        Auto-disable dirty rects after threshold.
        
        Args:
            page_key: Page identifier
            frame_count: Number of consecutive full frames
        """
        threshold = getattr(cfg, "DIRTY_RECT_TIMEOUT", 3)
        
        if frame_count > threshold and page_key not in self._disabled_pages:
            self._disabled_pages.add(page_key)
            showlog.warn(
                f"[DIRTY_RECT] Auto-disabled for '{page_key}' "
                f"(no dirty regions marked in {frame_count} frames)"
            )
            return True
        
        return page_key in self._disabled_pages
    
    def debug_overlay(self, screen):
        """
        Draw visual overlay showing dirty regions.
        Toggle via DEBUG_DIRTY_OVERLAY config.
        """
        if not getattr(cfg, "DEBUG_DIRTY_OVERLAY", False):
            return
        
        # Draw semi-transparent magenta rectangles over dirty regions
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        for rect in self._dirty:
            pygame.draw.rect(overlay, (255, 0, 255, 80), rect, 2)
        screen.blit(overlay, (0, 0))


class DirtyRectContext:
    """Context manager for automatic dirty rect tracking."""
    
    def __init__(self, manager, rect):
        self.manager = manager
        self.rect = rect
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = (time.perf_counter() - self.start_time) * 1000
        
        # Auto-mark if draw took time (likely changed)
        if duration > 0.5:  # >0.5ms suggests actual drawing occurred
            self.manager.mark_dirty(self.rect)
        
        return False  # Don't suppress exceptions


class DirtyRectAggregator:
    """
    Composite dirty manager for mixed pages (dials + custom widgets).
    Merges dirty regions from multiple sources.
    """
    
    def __init__(self):
        self._sources = []  # List of child dirty managers
    
    def add_source(self, manager):
        """Add a child dirty rect manager."""
        self._sources.append(manager)
    
    def get_all_dirty_rects(self):
        """Get merged list of all dirty rectangles."""
        all_rects = []
        for source in self._sources:
            all_rects.extend(source.get_dirty_rects())
        return all_rects
    
    def clear_all(self):
        """Clear dirty rects from all sources."""
        for source in self._sources:
            source.clear()
```

---

### E. Rendering Pipeline Update with Frame Tracing

Update `core/app.py` to use capabilities and add profiling:

```python
def _render(self):
    """Render the current frame."""
    ui_mode = self.mode_manager.get_current_mode()
    
    # Check if mode is transitioning
    if self.mode_manager.is_mode_blocked(ui_mode):
        return
    
    # Get page capabilities
    capabilities = self.page_registry.get_capabilities(ui_mode)
    
    offset_y = showheader.get_offset()
    in_burst = self.dirty_rect_manager.is_in_burst()
    
    # Frame trace profiling (if enabled)
    trace = getattr(cfg, "FRAME_TRACE", False)
    trace_start = time.perf_counter() if trace else None
    
    # Check if page requires full frame
    requires_full = capabilities.get("requires_full_frame", False)
    need_full = (
        requires_full or
        self.frame_controller.needs_full_frame() or
        self.mode_manager.needs_full_frame()
    )
    
    # Check if page supports dirty rects (and not auto-disabled)
    supports_dirty = capabilities.get("supports_dirty_rect", True)
    is_disabled = self.dirty_rect_manager.check_silent_plugin(ui_mode, self._full_frame_count.get(ui_mode, 0))
    can_use_dirty = supports_dirty and not need_full and not is_disabled
    
    # Render based on mode
    if can_use_dirty and in_burst:
        # TURBO mode - dirty rect optimization
        self._render_dirty_regions(offset_y)
        self._full_frame_count[ui_mode] = 0  # Reset counter
    elif can_use_dirty and not in_burst:
        # Idle - only refresh dynamic elements (log bar, etc.)
        self._render_idle_updates(offset_y)
        self._full_frame_count[ui_mode] = 0  # Reset counter
    else:
        # Full frame draw
        self._draw_full_frame(offset_y)
        self._full_frame_count[ui_mode] = self._full_frame_count.get(ui_mode, 0) + 1
    
    # Draw dirty rect debug overlay if enabled
    self.dirty_rect_manager.debug_overlay(self.screen)
    
    # Frame trace logging
    if trace and trace_start:
        duration = (time.perf_counter() - trace_start) * 1000
        dirty_count = len(self.dirty_rect_manager._dirty)
        fps = self.frame_controller.get_fps()
        showlog.debug(
            f"[TRACE] frame={self._frame_count} | "
            f"mode={ui_mode} | dirty={dirty_count} rects | "
            f"full={not can_use_dirty} | fps={fps:.1f} | "
            f"render={duration:.2f}ms"
        )
```

---

## Migration Plan

### Phase 1: Infrastructure (No Breaking Changes)
1. Add `rendering` field to page registry
2. Add `get_page_capabilities()` to registry
3. Update `get_target_fps()` to check capabilities (with fallback)
4. Add `dirty_manager` parameter to plugin draw functions (optional)

**Result:** Old plugins work unchanged, new plugins can opt-in

---

### Phase 2: Core Page Updates
1. Update built-in pages (dials, presets, mixer, vibrato) with metadata
2. Remove hardcoded `EXCLUDE_DIRTY` tuple
3. Remove hardcoded `FPS_HIGH_PAGES` tuple
4. Test each page with dirty rect validation

**Result:** Core pages use capability system

---

### Phase 3: Plugin Migration Guide
1. Document rendering protocol in plugin docs
2. Provide example plugin with full dirty rect support
3. Add debug mode warnings for plugins not marking regions dirty
4. Create plugin validation tool

**Result:** Plugin authors have clear guidance

---

### Phase 4: Deprecation (Future)
1. Mark old tuple-based config as deprecated
2. Log warnings when tuples are used
3. Eventually remove tuple support

**Result:** Clean, capability-based system only

---

## Configuration Enhancements

### New Config Options (config/performance.py):

```python
# --- Frame rate control ---
FPS_LOW    = 12
FPS_NORMAL = 60
FPS_HIGH   = 100
FPS_BURST  = 100

# Dynamic FPS scaling (lower FPS when idle)
DYNAMIC_FPS_SCALING = True
IDLE_FPS_THRESHOLD = 30  # Frames before downscaling

# Dirty rect system
DIRTY_RECT_TIMEOUT = 3   # Full frames before auto-disable
DEBUG_DIRTY_OVERLAY = False  # Visual overlay for dirty regions
FRAME_TRACE = False      # Enable frame-by-frame profiling

# No more page lists - plugins declare their own needs!
```

---

## Example: Vibrato Plugin Integration (Enhanced)

### Current Issue:
- Vibrato has custom widgets (not standard dials)
- Dirty rect system doesn't know what changed
- Falls back to full frame every render

### Solution with Context Manager:
```python
# plugins/vibrato_plugin.py

PLUGIN_METADATA = {
    "name": "vibrato",
    "schema_version": 1,
    "rendering": {
        "fps_mode": "high",
        "supports_dirty_rect": True,
        "requires_full_frame": False,
        "render_layer": "plugin"
    }
}

class VibratoPlugin:
    def __init__(self):
        self.widgets = []
        self._dirty_widgets = set()
    
    def on_widget_change(self, widget_id):
        """Called when widget value changes."""
        self._dirty_widgets.add(widget_id)
    
    def draw(self, screen, dirty_manager, offset_y=0):
        """Draw with dirty rect support using context manager."""
        
        # If no widgets changed, do nothing (idle optimization)
        if not self._dirty_widgets:
            return
        
        # Redraw only changed widgets using context manager
        for widget_id in self._dirty_widgets:
            widget = self.get_widget(widget_id)
            
            # Context manager auto-marks dirty if draw takes time
            with dirty_manager.track(widget.rect):
                widget.draw(screen)
        
        self._dirty_widgets.clear()
```

### Alternative: DirtyRectAggregator for Mixed Pages
```python
# For pages with both dials and custom widgets
def draw_mixed_page(screen, dials, dirty_manager, offset_y=0):
    """Draw page with both standard dials and custom widgets."""
    
    # Create aggregator for multiple dirty sources
    aggregator = DirtyRectAggregator()
    
    # Add dial dirty regions
    for dial in dials:
        if dial.dirty:
            aggregator.add_source(dial.get_dirty_manager())
    
    # Add custom widget dirty regions
    for widget in custom_widgets:
        if widget.dirty:
            aggregator.add_source(widget.get_dirty_manager())
    
    # Merge and present all dirty regions
    for rect in aggregator.get_all_dirty_rects():
        dirty_manager.mark_dirty(rect)
```

---

## Benefits

### For Plugin Authors:
✅ No config file editing required
✅ Clear rendering contract
✅ Automatic FPS optimization
✅ Debug tools to validate dirty rect usage

### For Core System:
✅ No hardcoded page lists
✅ Scales to unlimited plugins
✅ Easy to add new rendering features
✅ Better performance monitoring

### For Users:
✅ Consistent 100 FPS on all MIDI/CV pages
✅ Automatic optimization without config tweaking
✅ Better battery life (idle pages render less)

---

## Debug & Validation Tools (Enhanced)

### 1. Dirty Rect Validator with Auto-Detection
```python
# utils/validate_dirty_rects.py
def validate_plugin_dirty_rects(plugin_name, frames=60):
    """
    Monitor plugin for N frames and report:
    - Whether dirty rects are being marked
    - Full frame percentage
    - Average FPS
    - Timing glitches (>10ms spikes)
    - Recommendations
    
    Returns dict with metrics and recommendations.
    """
    metrics = {
        "total_frames": frames,
        "dirty_rect_frames": 0,
        "full_frames": 0,
        "avg_fps": 0,
        "timing_spikes": [],  # Frames with >10ms render time
        "recommendations": []
    }
    
    # Monitor and collect data...
    
    if metrics["dirty_rect_frames"] == 0:
        metrics["recommendations"].append(
            "Plugin never marked dirty regions. "
            "Consider implementing dirty_manager.mark_dirty() calls."
        )
    
    return metrics
```

### 2. Visual Dirty Rect Overlay
```python
# Enable via config or keypress (F12)
DEBUG_DIRTY_OVERLAY = True

# In rendering loop:
dirty_manager.debug_overlay(screen)  # Draws magenta boxes
```

### 3. Frame Trace Profiler
```python
# Enable in config
FRAME_TRACE = True

# Output example:
# [TRACE] frame=1234 | mode=vibrato | dirty=3 rects | full=False | fps=100.0 | render=3.6ms
```

### 4. Plugin Capability Report
```python
# utils/plugin_report.py
def generate_plugin_report():
    """
    Generate report of all registered plugins with:
    - Rendering capabilities
    - FPS modes
    - Dirty rect support status
    - Schema version
    """
    
    for page_key, data in page_registry.get_all():
        print(f"\n{page_key}:")
        print(f"  FPS Mode: {data['fps_mode']}")
        print(f"  Dirty Rects: {data['supports_dirty_rect']}")
        print(f"  Schema: v{data['schema_version']}")
        print(f"  Layer: {data['render_layer']}")

# Run with: python -m utils.plugin_report
```

### 5. CI Integration (Plugin Validation)
```python
# tests/test_plugin_capabilities.py
def test_all_plugins_have_metadata():
    """Ensure all plugins define PLUGIN_METADATA."""
    for plugin in discover_plugins():
        assert hasattr(plugin, 'PLUGIN_METADATA'), \
            f"{plugin.__name__} missing PLUGIN_METADATA"

def test_dirty_rect_implementation():
    """Test that plugins claiming dirty rect support actually mark regions."""
    for plugin in discover_plugins():
        if plugin.PLUGIN_METADATA['rendering']['supports_dirty_rect']:
            metrics = validate_plugin_dirty_rects(plugin.__name__, frames=30)
            assert metrics['dirty_rect_frames'] > 0, \
                f"{plugin.__name__} claims dirty rect support but never marks regions"
```

---

## Migration Plan (Updated)

### Phase 1: Infrastructure (No Breaking Changes) - Week 1
1. ✅ Add `DEFAULT_RENDERING` dict to page_registry.py
2. ✅ Implement metadata normalization in `register()`
3. ✅ Add `get_capabilities()` method
4. ✅ Update `get_target_fps()` to check capabilities (with fallback to hardcoded tuples)
5. ✅ Add FPS caching
6. ✅ Implement `DirtyRectContext` context manager
7. ✅ Add `debug_overlay()` to DirtyRectManager
8. ✅ Add `dirty_manager` parameter to plugin draw functions (optional, backward compatible)

**Result:** Old plugins work unchanged, new plugins can opt-in  
**Testing:** Verify no regressions on existing pages

---

### Phase 2: Core Page Updates - Week 2
1. Update built-in pages with PLUGIN_METADATA:
   - `dials` → `fps_mode: "high"`, `supports_dirty_rect: True`
   - `presets` → `fps_mode: "normal"`, `requires_full_frame: True`
   - `mixer` → `fps_mode: "high"`, `supports_dirty_rect: True`
   - `vibrato` → `fps_mode: "high"`, `supports_dirty_rect: True` (fix implementation)
   - `patchbay` → `fps_mode: "low"`, `requires_full_frame: True`
   - `device_select` → `fps_mode: "low"`, `requires_full_frame: True`

2. Implement dirty rect tracking in vibrato:
   - Add `_dirty_widgets` set
   - Use context manager for widget draws
   - Test thoroughly

3. Add frame trace logging (behind `FRAME_TRACE` flag)

4. Test each page:
   - Verify FPS targets
   - Check dirty rect behavior
   - Monitor for timing glitches

**Result:** Core pages use capability system  
**Testing:** Run validation tool on each page

---

### Phase 3: Deprecation Warnings - Week 3
1. Add deprecation warnings when hardcoded tuples are used
2. Log which pages are still using old system
3. Update documentation with migration examples
4. Provide plugin migration guide

**Result:** Clear path for external plugin authors  
**Testing:** Ensure warnings appear correctly

---

### Phase 4: Tuple Removal - Week 4+
1. Remove `FPS_HIGH_PAGES`, `FPS_LOW_PAGES` from config
2. Remove `EXCLUDE_DIRTY` tuple
3. Remove fallback code in `get_target_fps()`
4. Update all config profiles

**Result:** Clean, capability-based system only  
**Testing:** Full regression test suite

---

## Open Questions (Updated with Answers)

### 1. Should burst mode scale differently per plugin?
**Answer:** Yes, via `burst_multiplier` field
- Most plugins: 1.0 (100 FPS)
- High-performance plugins: 1.2 (120 FPS burst)
- Configurable per-plugin without global changes

### 2. How to handle mixed pages (e.g., dials + custom widgets)?
**Answer:** Use `DirtyRectAggregator`
- Merges dirty regions from multiple sources
- Both standard dials and custom widgets coexist
- Plugin doesn't need special handling

### 3. What if plugin forgets to mark regions dirty?
**Answer:** Auto-detection + fallback
- After 3 full frames without dirty marks → auto-disable dirty rects for that page
- Debug mode logs warning
- System remains stable

### 4. Should we support partial dirty rect (plugin-specific)?
**Answer:** Not initially, but architecture supports it
- Could add `dirty_rect_mode: "full" | "partial" | "auto"` in future
- For now, binary: supports_dirty_rect True/False
- Can extend in schema_version 2

### 5. How to handle frame pacing jitter for audio sync?
**Answer:** Frame trace profiler + timing spike detection
- Log frames taking >10ms
- Identify culprit (plugin name, operation)
- Helps debug audio-sync issues

### 6. GPU acceleration for future Pi 5?
**Answer:** `hardware_accel` flag reserved
- Currently False for all plugins
- Future: OpenGL/Vulkan rendering path
- Plugins opt-in when ready

---

## Benefits Summary

### For Plugin Authors:
✅ No config file editing required  
✅ Clear rendering contract with examples  
✅ Automatic FPS optimization  
✅ Debug tools to validate implementation  
✅ Context manager reduces boilerplate  
✅ Backward compatible (opt-in)

### For Core System:
✅ No hardcoded page lists  
✅ Scales to unlimited plugins  
✅ Auto-detection and fallback for broken plugins  
✅ Easy to add new rendering features (GPU, layers, etc.)  
✅ Better performance monitoring (frame trace)  
✅ Cleaner config files

### For Users:
✅ Consistent 100 FPS on all MIDI/CV pages  
✅ Automatic optimization without config tweaking  
✅ Better battery life (dynamic FPS scaling when idle)  
✅ Stable system (fallback for misbehaving plugins)  
✅ Visual feedback (debug overlay) when troubleshooting

---

## Implementation Checklist

### Week 1 (Infrastructure):
- [ ] Update `PageRegistry` with `DEFAULT_RENDERING` and normalization
- [ ] Add `get_capabilities()` method
- [ ] Implement FPS caching in `FrameController`
- [ ] Create `DirtyRectContext` context manager
- [ ] Add `DirtyRectAggregator` class
- [ ] Implement `debug_overlay()` method
- [ ] Add `check_silent_plugin()` auto-timeout
- [ ] Update `get_target_fps()` to check capabilities
- [ ] Add backward compatibility fallback
- [ ] Write unit tests

### Week 2 (Core Pages):
- [ ] Add PLUGIN_METADATA to all built-in pages
- [ ] Fix vibrato dirty rect implementation
- [ ] Test each page individually
- [ ] Add frame trace logging
- [ ] Run dirty rect validator on all pages
- [ ] Update integration tests

### Week 3 (Documentation):
- [ ] Write plugin migration guide
- [ ] Document dirty rect protocol with examples
- [ ] Create capability reference guide
- [ ] Add troubleshooting section
- [ ] Record demo video showing tools

### Week 4 (Cleanup):
- [ ] Add deprecation warnings
- [ ] Remove hardcoded tuples
- [ ] Update all config profiles
- [ ] Full regression testing
- [ ] Performance benchmarking

---

## Next Steps

**Immediate (Today):**
1. ✅ Review v2 plan with stakeholders
2. Identify any remaining gaps or concerns
3. Get approval to proceed with Phase 1

**This Week:**
1. Implement Phase 1 (infrastructure)
2. Fix vibrato dirty rect issue as proof-of-concept
3. Test with existing plugins

**Next Sprint:**
1. Complete Phase 2 (core page migration)
2. Add validation tools
3. Document plugin rendering guide

---

## References

**Related Documentation:**
- `docs/app-modernization-summary.md` - Core architecture
- `docs/PAGE_TRANSITION_FLICKER_FIX.md` - Rendering fixes
- `config/performance.py` - Performance settings
- `rendering/frame_control.py` - FPS management
- `rendering/dirty_rect.py` - Dirty rect system

**Key Files:**
- `core/page_registry.py` - Plugin registration
- `core/app.py` - Main render loop
- `rendering/` - All rendering components
- `plugins/` - Plugin implementations
