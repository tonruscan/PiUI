"""
Dirty rectangle management.

Optimizes rendering by tracking which parts of the screen need redrawing.
"""

import pygame
from typing import List, Optional

import config as cfg


class DirtyRectManager:
    """Manages dirty rectangles for optimized rendering."""
    
    def __init__(self):
        """Initialize dirty rect manager."""
        self._dirty: List[pygame.Rect] = []
        self._burst_active = False
        self._burst_last_ms = 0
    
    def mark_dirty(self, rect: Optional[pygame.Rect]):
        """
        Mark a rectangular region as needing redraw.
        
        Args:
            rect: The rectangle to mark dirty, or None for full screen
        """
        if rect and rect.width > 0 and rect.height > 0:
            self._dirty.append(rect)
    
    def present_dirty(self, force_full: bool = False):
        """
        Update the display with dirty regions.
        
        Args:
            force_full: Force a full screen update
        """
        if force_full:
            pygame.display.flip()
            self._dirty.clear()
            return
        
        if not self._dirty:
            return  # Nothing to do
        
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
