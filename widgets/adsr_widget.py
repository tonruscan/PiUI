# /widgets/adsr_widget.py
# Vibrato Maker "canvas" widget (prototype)
# - Two handles (Dot A = low floor, Dot B = high ceiling + fade-in time)
# - Dotted guides extend slightly beyond the canvas
# - Clean constraints and normalized outputs
# - Decoupled: use on_change callback to integrate with your state/state_manager/MIDI

from __future__ import annotations
import pygame
from typing import Optional, Callable, Dict, Tuple
import pygame.gfxdraw

from widgets.dirty_mixin import DirtyWidgetMixin
# Utility: dashed lines (fast-enough CPU, single pass)
def _draw_dashed_line(surface, color, start_pos, end_pos, dash_len=6, gap_len=6, width=1):
    x1, y1 = start_pos; x2, y2 = end_pos
    dx = x2 - x1; dy = y2 - y1
    dist = max(1, int((dx * dx + dy * dy) ** 0.5))
    ux, uy = dx / dist, dy / dist
    step = dash_len + gap_len
    n = dist // step + 1
    for i in range(int(n)):
        sx = x1 + (i * step) * ux
        sy = y1 + (i * step) * uy
        ex = x1 + (i * step + dash_len) * ux
        ey = y1 + (i * step + dash_len) * uy
        if (ux >= 0 and ex > x2) or (ux < 0 and ex < x2):
            ex, ey = x2, y2
        pygame.draw.line(surface, color, (int(sx), int(sy)), (int(ex), int(ey)), width)

# Define constants for dot size and touch area
DOT_SIZE = 8  # Half the original size
DOT_TOUCH_AREA = DOT_SIZE * 3  # Twice the size for collision

class VibratoField(DirtyWidgetMixin):
    """
    A landscape rectangle with two interactive dots:
      - Dot A (low) on left edge, vertical-only, cannot go above Dot B
      - Dot B (high) moves XY, X = fade-in time, Y = high cutoff, cannot go below A

    Normalized outputs:
      - low_norm  (0..1)  bottom=0, top=1
      - high_norm (0..1)
      - depth_norm = high_norm - low_norm
      - fade_ms   mapped from Dot B's X

    Public API:
      - draw(surface)
      - handle_event(event) -> bool (True if consumed)
      - get_state() -> dict
      - set_from_state(low_norm, high_norm, fade_ms)
    """

    def __init__(
        self,
        rect: pygame.Rect,
        on_change: Optional[Callable[[Dict[str, float]], None]] = None,
        fade_ms_range: Tuple[int, int] = (100, 5000),
        theme: Optional[Dict[str, Tuple[int, int, int]]] = None,
    ):
        super().__init__()
        self.rect = pygame.Rect(rect)
        self.on_change = on_change
        self.fade_min, self.fade_max = fade_ms_range

        # Theme (simple, you can swap colors later)

        th = theme or {}

        def _rgb3(c):
            return tuple(c[:3]) if isinstance(c, (list, tuple)) else c

        self.col_bg   = _rgb3(th.get("bg", (255, 255, 255)))
        self.col_fill = _rgb3(th.get("fill", (70, 90, 140)))

        # Robust outline color (accepts tuple/list or '#RRGGBB')
        outline_src = th.get("outline", (255, 255, 255))
        if isinstance(outline_src, str) and outline_src.startswith("#"):
            try:
                from helper import hex_to_rgb
                outline_src = hex_to_rgb(outline_src)
            except Exception:
                outline_src = (255, 255, 255)
        self.col_outline = tuple(outline_src[:3])

        self.col_guides  = (255, 255, 255)
        self.border_radius = 12



        # Minimum vertical gap in pixels between A and B (visual clarity)
        self.min_gap_px = 12

        # Initial dot positions (relative)
        # Using your defaults: A ≈ 25% up from bottom; B ≈ 25% from left, 25% down from top
        self._low_y = self._lerp(self.rect.bottom, self.rect.top, 0.25)  # 25% up => closer to bottom
        self._high_y = self._lerp(self.rect.top, self.rect.bottom, 0.25) # 25% down from top
        self._high_x = self.rect.left + int(0.25 * self.rect.width)

        # Ensure constraints on init
        self._apply_constraints(emit=False)

        # Drag state
        self._drag_mode = None  # "low" or "high"
        self._mouse_off = (0, 0)

        # Precompute dot radius based on rect (half the size)
        self.dot_r = max(3, min(self.rect.width, self.rect.height) // 44)
        self._guide_overshoot = 8
        self._crosshair_size = 5
        self.set_dirty_padding(
            max(DOT_SIZE, self._guide_overshoot),
            max(DOT_SIZE, self._guide_overshoot, self._crosshair_size)
        )
        self._prev_dirty_raw = None
        self._background_cache = None
        self._background_cache_rect = None

    # ----------------------------- math helpers -----------------------------
    @staticmethod
    def _lerp(a, b, t): return int(a + (b - a) * float(t))
    @staticmethod
    def _clamp(v, lo, hi): return hi if v > hi else lo if v < lo else v

    def _y_to_norm(self, y: int) -> float:
        # bottom → 0.0, top → 1.0
        y = self._clamp(y, self.rect.top, self.rect.bottom)
        return (self.rect.bottom - y) / max(1.0, self.rect.height)

    def _norm_to_y(self, n: float) -> int:
        n = self._clamp(n, 0.0, 1.0)
        return self._lerp(self.rect.bottom, self.rect.top, n)

    def _x_to_fade_ms(self, x: int) -> int:
        x = self._clamp(x, self.rect.left, self.rect.right)
        t = (x - self.rect.left) / max(1.0, self.rect.width)
        return int(self.fade_min + (self.fade_max - self.fade_min) * t)

    def _fade_ms_to_x(self, ms: int) -> int:
        ms = self._clamp(ms, self.fade_min, self.fade_max)
        t = (ms - self.fade_min) / max(1.0, (self.fade_max - self.fade_min))
        return self.rect.left + int(self.rect.width * t)

    # ----------------------------- public state -----------------------------
    def get_state(self) -> Dict[str, float]:
        low = self._y_to_norm(self._low_y)
        high = self._y_to_norm(self._high_y)
        fade = self._x_to_fade_ms(self._high_x)
        return {
            "low_norm": round(low, 4),
            "high_norm": round(high, 4),
            "depth_norm": round(max(0.0, high - low), 4),
            "fade_ms": fade
        }

    def set_from_state(self, low_norm: float, high_norm: float, fade_ms: int, emit=True):
        new_low = self._norm_to_y(low_norm)
        new_high = self._norm_to_y(high_norm)
        new_x = self._fade_ms_to_x(fade_ms)

        if new_low != self._low_y or new_high != self._high_y or new_x != self._high_x:
            self.mark_dirty()

        self._low_y = new_low
        self._high_y = new_high
        self._high_x = new_x
        self._apply_constraints(emit=emit)

    # ----------------------------- constraints ------------------------------
    def _apply_constraints(self, emit=True):
        # lock A.x to left wall
        # vertical bounds inside the canvas
        top = self.rect.top
        bot = self.rect.bottom

        # Store old values to detect changes
        old_low_y = self._low_y
        old_high_y = self._high_y
        old_high_x = self._high_x

        # Clamp Ys inside rect
        self._low_y = self._clamp(self._low_y, top, bot)
        self._high_y = self._clamp(self._high_y, top, bot)

        # Enforce ordering: low must be below high (y greater is lower on screen)
        # We want: self._low_y > self._high_y by at least min_gap_px
        if self._low_y <= self._high_y + self.min_gap_px:
            self._low_y = min(bot, self._high_y + self.min_gap_px)

        # Now ensure high not below low
        if self._high_y >= self._low_y - self.min_gap_px:
            self._high_y = max(top, self._low_y - self.min_gap_px)

        # Clamp high.x within rect
        self._high_x = self._clamp(self._high_x, self.rect.left, self.rect.right)

        # Mark dirty if values changed
        if old_low_y != self._low_y or old_high_y != self._high_y or old_high_x != self._high_x:
            self.mark_dirty()

        if emit and self.on_change:
            self.on_change(self.get_state())

    # ----------------------------- drawing ----------------------------------
    def draw(self, surface: pygame.Surface, device_name=None, offset_y=0):
        # Apply offset_y to all drawing operations
        offset_rect = self.rect.copy()
        offset_rect.y += offset_y
        raw_dirty = self.get_dirty_rect(offset_y) or offset_rect.copy()
        dirty_rect = raw_dirty.copy()
        if self._prev_dirty_raw:
            dirty_rect = dirty_rect.union(self._prev_dirty_raw)

        from helper import theme_rgb
        if device_name is None:
            import dialhandlers
            device_name = getattr(dialhandlers, "current_device_name", None)

        cache_invalid = (
            self._background_cache is None
            or self._background_cache_rect is None
            or self._background_cache_rect.topleft != dirty_rect.topleft
            or self._background_cache_rect.size != dirty_rect.size
        )

        if cache_invalid:
            try:
                self._background_cache = surface.subsurface(dirty_rect).copy()
                self._background_cache_rect = dirty_rect.copy()
            except ValueError:
                self._background_cache = None
                self._background_cache_rect = None

        if self._background_cache is not None and self._background_cache_rect is not None:
            surface.blit(self._background_cache, self._background_cache_rect)
        else:
            # Fallback to theme fill if we couldn't grab the background snapshot
            fallback_bg = theme_rgb(device_name, "BACKGROUND_COLOR")
            if isinstance(fallback_bg, (tuple, list)) and len(fallback_bg) >= 3:
                fallback_bg = tuple(int(c) for c in fallback_bg[:3])
            else:
                fallback_bg = (0, 0, 0)
            surface.fill(fallback_bg, dirty_rect)

        # Use the same background color as dial panels

        bg_color_raw = theme_rgb(device_name, "BACKGROUND_COLOR")
        if isinstance(bg_color_raw, (tuple, list)) and len(bg_color_raw) >= 3:
            theme_bg = tuple(int(c) for c in bg_color_raw[:3])
        else:
            theme_bg = (0, 0, 0)
        bg_color = theme_bg

        dial_bg_raw = theme_rgb(device_name, "DIAL_PANEL_COLOR")
        if isinstance(dial_bg_raw, (tuple, list)) and len(dial_bg_raw) >= 3:
            dial_bg_color = tuple(int(c) for c in dial_bg_raw[:3])
        else:
            dial_bg_color = bg_color

        pygame.draw.rect(surface, dial_bg_color, offset_rect, border_radius=self.border_radius)

        # Selection band (SOLID — no alpha)
        band_top = int(min(self._low_y, self._high_y)) + offset_y
        band_bot = int(max(self._low_y, self._high_y)) + offset_y
        if band_bot - band_top > 2:
            fill_rect = pygame.Rect(offset_rect.left + 2, band_top, offset_rect.width - 4, band_bot - band_top)
            fill = self.col_fill[:3] if isinstance(self.col_fill, (list, tuple)) else self.col_fill
            pygame.draw.rect(surface, fill, fill_rect, 0)

        overshoot = self._guide_overshoot
        left_ext = offset_rect.left - overshoot
        right_ext = offset_rect.right + overshoot

        _draw_dashed_line(
            surface,
            self.col_guides,
            (left_ext, self._low_y + offset_y),
            (right_ext, self._low_y + offset_y),
            dash_len=10,
            gap_len=6,
            width=1,
        )

        _draw_dashed_line(
            surface,
            self.col_guides,
            (left_ext, self._high_y + offset_y),
            (right_ext, self._high_y + offset_y),
            dash_len=10,
            gap_len=6,
            width=1,
        )

        _draw_dashed_line(
            surface,
            self.col_guides,
            (self._high_x, offset_rect.top - overshoot),
            (self._high_x, offset_rect.bottom + overshoot),
            dash_len=10,
            gap_len=6,
            width=1,
        )



        # ----------------------------- dots -----------------------------

        cx_lo = int(offset_rect.left)
        cy_lo = int(round(self._low_y)) + offset_y
        cx_hi = int(round(self._high_x))
        cy_hi = int(round(self._high_y)) + offset_y

        outline = self.col_outline[:3] if isinstance(self.col_outline, (list, tuple)) else self.col_outline
        dot_fill = self.col_bg[:3] if isinstance(self.col_bg, (list, tuple)) else self.col_bg

        for (cx, cy) in [(cx_lo, cy_lo), (cx_hi, cy_hi)]:
            # Draw the dot
            pygame.gfxdraw.filled_circle(surface, cx, cy, DOT_SIZE, dot_fill)
            pygame.gfxdraw.aacircle(surface, cx, cy, DOT_SIZE, outline)
            pygame.gfxdraw.aacircle(surface, cx, cy, DOT_SIZE - 1, outline)

            # Debug: Draw the collision area
            #if getattr(self, "debug", False):
            #pygame.draw.circle(surface, (10, 10, 10), (cx, cy), DOT_TOUCH_AREA, 1)

        # Draw a line connecting the two dots
        _draw_dashed_line(surface, (255, 255, 255), (cx_lo, cy_lo), (cx_hi, cy_hi), dash_len=10, gap_len=6, width=1)


        ## here i need a cross hair in the middle of each dot
        crosshair_size = self._crosshair_size
        for (cx, cy) in [(cx_lo, cy_lo), (cx_hi, cy_hi)]:
            pygame.draw.line(surface, (255, 255, 255), (cx - crosshair_size, cy), (cx + crosshair_size, cy), 1)
            pygame.draw.line(surface, (255, 255, 255), (cx, cy - crosshair_size), (cx, cy + crosshair_size), 1)

        self._prev_dirty_raw = raw_dirty.copy()
        return dirty_rect

    # ----------------------------- interaction ------------------------------
    def _hit_dot(self, pos) -> Optional[str]:
        # Circle hit test with expanded collision area
        x, y = pos; r = DOT_TOUCH_AREA + 3
        if (x - self.rect.left) ** 2 + (y - self._low_y) ** 2 <= r * r:
            return "low"
        if (x - self._high_x) ** 2 + (y - self._high_y) ** 2 <= r * r:
            return "high"
        return None

    def handle_event(self, event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and hasattr(event, "pos"):
            hit = self._hit_dot(event.pos)
            if hit:
                self._drag_mode = hit
                if hit == "low":
                    # store vertical offset only
                    self._mouse_off = (0, event.pos[1] - self._low_y)
                else:
                    # high: store both offsets
                    self._mouse_off = (event.pos[0] - self._high_x, event.pos[1] - self._high_y)
                return True

        elif event.type == pygame.MOUSEBUTTONUP:
            if self._drag_mode:
                self._drag_mode = None
                return True

        elif event.type == pygame.MOUSEMOTION and hasattr(event, "pos"):
            if not self._drag_mode:
                return False

            mx, my = event.pos
            if self._drag_mode == "low":
                # lock X; move Y only; clamp inside rect & under high
                new_y = my - self._mouse_off[1]
                old_low = self._low_y
                self._low_y = self._clamp(new_y, self.rect.top, self.rect.bottom)
                if self._low_y != old_low:
                    self.mark_dirty()
                # enforce ordering (below high)
                if self._low_y <= self._high_y + self.min_gap_px:
                    self._low_y = min(self.rect.bottom, self._high_y + self.min_gap_px)
                self._apply_constraints(emit=True)
                return True

            elif self._drag_mode == "high":
                # move both X and Y
                new_x = mx - self._mouse_off[0]
                new_y = my - self._mouse_off[1]
                old_high_x = self._high_x
                old_high_y = self._high_y
                self._high_x = self._clamp(new_x, self.rect.left, self.rect.right)
                self._high_y = self._clamp(new_y, self.rect.top, self.rect.bottom)
                if self._high_x != old_high_x or self._high_y != old_high_y:
                    self.mark_dirty()
                # enforce ordering (above low)
                if self._high_y >= self._low_y - self.min_gap_px:
                    self._high_y = max(self.rect.top, self._low_y - self.min_gap_px)
                self._apply_constraints(emit=True)
                return True

        return False


