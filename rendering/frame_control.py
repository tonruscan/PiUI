"""
Frame rate control.

Manages FPS targeting, burst mode detection, and dynamic FPS scaling.
"""

import pygame
import config as cfg
import showlog


class FrameController:
    """Controls frame rate and rendering frequency."""
    
    def __init__(self, page_registry=None):
        """
        Initialize frame controller.
        
        Args:
            page_registry: Optional PageRegistry for capability queries
        """
        self.clock = pygame.time.Clock()
        self._full_frames_left = 0
        self.page_registry = page_registry
        self._fps_cache = {}  # Cache (ui_mode, in_burst) -> fps
        self._idle_frame_count = {}  # Track idle frames per page for dynamic scaling
    
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
    
    def reset_idle_counter(self, ui_mode: str):
        """Reset idle frame counter when page becomes active."""
        self._idle_frame_count[ui_mode] = 0
    
    def increment_idle_counter(self, ui_mode: str):
        """Increment idle frame counter."""
        self._idle_frame_count[ui_mode] = self._idle_frame_count.get(ui_mode, 0) + 1
    
    def get_target_fps(self, ui_mode: str, in_burst: bool = False) -> int:
        """
        Get target FPS based on page capabilities with caching and dynamic scaling.
        
        Args:
            ui_mode: Current UI mode/page
            in_burst: Whether in burst mode (dial interactions)
        
        Returns:
            Target FPS value
        """
        # Check cache first (avoid recomputation)
        cache_key = (ui_mode, in_burst)
        if cache_key in self._fps_cache:
            cached_fps = self._fps_cache[cache_key]
            
            # Apply dynamic scaling if idle
            if not in_burst and self.supports_dynamic_fps_scaling():
                idle_frames = self._idle_frame_count.get(ui_mode, 0)
                return self.get_scaled_fps(cached_fps, idle_frames)
            
            if ui_mode == "drumbo":
                showlog.debug(f"*[FrameCtrl] drumbo: returning CACHED fps={cached_fps}")
            return cached_fps
        
        # Get page capabilities from registry
        if self.page_registry:
            capabilities = self.page_registry.get_capabilities(ui_mode)
            if ui_mode == "drumbo":
                showlog.debug(f"*[FrameCtrl] drumbo: capabilities from registry = {capabilities}")
        else:
            # Fallback to hardcoded behavior for backward compatibility
            capabilities = self._get_legacy_capabilities(ui_mode)
            if ui_mode == "drumbo":
                showlog.debug(f"*[FrameCtrl] drumbo: using LEGACY capabilities = {capabilities}")
        
        # Burst mode
        if in_burst:
            base_burst = int(getattr(cfg, "FPS_BURST", 100))
            multiplier = capabilities.get("burst_multiplier", 1.0)
            target_fps = int(base_burst * multiplier)
        else:
            # Non-burst: use declared fps_mode
            fps_mode = capabilities.get("fps_mode", "normal")
            
            if ui_mode == "drumbo":
                showlog.debug(f"*[FrameCtrl] drumbo: fps_mode='{fps_mode}'")
            
            if fps_mode == "low":
                target_fps = int(getattr(cfg, "FPS_LOW", 12))
            elif fps_mode == "high":
                target_fps = int(getattr(cfg, "FPS_HIGH", 100))
            else:
                target_fps = int(getattr(cfg, "FPS_NORMAL", 60))
        
        if ui_mode == "drumbo":
            showlog.debug(f"*[FrameCtrl] drumbo: calculated target_fps={target_fps}, caching...")
        
        # Cache result
        self._fps_cache[cache_key] = target_fps
        return target_fps
    
    def _get_legacy_capabilities(self, ui_mode: str) -> dict:
        """
        Fallback to hardcoded FPS behavior for backward compatibility.
        Used when page_registry is not available or page has no metadata.
        
        Args:
            ui_mode: Current UI mode
            
        Returns:
            Dict with legacy fps_mode and defaults
        """
        # Check old hardcoded tuples
        low_pages = getattr(cfg, "FPS_LOW_PAGES", ())
        high_pages = getattr(cfg, "FPS_HIGH_PAGES", ())
        
        if ui_mode in low_pages:
            fps_mode = "low"
        elif ui_mode in high_pages:
            fps_mode = "high"
        else:
            fps_mode = "normal"
        
        return {
            "fps_mode": fps_mode,
            "burst_multiplier": 1.0
        }
    
    def supports_dynamic_fps_scaling(self) -> bool:
        """Check if dynamic FPS downscaling is enabled."""
        return getattr(cfg, "DYNAMIC_FPS_SCALING", False)
    
    def get_scaled_fps(self, base_fps: int, idle_frames: int) -> int:
        """
        Scale FPS down when page is idle (no interaction).
        
        Args:
            base_fps: Base FPS for the page
            idle_frames: Number of consecutive idle frames
        
        Returns:
            Scaled FPS (lower when idle for power savings)
        """
        if not self.supports_dynamic_fps_scaling():
            return base_fps
        
        idle_threshold = getattr(cfg, "IDLE_FPS_THRESHOLD", 30)  # ~0.5s at 60 FPS
        
        if idle_frames > idle_threshold:
            # Drop to half FPS when idle, minimum 12 FPS
            return max(int(base_fps * 0.5), 12)
        
        return base_fps
    
    def invalidate_fps_cache(self, ui_mode: str = None):
        """
        Invalidate FPS cache when page metadata changes.
        
        Args:
            ui_mode: Specific mode to invalidate, or None to clear all
        """
        if ui_mode:
            self._fps_cache = {k: v for k, v in self._fps_cache.items() if k[0] != ui_mode}
        else:
            self._fps_cache.clear()
    
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
