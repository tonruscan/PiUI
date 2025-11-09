# widgets/luma_widget.py
import pygame
from typing import Any, Dict, Optional
import showlog


class LumaWidget:
    """
    Widget A: two special 'mini dials' rendered inside the widget surface.
    Contract: (rect, on_change=None, theme=None, init_state=None)
    Provides: get_state, set_state, mark_dirty, is_dirty, clear_dirty, update_value, handle_event, draw
    """
    def __init__(
        self,
        rect: pygame.Rect,
        on_change=None,
        theme: Optional[Dict[str, Any]] = None,
        init_state: Optional[Dict[str, Any]] = None
    ):
        showlog.debug("*[DEF LumaWidget.__init__ STEP 1] create widget instance")
        self.rect = rect
        self.on_change = on_change
        self.theme = theme or {}
        self._dirty = True

        # State for two mini dials (0..1)
        self.mini_a = 0.3
        self.mini_b = 0.7
        if init_state:
            showlog.debug(f"*[DEF LumaWidget.__init__ STEP 2] restoring init_state={init_state}")
            self.mini_a = float(init_state.get("mini_a", self.mini_a))
            self.mini_b = float(init_state.get("mini_b", self.mini_b))

        # Geometry setup
        self._offset_y = 0
        w, h = self.rect.width, self.rect.height
        pad = 12
        dial_w = (w - pad * 3) // 2
        dial_h = h - pad * 2
        self._zone_a = pygame.Rect(self.rect.x + pad, self.rect.y + pad, dial_w, dial_h)
        self._zone_b = pygame.Rect(self.rect.x + pad*2 + dial_w, self.rect.y + pad, dial_w, dial_h)

    # -------- state & dirty ----------
    def get_state(self) -> Dict[str, float]:
        return {"mini_a": self.mini_a, "mini_b": self.mini_b}

    def set_state(self, state: Dict[str, float]):
        showlog.debug(f"*[DEF LumaWidget.set_state STEP 1] applying state={state}")
        self.mini_a = float(state.get("mini_a", self.mini_a))
        self.mini_b = float(state.get("mini_b", self.mini_b))
        self.mark_dirty()
        self._emit_change()

    def mark_dirty(self):
        self._dirty = True

    def is_dirty(self) -> bool:
        return self._dirty

    def clear_dirty(self):
        self._dirty = False

    # -------- host → widget updates ----------
    def update_value(self, ctrl_id: str, value: float):
        showlog.debug(f"*[DEF LumaWidget.update_value STEP 1] ctrl_id={ctrl_id} value={value}")
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
            if self._zone_a.move(0, self._offset_y).collidepoint(mx, my):
                self._set_from_y("a", my)
            elif self._zone_b.move(0, self._offset_y).collidepoint(mx, my):
                self._set_from_y("b", my)
        elif event.type == pygame.MOUSEMOTION and event.buttons[0]:
            mx, my = event.pos
            if self._zone_a.move(0, self._offset_y).collidepoint(mx, my):
                self._set_from_y("a", my)
            elif self._zone_b.move(0, self._offset_y).collidepoint(mx, my):
                self._set_from_y("b", my)

    # -------- drawing ----------
    def draw(self, surface: pygame.Surface, device_name=None, offset_y: int = 0, **_):
        showlog.debug("*[DEF LumaWidget.draw STEP 1] drawing widget frame")
        self._offset_y = offset_y
        rect = self.rect.move(0, offset_y)
        bg = self.theme.get("plugin_background_color", (20, 20, 24))
        pygame.draw.rect(surface, bg, rect)

        outline = self.theme.get("mini_dial_outline", (90, 90, 100))
        fill = self.theme.get("mini_dial_fill", (160, 160, 210))
        text_col = self.theme.get("dial_text_color", (230, 230, 230))

        for zone, value, label in (
            (self._zone_a.move(0, offset_y), self.mini_a, "Mini A"),
            (self._zone_b.move(0, offset_y), self.mini_b, "Mini B"),
        ):
            pygame.draw.rect(surface, outline, zone, width=2)
            inner = zone.inflate(-6, -6)
            fill_h = int(inner.height * value)
            fill_rect = pygame.Rect(inner.x, inner.bottom - fill_h, inner.width, fill_h)
            pygame.draw.rect(surface, fill, fill_rect)
            self._draw_label(surface, label, text_col, zone.midtop[0], zone.y - 6)

        self.clear_dirty()
        return rect

    # -------- helpers ----------
    def _set_from_y(self, which: str, y: int):
        base_zone = self._zone_a if which == "a" else self._zone_b
        zone = base_zone.move(0, self._offset_y)
        inner = zone.inflate(-6, -6)
        rel = (inner.bottom - max(inner.y, min(y, inner.bottom))) / max(1, inner.height)
        if which == "a":
            self.mini_a = rel
        else:
            self.mini_b = rel
        showlog.debug(f"*[DEF LumaWidget._set_from_y STEP 1] {which}={rel}")
        self.mark_dirty()
        self._emit_change()

    def _emit_change(self):
        showlog.debug(f"*[DEF LumaWidget._emit_change STEP 1] a={self.mini_a} b={self.mini_b}")
        if callable(self.on_change):
            self.on_change(self.get_state())

    def _draw_label(self, surface: pygame.Surface, text: str, color, cx: int, y: int):
        pygame.draw.line(surface, color, (cx - 20, y), (cx + 20, y), width=1)
        # Keeping it textless to avoid font dependency.
