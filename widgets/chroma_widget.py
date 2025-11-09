# widgets/chroma_widget.py
import pygame
import math
from typing import Any, Dict, Optional
import showlog


class ChromaWidget:
    """
    Widget B: two special mini dials drawn as circular meters.
    Mirrors the same contract as LumaWidget.
    """
    def __init__(
        self,
        rect: pygame.Rect,
        on_change=None,
        theme: Optional[Dict[str, Any]] = None,
        init_state: Optional[Dict[str, Any]] = None
    ):
        showlog.debug("*[DEF ChromaWidget.__init__ STEP 1] create widget instance")
        self.rect = rect
        self.on_change = on_change
        self.theme = theme or {}
        self._dirty = True

        self.mini_a = 0.5
        self.mini_b = 0.5
        if init_state:
            showlog.debug(f"*[DEF ChromaWidget.__init__ STEP 2] restoring init_state={init_state}")
            self.mini_a = float(init_state.get("mini_a", self.mini_a))
            self.mini_b = float(init_state.get("mini_b", self.mini_b))

        # Geometry
        self._offset_y = 0
        w, h = self.rect.width, self.rect.height
        pad = 16
        diameter = min((w - pad * 3) // 2, h - pad * 2)
        self._dial_a_center = (self.rect.x + pad + diameter // 2, self.rect.centery)
        self._dial_b_center = (self.rect.x + pad * 2 + diameter + diameter // 2, self.rect.centery)
        self._radius = diameter // 2

    # -------- state & dirty ----------
    def get_state(self) -> Dict[str, float]:
        return {"mini_a": self.mini_a, "mini_b": self.mini_b}

    def set_state(self, state: Dict[str, float]):
        showlog.debug(f"*[DEF ChromaWidget.set_state STEP 1] applying state={state}")
        self.mini_a = float(state.get("mini_a", self.mini_a))
        self.mini_b = float(state.get("mini_b", self.mini_b))
        self.mark_dirty()
        self._emit_change()

    def mark_dirty(self): self._dirty = True
    def is_dirty(self) -> bool: return self._dirty
    def clear_dirty(self): self._dirty = False

    # -------- host → widget updates ----------
    def update_value(self, ctrl_id: str, value: float):
        showlog.debug(f"*[DEF ChromaWidget.update_value STEP 1] ctrl_id={ctrl_id} value={value}")
        if ctrl_id.endswith("_main_1"):
            self.mini_a = max(0.0, min(1.0, value))
        elif ctrl_id.endswith("_main_2"):
            self.mini_b = max(0.0, min(1.0, value))
        self.mark_dirty()
        self._emit_change()

    # -------- input handling ----------
    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            self._try_set_from_point(mx, my)
        elif event.type == pygame.MOUSEMOTION and event.buttons[0]:
            mx, my = event.pos
            self._try_set_from_point(mx, my)

    # -------- drawing ----------
    def draw(self, surface: pygame.Surface, device_name=None, offset_y: int = 0, **_):
        showlog.debug("*[DEF ChromaWidget.draw STEP 1] drawing widget frame")
        self._offset_y = offset_y
        rect = self.rect.move(0, offset_y)
        bg = self.theme.get("plugin_background_color", (16, 16, 20))
        outline = self.theme.get("mini_dial_outline", (90, 90, 100))
        fill = self.theme.get("mini_dial_fill", (160, 210, 160))
        text_col = self.theme.get("dial_text_color", (230, 230, 230))

        pygame.draw.rect(surface, bg, rect)

        for center, value, label in (
            ((self._dial_a_center[0], self._dial_a_center[1] + offset_y), self.mini_a, "Mini A"),
            ((self._dial_b_center[0], self._dial_b_center[1] + offset_y), self.mini_b, "Mini B"),
        ):
            pygame.draw.circle(surface, outline, center, self._radius, width=2)

            # Arc fill (0..1 → 270° sweep)
            start_angle = -math.pi * 0.75
            sweep = (math.pi * 1.5) * max(0.0, min(1.0, value))
            steps = 48
            for i in range(0, steps, 8):  # coarse segments only, avoid spam
                a0 = start_angle + sweep * (i / steps)
                a1 = start_angle + sweep * ((i + 8) / steps)
                p0 = (center[0] + int(self._radius * math.cos(a0)),
                      center[1] + int(self._radius * math.sin(a0)))
                p1 = (center[0] + int(self._radius * math.cos(a1)),
                      center[1] + int(self._radius * math.sin(a1)))
                pygame.draw.line(surface, fill, p0, p1, width=3)

            pygame.draw.line(
                surface, text_col,
                (center[0] - 18, center[1] + self._radius + 6),
                (center[0] + 18, center[1] + self._radius + 6), width=1
            )

        self.clear_dirty()
        return rect

    # -------- helpers ----------
    def _try_set_from_point(self, x: int, y: int):
        for which, center in (("a", self._dial_a_center), ("b", self._dial_b_center)):
            center = (center[0], center[1] + self._offset_y)
            dx, dy = x - center[0], y - center[1]
            if dx * dx + dy * dy <= (self._radius + 6) ** 2:
                ang = math.atan2(dy, dx)
                start = -math.pi * 0.75
                while ang < start:
                    ang += math.tau
                while ang > start + math.tau:
                    ang -= math.tau
                span = ang - start
                value = max(0.0, min(1.0, span / (math.pi * 1.5)))
                showlog.debug(f"*[DEF ChromaWidget._try_set_from_point STEP 1] {which}={value}")
                if which == "a":
                    self.mini_a = value
                else:
                    self.mini_b = value
                self.mark_dirty()
                self._emit_change()
                return

    def _emit_change(self):
        showlog.debug(f"*[DEF ChromaWidget._emit_change STEP 1] a={self.mini_a} b={self.mini_b}")
        if callable(self.on_change):
            self.on_change(self.get_state())
