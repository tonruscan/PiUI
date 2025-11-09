"""Sampler plugin entry point that hosts the sampler-native Drumbo module."""

from __future__ import annotations

import copy
from typing import Any, Dict

import showlog

from core.plugin import Plugin as PluginBase
from plugins.sampler.core.engine import InstrumentContext, InstrumentDescriptor
from plugins.sampler.core.event_bridge import EventBridge, SamplerEvent
from plugins.sampler.core.mixer_facade import MixerFacade
from plugins.sampler.core.preset_facade import PresetFacade
from plugins.sampler.core.services.instrument_registry import register_instrument
from plugins.sampler.instruments.drumbo.module import DrumboInstrument


# Compatibility export so existing sampler shell references keep working.
Drumbo = DrumboInstrument


class InMemoryPresetFacade(PresetFacade):
	"""Minimal preset facade that mirrors Drumbo snapshots in-memory."""

	def __init__(self) -> None:
		self._state_by_instrument: Dict[str, Dict[str, Any]] = {}

	def save_state(self, instrument_id: str, state: Dict[str, Any]) -> None:
		self._state_by_instrument[instrument_id] = copy.deepcopy(state)

	def load_state(self, instrument_id: str) -> Dict[str, Any] | None:
		stored = self._state_by_instrument.get(instrument_id)
		return copy.deepcopy(stored) if stored is not None else None


class ApplicationEventBridge(EventBridge):
	"""Forwards sampler events onto the application's event bus."""

	def __init__(self, event_bus=None) -> None:
		self._event_bus = event_bus

	def publish(self, event: SamplerEvent) -> None:
		if not self._event_bus:
			return

		event_type = "sampler.event"
		payload = event
		if isinstance(event, dict):
			event_type = event.get("type") or event_type

		try:
			self._event_bus.publish(event_type, payload)
		except Exception as exc:
			showlog.debug(f"[Sampler] Failed to publish sampler event '{event_type}': {exc}")


class FallbackMixerFacade(MixerFacade):
	"""Defers to the legacy Drumbo mixer until sampler audio services exist."""

	def ensure_ready(self) -> bool:
		return False

	def play_sample(self, path: str, volume: float) -> bool:
		return False


class SamplerPlugin(PluginBase):
	"""Sampler shell plugin that hosts Drumbo as the default instrument."""

	name = "Drumbo"
	version = "1.0.0"
	category = "test"
	author = "System"
	description = "Drumbo drum machine Plugin"
	icon = "default.png"
	page_id = DrumboInstrument.page_id

	def __init__(self) -> None:
		super().__init__()

		self._descriptor = InstrumentDescriptor(
			id=DrumboInstrument.MODULE_ID,
			display_name="Drumbo",
			category="drums",
			version=self.version,
			entry_module="plugins.sampler.instruments.drumbo.module",
			metadata_path=None,
			icon_path=None,
			default_preset=None,
		)

		self._preset_facade = InMemoryPresetFacade()
		self._mixer_facade = FallbackMixerFacade()
		self._event_bridge = ApplicationEventBridge()
		self._active_instrument = DrumboInstrument()
		self._instrument_context: InstrumentContext | None = None
		self._active_descriptor = self._descriptor

	def on_load(self, app) -> None:
		register_instrument(self._descriptor)

		event_bus = getattr(app, "event_bus", None)
		self._event_bridge = ApplicationEventBridge(event_bus)

		try:
			from pages import module_base as legacy_module_base
		except Exception:
			legacy_module_base = None

		try:
			from managers import preset_manager as legacy_preset_manager
		except Exception:
			legacy_preset_manager = None

		try:
			import pygame as legacy_pygame
		except Exception:
			legacy_pygame = None

		self._active_instrument.configure_sampler_facades(
			mixer=self._mixer_facade,
			presets=self._preset_facade,
			events=self._event_bridge,
		)

		self._instrument_context = InstrumentContext(
			mixer=self._mixer_facade,
			presets=self._preset_facade,
			events=self._event_bridge,
			config={
				"active_instrument": self._active_descriptor.id,
				"legacy": {
					"module_base": legacy_module_base,
					"preset_manager": legacy_preset_manager,
					"pygame": legacy_pygame,
				},
			},
		)
		self._active_instrument.bind_instrument_context(self._instrument_context)

		# Register the Drumbo page with the application just like the legacy plugin did.
		try:
			from pages import module_base as drumbo_page
			rendering_meta = {
				"fps_mode": "high",
				"supports_dirty_rect": True,
				"burst_multiplier": 1.0,
			}
			app.page_registry.register(
				self.page_id,
				drumbo_page,
				label=self.name,
				meta={"rendering": rendering_meta},
			)
			showlog.info(f"[Sampler] Registered Drumbo page '{self.page_id}'")
		except Exception as exc:
			import traceback
			showlog.error(f"[Sampler] Failed to register Drumbo page: {exc}")
			showlog.error(traceback.format_exc())

		showlog.info("[Sampler] Drumbo registered via SamplerPlugin shell")

	@property
	def active_instrument(self) -> Drumbo:
		return self._active_instrument

	@property
	def instrument_context(self) -> InstrumentContext | None:
		return self._instrument_context


# Maintain legacy convenience exports for migration safety.
Plugin = SamplerPlugin
ActiveInstrument = DrumboInstrument
