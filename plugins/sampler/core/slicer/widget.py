"""Sampler-native auto-slicer widget (4x2 grid layout)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import pygame
import showlog

import helper
import utils.font_helper as font_helper

from .models import SliceSet, SliceSummary

SelectionCallback = Callable[[int, Optional[SliceSummary]], None]


@dataclass
class CellLayout:
    rect: pygame.Rect
    summary: Optional[SliceSummary]


class AutoSlicerWidget:
    """Visualises up to eight auto-detected slices in a 4×2 grid."""

    def __init__(
        self,
        rect: pygame.Rect,
        on_change: Optional[SelectionCallback] = None,
        theme: Optional[dict] = None,
        init_state: Optional[dict] = None,
    ) -> None:
        self.rect = rect
        self.on_change = on_change
        self.theme = theme or {}

        self.slice_set: Optional[SliceSet] = None
        self.selected_index: int = 0

        self._dirty = True
        self._cell_rects: list[pygame.Rect] = []

        font_path_regular = font_helper.main_font("Regular")
        font_path_bold = font_helper.main_font("Bold")
        self.title_font = pygame.font.Font(font_path_bold, 18)
        self.detail_font = pygame.font.Font(font_path_regular, 15)
        self.status_font = pygame.font.Font(font_path_regular, 13)

        self._resolve_theme()

        if init_state:
            self.set_state(init_state)

        showlog.info(f"[AutoSlicerWidget] Initialized rect={rect}")

    # ------------------------------------------------------------------
    # Theme helpers
    # ------------------------------------------------------------------
    def _resolve_theme(self) -> None:
        def _resolve_color(value, fallback_hex: str, default_rgb: tuple[int, int, int]):
            if isinstance(value, (list, tuple)):
                try:
                    return tuple(int(c) for c in value[:3])
                except Exception:
                    pass
            if isinstance(value, str):
                try:
                    return helper.hex_to_rgb(value)
                except Exception:
                    pass
            if fallback_hex:
                try:
                    return helper.hex_to_rgb(fallback_hex)
                except Exception:
                    pass
            return default_rgb

        self.bg_color = _resolve_color(
            self.theme.get("plugin_background_color"),
            "#121212",
            (18, 18, 18),
        )
        self.border_color = _resolve_color(self.theme.get("outline"), "#3A3A3A", (58, 58, 58))
        self.cell_color = _resolve_color(self.theme.get("dial_panel_color"), "#1E1E1E", (30, 30, 30))
        self.empty_cell_color = _resolve_color(self.theme.get("slicer_empty_cell", None), "#101010", (16, 16, 16))
        self.highlight_color = _resolve_color(self.theme.get("button_active_fill"), "#D97706", (217, 119, 6))
        self.text_color = _resolve_color(self.theme.get("dial_text_color"), "#F5F5F5", (245, 245, 245))
        self.subtext_color = _resolve_color(self.theme.get("preset_text_color"), "#B0B0B0", (176, 176, 176))
        self.meter_color = _resolve_color(self.theme.get("slicer_meter_color"), "#4ADE80", (74, 222, 128))
        self.meter_bg_color = _resolve_color(self.theme.get("slicer_meter_bg"), "#202020", (32, 32, 32))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_slice_set(self, slice_set: SliceSet | None) -> None:
        self.slice_set = slice_set
        if slice_set and slice_set.slices:
            self.selected_index = max(0, min(self.selected_index, len(slice_set.slices) - 1))
        else:
            self.selected_index = 0
        self.mark_dirty()

    def update_slice_label(self, index: int, label: Optional[str]) -> None:
        if not self.slice_set or index < 0 or index >= len(self.slice_set.slices):
            return
        summary = self.slice_set.slices[index]
        summary.label = label
        self.mark_dirty()

    def get_state(self) -> dict:
        return {
            "recording_id": self.slice_set.recording_id if self.slice_set else None,
            "selected_index": self.selected_index,
            "labels": [summary.label for summary in (self.slice_set.slices if self.slice_set else [])],
        }

    def set_state(self, state: dict | None) -> None:
        if not state:
            return
        self.selected_index = int(state.get("selected_index", 0))
        labels = state.get("labels") or []
        if self.slice_set and labels:
            for summary, label in zip(self.slice_set.slices, labels):
                summary.label = label
        self.mark_dirty()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def draw(self, surface: pygame.Surface, device_name: Optional[str] = None, offset_y: int = 0) -> pygame.Rect:
        panel_rect = self.rect.copy()
        panel_rect.y += offset_y
        pygame.draw.rect(surface, self.bg_color, panel_rect, border_radius=18)
        pygame.draw.rect(surface, self.border_color, panel_rect, width=2, border_radius=18)

        gutter = 14
        cols = 4
        rows = 2

        inner = panel_rect.inflate(-gutter * 2, -gutter * 2)
        cell_width = (inner.width - gutter * (cols - 1)) // cols
        cell_height = (inner.height - gutter * (rows - 1)) // rows

        self._cell_rects = []
        slices = self.slice_set.slices if self.slice_set else []

        for idx in range(rows * cols):
            row = idx // cols
            col = idx % cols

            cell_left = inner.left + col * (cell_width + gutter)
            cell_top = inner.top + row * (cell_height + gutter)
            cell_rect = pygame.Rect(cell_left, cell_top, cell_width, cell_height)
            self._cell_rects.append(cell_rect)

            summary = slices[idx] if idx < len(slices) else None
            self._draw_cell(surface, cell_rect, summary, idx == self.selected_index)

        self.clear_dirty()
        return panel_rect

    def _draw_cell(self, surface: pygame.Surface, rect: pygame.Rect, summary: Optional[SliceSummary], selected: bool) -> None:
        bg_color = self.cell_color if summary else self.empty_cell_color
        pygame.draw.rect(surface, bg_color, rect, border_radius=10)
        pygame.draw.rect(surface, self.highlight_color if selected else self.border_color, rect, width=2, border_radius=10)

        padding = 10
        content_rect = rect.inflate(-padding * 2, -padding * 2)

        if not summary:
            placeholder = self.status_font.render("—", True, self.subtext_color)
            placeholder_pos = placeholder.get_rect(center=content_rect.center)
            surface.blit(placeholder, placeholder_pos)
            return

        title = summary.label or f"Slice {summary.index + 1}"
        title_surf = self.title_font.render(title.upper(), True, self.text_color)
        surface.blit(title_surf, (content_rect.left, content_rect.top))

        duration_text = f"{summary.duration_ms:.0f} ms"
        duration_surf = self.detail_font.render(duration_text, True, self.subtext_color)
        surface.blit(duration_surf, (content_rect.left, content_rect.top + title_surf.get_height() + 4))

        if summary.peak_db is not None:
            level_text = f"{summary.peak_db:.1f} dBFS"
        else:
            level_text = "— dBFS"
        level_surf = self.status_font.render(level_text, True, self.subtext_color)
        surface.blit(level_surf, (content_rect.left, content_rect.bottom - level_surf.get_height()))

        meter_rect = pygame.Rect(
            content_rect.left,
            content_rect.bottom - level_surf.get_height() - 12,
            content_rect.width,
            6,
        )
        pygame.draw.rect(surface, self.meter_bg_color, meter_rect, border_radius=3)
        meter_width = int(meter_rect.width * max(0.0, min(1.0, summary.peak_normalized)))
        if meter_width > 0:
            active_rect = pygame.Rect(meter_rect.left, meter_rect.top, meter_width, meter_rect.height)
            pygame.draw.rect(surface, self.meter_color, active_rect, border_radius=3)

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and getattr(event, "button", None) == 1:
            pos = getattr(event, "pos", None)
            if pos and self.rect.collidepoint(pos):
                for idx, cell_rect in enumerate(self._cell_rects):
                    if cell_rect.collidepoint(pos):
                        self.selected_index = idx
                        self.mark_dirty()
                        self._emit_selection()
                        return True
        if event.type == pygame.KEYDOWN and self._cell_rects:
            if event.key in (pygame.K_RIGHT, pygame.K_d):
                self._nudge_selection(1)
                return True
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self._nudge_selection(-1)
                return True
            if event.key in (pygame.K_UP, pygame.K_w):
                self._nudge_selection(-4)
                return True
            if event.key in (pygame.K_DOWN, pygame.K_s):
                self._nudge_selection(4)
                return True
        return False

    def _nudge_selection(self, delta: int) -> None:
        total = len(self._cell_rects)
        if total == 0:
            return
        new_index = (self.selected_index + delta) % total
        if new_index != self.selected_index:
            self.selected_index = new_index
            self.mark_dirty()
            self._emit_selection()

    def _emit_selection(self) -> None:
        if not self.on_change:
            return
        summary = None
        if self.slice_set and 0 <= self.selected_index < len(self.slice_set.slices):
            summary = self.slice_set.slices[self.selected_index]
        try:
            self.on_change(self.selected_index, summary)
        except Exception as exc:  # pragma: no cover - defensive
            showlog.debug(f"[AutoSlicerWidget] on_change failed: {exc}")

    # ------------------------------------------------------------------
    # Dirty tracking
    # ------------------------------------------------------------------
    def mark_dirty(self) -> None:
        self._dirty = True

    def clear_dirty(self) -> None:
        self._dirty = False

    def is_dirty(self) -> bool:
        return self._dirty

    def get_dirty_rect(self) -> pygame.Rect | None:
        return self.rect if self._dirty else None
