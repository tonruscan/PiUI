# /build/widgets/dial_widget.py
import pygame
from assets.dial import Dial
import config as cfg
import showlog
from pages import page_dials
from widgets.dirty_mixin import DirtyWidgetMixin


class DialWidget(DirtyWidgetMixin):
    """
    A single interactive Dial wrapped as a widget.
    Will later be positioned by the module grid system.
    """
    def __init__(self, uid: str, rect: pygame.Rect, config: dict):
        super().__init__()
        self.uid = uid
        self.rect = pygame.Rect(rect)
        self.config = config or {}

        # Build one Dial centred in this rect
        cx, cy = self.rect.center
        self.dial = Dial(cx, cy)  # Back to original - uses cfg.DIAL_SIZE
        self.dial.id = config.get("id", 1)
        self.dial.label = config.get("label", uid)
        self.dial.range = config.get("range", [0, 127])
        self.dial.options = config.get("options")
        self.dial.type = config.get("type", "raw")
        dial_size_override = config.get("dial_size")
        if dial_size_override is not None:
            try:
                new_radius = int(round(float(dial_size_override)))
                if new_radius > 0:
                    self.dial.radius = new_radius
                    panel_size = self.dial.radius * 2 + 20
                    self.rect = pygame.Rect(0, 0, panel_size, panel_size)
                    self.rect.center = (cx, cy)
            except Exception:
                pass
        visual_mode = config.get("visual_mode")
        if visual_mode is not None:
            try:
                self.dial.set_visual_mode(visual_mode)
            except ValueError as exc:
                showlog.warn(f"[DialWidget] Invalid visual_mode '{visual_mode}' for {uid}: {exc}")

        # Simple interaction state
        self.dragging = False

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------
    def handle_event(self, event) -> bool:
        """Return True if the event was consumed."""
        if getattr(self.dial, "visual_mode", "default") == "hidden":
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and hasattr(event, "pos"):
            if self._hit(event.pos):
                self.dragging = True
                return True
        elif event.type == pygame.MOUSEBUTTONUP:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            old_value = self.dial.value
            self.dial.update_from_mouse(*event.pos)
            if old_value != self.dial.value:
                self.mark_dirty()  # Mark dirty when value changes
            return True
        return False

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def draw(self, screen, device_name=None, offset_y=0):
        """
        Draw this dial using the shared page_dials renderer.
        Returns the dirty rect that was drawn.
        """
        if getattr(self.dial, "visual_mode", "default") == "hidden":
            return None
        try:
            rect = page_dials.redraw_single_dial(
                screen,
                self.dial,
                offset_y=offset_y,
                device_name=device_name,
                is_page_muted=False,
                update_label=True,
                force_label=False,
            )
            return rect
        except Exception as e:
            showlog.warn(f"[DialWidget] Draw failed for {self.uid}: {e}")
            return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _hit(self, pos) -> bool:
        dx = pos[0] - self.dial.cx
        dy = pos[1] - self.dial.cy
        return (dx * dx + dy * dy) <= (self.dial.radius * self.dial.radius)

    def get_state(self):
        """Return current dial value; placeholder for persistence."""
        return {"uid": self.uid, "value": int(self.dial.value)}

    def set_state(self, data):
        """Restore dial value if available."""
        try:
            if isinstance(data, dict) and "value" in data:
                self.dial.set_value(int(data["value"]))
        except Exception:
            pass
