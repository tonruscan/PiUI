# widgets/vibrato_maker_widget.py
import pygame
import math

def _dashed_hline(surf, y, x0, x1, dash=8, gap=6, color=(200,200,200), w=2):
    x = int(min(x0, x1))
    x_end = int(max(x0, x1))
    on = True
    while x < x_end:
        seg = min(dash, x_end - x)
        if on:
            pygame.draw.line(surf, color, (x, int(y)), (x + seg, int(y)), w)
        x += seg + gap
        on = not on

def _dashed_vline(surf, x, y0, y1, dash=8, gap=6, color=(200,200,200), w=2):
    y = int(min(y0, y1))
    y_end = int(max(y0, y1))
    on = True
    while y < y_end:
        seg = min(dash, y_end - y)
        if on:
            pygame.draw.line(surf, color, (int(x), y), (int(x), y + seg), w)
        y += seg + gap
        on = not on

class VibratoMakerWidget:
    """
    Interactive 2-dot vibrato field:

    Dot A (low)  : clamped to left wall, vertical only
    Dot B (high) : free within field (x,y), cannot drop below A (keeps A <= B by ceiling logic)

    • Horizontal dashed line through each dot (low/high levels)
    • Vertical dashed line through B (fade-in time)
    • Emits normalized params (0..1) and handy derived numbers
    """
    def __init__(self, rect, theme=None):
        self.rect = pygame.Rect(rect)
        self.theme = theme or {}
        self.dot_r = 10
        self._drag = None

        # defaults (fractions; 0=bottom, 1=top for y)
        self.a_y = 0.25   # A ≈ 25% up from bottom
        self.b_x = 0.25   # B ≈ 25% from left
        self.b_y = 0.75   # B ≈ 25% down from top  → y_frac = 0.75 means high level near top

        # cache last emitted tuple to avoid spamming
        self._last_emit = None

    # ---------- helpers ----------
    def _xy_from_fracs(self, fx, fy, rect=None):
        # fy: 0 bottom → 1 top; convert to screen
        # Use provided rect or default to self.rect
        r = rect if rect is not None else self.rect
        x = r.left + fx * r.width
        y = r.bottom - fy * r.height
        return int(x), int(y)

    def _fracs_from_xy(self, x, y, rect=None):
        # Use provided rect or default to self.rect
        r = rect if rect is not None else self.rect
        fx = (x - r.left) / max(1, r.width)
        fy = (r.bottom - y) / max(1, r.height)
        return max(0, min(1, fx)), max(0, min(1, fy))

    def _clamp_layout(self):
        # B must not be below A: enforce b_y >= a_y
        if self.b_y < self.a_y:
            self.b_y = self.a_y

    # ---------- public API ----------
    def get_params(self):
        """
        Return normalized + derived parameters:
          - low_norm  (0..1) from Dot A (floor)
          - high_norm (0..1) from Dot B (ceiling)
          - fade_frac (0..1) from Dot B X
          - span_norm = (high - low), clamped to >= 0
        """
        low_norm  = self.a_y
        high_norm = self.b_y
        if high_norm < low_norm:
            high_norm = low_norm
        fade_frac = self.b_x
        span_norm = max(0.0, high_norm - low_norm)
        return {
            "low_norm":  low_norm,
            "high_norm": high_norm,
            "fade_frac": fade_frac,
            "span_norm": span_norm,
        }

    def draw(self, screen, offset_y=0):
        # colors (fall back to neutrals if not themed)
        bg   = self.theme.get("background_color", (26, 26, 34))
        box  = self.theme.get("dial_panel_color", (48, 16, 32))
        line = self.theme.get("dial_outline_color", (255, 176, 208))
        dotA = self.theme.get("dial_fill_color", (255, 149, 0))
        dotB = self.theme.get("accent_color", (255, 210, 102))

        # Apply offset_y to the rect for drawing
        offset_rect = self.rect.copy()
        offset_rect.y += offset_y

        # field background
        pygame.draw.rect(screen, box, offset_rect, border_radius=18)
        # pygame.draw.rect(screen, line, offset_rect, width=2, border_radius=18)  # Removed thick border

        # current points (using offset_rect for calculations)
        ax, ay = self._xy_from_fracs(0.0, self.a_y, offset_rect)     # x locked to left wall
        bx, by = self._xy_from_fracs(self.b_x, self.b_y, offset_rect)

        # dashed guides
        _dashed_hline(screen, ay, offset_rect.left+6, offset_rect.right-6, color=(200,200,200))
        _dashed_hline(screen, by, offset_rect.left+6, offset_rect.right-6, color=(220,220,220))
        _dashed_vline(screen, bx, offset_rect.top+6, offset_rect.bottom-6, color=(220,220,220))

        # dots
        pygame.draw.circle(screen, dotA, (offset_rect.left+8, ay), self.dot_r)  # on wall
        pygame.draw.circle(screen, dotB, (bx, by), self.dot_r)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and hasattr(event, "pos"):
            x, y = event.pos
            ax, ay = self._xy_from_fracs(0.0, self.a_y)
            bx, by = self._xy_from_fracs(self.b_x, self.b_y)
            if (x - (self.rect.left+8))**2 + (y - ay)**2 <= (self.dot_r+6)**2:
                self._drag = ("A", 0, y - ay)
                return True
            if (x - bx)**2 + (y - by)**2 <= (self.dot_r+6)**2:
                self._drag = ("B", x - bx, y - by)
                return True

        elif event.type == pygame.MOUSEBUTTONUP:
            if self._drag:
                self._drag = None
                return True

        elif event.type == pygame.MOUSEMOTION and self._drag and hasattr(event, "pos"):
            who, dx, dy = self._drag
            x, y = event.pos

            if who == "A":
                # vertical only on left wall
                _, fy = self._fracs_from_xy(self.rect.left+8, y - dy)
                self.a_y = max(0.0, min(1.0, fy))
            else:
                fx, fy = self._fracs_from_xy(x - dx, y - dy)
                # B free inside rect
                self.b_x = max(0.0, min(1.0, fx))
                self.b_y = max(0.0, min(1.0, fy))

            self._clamp_layout()
            return True

        return False
