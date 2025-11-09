"""
Dirty rectangle management.

Optimizes rendering by tracking which parts of the screen need redrawing.
"""

import pygame
import time
from typing import List, Optional, Set
from contextlib import contextmanager

import config as cfg
import showlog


class DirtyRectAggregator:
    """
    Helper for aggregating multiple dirty rects from a plugin render.
    
    Usage:
        aggregator = DirtyRectAggregator()
        with aggregator.track(rect1):
            draw_something()
        with aggregator.track(rect2):
            draw_something_else()
        manager.mark_dirty(aggregator.get_bounds())
    """
    
    def __init__(self):
        """Initialize aggregator."""
        self._rects: List[pygame.Rect] = []
        self._draw_start_time: Optional[float] = None
    
    @contextmanager
    def track(self, rect: Optional[pygame.Rect]):
        """
        Track a drawing operation.
        
        Args:
            rect: Rectangle being drawn to
            
        Yields:
            None
        """
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            
            # Auto-mark as dirty if draw took significant time
            if rect and elapsed_ms > 0.5:
                self._rects.append(rect)
    
    def add(self, rect: Optional[pygame.Rect]):
        """Manually add a rect to the aggregate."""
        if rect:
            self._rects.append(rect)
    
    def get_bounds(self) -> Optional[pygame.Rect]:
        """Get the bounding rect of all tracked rects."""
        if not self._rects:
            return None
        
        # Use pygame's unionall to get bounding rect
        return pygame.Rect.unionall(self._rects)
    
    def clear(self):
        """Clear tracked rects."""
        self._rects.clear()


class DirtyRectManager:
    """Manages dirty rectangles for optimized rendering."""
    
    def __init__(self):
        """Initialize dirty rect manager."""
        self._dirty: List[pygame.Rect] = []
        self._burst_active = False
        self._burst_last_ms = 0
        
        # Debug tracking
        self._full_frame_count: dict = {}  # page_id -> consecutive full frame count
        self._disabled_pages: Set[str] = set()  # Pages with dirty rect disabled
        self._debug_rects: List[pygame.Rect] = []  # For debug overlay

    def _log_debug(self, message: str):
        """Emit a verbose log when dirty rect diagnostics are enabled."""
        try:
            if getattr(cfg, "DEBUG_DIRTY_LOG", False):
                showlog.verbose(f"[DIRTY] {message}")
        except Exception:
            pass
    
    def mark_dirty(self, rect: Optional[pygame.Rect]):
        """
        Mark a rectangular region as needing redraw.
        
        Args:
            rect: The rectangle to mark dirty, or None for full screen
        """
        if rect and rect.width > 0 and rect.height > 0:
            self._dirty.append(rect)
            self._log_debug(f"Marked dirty rect {rect} (pending={len(self._dirty)})")
        else:
            self._log_debug(f"Ignored dirty rect request (rect={rect})")
    
    def present_dirty(self, force_full: bool = False):
        """
        Update the display with dirty regions.
        
        Args:
            force_full: Force a full screen update
        """
        # Store rects for debug overlay before clearing
        self._store_debug_rects()
        
        if force_full:
            self._log_debug("Presenting full frame via pygame.display.flip()")
            pygame.display.flip()
            self._dirty.clear()
            return
        
        if not self._dirty:
            return  # Nothing to do
        
        rect_count = len(self._dirty)
        details = ", ".join(str(rect) for rect in self._dirty[:3])
        if rect_count > 3:
            details += ", …"
        self._log_debug(f"Calling pygame.display.update with {rect_count} rect(s): {details}")
        pygame.display.update(self._dirty)
        self._dirty.clear()
    
    def start_burst(self):
        """Start burst mode (frequent updates)."""
        self._burst_active = True
        self._burst_last_ms = pygame.time.get_ticks()
    
    def update_burst(self):
        """Update burst timing."""
        if self._burst_active:
            self._burst_last_ms = pygame.time.get_ticks()
    
    def is_in_burst(self) -> bool:
        """
        Check if currently in burst mode.
        
        Returns:
            True if in burst mode
        """
        if not getattr(cfg, "DIRTY_BURST_MODE", True):
            return False
        
        if not self._burst_active:
            return False
        
        now_ms = pygame.time.get_ticks()
        grace_ms = int(getattr(cfg, "DIRTY_GRACE_MS", 120))
        
        in_burst = (now_ms - self._burst_last_ms) <= grace_ms
        
        if not in_burst:
            self._burst_active = False
        
        return in_burst
    
    def end_burst(self):
        """Explicitly end burst mode."""
        self._burst_active = False
    
    def clear(self):
        """Clear all dirty rects."""
        self._dirty.clear()
    
    def has_dirty_regions(self) -> bool:
        """Check if there are dirty regions."""
        return len(self._dirty) > 0
    
    @contextmanager
    def track(self, rect: Optional[pygame.Rect]):
        """
        Context manager for tracking dirty rects.
        
        Usage:
            with dirty_manager.track(my_rect):
                draw_something(surface, my_rect)
        
        Args:
            rect: Rectangle being drawn to
            
        Yields:
            None
        """
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            
            # Auto-mark as dirty if draw took significant time
            if rect and elapsed_ms > 0.5:
                self.mark_dirty(rect)
    
    def check_silent_plugin(self, page_id: str, did_mark_dirty: bool, screen_rect: pygame.Rect):
        """
        Check if a plugin is failing to mark dirty rects.
        
        After 3 consecutive full frames without marking dirty, assumes the plugin
        doesn't support dirty rects and disables optimization for that page.
        
        Args:
            page_id: The page being rendered
            did_mark_dirty: Whether the plugin marked any dirty regions
            screen_rect: Full screen rect for fallback
        """
        timeout = getattr(cfg, "DIRTY_RECT_TIMEOUT", 3)
        
        if page_id in self._disabled_pages:
            # Already disabled, force full frame
            self.mark_dirty(screen_rect)
            return
        
        if not did_mark_dirty:
            # Plugin didn't mark dirty - increment count
            self._full_frame_count[page_id] = self._full_frame_count.get(page_id, 0) + 1
            
            if self._full_frame_count[page_id] >= timeout:
                # Plugin is silent - disable dirty rect optimization
                print(f"[DirtyRect] Page '{page_id}' doesn't mark dirty rects - disabling optimization")
                self._disabled_pages.add(page_id)
                self._full_frame_count.pop(page_id, None)
            
            # Force full frame
            self.mark_dirty(screen_rect)
        else:
            # Plugin marked dirty - reset count
            self._full_frame_count.pop(page_id, None)
    
    def debug_overlay(self, surface: pygame.Surface):
        """
        Draw debug overlay showing dirty regions.
        
        Args:
            surface: Surface to draw on
        """
        if not getattr(cfg, "DEBUG_DIRTY_OVERLAY", False):
            return
        
        # Draw magenta boxes around dirty regions
        for rect in self._debug_rects:
            pygame.draw.rect(surface, (255, 0, 255), rect, 2)
        
        self._debug_rects.clear()
    
    def _store_debug_rects(self):
        """Store current dirty rects for debug overlay."""
        if getattr(cfg, "DEBUG_DIRTY_OVERLAY", False):
            self._debug_rects = self._dirty.copy()
