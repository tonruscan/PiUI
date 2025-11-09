"""
Main renderer.

Coordinates all drawing operations for the UI.
"""

import pygame
from typing import Optional
import inspect

import showlog
import showheader
import dialhandlers
import navigator
import time
import config.performance as perf
import config.layout as cfg

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
        self._last_log_draw_time = 0.0
    
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

        log_h = getattr(cfg, "LOG_BAR_HEIGHT", 20)
        self.screen.fill((0, 0, 0), pygame.Rect(0, 0, self.screen.get_width(), self.screen.get_height() - log_h))
        
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
                        elif ui_mode in ("mixer", "vibrato", "vk8m_main", "ascii_animator", "drumbo", "drumbo_main", "test_minimal_main"):
                            page["draw_ui"](self.screen, offset_y=offset_y)
                        else:
                            handler = page["draw_ui"]
                            try:
                                sig = inspect.signature(handler)
                            except (TypeError, ValueError):
                                handler(self.screen, offset_y=offset_y)
                            else:
                                call_args = []
                                call_kwargs = {}
                                missing_required = False

                                for name, param in sig.parameters.items():
                                    if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
                                        continue

                                    if name in {"screen", "surface"}:
                                        call_args.append(self.screen)
                                    elif name == "dials":
                                        call_args.append(dials)
                                    elif name == "radius":
                                        call_args.append(radius)
                                    elif name in {"exit_rect", "exit_button_rect"}:
                                        call_args.append(self.exit_rect)
                                    elif name in {"header_text", "title"}:
                                        call_args.append(header_text)
                                    elif name in {"pressed_button", "active_button"}:
                                        call_args.append(pressed_button)
                                    elif name == "offset_y":
                                        call_kwargs.setdefault("offset_y", offset_y)
                                    elif param.default is inspect._empty:
                                        missing_required = True
                                        break

                                if missing_required:
                                    showlog.warn(f"[RENDERER] Unable to auto-call draw_ui for {ui_mode}; unsupported parameter signature")
                                    try:
                                        handler(self.screen, offset_y=offset_y)
                                    except TypeError:
                                        handler(self.screen)
                                else:
                                    handler(*call_args, **call_kwargs)
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
        themed_pages = ("dials", "presets", "mixer", "vibrato", "vk8m_main", "module_presets", "ascii_animator", "drumbo", "drumbo_main", "test_minimal_main")
        
        if ui_mode in themed_pages and device_name:
            showheader.show(self.screen, header_text, device_name)
        else:
            showheader.show(self.screen, header_text)
    
    def _should_draw_log_bar(self) -> bool:
        """Return True if enough time has passed to draw the log bar."""
        now = time.time()
        interval = 1.0 / getattr(perf, "LOG_BAR_UPDATE_HZ", 1)
        if now - self._last_log_draw_time >= interval:
            self._last_log_draw_time = now
            return True
        return False

    def _draw_log_bar(self):
        """Draw the footer/log bar at a limited rate."""
        try:
            if not self._should_draw_log_bar():
                return  # Skip if not time yet

            fps = self.frame_controller.get_fps() if self.frame_controller else 0
            showlog.draw_bar(self.screen, fps_value=fps)

        except Exception as e:
            showlog.error(f"[RENDERER] Log bar draw error: {e}")

    def draw_log_bar_only(self, fps: float):
        """
        Draw only the log bar (for dirty rect optimization).
        Returns the rectangle of the log bar region.
        """
        try:
            if not self._should_draw_log_bar():
                return None  # Skip if not time yet

            import config as cfg
            showlog.draw_bar(self.screen, fps_value=fps)
            log_h = getattr(cfg, "LOG_BAR_HEIGHT", 20)
            return pygame.Rect(
                0,
                self.screen.get_height() - log_h,
                self.screen.get_width(),
                log_h,
            )
        except Exception:
            return None

    
    def present_frame(self):
        """Present the rendered frame."""
        pygame.display.flip()
