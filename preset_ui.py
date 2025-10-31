# preset_ui.py
"""
UI overlay for saving presets with text input field.
Displays a modal-style overlay with text input and save/cancel buttons.
"""

import pygame
import config as cfg
from helper import hex_to_rgb
import showlog


class PresetSaveUI:
    """
    Modal overlay for saving a preset with a text input field.
    """
    
    def __init__(self, screen_size):
        """
        Initialize the preset save UI.
        
        Args:
            screen_size: Tuple of (width, height) for the screen
        """
        self.screen_width, self.screen_height = screen_size
        self.active = False
        self.text = ""
        self.cursor_visible = True
        self.cursor_timer = 0
        self.cursor_blink_rate = 500  # milliseconds
        
        # UI dimensions
        self.overlay_width = int(self.screen_width * 0.8)
        self.overlay_height = 200
        self.overlay_x = (self.screen_width - self.overlay_width) // 2
        self.overlay_y = (self.screen_height - self.overlay_height) // 2
        
        # Colors
        self.bg_color = (26, 26, 34, 240)  # Semi-transparent dark background
        self.panel_color = (48, 48, 64)
        self.border_color = (100, 100, 120)
        self.text_color = (255, 255, 255)
        self.input_bg = (32, 32, 40)
        self.button_color = (67, 101, 142)
        self.button_hover = (90, 120, 170)
        self.button_cancel = (120, 40, 40)
        
        # Fonts
        try:
            self.title_font = pygame.font.SysFont("arial", 24, bold=True)
            self.input_font = pygame.font.SysFont("arial", 20)
            self.button_font = pygame.font.SysFont("arial", 18, bold=True)
        except:
            self.title_font = pygame.font.Font(None, 24)
            self.input_font = pygame.font.Font(None, 20)
            self.button_font = pygame.font.Font(None, 18)
        
        # Button rectangles
        self.save_button = None
        self.cancel_button = None
        self.input_rect = None
        
        # Callback
        self.on_save = None  # Callback function when user saves
        self.on_cancel = None  # Callback function when user cancels
    
    def show(self, on_save_callback=None, on_cancel_callback=None, default_text=""):
        """
        Show the preset save UI overlay.
        
        Args:
            on_save_callback: Function to call with preset name when saved
            on_cancel_callback: Function to call when cancelled
            default_text: Default text in the input field
        """
        self.active = True
        self.text = default_text
        self.on_save = on_save_callback
        self.on_cancel = on_cancel_callback
        self.cursor_visible = True
        self.cursor_timer = pygame.time.get_ticks()
        
        # Enable remote keyboard input (send CC 119 = 127)
        try:
            import midiserver
            midiserver.send_cc_raw(119, 127)
            showlog.debug("[PresetSaveUI] Sent CC 119 = 127 (enable keyboard)")
        except Exception as e:
            showlog.warn(f"[PresetSaveUI] Failed to enable keyboard: {e}")
        
        showlog.debug("[PresetSaveUI] Overlay shown")
    
    def hide(self):
        """Hide the preset save UI overlay."""
        self.active = False
        self.text = ""
        
        # Disable remote keyboard input (send CC 119 = 0)
        try:
            import midiserver
            midiserver.send_cc_raw(119, 0)
            showlog.debug("[PresetSaveUI] Sent CC 119 = 0 (disable keyboard)")
        except Exception as e:
            showlog.warn(f"[PresetSaveUI] Failed to disable keyboard: {e}")
        
        showlog.debug("[PresetSaveUI] Overlay hidden")
    
    def handle_remote_input(self, data):
        """
        Handle remote keyboard input from the remote_typing_server.
        
        Args:
            data: Character or special key from remote keyboard
        """
        if not self.active:
            return
        
        # Backspace
        if data == "\b":
            if len(self.text) > 0:
                self.text = self.text[:-1]
                self.cursor_visible = True
                self.cursor_timer = pygame.time.get_ticks()
        
        # Enter key - save
        elif data == "\n":
            if self.text.strip():
                if self.on_save:
                    self.on_save(self.text.strip())
                self.hide()
        
        # Escape key - cancel
        elif data == "\x1b":  # ESC character
            if self.on_cancel:
                self.on_cancel()
            self.hide()
        
        # Normal typing
        elif len(data) == 1 and data.isprintable():
            # Filter to alphanumeric, space, underscore, hyphen
            if data.isalnum() or data in (' ', '_', '-'):
                if len(self.text) < 32:  # Max 32 characters
                    self.text += data
                    self.cursor_visible = True
                    self.cursor_timer = pygame.time.get_ticks()
    
    def handle_event(self, event):
        """
        Handle input events for the overlay.
        
        Args:
            event: Pygame event
            
        Returns:
            True if event was handled, False otherwise
        """
        if not self.active:
            return False
        
        if event.type == pygame.MOUSEBUTTONDOWN and hasattr(event, "pos"):
            x, y = event.pos
            
            # Check save button
            if self.save_button and self.save_button.collidepoint(x, y):
                if self.text.strip():  # Only save if text is not empty
                    if self.on_save:
                        self.on_save(self.text.strip())
                    self.hide()
                return True
            
            # Check cancel button
            if self.cancel_button and self.cancel_button.collidepoint(x, y):
                if self.on_cancel:
                    self.on_cancel()
                self.hide()
                return True
            
            # Check if clicking inside input field (for future cursor positioning)
            if self.input_rect and self.input_rect.collidepoint(x, y):
                # Input field is active - could add cursor positioning here
                return True
            
            # Click outside overlay - treat as cancel
            overlay_rect = pygame.Rect(self.overlay_x, self.overlay_y, 
                                       self.overlay_width, self.overlay_height)
            if not overlay_rect.collidepoint(x, y):
                if self.on_cancel:
                    self.on_cancel()
                self.hide()
                return True
        
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                # Enter key - save
                if self.text.strip():
                    if self.on_save:
                        self.on_save(self.text.strip())
                    self.hide()
                return True
            
            elif event.key == pygame.K_ESCAPE:
                # Escape key - cancel
                if self.on_cancel:
                    self.on_cancel()
                self.hide()
                return True
            
            elif event.key == pygame.K_BACKSPACE:
                # Backspace - delete character
                if len(self.text) > 0:
                    self.text = self.text[:-1]
                    self.cursor_visible = True
                    self.cursor_timer = pygame.time.get_ticks()
                return True
            
            elif hasattr(event, 'unicode'):
                # Regular character input
                char = event.unicode
                # Filter to alphanumeric, space, underscore, hyphen
                if char and (char.isalnum() or char in (' ', '_', '-')):
                    if len(self.text) < 32:  # Max 32 characters
                        self.text += char
                        self.cursor_visible = True
                        self.cursor_timer = pygame.time.get_ticks()
                return True
        
        return True  # Block all events when overlay is active
    
    def update(self):
        """Update cursor blink animation."""
        if not self.active:
            return
        
        now = pygame.time.get_ticks()
        if now - self.cursor_timer > self.cursor_blink_rate:
            self.cursor_visible = not self.cursor_visible
            self.cursor_timer = now
    
    def draw(self, screen):
        """
        Draw the preset save UI overlay.
        
        Args:
            screen: Pygame surface to draw on
        """
        if not self.active:
            return
        
        # Draw semi-transparent background
        overlay_surf = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
        overlay_surf.fill((0, 0, 0, 180))
        screen.blit(overlay_surf, (0, 0))
        
        # Draw main panel
        panel_rect = pygame.Rect(self.overlay_x, self.overlay_y, 
                                 self.overlay_width, self.overlay_height)
        pygame.draw.rect(screen, self.panel_color, panel_rect, border_radius=12)
        pygame.draw.rect(screen, self.border_color, panel_rect, width=2, border_radius=12)
        
        # Title
        title = self.title_font.render("Save Preset", True, self.text_color)
        title_rect = title.get_rect(centerx=panel_rect.centerx, 
                                    top=panel_rect.top + 20)
        screen.blit(title, title_rect)
        
        # Input field
        input_y = panel_rect.top + 70
        input_height = 40
        input_padding = 20
        self.input_rect = pygame.Rect(self.overlay_x + input_padding, input_y,
                                      self.overlay_width - (input_padding * 2), input_height)
        
        pygame.draw.rect(screen, self.input_bg, self.input_rect, border_radius=6)
        pygame.draw.rect(screen, self.border_color, self.input_rect, width=2, border_radius=6)
        
        # Draw text
        if self.text:
            text_surf = self.input_font.render(self.text, True, self.text_color)
            text_rect = text_surf.get_rect(left=self.input_rect.left + 10,
                                          centery=self.input_rect.centery)
            
            # Clip text if too long
            old_clip = screen.get_clip()
            screen.set_clip(self.input_rect.inflate(-4, -4))
            screen.blit(text_surf, text_rect)
            screen.set_clip(old_clip)
            
            # Draw cursor
            if self.cursor_visible:
                cursor_x = text_rect.right + 2
                cursor_y1 = self.input_rect.centery - 12
                cursor_y2 = self.input_rect.centery + 12
                pygame.draw.line(screen, self.text_color, 
                               (cursor_x, cursor_y1), (cursor_x, cursor_y2), 2)
        else:
            # Placeholder text
            placeholder = self.input_font.render("Enter preset name...", True, (128, 128, 128))
            placeholder_rect = placeholder.get_rect(left=self.input_rect.left + 10,
                                                   centery=self.input_rect.centery)
            screen.blit(placeholder, placeholder_rect)
            
            # Draw cursor at start if blinking
            if self.cursor_visible:
                cursor_x = self.input_rect.left + 10
                cursor_y1 = self.input_rect.centery - 12
                cursor_y2 = self.input_rect.centery + 12
                pygame.draw.line(screen, self.text_color,
                               (cursor_x, cursor_y1), (cursor_x, cursor_y2), 2)
        
        # Buttons
        button_y = panel_rect.bottom - 60
        button_width = 100
        button_height = 36
        button_spacing = 20
        
        # Cancel button
        cancel_x = panel_rect.centerx - button_width - button_spacing // 2
        self.cancel_button = pygame.Rect(cancel_x, button_y, button_width, button_height)
        pygame.draw.rect(screen, self.button_cancel, self.cancel_button, border_radius=8)
        pygame.draw.rect(screen, self.border_color, self.cancel_button, width=2, border_radius=8)
        
        cancel_text = self.button_font.render("Cancel", True, self.text_color)
        cancel_text_rect = cancel_text.get_rect(center=self.cancel_button.center)
        screen.blit(cancel_text, cancel_text_rect)
        
        # Save button
        save_x = panel_rect.centerx + button_spacing // 2
        self.save_button = pygame.Rect(save_x, button_y, button_width, button_height)
        
        # Disable save button if text is empty
        btn_color = self.button_color if self.text.strip() else (60, 60, 70)
        pygame.draw.rect(screen, btn_color, self.save_button, border_radius=8)
        pygame.draw.rect(screen, self.border_color, self.save_button, width=2, border_radius=8)
        
        save_text = self.button_font.render("Save", True, self.text_color)
        save_text_rect = save_text.get_rect(center=self.save_button.center)
        screen.blit(save_text, save_text_rect)
