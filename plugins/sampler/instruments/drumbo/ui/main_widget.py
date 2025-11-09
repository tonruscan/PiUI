"""Sampler-aware Drumbo widget.

This widget mirrors the legacy Drumbo UI (16 mic dials laid out in four rows)
while living under the sampler package.  It keeps the rendering and dirty-rect
optimisation logic intact so `LegacyUISyncService` can continue to position the
hardware-linked dial widgets and reuse the headless redraw shortcuts.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

import pygame
import showlog

import config as cfg
import helper
import utils.font_helper as font_helper


class DrumboMainWidget:
	"""UI surface that hosts Drumbo's mic dials and status strip."""

	MINI_DIAL_LAYOUT_OVERRIDES: Dict[str, Any] = {}

	def __init__(
		self,
		rect: pygame.Rect,
		on_change: Optional[Any] = None,
		theme: Optional[Dict[str, Any]] = None,
		init_state: Optional[Dict[str, Any]] = None,
	) -> None:
		self.rect = rect
		self.on_change = on_change
		self.theme = theme or {}
		self._module = None

		self._dirty = True
		self._dirty_dial = None
		self.msg_queue = None

		self.current_instrument = "snare"
		self.active_bank = "A"
		self.mic_dials_row_1: list[Any] = []
		self.mic_dials_row_2: list[Any] = []
		self.current_page_rect = rect.copy()

		self.midi_note_detected = False
		self.midi_note_time = 0.0
		self.midi_flash_duration = 0.1
		self._midi_settle_pending = False

		self._update_colors()

		font_path = font_helper.main_font("Bold")
		self.label_font = pygame.font.Font(font_path, cfg.DIAL_FONT_SIZE)

		showlog.info(f"[DrumboMainWidget] Initialized with rect={rect}")

	def _update_colors(self) -> None:
		theme = self.theme or {}

		showlog.info(f"[DrumboMainWidget] Received theme keys: {list(theme.keys())}")
		showlog.info(f"[DrumboMainWidget] plugin_background_color = {theme.get('plugin_background_color')}")
		showlog.info(f"[DrumboMainWidget] bg = {theme.get('bg')}")

		def _rgb3(value: Any):
			if isinstance(value, (list, tuple)):
				return tuple(value[:3])
			return value

		def _to_rgb(value: Any, fallback_hex: str):
			if isinstance(value, (list, tuple)):
				return tuple(value[:3])
			if isinstance(value, str):
				try:
					return helper.hex_to_rgb(value)
				except Exception:
					pass
			return helper.hex_to_rgb(fallback_hex)

		if "plugin_background_color" in theme:
			self.bg_color = _to_rgb(theme.get("plugin_background_color"), cfg.DIAL_PANEL_COLOR)
			showlog.info(f"[DrumboMainWidget] Using plugin_background_color: {self.bg_color}")
		elif "bg" in theme:
			self.bg_color = _rgb3(theme.get("bg"))
			showlog.info(f"[DrumboMainWidget] Using bg: {self.bg_color}")
		else:
			hex_bg = helper.device_theme.get(
				"",
				"plugin_background_color",
				getattr(cfg, "PLUGIN_BACKGROUND_COLOR", cfg.DIAL_PANEL_COLOR),
			)
			self.bg_color = helper.hex_to_rgb(hex_bg)
			showlog.info(f"[DrumboMainWidget] Using fallback: {self.bg_color}")

		self.border_color = _rgb3(theme.get("outline")) if "outline" in theme else helper.hex_to_rgb(cfg.DIAL_OUTLINE_COLOR)
		self.kick_blank_bg_color = _to_rgb(theme.get("kick_blank_background"), "#120805")
		self.kick_blank_border_color = _to_rgb(theme.get("kick_blank_border"), "#2C1810")

		import dialhandlers

		device_name = getattr(dialhandlers, "current_device_name", None)
		dial_text_hex = helper.device_theme.get(
			device_name,
			"dial_text_color",
			getattr(cfg, "DIAL_TEXT_COLOR", "#FFFFFF"),
		)
		self.text_color = helper.hex_to_rgb(dial_text_hex)

	def draw(self, surface: pygame.Surface, device_name: Optional[str] = None, offset_y: int = 0) -> pygame.Rect:
		if self._dirty_dial is not None:
			try:
				dial = self._dirty_dial
				radius = getattr(dial, "radius", 25)
				cx = int(getattr(dial, "cx", 0))
				cy = int(getattr(dial, "cy", 0))

				dial_rect = pygame.Rect(cx - radius - 2, cy - radius - 2, radius * 2 + 4, radius * 2 + 4)
				label_rect = pygame.Rect(cx - 40, cy + radius + 5, 80, 60)

				dial_rect.y += offset_y
				label_rect.y += offset_y
				return dial_rect.union(label_rect)
			except Exception as exc:
				showlog.warn(f"[DrumboWidget] Failed to calculate dial dirty rect: {exc}")

		draw_rect = self.rect.copy()
		draw_rect.y += offset_y

		instrument_lower = (self.current_instrument or "").strip().lower()
		if instrument_lower == "kick":
			self._draw_kick_page(surface, draw_rect)
		else:
			self._draw_snare_page(surface, draw_rect)

		label_text = "DRUM MACHINE - 16 MIC ARTICULATION SYSTEM"
		label_surf = self.label_font.render(label_text, True, self.text_color)

		instrument_text = (self.current_instrument or "snare").upper()
		rr_value = getattr(self._module, "round_robin_index", None) if self._module else None
		rr_total = getattr(self._module, "round_robin_cycle_size", None) if self._module else None
		if rr_value is None or not rr_total:
			instrument_display = f"{instrument_text}: —"
		else:
			try:
				instrument_display = f"{instrument_text}: {int(rr_value)}/{int(rr_total)}"
			except (TypeError, ValueError):
				instrument_display = f"{instrument_text}: {rr_value}/{rr_total}"

		instrument_surf = self.label_font.render(instrument_display, True, self.text_color)
		brackets_text = "MIDI [   ]"
		brackets_surf = self.label_font.render(brackets_text, True, self.text_color)

		label_x = draw_rect.left
		label_y = draw_rect.bottom + 10
		instrument_x = label_x + label_surf.get_width() + 24
		midi_x = draw_rect.right - brackets_surf.get_width()
		midi_y = label_y

		text_right = max(
			label_x + label_surf.get_width(),
			instrument_x + instrument_surf.get_width(),
			midi_x + brackets_surf.get_width(),
		)
		text_height = max(
			label_surf.get_height(),
			instrument_surf.get_height(),
			brackets_surf.get_height(),
		)

		text_bg_rect = pygame.Rect(label_x, label_y, text_right - label_x, text_height)
		pygame.draw.rect(surface, (0, 0, 0), text_bg_rect)

		surface.blit(label_surf, (label_x, label_y))
		surface.blit(instrument_surf, (instrument_x, label_y))
		surface.blit(brackets_surf, (midi_x, midi_y))

		current_time = time.time()
		midi_active = (current_time - self.midi_note_time) < self.midi_flash_duration
		if midi_active:
			star_font_size = cfg.DIAL_FONT_SIZE * 2
			star_font = pygame.font.Font(font_helper.main_font("Bold"), star_font_size)
			star_surf = star_font.render("*", True, self.text_color)

			bracket_open_width = self.label_font.render("MIDI [", True, self.text_color).get_width()
			bracket_space_width = self.label_font.render("   ", True, self.text_color).get_width()

			star_x = midi_x + bracket_open_width + (bracket_space_width - star_surf.get_width()) // 2
			star_y = midi_y + (brackets_surf.get_height() - star_surf.get_height()) // 2 + 9

			surface.blit(star_surf, (star_x, star_y))
			self.mark_dirty()
		elif self._midi_settle_pending:
			self.mark_dirty()
			self._midi_settle_pending = False

		full_rect = draw_rect.copy()
		label_rect = pygame.Rect(label_x, label_y, label_surf.get_width(), label_surf.get_height())
		instrument_rect = pygame.Rect(
			instrument_x,
			label_y,
			instrument_surf.get_width(),
			instrument_surf.get_height(),
		)
		midi_rect = pygame.Rect(midi_x, midi_y, brackets_surf.get_width(), brackets_surf.get_height())
		full_rect = full_rect.union(label_rect).union(instrument_rect).union(midi_rect)

		self.clear_dirty()
		return full_rect

	def _draw_snare_page(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
		pygame.draw.rect(surface, self.bg_color, rect, border_radius=20)
		pygame.draw.rect(surface, self.border_color, rect, 2, border_radius=20)
		self.current_page_rect = rect.copy()

	def _draw_kick_page(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
		pygame.draw.rect(surface, self.kick_blank_bg_color, rect, border_radius=20)
		pygame.draw.rect(surface, self.kick_blank_border_color, rect, 2, border_radius=20)
		self.current_page_rect = rect.copy()

	def handle_event(self, event: pygame.event.Event) -> bool:
		if event.type == pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(event.pos):
			showlog.info(f"[DrumboMainWidget] Widget clicked at {event.pos}")
			self.mark_dirty()
			return True
		return False

	def handle_button(self, btn_id: int) -> None:
		return None

	def set_instrument(self, instrument: str) -> None:
		self.current_instrument = instrument
		showlog.info(f"[DrumboMainWidget] Instrument changed to {instrument}")
		self.mark_dirty()

	def on_midi_note(self, note: int, velocity: int) -> None:
		if velocity > 0:
			self.midi_note_detected = True
			self.midi_note_time = time.time()
			self._midi_settle_pending = True
			self.mark_dirty()
			showlog.info(f"[DrumboMainWidget] MIDI note detected: note={note}, velocity={velocity}")

	def get_state(self) -> Dict[str, Any]:
		return {"current_instrument": self.current_instrument}

	def set_state(self, state: Dict[str, Any]) -> None:
		self.current_instrument = state.get("current_instrument", "snare")
		self.mark_dirty()

	def mark_dirty(self, dial: Optional[Any] = None) -> None:
		self._dirty = True
		self._dirty_dial = dial
		if self.msg_queue:
			try:
				self.msg_queue.put(("burst", 0.5))
			except Exception:
				pass

	def is_dirty(self) -> bool:
		if self.midi_note_detected:
			if (time.time() - self.midi_note_time) < self.midi_flash_duration:
				return True
			self.midi_note_detected = False
		if self._midi_settle_pending:
			return True
		result = self._dirty
		if result:
			showlog.debug("[DrumboWidget] is_dirty returning True")
		return result

	def clear_dirty(self) -> None:
		self._dirty = False
		self._dirty_dial = None

	def get_dirty_rect(self) -> Optional[pygame.Rect]:
		if not self._dirty:
			return None
		if self._dirty_dial is not None:
			try:
				dial = self._dirty_dial
				radius = getattr(dial, "radius", 25)
				cx = int(getattr(dial, "cx", 0))
				cy = int(getattr(dial, "cy", 0))
				dial_rect = pygame.Rect(cx - radius - 2, cy - radius - 2, radius * 2 + 4, radius * 2 + 4)
				label_rect = pygame.Rect(cx - 40, cy + radius + 5, 80, 60)
				dirty_rect = dial_rect.union(label_rect)
				showlog.debug(f"[DrumboWidget] Returning minimal dirty rect for dial: {dirty_rect}")
				return dirty_rect
			except Exception as exc:
				showlog.warn(f"[DrumboWidget] Failed to calculate dial dirty rect: {exc}")
		showlog.debug("[DrumboWidget] Returning full widget rect")
		return self.rect
