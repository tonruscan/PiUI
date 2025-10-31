"""
Frame rate control.

Manages FPS targeting and burst mode detection.
"""

import pygame
import config as cfg


class FrameController:
    """Controls frame rate and rendering frequency."""
    
    def __init__(self):
        """Initialize frame controller."""
        self.clock = pygame.time.Clock()
        self._full_frames_left = 0
    
    def request_full_frames(self, count: int):
        """
        Request a number of full redraw frames.
        
        Args:
            count: Number of frames to force full redraw
        """
        self._full_frames_left = max(self._full_frames_left, count)
    
    def needs_full_frame(self) -> bool:
        """
        Check if a full frame redraw is needed.
        
        Returns:
            True if full frame is needed
        """
        if self._full_frames_left > 0:
            self._full_frames_left -= 1
            return True
        return False
    
    def get_target_fps(self, ui_mode: str, in_burst: bool = False) -> int:
        """
        Get target FPS for current mode.
        
        Args:
            ui_mode: Current UI mode/page
            in_burst: Whether in burst mode
        
        Returns:
            Target FPS value
        """
        # Always lock Dials page to 100 FPS baseline
        if ui_mode == "dials":
            return 100
        
        # Burst mode gets turbo FPS
        if in_burst:
            return int(getattr(cfg, "FPS_TURBO", 120))
        
        # Check page-specific FPS settings
        try:
            low_pages = getattr(cfg, "FPS_LOW_PAGES", ())
            turbo_pages = getattr(cfg, "FPS_TURBO_PAGES", ())
            
            if ui_mode in turbo_pages:
                return int(getattr(cfg, "FPS_TURBO", 120))
            elif ui_mode in low_pages:
                return int(getattr(cfg, "FPS_LOW", 12))
            else:
                return int(getattr(cfg, "FPS_NORMAL", 60))
        except Exception:
            return 60
    
    def tick(self, target_fps: int):
        """
        Tick the clock to maintain target FPS.
        
        Args:
            target_fps: Target frames per second
        """
        self.clock.tick(target_fps)
    
    def get_fps(self) -> float:
        """
        Get current FPS.
        
        Returns:
            Current frames per second
        """
        return self.clock.get_fps()
