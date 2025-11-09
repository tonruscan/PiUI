"""Reusable helpers for widgets that participate in dirty-rect rendering."""

from __future__ import annotations

import config as cfg


def _resolve_padding(value) -> tuple[int, int]:
    if isinstance(value, (tuple, list)):
        if len(value) == 0:
            return (0, 0)
        if len(value) == 1:
            return (int(value[0]), int(value[0]))
        return (int(value[0]), int(value[1]))
    try:
        scalar = int(value)
    except Exception:
        scalar = 0
    return (scalar, scalar)


class DirtyWidgetMixin:
    def __init__(self, *args, **kwargs):
        self.dirty = False
        self._dirty_pad = (0, 0)
        super().__init__(*args, **kwargs)

    def set_dirty_padding(self, pad_x, pad_y=None):
        if pad_y is None:
            pad_y = pad_x
        pad_x = max(0, int(pad_x))
        pad_y = max(0, int(pad_y))
        self._dirty_pad = (pad_x, pad_y)

    def mark_dirty(self):
        self.dirty = True

    def clear_dirty(self):
        self.dirty = False

    def is_dirty(self):
        return bool(self.dirty)

    def get_dirty_rect(self, offset_y=0):
        if not hasattr(self, "rect"):
            return None
        rect = self.rect.copy()
        rect.y += offset_y
        pad_x, pad_y = self._dirty_pad

        global_pad = _resolve_padding(getattr(cfg, "DIRTY_WIDGET_PADDING", 0))
        pad_x += global_pad[0]
        pad_y += global_pad[1]

        if pad_x or pad_y:
            rect = rect.inflate(pad_x * 2, pad_y * 2)
        return rect
