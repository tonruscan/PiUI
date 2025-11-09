"""
Rendering mixin.

Handles all rendering operations and frame drawing logic.
"""

import pygame
import showlog
import showheader


class RenderMixin:
    """Mixin for rendering operations."""
    
    def _render(self):
        """Render the current frame."""
        offset_y = showheader.get_offset()
        ui_mode = self.mode_manager.get_current_mode()
        in_burst = self.dirty_rect_manager.in_burst()
        
        # Check if we need a full frame
        need_full = (
            self.frame_controller.needs_full_frame() or
            self.mode_manager.needs_full_frame()
        )
        
        # Check if header is animating (if method exists)
        try:
            if hasattr(showheader, 'is_animating') and showheader.is_animating():
                need_full = True
        except Exception:
            pass
        
        if ui_mode == "dials" and not need_full and not in_burst:
            # Idle dials - only refresh log bar
            fps = self.frame_controller.get_fps()
            log_rect = self.renderer.draw_log_bar_only(fps)
            if log_rect:
                self.dirty_rect_manager.mark_dirty(log_rect)
            self.dirty_rect_manager.present_dirty(force_full=False)
        else:
            # Full frame draw
            self._draw_full_frame(offset_y)
            pygame.display.flip()
    
    def _draw_full_frame(self, offset_y: int):
        """
        Draw a complete frame.
        
        Args:
            offset_y: Y offset for header animation
        """
        self.renderer.draw_current_page(
            self.mode_manager.get_current_mode(),
            self.mode_manager.get_header_text(),
            self.dial_manager.get_dials(),
            60,  # radius
            self.button_manager.get_pressed_button(),
            offset_y=offset_y
        )
