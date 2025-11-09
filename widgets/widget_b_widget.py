# widgets/widget_b_widget.py
import pygame
import showlog


class WidgetB:
    """Alternate widget variant with its own styling."""

    TITLE = "Widget B"

    def __init__(self, rect, on_change=None, theme=None, init_state=None):
        self.rect = pygame.Rect(rect)
        self.on_change = on_change
        self.theme = dict(theme or {})
        self._state = {"dial1": 32, "dial2": 112}
        if isinstance(init_state, dict):
            for key in self._state:
                if key in init_state:
                    self._state[key] = self._clamp(init_state[key])

        self._dials = []
        self._dirty = True
        self._font = pygame.font.SysFont(None, 24)

    # ------------------------------------------------------------------
    def apply_theme(self, theme):
        self.theme = dict(theme or {})
        self.mark_dirty()

    def bind_dials(self, dials):
        self._dials = list(dials or [])
        for idx, dial in enumerate(self._dials, start=1):
            try:
                dial.set_value(self._state.get(f"dial{idx}", 0))
            except Exception:
                dial.value = self._state.get(f"dial{idx}", 0)
            dial.label = f"B{idx}"
        self.mark_dirty()

    def get_widget_dials(self):
        return self._dials

    def set_state(self, state):
        if not isinstance(state, dict):
            return
        for idx, key in enumerate(("dial1", "dial2"), start=1):
            if key in state:
                value = self._clamp(state[key])
                self._state[key] = value
                if idx <= len(self._dials):
                    try:
                        self._dials[idx - 1].set_value(value)
                    except Exception:
                        self._dials[idx - 1].value = value
        self.mark_dirty()

    def update_value(self, index, value):
        key = f"dial{index + 1}"
        clamped = self._clamp(value)
        self._state[key] = clamped
        if index < len(self._dials):
            try:
                self._dials[index].set_value(clamped)
            except Exception:
                self._dials[index].value = clamped
        self.mark_dirty()

    def get_state(self):
        return dict(self._state)

    # ------------------------------------------------------------------
    def mark_dirty(self):
        self._dirty = True

    def is_dirty(self):
        return self._dirty

    def clear_dirty(self):
        self._dirty = False

    def handle_event(self, event):
        return False

    # ------------------------------------------------------------------
    def draw(self, surface, device_name=None, offset_y=0):
        panel_rect = self.rect.copy()
        panel_rect.y += offset_y

        panel_color = self.theme.get("plugin_background_color", (30, 22, 40))
        accent = self.theme.get("mini_dial_fill", (255, 150, 120))
        outline = self.theme.get("mini_dial_outline", (100, 70, 90))
        text_color = self.theme.get("dial_text_color", (240, 240, 240))

        pygame.draw.rect(surface, panel_color, panel_rect, border_radius=16)

        title = self._font.render(self.TITLE, True, text_color)
        surface.blit(title, (panel_rect.x + 20, panel_rect.y + 18))

        for idx, key in enumerate(("dial1", "dial2")):
            value = self._state[key]
            base_y = panel_rect.y + 60 + idx * 70

            label = self._font.render(f"B{idx + 1}: {value:03d}", True, text_color)
            surface.blit(label, (panel_rect.x + 20, base_y))

            track_rect = pygame.Rect(
                panel_rect.x + 20,
                base_y + 26,
                panel_rect.width - 40,
                18,
            )
            pygame.draw.rect(surface, outline, track_rect, border_radius=6)

            fill_width = int(track_rect.width * (value / 127.0))
            if fill_width > 0:
                fill_rect = pygame.Rect(track_rect.x, track_rect.y, fill_width, track_rect.height)
                pygame.draw.rect(surface, accent, fill_rect, border_radius=6)

        self.clear_dirty()
        showlog.verbose(f"[WidgetB] Drawn at {panel_rect}")
        return panel_rect

    # ------------------------------------------------------------------
    @staticmethod
    def _clamp(value):
        try:
            return max(0, min(127, int(value)))
        except Exception:
            return 0
