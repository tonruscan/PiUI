# /build/widgets/dial_widget.py
import pygame
from assets.dial import Dial
import config as cfg
import helper
import showlog
from pages import page_dials

class DialWidget:
    """
    A single interactive Dial wrapped as a widget.
    Will later be positioned by the module grid system.
    """
    def __init__(self, uid: str, rect: pygame.Rect, config: dict):
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

        # Simple interaction state
        self.dragging = False

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------
    def handle_event(self, event) -> bool:
        """Return True if the event was consumed."""
        if event.type == pygame.MOUSEBUTTONDOWN and hasattr(event, "pos"):
            if self._hit(event.pos):
                self.dragging = True
                return True
        elif event.type == pygame.MOUSEBUTTONUP:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self.dial.update_from_mouse(*event.pos)
            return True
        return False

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def draw(self, screen, device_name=None, offset_y=0):
        """Draw this dial using the shared page_dials renderer."""
        try:
            page_dials.redraw_single_dial(
                screen,
                self.dial,
                offset_y=offset_y,
                device_name=device_name,
                is_page_muted=False,
                update_label=True,
                force_label=False,
            )
        except Exception as e:
            showlog.warn(f"[DialWidget] draw failed for {self.uid}: {e}")

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
