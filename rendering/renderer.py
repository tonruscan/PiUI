"""
Main renderer.

Coordinates all drawing operations for the UI.
"""

import pygame
from typing import Optional

import showlog
import showheader
import dialhandlers
import navigator


class Renderer:
    """Main rendering coordinator."""
    
    def __init__(self, screen: pygame.Surface, preset_manager=None, page_registry=None, frame_controller=None):
        """
        Initialize renderer.
        
        Args:
            screen: Pygame screen surface
            preset_manager: Optional UnifiedPresetManager instance
            page_registry: Optional PageRegistry instance
            frame_controller: Optional FrameController for FPS tracking
        """
        self.screen = screen
        self.preset_manager = preset_manager
        self.page_registry = page_registry
        self.frame_controller = frame_controller
        self.exit_rect = pygame.Rect(755, 5, 40, 40)
    
    def draw_current_page(self, 
                         ui_mode: str,
                         header_text: str,
                         dials: list,
                         radius: int,
                         pressed_button: Optional[str],
                         offset_y: int = 0):
        """
        Render the current page.
        
        Args:
            ui_mode: Current UI mode/page
            header_text: Header text to display
            dials: List of Dial objects
            radius: Dial radius
            pressed_button: Currently pressed button
            offset_y: Y offset for header animation
        """
        # Clear background
        self.screen.fill((0, 0, 0))
        
        # Guard for transitions
        if navigator.is_transitioning():
            showlog.debug("[RENDERER] Skipping frame (page transition in progress)")
            return
        
        # Draw active page using page registry
        try:
            # Special handling for preset pages (managed by UnifiedPresetManager)
            if ui_mode in ("presets", "module_presets"):
                if self.preset_manager:
                    self.preset_manager.draw(offset_y=offset_y)
            elif self.page_registry:
                # Use page registry for dynamic dispatch
                page = self.page_registry.get(ui_mode)
                if page:
                    # Try draw_ui first (most pages use this)
                    if page["draw_ui"]:
                        # Build args based on page requirements
                        if ui_mode == "dials":
                            page["draw_ui"](
                                self.screen, dials, radius, self.exit_rect,
                                header_text, pressed_button, offset_y=offset_y
                            )
                        elif ui_mode == "device_select":
                            page["draw_ui"](
                                self.screen, self.exit_rect, header_text,
                                pressed_button, offset_y=offset_y
                            )
                        elif ui_mode == "patchbay":
                            page["draw_ui"](
                                self.screen, self.exit_rect, header_text,
                                pressed_button, offset_y=offset_y
                            )
                        elif ui_mode in ("mixer", "vibrato"):
                            page["draw_ui"](self.screen, offset_y=offset_y)
                    # Try draw as fallback
                    elif page["draw"]:
                        page["draw"](self.screen, offset_y=offset_y)
                else:
                    showlog.warn(f"[RENDERER] Unknown page: {ui_mode}")
            else:
                # Fallback if no page registry (shouldn't happen)
                showlog.error(f"[RENDERER] No page registry available")
        except Exception as e:
            showlog.error(f"[RENDERER] Page draw error: {e}")
        
        # Draw header
        self._draw_header(ui_mode, header_text, offset_y)
        
        # Draw log bar
        self._draw_log_bar()
    
    def _draw_header(self, ui_mode: str, header_text: str, offset_y: int = 0):
        """
        Draw the header.
        
        Args:
            ui_mode: Current UI mode
            header_text: Header text to display
            offset_y: Y offset for animation
        """
        device_name = getattr(dialhandlers, "current_device_name", None)
        themed_pages = ("dials", "presets", "mixer", "vibrato", "module_presets")
        
        if ui_mode in themed_pages and device_name:
            showheader.show(self.screen, header_text, device_name)
        else:
            showheader.show(self.screen, header_text)
    
    def _draw_log_bar(self):
        """Draw the footer/log bar."""
        try:
            # Get FPS from frame controller if available
            fps = self.frame_controller.get_fps() if self.frame_controller else 0
            showlog.draw_bar(self.screen, fps_value=fps)
        except Exception as e:
            showlog.error(f"[RENDERER] Log bar draw error: {e}")
    
    def present_frame(self):
        """Present the rendered frame."""
        pygame.display.flip()
    
    def draw_log_bar_only(self, fps: float):
        """
        Draw only the log bar (for dirty rect optimization).
        
        Args:
            fps: Current FPS value
        
        Returns:
            Rectangle of the log bar region
        """
        try:
            import config as cfg
            showlog.draw_bar(self.screen, fps_value=fps)
            log_h = getattr(cfg, "LOG_BAR_HEIGHT", 20)
            return pygame.Rect(0, self.screen.get_height() - log_h, 
                             self.screen.get_width(), log_h)
        except Exception:
            return None
