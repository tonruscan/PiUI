# /assets/fader.py
import pygame
import config as cfg
from helper import hex_to_rgb, render_text_with_spacing
import helper
import showlog
import dialhandlers


class Fader:
    """
    Simple vertical slider with optional mute button.
    Range: 0–99 (matches Quadraverb mixer).
    All dimensions, colors, and fonts are loaded from cfg.MIXER_* (with fallbacks).
    """

    def __init__(self, x, y, height=None, width=None, label="FADER", initial=50, on_change=None):
        self.device_name = getattr(dialhandlers, "current_device_name", None)


        # --- base geometry (keep legacy args; fall back to config) ---
        self.x = int(x)
        self.y = int(y)
        self.height = int(height if height is not None else getattr(cfg, "MIXER_HEIGHT", 200))
        self.width  = int(width  if width  is not None else getattr(cfg, "MIXER_WIDTH", 24))
        self.label = label
        self.value = int(initial if initial is not None else 50)
        self.on_change = on_change

        # --- theme-aware colors ---
        dn = self.device_name  # shorthand for readability
        self.track_color     = helper.theme_rgb(dn, "MIXER_TRACK_COLOR", "#1A1A1A")
        self.knob_color      = helper.theme_rgb(dn, "MIXER_KNOB_COLOR", "#FF8000")
        self.mute_color_off  = helper.theme_rgb(dn, "MIXER_MUTE_COLOR_OFF", "#3C3C3C")
        self.mute_color_on   = helper.theme_rgb(dn, "MIXER_MUTE_COLOR_ON", "#FF3232")
        self.label_color     = helper.theme_rgb(dn, "MIXER_LABEL_COLOR", "#C8C8C8")
        self.value_color     = helper.theme_rgb(dn, "MIXER_VALUE_COLOR", "#FFFFFF")


        # --- mute state ---
        self.is_muted = False
        self._last_value_before_mute = self.value

        # --- geometry rects ---
        mute_w = int(getattr(cfg, "MIXER_MUTE_WIDTH", self.width + 12))
        mute_h = int(getattr(cfg, "MIXER_MUTE_HEIGHT", 24))
        mute_offset = int(getattr(cfg, "MIXER_MUTE_OFFSET_Y", 18))
        self.rect = pygame.Rect(self.x, self.y, self.width, self.height)
        self.mute_rect = pygame.Rect(
            self.x - (mute_w - self.width) // 2,
            self.y + self.height + mute_offset,
            mute_w,
            mute_h
        )

        # --- fonts (your requested syntax) ---
        # base size & scales (fallback to TYPE_FONT_SCALE if MIXER_* not provided)
        base_size   = int(getattr(cfg, "DIAL_FONT_SIZE", 20))
        label_scale = float(getattr(cfg, "MIXER_LABEL_FONT_SCALE",
                              getattr(cfg, "TYPE_FONT_SCALE", 1.0)))
        value_scale = float(getattr(cfg, "MIXER_VALUE_FONT_SCALE",
                              getattr(cfg, "TYPE_FONT_SCALE", 1.0)))
        mute_scale  = float(getattr(cfg, "MIXER_MUTE_FONT_SCALE",
                              getattr(cfg, "TYPE_FONT_SCALE", 1.0)))

        font_path = cfg.font_helper.main_font("Regular")  # ← EXACTLY like your reference
        self.font_label = pygame.font.Font(font_path, int(base_size * label_scale))
        self.font_value = pygame.font.Font(font_path, int(base_size * value_scale))
        self.font_mute  = pygame.font.Font(font_path, int(base_size * mute_scale))

        # --- range (0–99) & style ---
        self.range = int(getattr(cfg, "MIXER_VALUE_RANGE", 99))
        self._corner = int(getattr(cfg, "MIXER_CORNER_RADIUS", 6))
        self._label_offset_y = int(getattr(cfg, "MIXER_LABEL_OFFSET_Y", 20))
        self._value_offset_y = int(getattr(cfg, "MIXER_VALUE_OFFSET_Y", 5))
        self._label_case = str(getattr(cfg, "MIXER_LABEL_CASE", "upper")).lower()

    # -------------------------------------------------
    # Conversion helpers
    # -------------------------------------------------
    def _val_to_y(self, val):
        """Map 0–range → pixel position within fader track."""
        val = max(0, min(self.range, int(val)))
        return self.y + self.height - int((val / self.range) * self.height)

    def _y_to_val(self, y_pos):
        """Map pixel position back to 0–range."""
        rel = self.y + self.height - int(y_pos)
        rel = max(0, min(self.height, rel))
        return int(round((rel / self.height) * self.range))

    def draw(self, screen):
        """Draw the fader, value, mute, and a full-height background panel with padding."""
        #showlog.log(None, f"[DEBUG FADER] Drawing fader {self.label} at value {self.value} (muted={self.is_muted})")

        # --- pre-render LABEL (with letter spacing helper if configured) ---
        lbl_text = self.label
        if self._label_case == "upper":
            lbl_text = lbl_text.upper()
        elif self._label_case == "title":
            lbl_text = lbl_text.title()

        # Optional letter-spacing for main label
        try:
            from helper import render_text_with_spacing
            label_spacing = int(getattr(cfg, "MIXER_LABEL_SPACING", 0))
            label_surf, label_rect = render_text_with_spacing(lbl_text, self.font_label, self.label_color, spacing=label_spacing)
        except Exception:
            # fallback: simple render
            label_surf = self.font_label.render(lbl_text, True, self.label_color)
            label_rect = label_surf.get_rect()

        label_rect.center = (int(self.x + self.width / 2), int(self.y - self._label_offset_y))

        # --- pre-render VALUE ---
        val_str  = str(self.value).rjust(3)
        val_surf = self.font_value.render(val_str, True, self.value_color)
        val_cx   = int(self.x + self.width / 2 + int(getattr(cfg, "MIXER_VALUE_OFFSET_X", 0)))
        val_cy   = int(self.y + self.height + self._value_offset_y)
        val_rect = val_surf.get_rect(center=(val_cx, val_cy))

        # --- compute full module bounds (label → mute) for panel ---
        cx = self.x + self.width / 2
        pad_y = int(getattr(cfg, "MIXER_PANEL_PADDING_Y", 14))

        panel_width  = int(getattr(cfg, "MIXER_PANEL_WIDTH", 120))  # ← fixed width
        panel_left   = int(cx - (panel_width / 2))
        panel_top    = int(label_rect.top - pad_y)
        panel_height = int(self.mute_rect.bottom - label_rect.top + (2 * pad_y))
        panel_rect   = pygame.Rect(panel_left, panel_top, panel_width, panel_height)


        # --- draw background panel (behind everything) ---
        if bool(getattr(cfg, "MIXER_PANEL_ENABLED", True)):
            panel_color = helper.theme_rgb(self.device_name, "MIXER_PANEL_COLOR", "#0E0E0E")
            panel_radius = int(getattr(cfg, "MIXER_PANEL_RADIUS", 12))
            pygame.draw.rect(screen, panel_color, panel_rect, border_radius=panel_radius)

            ow = int(getattr(cfg, "MIXER_PANEL_OUTLINE_WIDTH", 0))
            if ow > 0:
                oc = helper.theme_rgb(self.device_name, "MIXER_PANEL_OUTLINE_COLOR", "#202020")
                pygame.draw.rect(screen, oc, panel_rect, ow, border_radius=panel_radius)


        # --- track (on top of panel) ---
        pygame.draw.rect(screen, self.track_color, self.rect, border_radius=self._corner)

        # --- knob ---
        knob_y = self._val_to_y(self.value)
        knob_rect = pygame.Rect(self.x - 4, knob_y - 6, self.width + 8, 12)
        pygame.draw.rect(screen, self.knob_color, knob_rect, border_radius=self._corner)

        # --- label (on top) ---
        screen.blit(label_surf, label_rect)

        # --- numeric value (on top) ---
        screen.blit(val_surf, val_rect)

        # --- mute button (on top) ---
        color = self.mute_color_on if self.is_muted else self.mute_color_off
        pygame.draw.rect(screen, color, self.mute_rect, border_radius=self._corner)
        m_txt  = self.font_mute.render("M", True, (255, 255, 255))
        m_rect = m_txt.get_rect(center=self.mute_rect.center)
        screen.blit(m_txt, m_rect)


    # -------------------------------------------------
    # Event handling
    # -------------------------------------------------
    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.mute_rect.collidepoint(event.pos):
                self.toggle_mute()
                return True
            elif self.rect.collidepoint(event.pos):
                self._update_from_mouse(event.pos[1])
                return True

        elif event.type == pygame.MOUSEMOTION and event.buttons[0]:
            if self.rect.collidepoint(event.pos):
                self._update_from_mouse(event.pos[1])
                return True

        return False

    def update_from_mouse(self, pos):
        """Update fader value based on current mouse/touch Y position and repaint."""
        _, my = pos
        top = self.y
        bottom = self.y + self.height
        my = max(top, min(bottom, my))

        rel = (bottom - my) / self.height
        new_val = int(round(rel * self.range))

        if new_val != self.value:
            self.value = new_val
            if self.on_change:
                self.on_change(new_val)
            self.draw(pygame.display.get_surface())
            # pygame.display.update(self.rect)

    # -------------------------------------------------
    # State + Callbacks
    # -------------------------------------------------
    def _update_from_mouse(self, y_pos):
        if self.is_muted:
            return
        new_val = self._y_to_val(y_pos)
        if new_val != self.value:
            self.value = new_val
            if callable(self.on_change):
                self.on_change(self.value)

    def toggle_mute(self):
        if self.is_muted:
            self.is_muted = False
            self.value = self._last_value_before_mute
        else:
            self._last_value_before_mute = self.value
            self.value = 0
            self.is_muted = True
        if callable(self.on_change):
            self.on_change(self.value)
