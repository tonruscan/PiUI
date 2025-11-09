# /build/assets/dial.py
import math
import helper, config as cfg


# ---------------------------------------------------------------------
# Dial class
# ---------------------------------------------------------------------
class Dial:
    def __init__(self, cx, cy, radius=None, arc_start=240, arc_end=660):
        if radius is None:
            radius = cfg.DIAL_SIZE

        self.cx, self.cy = cx, cy
        self.radius = radius
        self.arc_start = arc_start
        self.arc_end = arc_end
        self.arc_span = arc_end - arc_start

        # State
        self.angle = arc_start
        self.value = 0
        self.dragging = False
        self.sticky_max = False
        self.sticky_min = False
        self.t = 0.0
        self.EDGE_EPS = 0.02
        self.range = [0, 127]
        
        # Graphics optimization flags (Phase 1)
        self.is_empty = False  # True if dial label is "EMPTY"
        self.is_muted = False  # True if page is muted (set externally)
        self.dirty = False     # True if dial needs redraw (dirty rect)
        self.visual_mode = "default"  # Rendering mode: default|hidden|custom

    # --------------------------------------------------------------
    # Utility methods
    # --------------------------------------------------------------
    def set_visual_mode(self, mode: str):
        """Control whether the stock dial renderer should draw this dial."""
        if mode is None:
            normalized = "default"
        else:
            normalized = str(mode).strip().lower()
            if normalized in ("default", "visible", ""):
                normalized = "default"
            elif normalized == "hidden":
                pass
            else:
                raise ValueError(f"Unsupported dial visual_mode '{mode}'")

        if getattr(self, "visual_mode", "default") != normalized:
            self.visual_mode = normalized
            if hasattr(self, "dirty"):
                self.dirty = True

    def on_mouse_up(self):
        self.sticky_max = False
        self.sticky_min = False

    def _circular_clamp_and_progress(self, raw_deg, start_deg, end_deg, use_long_arc=False):
        raw = raw_deg % 360
        short_len = (end_deg - start_deg) % 360

        if not use_long_arc:
            prog = (raw - start_deg) % 360
            if prog > short_len:
                prog = short_len if prog - short_len < short_len / 2 else 0
            clamped = (start_deg + prog) % 360
            t = prog / short_len if short_len else 0.0
        else:
            long_len = (360 - short_len) % 360
            prog_long = (raw - end_deg) % 360
            if prog_long > long_len:
                prog_short = prog_long - long_len
                prog_long = 0.0 if prog_short <= short_len / 2 else long_len
            clamped = (end_deg + prog_long) % 360
            t = prog_long / long_len if long_len else 0.0
        return clamped, t

    def _snap_cc(self, raw_cc: int) -> int:
        cc = max(0, min(127, int(raw_cc)))
        opts = getattr(self, "options", None)
        if opts:
            steps = len(opts)
            if steps > 1:
                idx = round((cc / 127) * (steps - 1))
                return int(round((idx / (steps - 1)) * 127))
            return 0

        r = getattr(self, "range", [0, 127])
        if isinstance(r, (list, tuple)) and len(r) == 2:
            try:
                steps = int(r[1] - r[0] + 1)
            except Exception:
                steps = 128
            if 1 < steps < 127:
                idx = round((cc / 127) * (steps - 1))
                return int(round((idx / (steps - 1)) * 127))
        return cc

    # --------------------------------------------------------------
    # Interaction + rendering
    # --------------------------------------------------------------
    def update_from_mouse(self, mx, my):
        dx = mx - self.cx
        dy = self.cy - my
        raw = (math.degrees(math.atan2(dy, dx))) % 360

        start, end = 240, 300
        clamped_deg, t_ccw = self._circular_clamp_and_progress(raw, start, end, use_long_arc=True)
        t_new = 1.0 - t_ccw

        # Hysteresis deadzone
        if self.t >= 1.0 - self.EDGE_EPS and t_new >= self.t:
            t_new = 1.0
        elif self.t <= self.EDGE_EPS and t_new <= self.t:
            t_new = 0.0

        raw_cc = int(round(t_new * 127))
        snapped_cc = self._snap_cc(raw_cc)
        self.value = snapped_cc
        self.t = snapped_cc / 127.0

        short_len = (end - start) % 360
        long_len = (360 - short_len) % 360
        self.angle = (end + (1.0 - self.t) * long_len) % 360

    def draw(self, surface):
        """High-quality dial rendered with pygame.gfxdraw (no PNG)."""
        import pygame.gfxdraw

        # --- Panel behind dial ---
        panel_size = self.radius * 2 + 20
        panel_rect = pygame.Rect(0, 0, panel_size, panel_size)
        panel_rect.center = (self.cx, self.cy)
        pygame.draw.rect(
            surface,
            helper.hex_to_rgb(cfg.DIAL_PANEL_COLOR),
            panel_rect,
            border_radius=15
        )

        # --- Dial colors from theme ---
        fill_col    = helper.hex_to_rgb(cfg.DIAL_FILL_COLOR)
        outline_col = helper.hex_to_rgb(cfg.DIAL_OUTLINE_COLOR)
        text_col    = helper.hex_to_rgb(cfg.DIAL_TEXT_COLOR)

        # --- Smooth dial circle ---
        # gfxdraw requires integer positions
        cx = int(round(self.cx))
        cy = int(round(self.cy))
        r  = int(round(self.radius))

        pygame.gfxdraw.filled_circle(surface, cx, cy, r, fill_col)
        pygame.gfxdraw.aacircle(surface, cx, cy, r, outline_col)
        pygame.gfxdraw.aacircle(surface, cx, cy, r + 1, outline_col)


        # --- Pointer line ---
        rad = math.radians(self.angle)
        x0 = self.cx + (self.radius * 0.5) * math.cos(rad)
        y0 = self.cy - (self.radius * 0.5) * math.sin(rad)
        x1 = self.cx + self.radius * math.cos(rad)
        y1 = self.cy - self.radius * math.sin(rad)
# Pointer line (gfxdraw.line + pygame.draw.aaline for smoothness)
        pygame.gfxdraw.line(surface, int(x0), int(y0), int(x1), int(y1), text_col)
        pygame.draw.aaline(surface, text_col, (int(x0), int(y0)), (int(x1), int(y1)))




    def set_value(self, val: int):
        val = max(0, min(127, int(val)))
        snapped = self._snap_cc(val)
        self.value = snapped
        self.t = snapped / 127.0
        start, end = 240, 300
        short_len = (end - start) % 360
        long_len = (360 - short_len) % 360
        self.angle = (end + (1.0 - self.t) * long_len) % 360
