# /widgets/drumbo_main_widget.py
# Main widget for Drumbo drum machine - simple rounded rectangle space
# Just a clean 4x2 area, no complex controls yet

import pygame
import showlog
import config as cfg
import helper
import time
import utils.font_helper as font_helper
from typing import Optional, Dict, Any


class DrumboMainWidget:
    """
    Main widget for Drumbo drum machine.
    
    Clean 4x2 rounded rectangle space for future drum controls.
    """

    # Override these to fine-tune mini dial placement for Drumbo without
    # affecting global config defaults. All keys are optional; see
    # Drumbo._position_mini_dials for the list of supported values.
    MINI_DIAL_LAYOUT_OVERRIDES = {}
    
    def __init__(self, rect: pygame.Rect, on_change=None, theme=None, init_state=None):
        """Initialize the Drumbo main widget."""
        self.rect = rect
        self.on_change = on_change
        self.theme = theme or {}
        self._module = None  # Will be set by module via attach_widget()
        
        # Dirty rendering support
        self._dirty = True
        self._dirty_dial = None  # Track which specific dial changed for minimal dirty rect
        self.msg_queue = None
        
        # State
        self.current_instrument = "snare"  # "snare" or "kick"
        self.active_bank = "A"
        self.mic_dials_row_1 = []
        self.mic_dials_row_2 = []
        self.current_page_rect = rect.copy()
        
        # MIDI note detection indicator
        self.midi_note_detected = False
        self.midi_note_time = 0  # Time of last MIDI note detection
        self.midi_flash_duration = 0.1  # Flash duration in seconds
        self._midi_settle_pending = False
        
        # Colors from theme
        self._update_colors()
        
        # Font for label below widget (same style as dial labels)
        font_path = font_helper.main_font("Bold")
        self.label_font = pygame.font.Font(font_path, cfg.DIAL_FONT_SIZE)
        
        showlog.info(f"[DrumboMainWidget] Initialized with rect={rect}")
    
    def _update_colors(self):
        """Extract colors from theme (using short keys passed by module_base)."""
        # Theme dict has short keys: "bg", "fill", "outline"
        th = self.theme or {}
        
        # Debug: Log what we received
        showlog.info(f"[DrumboMainWidget] Received theme keys: {list(th.keys())}")
        showlog.info(f"[DrumboMainWidget] plugin_background_color = {th.get('plugin_background_color')}")
        showlog.info(f"[DrumboMainWidget] bg = {th.get('bg')}")
        
        def _rgb3(c):
            return tuple(c[:3]) if isinstance(c, (list, tuple)) else c
        
        def _to_rgb(val, fallback_hex):
            """Normalise a theme value (tuple or hex string) to an RGB tuple."""
            if isinstance(val, (list, tuple)):
                return tuple(val[:3])
            if isinstance(val, str):
                try:
                    return helper.hex_to_rgb(val)
                except Exception:
                    pass
            return helper.hex_to_rgb(fallback_hex)
        
        # Background priority:
        # 1) explicit 'plugin_background_color' in module THEME (hex string)
        # 2) short-key 'bg' passed to widget (RGB tuple)
        # 3) active module/device THEME 'plugin_background_color' via helper
        # 4) config.PLUGIN_BACKGROUND_COLOR or cfg.DIAL_PANEL_COLOR
        if "plugin_background_color" in th:
            self.bg_color = _to_rgb(th.get("plugin_background_color"), cfg.DIAL_PANEL_COLOR)
            showlog.info(f"[DrumboMainWidget] Using plugin_background_color: {self.bg_color}")
        elif "bg" in th:
            self.bg_color = _rgb3(th.get("bg"))
            showlog.info(f"[DrumboMainWidget] Using bg: {self.bg_color}")
        else:
            hex_bg = helper.device_theme.get("", "plugin_background_color", getattr(cfg, "PLUGIN_BACKGROUND_COLOR", cfg.DIAL_PANEL_COLOR))
            self.bg_color = helper.hex_to_rgb(hex_bg)
            showlog.info(f"[DrumboMainWidget] Using fallback: {self.bg_color}")

        self.border_color = _rgb3(th.get("outline")) if "outline" in th else helper.hex_to_rgb(cfg.DIAL_OUTLINE_COLOR)
        self.kick_blank_bg_color = _to_rgb(th.get("kick_blank_background"), "#120805")
        self.kick_blank_border_color = _to_rgb(th.get("kick_blank_border"), "#2C1810")
        
        # Get text color from device theme (like drawbar widget does)
        import dialhandlers
        device_name = getattr(dialhandlers, "current_device_name", None)
        dial_text_hex = helper.device_theme.get(device_name, "dial_text_color", cfg.DIAL_TEXT_COLOR if hasattr(cfg, 'DIAL_TEXT_COLOR') else '#FFFFFF')
        self.text_color = helper.hex_to_rgb(dial_text_hex)
    
    def draw(self, surface: pygame.Surface, device_name=None, offset_y=0):
        """Draw the widget - only if full redraw needed, otherwise return minimal dirty rect."""
        # If we only have a specific dial dirty, don't redraw the widget background
        # Just return the dial's dirty rect so the dial can be redrawn over existing background
        if self._dirty_dial is not None:
            try:
                # Get dial bounds (circle + label area)
                dial = self._dirty_dial
                radius = getattr(dial, 'radius', 25)
                cx = int(getattr(dial, 'cx', 0))
                cy = int(getattr(dial, 'cy', 0))
                
                # Dial circle area
                dial_rect = pygame.Rect(cx - radius - 2, cy - radius - 2, 
                                       radius * 2 + 4, radius * 2 + 4)
                
                # Add label area below (roughly 60px tall, 80px wide centered on dial)
                label_rect = pygame.Rect(cx - 40, cy + radius + 5, 80, 60)
                
                # Apply offset_y
                dial_rect.y += offset_y
                label_rect.y += offset_y
                
                # Return union of dial + label WITHOUT redrawing widget background
                dirty_rect = dial_rect.union(label_rect)
                return dirty_rect
            except Exception as e:
                showlog.warn(f"[DrumboWidget] Failed to calculate dial dirty rect: {e}")
                # Fall through to full redraw
        
        # Full widget redraw (instrument change, bank change, initial draw, etc.)
        showlog.debug(f"[DrumboWidget] draw() performing FULL widget redraw")
        
        # Apply offset
        draw_rect = self.rect.copy()
        draw_rect.y += offset_y
        
        instrument_lower = (self.current_instrument or "").strip().lower()
        if instrument_lower == "kick":
            self._draw_kick_page(surface, draw_rect)
        else:
            self._draw_snare_page(surface, draw_rect)

        # Draw label text below widget (same style as dial labels)
        # Position: 10px below widget bottom, left-aligned with widget left edge
        label_text = "DRUM MACHINE - 16 MIC ARTICULATION SYSTEM"
        label_surf = self.label_font.render(label_text, True, self.text_color)
        instrument_text = self.current_instrument.upper()

        rr_value = None
        rr_total = None
        if self._module is not None:
            try:
                rr_value = getattr(self._module, "round_robin_index", None)
                rr_total = getattr(self._module, "round_robin_cycle_size", None)
            except Exception:
                rr_value = None
                rr_total = None

        if rr_value is None or not rr_total:
            instrument_display = f"{instrument_text}: —"
        else:
            try:
                instrument_display = f"{instrument_text}: {int(rr_value)}/{int(rr_total)}"
            except (TypeError, ValueError):
                instrument_display = f"{instrument_text}: {rr_value}/{rr_total}"

        instrument_surf = self.label_font.render(instrument_display, True, self.text_color)
        brackets_text = "MIDI [   ]"
        brackets_surf = self.label_font.render(brackets_text, True, self.text_color)

        label_x = draw_rect.left
        label_y = draw_rect.bottom + 10  # 10px below widget (same as dial label spacing)
        instrument_gap = 24
        instrument_x = label_x + label_surf.get_width() + instrument_gap
        midi_x = draw_rect.right - brackets_surf.get_width()
        midi_y = label_y

        text_right = max(
            label_x + label_surf.get_width(),
            instrument_x + instrument_surf.get_width(),
            midi_x + brackets_surf.get_width(),
        )
        text_height = max(
            label_surf.get_height(),
            instrument_surf.get_height(),
            brackets_surf.get_height(),
        )

        text_bg_rect = pygame.Rect(label_x, label_y, text_right - label_x, text_height)
        pygame.draw.rect(surface, (0, 0, 0), text_bg_rect)

        surface.blit(label_surf, (label_x, label_y))
        surface.blit(instrument_surf, (instrument_x, label_y))
        surface.blit(brackets_surf, (midi_x, midi_y))

        current_time = time.time()
        time_since_note = current_time - self.midi_note_time
        midi_active = time_since_note < self.midi_flash_duration

        if midi_active:
            star_font_size = cfg.DIAL_FONT_SIZE * 2
            star_font = pygame.font.Font(font_helper.main_font("Bold"), star_font_size)
            star_surf = star_font.render("*", True, self.text_color)

            bracket_open_width = self.label_font.render("MIDI [", True, self.text_color).get_width()
            bracket_space_width = self.label_font.render("   ", True, self.text_color).get_width()

            star_x = midi_x + bracket_open_width + (bracket_space_width - star_surf.get_width()) // 2
            star_y = midi_y + (brackets_surf.get_height() - star_surf.get_height()) // 2 + 9

            surface.blit(star_surf, (star_x, star_y))
            self.mark_dirty()

        if not midi_active and self._midi_settle_pending:
            self.mark_dirty()
            self._midi_settle_pending = False

        full_rect = draw_rect.copy()
        label_rect = pygame.Rect(label_x, label_y, label_surf.get_width(), label_surf.get_height())
        instrument_rect = pygame.Rect(
            instrument_x,
            label_y,
            instrument_surf.get_width(),
            instrument_surf.get_height(),
        )
        midi_rect = pygame.Rect(midi_x, midi_y, brackets_surf.get_width(), brackets_surf.get_height())
        full_rect = full_rect.union(label_rect)
        full_rect = full_rect.union(instrument_rect)
        full_rect = full_rect.union(midi_rect)

        self.clear_dirty()
        return full_rect

    def _draw_snare_page(self, surface: pygame.Surface, rect: pygame.Rect):
        """Render the snare background layer."""
        pygame.draw.rect(surface, self.bg_color, rect, border_radius=20)
        pygame.draw.rect(surface, self.border_color, rect, 2, border_radius=20)
        self.current_page_rect = rect.copy()

    def _draw_kick_page(self, surface: pygame.Surface, rect: pygame.Rect):
        """Render the kick background layer."""
        pygame.draw.rect(surface, self.kick_blank_bg_color, rect, border_radius=20)
        pygame.draw.rect(surface, self.kick_blank_border_color, rect, 2, border_radius=20)
        self.current_page_rect = rect.copy()
    
    def handle_event(self, event) -> bool:
        """Handle mouse events - minimal for now."""
        if event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = event.pos
            
            # Check if widget was clicked
            if self.rect.collidepoint(mouse_pos):
                showlog.info(f"[DrumboMainWidget] Widget clicked at {mouse_pos}")
                self.mark_dirty()
                return True
        
        return False
    
    def handle_button(self, btn_id: int):
        """Handle button presses forwarded from module."""
        pass
    
    def set_instrument(self, instrument: str):
        """Change current instrument (snare or kick)."""
        self.current_instrument = instrument
        showlog.info(f"[DrumboMainWidget] Instrument changed to {instrument}")
        self.mark_dirty()
    
    def on_midi_note(self, note: int, velocity: int):
        """
        Handle incoming MIDI note (not CC).
        
        Args:
            note: MIDI note number (0-127)
            velocity: MIDI velocity (0-127)
        """
        if velocity > 0:  # Note on
            self.midi_note_detected = True
            self.midi_note_time = time.time()
            self._midi_settle_pending = True
            self.mark_dirty()
            showlog.info(f"[DrumboMainWidget] MIDI note detected: note={note}, velocity={velocity}")
    
    def get_state(self) -> Dict[str, Any]:
        """Get widget state for preset saving."""
        return {
            "current_instrument": self.current_instrument,
        }
    
    def set_state(self, state: Dict[str, Any]):
        """Restore widget state from preset."""
        self.current_instrument = state.get("current_instrument", "snare")
        self.mark_dirty()
    
    def mark_dirty(self, dial=None):
        """Mark widget as needing redraw. If dial provided, track it for minimal dirty rect."""
        # import traceback
        # stack = ''.join(traceback.format_stack()[-3:-1])  # Get caller info
        # showlog.verbose(f"[DrumboWidget] mark_dirty() called from:\n{stack}")
        
        self._dirty = True
        if dial is not None:
            self._dirty_dial = dial
        else:
            self._dirty_dial = None
        if self.msg_queue:
            try:
                self.msg_queue.put(("burst", 0.5))
            except:
                pass
    
    def is_dirty(self) -> bool:
        """Check if widget needs redraw (includes MIDI flash animation)."""
        # Check if we're in the MIDI flash duration
        if self.midi_note_detected:
            current_time = time.time()
            time_since_note = current_time - self.midi_note_time
            if time_since_note < self.midi_flash_duration:
                return True  # Keep redrawing during flash
            else:
                # Flash ended, clear the flag
                self.midi_note_detected = False
                # Leave _midi_settle_pending True so the star gets wiped next frame

        if self._midi_settle_pending:
            return True
        
        result = self._dirty
        if result:
            showlog.debug(f"[DrumboWidget] is_dirty returning True")
        return result
    
    def clear_dirty(self):
        """Clear dirty flag after redraw."""
        self._dirty = False
        self._dirty_dial = None  # Clear the specific dial tracking
    
    def get_dirty_rect(self) -> Optional[pygame.Rect]:
        """Get the rectangle that needs redrawing - just the changed dial if possible."""
        if not self._dirty:
            return None
        
        # If we have a specific dial that changed, return just its area
        if self._dirty_dial is not None:
            try:
                # Get dial bounds (circle + label area)
                dial = self._dirty_dial
                radius = getattr(dial, 'radius', 25)
                cx = int(getattr(dial, 'cx', 0))
                cy = int(getattr(dial, 'cy', 0))
                
                # Dial circle area
                dial_rect = pygame.Rect(cx - radius - 2, cy - radius - 2, 
                                       radius * 2 + 4, radius * 2 + 4)
                
                # Add label area below (roughly 60px tall, 80px wide centered on dial)
                label_rect = pygame.Rect(cx - 40, cy + radius + 5, 80, 60)
                
                # Return union of dial + label
                dirty_rect = dial_rect.union(label_rect)
                showlog.debug(f"[DrumboWidget] Returning minimal dirty rect for dial: {dirty_rect}")
                return dirty_rect
            except Exception as e:
                showlog.warn(f"[DrumboWidget] Failed to calculate dial dirty rect: {e}")
        
        # Fallback: return full widget rect
        showlog.debug(f"[DrumboWidget] Returning full widget rect")
        return self.rect
