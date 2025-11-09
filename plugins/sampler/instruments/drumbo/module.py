"""Sampler-native Drumbo instrument implementation."""

from __future__ import annotations

import copy
import importlib
import inspect
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Set, Tuple

import showlog
from system.module_core import ModuleBase

from plugins.sampler.core.engine import InstrumentContext, InstrumentModule
from plugins.sampler.core.event_bridge import EventBridge, NullEventBridge, SamplerEvent
from plugins.sampler.core.mixer_facade import MixerFacade, NullMixerFacade
from plugins.sampler.core.preset_facade import PresetFacade, NullPresetFacade
from plugins.sampler.core.services.sample_loader import (
	LegacySampleLoader,
	MixerStatus,
	SampleLoadResult,
)
from plugins.sampler.core.utils import normalize_bank, parse_bool, parse_int
from plugins.sampler.core.slicer import AutoSlicerController, AutoSlicerWidget, SliceSet
from plugins.sampler.instruments.drumbo import config as drumbo_config
from plugins.sampler.instruments.drumbo.services.ui_service import LegacyUISyncService


class DrumboInstrument(ModuleBase, InstrumentModule):
	"""Sampler engine implementation of the Drumbo instrument."""

	MODULE_ID = "drumbo"
	PLUGIN_ID = "drumbo"
	STANDALONE = True
	page_id = "drumbo_main"
	page_label = "Drumbo (Main)"

	SAMPLE_ROOT = drumbo_config.SAMPLE_ROOT
	SAMPLE_FOLDERS = drumbo_config.SAMPLE_FOLDERS
	NOTE_MAP = drumbo_config.NOTE_MAP
	DEFAULT_METADATA_DIAL_VALUE = drumbo_config.DEFAULT_METADATA_DIAL_VALUE
	DEFAULT_AUDIO_DEVICE_KEYWORDS = drumbo_config.DEFAULT_AUDIO_DEVICE_KEYWORDS

	THEME = drumbo_config.THEME
	INIT_STATE = drumbo_config.INIT_STATE
	PRESET_STATE = drumbo_config.PRESET_STATE
	CUSTOM_WIDGET = drumbo_config.CUSTOM_WIDGET
	SLICER_WIDGET = drumbo_config.SLICER_WIDGET
	_MINI_DIAL_RADIUS = drumbo_config.MINI_DIAL_RADIUS
	GRID_LAYOUT = drumbo_config.GRID_LAYOUT
	DIAL_LAYOUT_HINTS = drumbo_config.DIAL_LAYOUT_HINTS

	DIAL_BANK_CONFIG = drumbo_config.DIAL_BANK_CONFIG
	BANK_SWITCH_NOTE_MAP = drumbo_config.BANK_SWITCH_NOTE_MAP
	BANK_SWITCH_ALLOWED_CHANNELS = getattr(drumbo_config, "BANK_SWITCH_ALLOWED_CHANNELS", set())
	BUTTONS = drumbo_config.BUTTONS
	SLOT_TO_CTRL = {
		**{idx + 1: ctrl_id for idx, ctrl_id in enumerate(drumbo_config.DIAL_BANK_CONFIG.get("A", {}).get("ctrl_ids", []))},
		**{idx + 9: ctrl_id for idx, ctrl_id in enumerate(drumbo_config.DIAL_BANK_CONFIG.get("B", {}).get("ctrl_ids", []))},
	}
	BANK_A_REGISTRY: Dict[str, dict] = copy.deepcopy(drumbo_config.BANK_A_REGISTRY)
	BANK_B_REGISTRY: Dict[str, dict] = copy.deepcopy(drumbo_config.BANK_B_REGISTRY)
	LABEL_TO_VARIABLE = dict(drumbo_config.LABEL_TO_VARIABLE)
	REGISTRY: Dict[str, dict] = copy.deepcopy(drumbo_config.BANK_A_REGISTRY)

	_EVENT_ALIAS: Dict[str, str] = {
		"sampler.note_on": "note",
		"sampler.midi.note": "note",
		"note_on": "note",
		"midi.note_on": "note",
		"midi.note": "note",
		"sampler.dial_change": "dial",
		"sampler.dial.update": "dial",
		"sampler.dial": "dial",
		"dial_change": "dial",
		"dial.update": "dial",
		"sampler.button": "button",
		"sampler.button_press": "button",
		"button": "button",
		"button_press": "button",
		"sampler.preset_loaded": "preset",
		"sampler.preset.load": "preset",
		"preset_loaded": "preset",
		"preset.load": "preset",
		"sampler.bank.set": "bank",
		"sampler.bank": "bank",
		"sampler.activate_bank": "bank",
		"bank.set": "bank",
		"bank": "bank",
		"sampler.instrument.set": "instrument",
		"sampler.instrument": "instrument",
		"instrument.set": "instrument",
		"instrument": "instrument",
		"sampler.attach_widget": "widget",
		"sampler.widget.attach": "widget",
		"attach_widget": "widget",
	}

	def __init__(self) -> None:
		super().__init__()
		self.widget = None

		self.sample_root = Path(self.SAMPLE_ROOT) if self.SAMPLE_ROOT else Path()
		self._legacy_handle_cache: Dict[tuple[str, Optional[str]], Any] = {}
		self._legacy_module_base = None
		self._legacy_pygame = None

		self._mixer_facade: MixerFacade = NullMixerFacade()
		self._preset_facade: PresetFacade = NullPresetFacade()
		self._event_bridge: EventBridge = NullEventBridge()
		self._legacy_sample_loader = LegacySampleLoader(self)
		self._ui_service = LegacyUISyncService()
		self._auto_slicer = AutoSlicerController()
		self._auto_slicer.add_listener(self._handle_slice_set)
		self._latest_slice_set: SliceSet | None = None
		self._slicer_widget = None
		self._drumbo_widget = None
		self._widget_mode = "drumbo"
		self._auto_slicer_last_error: str | None = None
		self._dial_banks_visible = True

		self.sample_sets: Dict[str, dict] = {}
		self.sample_meta: Dict[str, dict] = {}
		self.sample_indices: Dict[str, dict] = {}
		self._sample_path_override: Dict[str, str] = {}
		self._metadata_specs: Dict[str, Any] = {}
		self._metadata_instrument_id: Optional[str] = None
		self._active_instrument_spec: Any = None
		self._metadata_presets: Dict[str, Any] = {}
		self._metadata_round_robin: Dict[str, Any] = {}
		self._missing_sample_paths: Set[str] = set()
		self._empty_sample_paths: Set[str] = set()

		default_bank = [int(self.DEFAULT_METADATA_DIAL_VALUE)] * 8
		self._instrument_bank_values: Dict[str, Dict[str, list[int]]] = {
			"snare": {"A": list(default_bank), "B": list(default_bank)},
			"kick": {"A": list(default_bank), "B": list(default_bank)},
		}

		self.button_states: Dict[str, int] = {"1": 0, "2": 0, "3": 0}
		self.current_instrument = "snare"
		self.current_bank = "A"
		self.REGISTRY = copy.deepcopy(self.BANK_A_REGISTRY)

		for idx in range(1, 17):
			setattr(self, f"mic_{idx}_level", int(self.DEFAULT_METADATA_DIAL_VALUE))

		self.master_volume = 127
		self.round_robin_index = 0
		self.round_robin_cycle_size = 1

		self.preset_instrument = "snare"
		self.preset_bank_a_values = list(default_bank)
		self.preset_bank_b_values = list(default_bank)

		self._audio_config_loaded = False
		self._audio_config_module = None
		self._audio_pref_cache = None
		self._output_device_cache = None

		self._mixer_ready = False
		self._mixer_failed = False
		self._mixer_warned = False
		self._mixer_device: Optional[str] = None
		self._mixer_channel_count = 0
		self._forced_reinit = False
		self._mixer_init_kwargs_cache = None

		self._last_mixer_status: MixerStatus | None = None
		self._last_sample_load_result: SampleLoadResult | None = None
		self._last_playback_facade_paths: list[str] = []
		self._last_playback_fallback_paths: list[str] = []

		self._instrument_context: InstrumentContext | None = None
		self._active = False

		self._event_handlers: Dict[str, Callable[[Dict[str, Any]], None]] = {
			"note": self._handle_note_event,
			"dial": self._handle_dial_event,
			"button": self._handle_button_event,
			"preset": self._handle_preset_event,
			"bank": self._handle_bank_event,
			"instrument": self._handle_instrument_event,
			"widget": self._handle_widget_event,
		}

		manager = None
		try:
			manager = self._ensure_bank_setup(default_bank=self.current_bank)
		except Exception as exc:
			showlog.warn(f"[Drumbo] Failed to initialize dial banks during __init__: {exc}")

		if not manager:
			try:
				module_base = self._get_module_base()
				manager = module_base.get_dial_bank_manager() if module_base else None
			except Exception:
				manager = None

		if manager:
			try:
				self._capture_instrument_values(self.current_instrument)
				snare_state = self._instrument_bank_values.get("snare", {})
				kick_state = self._instrument_bank_values.setdefault("kick", {"A": [0] * 8, "B": [0] * 8})
				kick_state["A"] = list(snare_state.get("A", [0] * 8))
				kick_state["B"] = list(snare_state.get("B", [0] * 8))
			except Exception as exc:
				showlog.warn(f"[Drumbo] Failed to capture initial instrument values: {exc}")
			self._refresh_widget_bank_refs(manager)

		self._update_preset_snapshot()
		self._push_button_states()
		showlog.info("[Drumbo] Module initialized")

	def _handle_slice_set(self, slice_set: SliceSet | None) -> None:
		"""Update cached slice metadata and refresh the slicer widget."""

		if slice_set is None:
			return
		self._latest_slice_set = slice_set
		self._auto_slicer_last_error = None
		self._update_slicer_widget()
		if self._widget_mode == "slicer":
			try:
				from pages import module_base
			except Exception as exc:  # pragma: no cover - defensive
				showlog.debug(f"[Drumbo] Slicer redraw skipped: {exc}")
			else:
				module_base.request_custom_widget_redraw(include_overlays=False)

	def _update_slicer_widget(self) -> None:
		if not self._slicer_widget:
			return
		try:
			self._slicer_widget.set_slice_set(self._latest_slice_set)
			if hasattr(self._slicer_widget, "mark_dirty"):
				self._slicer_widget.mark_dirty()
		except Exception as exc:  # pragma: no cover - defensive
			showlog.warn(f"[Drumbo] Failed to update slicer widget: {exc}")

	def _sync_existing_slice_sets(self) -> None:
		try:
			existing = list(self._auto_slicer.discover_processed())
		except Exception as exc:  # pragma: no cover - defensive
			showlog.debug(f"[Drumbo] discover_processed failed: {exc}")
			return
		if not existing:
			return

		def _created_at_key(item):
			created = getattr(item, "created_at", None)
			if hasattr(created, "timestamp"):
				try:
					return created.timestamp()
				except Exception:
					return 0.0
			return 0.0

		latest = max(existing, key=_created_at_key)
		self._handle_slice_set(latest)

	def _ensure_auto_slicer_ready(self, *, process_pending: bool = False) -> None:
		try:
			if process_pending:
				processed = self._auto_slicer.process_pending()
				if processed:
					self._handle_slice_set(processed[-1])
			if not self._latest_slice_set:
				self._sync_existing_slice_sets()
			last_error = self._auto_slicer.get_last_error()
			if last_error:
				self._auto_slicer_last_error = last_error
			elif self._latest_slice_set:
				self._auto_slicer_last_error = None
		except Exception as exc:  # pragma: no cover - defensive
			self._auto_slicer_last_error = str(exc)
			showlog.warn(f"[Drumbo] Auto-slicer refresh failed: {exc}")

	def _set_dial_banks_visible(self, visible: bool) -> None:
		visible_flag = bool(visible)
		self._dial_banks_visible = visible_flag
		manager = None
		try:
			manager = self._ensure_bank_setup(default_bank=self.current_bank)
		except Exception:
			manager = None
		if not manager:
			try:
				module_base = self._get_module_base()
			except Exception:
				module_base = None
			if module_base:
				try:
					manager = module_base.get_dial_bank_manager()
				except Exception:
					manager = None
		if not manager:
			return
		try:
			if hasattr(manager, "set_show_all_banks"):
				manager.set_show_all_banks(visible_flag)
		except Exception:
			pass
		for bank_key in ("A", "B"):
			try:
				manager.set_bank_visible(bank_key, visible_flag)
			except Exception:
				continue
		try:
			widgets_map = getattr(manager, "bank_widgets", {}) or {}
			for widgets in widgets_map.values():
				for widget in widgets:
					if hasattr(widget, "mark_dirty"):
						widget.mark_dirty()
		except Exception:
			pass
		try:
			from pages import module_base as module_base_mod
		except Exception:
			module_base_mod = None
		if module_base_mod and hasattr(module_base_mod, "request_custom_widget_redraw"):
			module_base_mod.request_custom_widget_redraw(include_overlays=True)

	def _show_widget_mode(self, mode: str, *, force: bool = False) -> None:
		target = "slicer" if str(mode or "").lower().startswith("s") else "drumbo"
		if not force and target == self._widget_mode:
			return
		if target == "slicer":
			self._ensure_auto_slicer_ready(process_pending=True)
		try:
			from pages import module_base
		except Exception as exc:  # pragma: no cover - defensive
			showlog.debug(f"[Drumbo] Widget mode switch skipped: {exc}")
			self._widget_mode = target
			return
		if target == "slicer":
			module_base.set_custom_widget_override(self.SLICER_WIDGET, include_overlays=True)
		else:
			module_base.clear_custom_widget_override(include_overlays=True)
			self._slicer_widget = None
		self._widget_mode = target
		try:
			self._set_dial_banks_visible(target == "drumbo")
		except Exception:
			pass

		state_value = 1 if target == "slicer" else 0
		self.button_states["3"] = state_value
		self._push_button_states()

	# ------------------------------------------------------------------
	# InstrumentModule lifecycle
	# ------------------------------------------------------------------

	def activate(self, context: InstrumentContext) -> None:
		"""Bind sampler services and allow the module to service events."""

		self._active = True
		self._instrument_context = context
		self.bind_instrument_context(context)
		self._show_widget_mode("drumbo", force=True)
		self._ensure_auto_slicer_ready(process_pending=False)
		try:
			self._ensure_bank_setup(default_bank=self.current_bank)
		except Exception as exc:  # pragma: no cover - defensive logging
			showlog.debug(f"[Drumbo] Bank setup during activate failed: {exc}")

	def deactivate(self) -> None:
		"""Release sampler services and reset any UI bindings."""

		self._active = False
		self.bind_instrument_context(None)
		self._show_widget_mode("drumbo", force=True)
		self._instrument_context = None
		if getattr(self, "widget", None) is not None:
			try:
				self.attach_widget(None)
			except Exception:  # pragma: no cover - defensive logging
				self.widget = None

	def handle_event(self, event: SamplerEvent) -> None:
		"""Translate sampler-layer events into Drumbo method calls."""

		event_type, payload = self._normalize_event(event)
		if not event_type:
			return

		alias = self._EVENT_ALIAS.get(event_type, event_type)
		handler = self._event_handlers.get(alias)
		if handler:
			handler(payload)
			return

		method_name = payload.pop("method", None)
		if method_name and hasattr(self, method_name):
			self._invoke_with_payload(getattr(self, method_name), payload)
			return

		canonical = event_type
		if canonical.startswith("sampler."):
			canonical = canonical[len("sampler.") :]
		canonical = canonical.replace(".", "_")

		for candidate in (canonical, f"on_{canonical}"):
			if hasattr(self, candidate):
				self._invoke_with_payload(getattr(self, candidate), payload)
				return

		showlog.debug(f"[Drumbo] Unhandled sampler event '{event_type}' payload={payload}")

	# ------------------------------------------------------------------
	# Legacy Drumbo functionality
	# ------------------------------------------------------------------

	def attach_widget(self, widget):
		"""Wire the Drumbo widget into the sampler-backed module."""

		if widget is None:
			if self._widget_mode == "slicer":
				self._slicer_widget = None
			else:
				self._drumbo_widget = None
				self.widget = None
			return

		if isinstance(widget, AutoSlicerWidget):
			self._slicer_widget = widget
			setattr(widget, "_module", self)
			self._update_slicer_widget()
			return

		self._drumbo_widget = widget
		self.widget = widget
		setattr(widget, "_module", self)

		manager = None
		try:
			manager = self._ensure_bank_setup(default_bank=self.current_bank)
		except Exception as exc:
			showlog.warn(f"[Drumbo] Failed to ensure dial banks during attach_widget: {exc}")

		if not manager:
			try:
				module_base = self._get_module_base()
				manager = module_base.get_dial_bank_manager() if module_base else None
			except Exception:
				manager = None

		if widget is not None and manager:
			self._refresh_widget_bank_refs(manager)
			if hasattr(widget, "active_bank"):
				widget.active_bank = self.current_bank
			if hasattr(widget, "set_instrument"):
				try:
					widget.set_instrument(self.current_instrument)
				except Exception:
					setattr(widget, "current_instrument", self.current_instrument)
			if hasattr(widget, "mark_dirty"):
				try:
					widget.mark_dirty()
				except Exception:
					pass

		self._push_button_states()
		showlog.info("[Drumbo] Widget attached")

	def configure_sampler_facades(
		self,
		*,
		mixer: MixerFacade | None = None,
		presets: PresetFacade | None = None,
		events: EventBridge | None = None,
	) -> None:
		"""Attach mixer, preset, and event facades used by the sampler layer."""

		def _resolve(candidate, fallback_factory, required_attrs: tuple[str, ...]):
			"""Normalize callable/class facades while preserving proxy objects."""

			fallback = fallback_factory()
			if candidate is None:
				return fallback

			instance = candidate
			try:
				if inspect.isclass(candidate):
					instance = candidate()
				elif callable(candidate) and not all(hasattr(candidate, attr) for attr in required_attrs):
					instance = candidate()
			except Exception:
				return fallback

			if isinstance(instance, fallback.__class__):
				return fallback

			for attr in required_attrs:
				if hasattr(instance, attr):
					continue
				if hasattr(instance, "__getattr__") and not isinstance(instance, fallback.__class__):
					return instance
				return fallback

			return instance

		self._mixer_facade = _resolve(mixer, NullMixerFacade, ("ensure_ready", "play_sample"))
		self._preset_facade = _resolve(presets, NullPresetFacade, ("save_state", "load_state"))
		self._event_bridge = _resolve(events, NullEventBridge, ("publish",))

		showlog.info(f"[DEBUG] Mixer facade = {type(self._mixer_facade).__name__}")
		showlog.info(f"[DEBUG] Preset facade = {type(self._preset_facade).__name__}")
		showlog.info(f"[DEBUG] Event bridge = {type(self._event_bridge).__name__}")

		self._legacy_sample_loader = LegacySampleLoader(self)

		self.sample_sets = dict(self.sample_sets or {})
		self.sample_meta = dict(self.sample_meta or {})
		self.sample_indices = dict(self.sample_indices or {})
		self._sample_sets = self.sample_sets
		self._sample_meta = self.sample_meta
		self._sample_indices = self.sample_indices

	def bind_instrument_context(self, context: InstrumentContext | None) -> None:
		"""Bind the shared sampler context so facades resolve from the host shell."""

		self._instrument_context = context
		if context is None:
			return

		mixer = getattr(context, "mixer", None)
		presets = getattr(context, "presets", None)
		events = getattr(context, "events", None)

		self.configure_sampler_facades(mixer=mixer, presets=presets, events=events)

	def _load_legacy_handle(self, dotted_path: str, attr_name: str | None = None):
		"""Import a legacy module or attribute on demand for compatibility paths."""

		if not dotted_path:
			return None

		cache_key = (dotted_path, attr_name)
		cached = self._legacy_handle_cache.get(cache_key)
		if cache_key in self._legacy_handle_cache:
			return cached

		try:
			module = importlib.import_module(dotted_path)
		except Exception:
			self._legacy_handle_cache[cache_key] = None
			return None

		if attr_name:
			value = getattr(module, attr_name, None)
		else:
			value = module

		self._legacy_handle_cache[cache_key] = value
		return value

	def _get_module_base(self):
		"""Lazily import the legacy module_base so dial helpers keep functioning."""

		if self._legacy_module_base is None:
			self._legacy_module_base = self._load_legacy_handle("pages.module_base")
		return self._legacy_module_base

	def _get_pygame(self):
		"""Lazily import pygame for legacy mixer and widget fallbacks."""

		if self._legacy_pygame is None:
			self._legacy_pygame = self._load_legacy_handle("pygame")
		return self._legacy_pygame

	def _get_pygame_mixer(self):
		pygame_mod = self._get_pygame()
		if not pygame_mod:
			return None
		return getattr(pygame_mod, "mixer", None)

	def _ensure_mixer(self) -> bool:
		"""Prime the mixer facade, falling back to the legacy pygame loader when needed."""

		if self._mixer_failed:
			return False

		try:
			if self._mixer_facade.ensure_ready():
				self._mixer_ready = True
				self._mixer_failed = False
				self._mixer_warned = False
				self._last_mixer_status = MixerStatus(ready=True, selected_device=None, used_fallback=False)
				return True
		except Exception as exc:
			showlog.warn(f"[Drumbo] Mixer facade ensure_ready failed: {exc}")

		status = self._legacy_sample_loader.ensure_mixer()
		self._last_mixer_status = status

		if status.ready:
			if status.selected_device:
				self._mixer_device = status.selected_device
			self._mixer_ready = True
			self._mixer_failed = False
			self._mixer_warned = False
			if status.used_fallback:
				showlog.debug("[Drumbo] Mixer ready via legacy pygame fallback")
			return True

		self._mixer_ready = False
		self._mixer_failed = True
		if status.message and not self._mixer_warned:
			showlog.warn(f"[Drumbo] Legacy mixer unavailable: {status.message}")
			self._mixer_warned = True
		return False

	def _load_samples_for(self, instrument: str) -> bool:
		"""Load samples using metadata overrides, falling back to pygame readers."""

		instrument_key = (instrument or "").lower()
		if instrument_key not in self.SAMPLE_FOLDERS:
			return False

		result = self._legacy_sample_loader.load_samples_for(instrument_key)
		self._last_sample_load_result = result
		return bool(result.loaded)

	def _play_sample(self, instrument: str, velocity: int, note_ts: float | None = None) -> bool:
		"""Attempt playback through the mixer facade before deferring to pygame fallback."""

		instrument_key = (instrument or "").lower()
		if instrument_key not in self.SAMPLE_FOLDERS:
			return False

		if velocity <= 0:
			return False

		if not self._ensure_mixer():
			return False

		if not self._load_samples_for(instrument_key):
			return False

		facade_instance = None if isinstance(self._mixer_facade, NullMixerFacade) else self._mixer_facade
		playback = self._legacy_sample_loader.play_samples(instrument_key, velocity, note_ts, facade_instance)
		self._last_playback_facade_paths = playback.facade_paths
		self._last_playback_fallback_paths = playback.fallback_paths

		if playback.facade_paths and playback.fallback_paths:
			showlog.info(
				"[Drumbo] Sample playback split between mixer facade and pygame fallback",
			)
		elif playback.facade_paths:
			showlog.info("[Drumbo] Sample playback routed through mixer facade")
		elif playback.fallback_paths:
			showlog.info("[Drumbo] Sample playback routed through pygame fallback")

		if self.widget and playback.played:
			try:
				self.widget.mark_dirty()
			except Exception:
				pass

		return bool(playback.played)

	def on_dial_change(self, dial_label: str, value: int):
		"""Handle dial changes - update widget's mic dials based on active bank."""

		showlog.debug(f"*[Drumbo] Dial '{dial_label}' changed to {value}")

		if not self.widget or not hasattr(self.widget, "mic_dials_row_1"):
			return

		label = (dial_label or "").strip().upper()
		if not label.startswith("M"):
			return

		try:
			mic_number = int(label[1:])
		except ValueError:
			showlog.debug(f"[Drumbo] Ignoring dial change with unparsable label '{dial_label}'")
			return

		self._apply_mic_value(
			mic_number,
			int(value),
			label,
			mark_dirty=True,
			update_snapshot=True,
			log_debug=True,
			allow_headless=False,
		)

	def on_button(self, btn_id: str, state_index: int = 0, state_data: dict = None):
		"""Handle button presses."""

		showlog.info(f"[Drumbo] Button {btn_id} pressed, state={state_index}")

		if btn_id == "1":
			target_instrument = "snare" if state_index == 0 else "kick"
			showlog.info(f"[Drumbo] Switched to {target_instrument.upper()}")
			self._set_instrument(target_instrument)
			self._show_widget_mode("drumbo", force=True)

		elif btn_id == "2":
			target_label = None
			if state_data and isinstance(state_data, dict):
				target_label = state_data.get("label")
			if target_label is None:
				target_label = "A" if state_index == 0 else "B"

			bank_key = (target_label or "A").strip().upper()
			if bank_key not in {"A", "B"}:
				bank_key = "A" if state_index == 0 else "B"

			self._activate_bank(bank_key)

		elif btn_id == "3":
			mode = "slicer" if state_index else "drumbo"
			self._show_widget_mode(mode, force=True)

	def on_midi_note(self, note: int, velocity: int, channel: int = None):
		"""Route MIDI events through bank switching, mixer facade playback, and fallbacks."""

		note_int = int(note)
		showlog.debug(f"*[Drumbo] MIDI note received note={note_int} velocity={velocity} channel={channel}")
		bank_target = self.BANK_SWITCH_NOTE_MAP.get(note_int)
		if bank_target:
			allowed_channels = getattr(self, "BANK_SWITCH_ALLOWED_CHANNELS", set())
			channel_matches = True
			if allowed_channels:
				try:
					ch_val = int(channel) if channel is not None else None
				except (TypeError, ValueError):
					ch_val = None
				if ch_val is not None and ch_val not in allowed_channels:
					channel_matches = False
					showlog.debug(
						f"*[Drumbo] Bank hotkey ignored: channel {ch_val} not in {sorted(allowed_channels)}"
					)
			if channel_matches:
				try:
					trigger_velocity = int(velocity)
				except (TypeError, ValueError):
					trigger_velocity = 0

				if trigger_velocity > 0:
					showlog.info(f"[Drumbo] MIDI note {note_int} (ch={channel}) → bank {bank_target}")
					showlog.debug(f"*[Drumbo] Activating bank {bank_target} from MIDI note {note_int}")
					self._activate_bank(bank_target)
				else:
					showlog.debug(
						f"*[Drumbo] Bank hotkey note {note_int} ignored: velocity {trigger_velocity}"
					)
				return True
			else:
				showlog.debug(
					f"*[Drumbo] MIDI note {note_int} matched bank hotkey but channel gate failed"
				)

		event_ts = time.perf_counter()
		if velocity <= 0:
			return False

		instrument_from_note = self._resolve_instrument(note)
		target_instrument = instrument_from_note or self.current_instrument or "snare"

		played = self._play_sample(target_instrument, velocity, event_ts)
		if not played:
			showlog.debug(f"[Drumbo] No sample played for instrument '{target_instrument}'")

		try:
			velocity_int = int(velocity)
		except (TypeError, ValueError):
			velocity_int = 0

		try:
			sampler_event = {
				"type": "sampler.note_on",
				"module": self.MODULE_ID,
				"note": note_int,
				"velocity": velocity_int,
				"channel": channel,
				"instrument": target_instrument,
				"played": bool(played),
				"timestamp": event_ts,
			}
			self._event_bridge.publish(sampler_event)
		except Exception:
			pass

		if instrument_from_note:
			self._set_instrument(instrument_from_note)

		if self.widget and hasattr(self.widget, "on_midi_note"):
			try:
				self.widget.on_midi_note(note, velocity)
			except Exception as exc:
				showlog.warn(f"[Drumbo] Widget MIDI note hook failed: {exc}")

		return True

	def _activate_bank(self, bank_key: str):
		"""Coordinate state changes for a specific dial bank."""

		self._ui_service.activate_bank(self, bank_key)

	def _switch_to_bank_a(self):
		self._activate_bank("A")

	def _switch_to_bank_b(self):
		self._activate_bank("B")

	def _slot_map_for_bank(self, bank_key: str) -> dict:
		bank = self.DIAL_BANK_CONFIG.get(bank_key)
		if not bank:
			return {}
		return {idx + 1: ctrl_id for idx, ctrl_id in enumerate(bank.get("ctrl_ids", []))}

	def _get_bank_config(self):
		return copy.deepcopy(self.DIAL_BANK_CONFIG)

	def _ensure_bank_setup(self, default_bank: str = None):
		return self._ui_service.ensure_bank_setup(self, default_bank)

	def _refresh_widget_bank_refs(self, manager=None):
		self._ui_service.refresh_widget_bank_refs(self, manager)

	def _push_button_states(self):
		self._ui_service.push_button_states(self)

	def _resolve_metadata_slot(self, spec) -> str:
		category = getattr(spec, "category", None)
		if category:
			slot = str(category).strip().lower()
			if slot in {"snare", "kick"}:
				return slot
		current = (self.current_instrument or "snare").strip().lower()
		return current if current in {"snare", "kick"} else "snare"

	def _update_sample_override(self, slot: str, spec) -> None:
		samples_path = getattr(spec, "samples_path", None)
		if not samples_path:
			return
		base_path = Path(samples_path)
		self._sample_path_override[slot] = str(base_path)
		path_str = str(base_path)
		self._missing_sample_paths.discard(path_str)
		self._empty_sample_paths.discard(path_str)
		self.sample_sets[slot] = {}
		self.sample_meta[slot] = {}
		self.sample_indices[slot] = {}

	def _apply_metadata_bank(self, bank_spec, manager, label_map):
		bank_key = str(getattr(bank_spec, "id", "") or "").strip().upper()
		widgets = manager.bank_widgets.get(bank_key) if manager else None
		if not bank_key or not widgets:
			return None

		values = [int(getattr(widget.dial, "value", 0)) for widget in widgets]
		used_slots = set()
		slot_ranges = {}
		module_entry = {"type": "module"}

		for dial_spec in (getattr(bank_spec, "dials", None) or []):
			slot_raw = getattr(dial_spec, "slot", None)
			try:
				slot = int(slot_raw)
			except (TypeError, ValueError):
				continue
			if slot <= 0:
				continue
			index = slot - 1
			if index >= len(widgets):
				showlog.debug(f"*[Drumbo] Bank {bank_key} ignoring slot {slot} (index out of range)")
				continue

			widget = widgets[index]
			dial = widget.dial
			label = str(getattr(dial_spec, "label", "") or "").strip() or f"Slot {slot}"
			rng = getattr(dial_spec, "range", None) or (0, 127)
			try:
				lo = int(rng[0])
				hi = int(rng[1])
			except (TypeError, ValueError, IndexError):
				lo, hi = 0, 127
			if lo > hi:
				lo, hi = hi, lo
			dial.range = [lo, hi]
			dial.label = label
			dial.custom_label_text = label
			dial.custom_label_upper = True
			dial.cached_surface = None

			default_value = getattr(dial_spec, "default", None)
			if default_value is None:
				current_value = int(getattr(dial, "value", 0))
			else:
				try:
					current_value = int(default_value)
				except (TypeError, ValueError):
					current_value = int(getattr(dial, "value", 0))
			safe_value = int(max(lo, min(hi, current_value)))
			try:
				dial.set_value(safe_value)
			except Exception:
				dial.value = safe_value
			values[index] = safe_value
			used_slots.add(slot)
			slot_ranges[slot] = (lo, hi)

			variable = str(getattr(dial_spec, "variable", "") or "").strip()
			if variable:
				label_map[label.upper()] = variable
				module_entry[f"{slot:02d}"] = {
					"label": label,
					"range": [lo, hi],
					"type": "raw",
					"default_slot": slot,
					"family": "drumbo",
					"variable": variable,
				}

			color = getattr(dial_spec, "color", None)
			if color:
				dial.label_text_color_override = color
			elif hasattr(dial, "label_text_color_override"):
				dial.label_text_color_override = None

			try:
				widget.mark_dirty()
			except Exception:
				pass

			try:
				dial.set_visual_mode("default")
			except ValueError:
				dial.visual_mode = "default"

		fallback_level = int(max(0, min(127, getattr(self, "DEFAULT_METADATA_DIAL_VALUE", 100))))
		if used_slots:
			any_non_zero = any(
				values[slot - 1] > 0 for slot in used_slots if 0 <= (slot - 1) < len(values)
			)
			if not any_non_zero:
				for slot in used_slots:
					index = slot - 1
					if index >= len(widgets):
						continue
					lo, hi = slot_ranges.get(slot, (0, 127))
					fallback_value = int(max(lo, min(hi, fallback_level)))
					dial = widgets[index].dial
					try:
						dial.set_value(fallback_value)
					except Exception:
						dial.value = fallback_value
					values[index] = fallback_value
					try:
						widgets[index].mark_dirty()
					except Exception:
						pass

		default_registry = self.BANK_A_REGISTRY if bank_key == "A" else self.BANK_B_REGISTRY
		default_entries = (
			default_registry.get("drumbo", {}) if isinstance(default_registry, dict) else {}
		)

		for idx, widget in enumerate(widgets):
			slot_index = idx + 1
			dial = widget.dial
			if slot_index in used_slots:
				continue

			registry_key = f"{slot_index:02d}"
			default_meta = default_entries.get(registry_key, {})
			mic_number = slot_index if bank_key == "A" else slot_index + 8
			default_label = str(default_meta.get("label", getattr(dial, "label", "")) or f"M{mic_number}")
			default_variable = default_meta.get("variable") or f"mic_{mic_number}_level"

			dial.label = default_label
			dial.custom_label_text = default_label
			dial.custom_label_upper = True
			dial.cached_surface = None

			label_map.setdefault(default_label.upper(), default_variable)
			module_entry[registry_key] = {
				"label": default_label,
				"range": list(default_meta.get("range", [0, 127])),
				"type": default_meta.get("type", "raw"),
				"default_slot": slot_index,
				"family": default_meta.get("family", "drumbo"),
				"variable": default_variable,
			}

			try:
				dial.set_visual_mode("default")
			except ValueError:
				dial.visual_mode = "default"

			fallback_value = int(max(0, min(127, fallback_level)))
			if idx >= len(values):
				values.append(fallback_value)
			values[idx] = fallback_value

			try:
				widget.mark_dirty()
			except Exception:
				pass

		return bank_key, values, {"drumbo": module_entry}

	def load_instrument_from_spec(self, spec):
		"""Apply instrument metadata discovered by the scanner service."""

		if spec is None:
			showlog.warn("*[Drumbo] load_instrument_from_spec called with None")
			return False

		instrument_id = getattr(spec, "id", None)
		display_name = getattr(spec, "display_name", None) or instrument_id
		showlog.info(f"[Drumbo] Metadata instrument selected → {instrument_id}")
		showlog.debug(
			f"*[Drumbo] load_instrument_from_spec display='{display_name}' category={getattr(spec, 'category', None)}"
		)

		self._metadata_instrument_id = instrument_id
		self._active_instrument_spec = spec

		manager = None
		try:
			manager = self._ensure_bank_setup()
		except Exception as exc:
			showlog.warn(f"*[Drumbo] Bank manager unavailable during metadata load: {exc}")
			manager = None

		slot = self._resolve_metadata_slot(spec)
		self._metadata_specs[slot] = spec

		base_label_map = dict(getattr(type(self), "LABEL_TO_VARIABLE", {}))
		label_map = dict(base_label_map)
		bank_defaults: Dict[str, list[int]] = {}
		registry_map: Dict[str, dict] = {}
		processed_banks: Set[str] = set()

		banks = list(getattr(spec, "banks", []) or [])

		if manager:
			for bank_spec in banks:
				result = self._apply_metadata_bank(bank_spec, manager, label_map)
				if not result:
					continue
				bank_key, values, registry = result
				processed_banks.add(bank_key)
				normalized = normalize_bank(values)
				bank_defaults[bank_key] = list(normalized)
				if registry:
					registry_map[bank_key] = registry
				manager.bank_values[bank_key] = list(normalized)

			available_banks = set(getattr(manager, "bank_widgets", {}).keys())
			for bank_key in available_banks - processed_banks:
				try:
					manager.set_bank_visible(bank_key, False)
				except Exception:
					pass
				zero_count = len(manager.bank_widgets.get(bank_key, []))
				bank_defaults[bank_key] = [0] * zero_count
				manager.bank_values[bank_key] = [0] * zero_count
		else:
			for bank_spec in banks:
				bank_key = str(getattr(bank_spec, "id", "") or "").strip().upper()
				if not bank_key:
					continue
				module_entry = {"type": "module"}
				values: list[int] = []
				used_slots = set()
				slot_ranges = {}
				for dial_spec in (getattr(bank_spec, "dials", None) or []):
					slot_raw = getattr(dial_spec, "slot", None)
					try:
						slot_index = int(slot_raw)
					except (TypeError, ValueError):
						continue
					if slot_index <= 0:
						continue
					label = str(getattr(dial_spec, "label", "") or "").strip() or f"Slot {slot_index}"
					rng = getattr(dial_spec, "range", None) or (0, 127)
					try:
						lo = int(rng[0])
						hi = int(rng[1])
					except (TypeError, ValueError, IndexError):
						lo, hi = 0, 127
					if lo > hi:
						lo, hi = hi, lo
					default_value = getattr(dial_spec, "default", None)
					try:
						raw_default = int(default_value) if default_value is not None else 0
					except (TypeError, ValueError):
						raw_default = 0
					safe_value = int(max(lo, min(hi, raw_default)))
					while len(values) < slot_index:
						values.append(0)
					values[slot_index - 1] = safe_value
					used_slots.add(slot_index)
					slot_ranges[slot_index] = (lo, hi)
					variable = str(getattr(dial_spec, "variable", "") or "").strip()
					if variable:
						label_map[label.upper()] = variable
						module_entry[f"{slot_index:02d}"] = {
							"label": label,
							"range": [lo, hi],
							"type": "raw",
							"default_slot": slot_index,
							"family": "drumbo",
							"variable": variable,
						}

				default_registry = self.BANK_A_REGISTRY if bank_key == "A" else self.BANK_B_REGISTRY
				default_entries = (
					default_registry.get("drumbo", {}) if isinstance(default_registry, dict) else {}
				)
				for slot_index in range(1, 9):
					registry_key = f"{slot_index:02d}"
					if slot_index in used_slots:
						continue
					default_meta = default_entries.get(registry_key, {})
					mic_number = slot_index if bank_key == "A" else slot_index + 8
					default_label = str(default_meta.get("label", f"M{mic_number}"))
					default_variable = default_meta.get("variable") or f"mic_{mic_number}_level"
					label_map.setdefault(default_label.upper(), default_variable)
					module_entry[registry_key] = {
						"label": default_label,
						"range": list(default_meta.get("range", [0, 127])),
						"type": default_meta.get("type", "raw"),
						"default_slot": slot_index,
						"family": default_meta.get("family", "drumbo"),
						"variable": default_variable,
					}
					while len(values) < slot_index:
						values.append(0)
					values[slot_index - 1] = int(
						max(0, min(127, getattr(self, "DEFAULT_METADATA_DIAL_VALUE", 100)))
					)

				if used_slots:
					any_non_zero = any(
						values[slot - 1] > 0 for slot in used_slots if 0 <= (slot - 1) < len(values)
					)
					if not any_non_zero:
						fallback_level = int(
							max(0, min(127, getattr(self, "DEFAULT_METADATA_DIAL_VALUE", 100)))
						)
						for slot_index in used_slots:
							idx = slot_index - 1
							if idx >= len(values):
								continue
							lo, hi = slot_ranges.get(slot_index, (0, 127))
							values[idx] = int(max(lo, min(hi, fallback_level)))

				if values:
					bank_defaults[bank_key] = list(normalize_bank(values))
				registry_map[bank_key] = {"drumbo": module_entry}

		if label_map:
			base_label_map.update(label_map)
			self.LABEL_TO_VARIABLE = base_label_map

		if registry_map.get("A"):
			self.BANK_A_REGISTRY = registry_map["A"]
		if registry_map.get("B"):
			self.BANK_B_REGISTRY = registry_map["B"]

		self._update_sample_override(slot, spec)
		self._metadata_presets[slot] = getattr(spec, "presets", None)
		try:
			self._metadata_round_robin[slot] = dict(getattr(spec, "round_robin", {}) or {})
		except Exception:
			self._metadata_round_robin[slot] = {}

		state = self._instrument_bank_values.setdefault(slot, {"A": [0] * 8, "B": [0] * 8})
		for bank_key in ("A", "B"):
			if bank_key in bank_defaults:
				state[bank_key] = list(normalize_bank(bank_defaults[bank_key]))
			else:
				state[bank_key] = [0] * 8

		self._set_instrument(slot, force_apply=True)

		if manager:
			self._refresh_widget_bank_refs(manager)

		try:
			self._activate_bank(self.current_bank or "A")
		except Exception as exc:
			showlog.warn(f"*[Drumbo] Bank activation failed after metadata load: {exc}")

		if self.widget:
			try:
				self.widget.current_instrument = display_name or instrument_id or "—"
				self.widget.mark_dirty()
			except Exception as exc:
				showlog.warn(f"*[Drumbo] Failed to update widget instrument label: {exc}")

		self._update_preset_snapshot()
		return True

	def _load_preset_facade_state(self) -> Dict[str, Any]:
		try:
			state = self._preset_facade.load_state(self.MODULE_ID)
		except Exception:
			return {}

		if isinstance(state, dict):
			return dict(state)

		try:
			return dict(state)
		except Exception:
			return {}

	def _save_preset_facade_state(self, snapshot: Dict[str, Any]) -> None:
		try:
			self._preset_facade.save_state(self.MODULE_ID, snapshot)
		except Exception:
			pass

	def _update_preset_snapshot(self):
		current = (self.current_instrument or "snare").strip().lower()
		if current not in self._instrument_bank_values:
			current = "snare"

		for instrument in ("snare", "kick"):
			state = self._instrument_bank_values.setdefault(
				instrument, {"A": [0] * 8, "B": [0] * 8}
			)
			state["A"] = normalize_bank(state.get("A"))
			state["B"] = normalize_bank(state.get("B"))

		state = self._instrument_bank_values[current]
		self.preset_instrument = current
		self.preset_bank_a_values = state["A"][:]
		self.preset_bank_b_values = state["B"][:]

		snapshot = {
			"preset_instrument": self.preset_instrument,
			"preset_bank_a_values": list(self.preset_bank_a_values),
			"preset_bank_b_values": list(self.preset_bank_b_values),
		}
		self._save_preset_facade_state(snapshot)

	def _capture_instrument_values(self, instrument: str):
		instrument_key = (instrument or "snare").strip().lower()
		if instrument_key not in self._instrument_bank_values:
			return
		try:
			module_base = self._get_module_base()
			if not module_base:
				showlog.warn("[Drumbo] module_base unavailable during dial capture")
				return
			module_base.capture_active_dial_bank_values()
			for bank_key in ("A", "B"):
				values = module_base.get_dial_bank_values(bank_key)
				if values:
					self._instrument_bank_values[instrument_key][bank_key] = list(values[:8])
			self._update_preset_snapshot()
		except Exception as exc:
			showlog.warn(f"[Drumbo] Failed to capture {instrument_key} dial state: {exc}")

	def _apply_instrument_values(self, instrument: str):
		instrument_key = (instrument or "snare").strip().lower()
		facade_state = self._load_preset_facade_state()
		if facade_state:
			persisted_instrument = (facade_state.get("preset_instrument") or "").strip().lower()
			if persisted_instrument in {"snare", "kick"}:
				state_entry = self._instrument_bank_values.setdefault(
					persisted_instrument, {"A": [0] * 8, "B": [0] * 8}
				)
				bank_a = facade_state.get("preset_bank_a_values")
				bank_b = facade_state.get("preset_bank_b_values")
				if bank_a is not None:
					state_entry["A"] = normalize_bank(bank_a)
				if bank_b is not None:
					state_entry["B"] = normalize_bank(bank_b)

		bank_map = self._instrument_bank_values.get(instrument_key)
		if not bank_map:
			return
		try:
			module_base = self._get_module_base()
			if not module_base:
				showlog.warn("[Drumbo] module_base unavailable during dial restore")
				return
			for bank_key, values in bank_map.items():
				module_base.set_dial_bank_values(bank_key, list(values))
			self._update_preset_snapshot()
		except Exception as exc:
			showlog.warn(f"[Drumbo] Failed to apply {instrument_key} dial state: {exc}")

	def _replay_loaded_dials(self, instrument: str):
		self._ui_service.replay_loaded_dials(self, instrument)

	def _apply_mic_value(
		self,
		mic_number: int,
		value: int,
		label: str,
		*,
		mark_dirty: bool = True,
		update_snapshot: bool = True,
		log_debug: bool = False,
		allow_headless: bool = False,
		instrument_key_override: str = None,
	) -> bool:
		return self._ui_service.apply_mic_value(
			self,
			mic_number,
			value,
			label,
			mark_dirty=mark_dirty,
			update_snapshot=update_snapshot,
			log_debug=log_debug,
			allow_headless=allow_headless,
			instrument_key_override=instrument_key_override,
		)

	def _set_instrument(self, instrument: str, force_apply: bool = False):
		self._ui_service.set_instrument(self, instrument, force_apply=force_apply)

	def _position_mini_dials(self, manager):
		self._ui_service.position_mini_dials(self, manager)

	def prepare_preset_save(self):
		"""Sync dial banks and instrument values prior to invoking the preset facade."""

		try:
			module_base = self._get_module_base()
			if module_base:
				module_base.capture_active_dial_bank_values()
			else:
				showlog.debug("[Drumbo] module_base unavailable before preset save; skipping capture")
		except Exception as exc:
			showlog.debug(f"[Drumbo] capture_active_dial_bank_values failed before save: {exc}")
		self._capture_instrument_values(self.current_instrument)
		self._update_preset_snapshot()

	def get_preset_variant_suffix(self):
		return (self.current_instrument or "snare").strip().lower()

	def normalize_preset_name(self, raw_name: str) -> str:
		safe = (raw_name or "").strip()
		if not safe:
			return safe

		if safe.lower().endswith(".json"):
			safe = safe[:-5]

		suffix = (self.get_preset_variant_suffix() or "").strip().lower()
		if not suffix:
			return safe

		parts = safe.split(".") if safe else []
		known_variants = {name.lower() for name in self._instrument_bank_values.keys()}

		if parts and parts[-1].lower() == suffix:
			return safe

		if parts and parts[-1].lower() in known_variants:
			parts = parts[:-1]

		parts.append(suffix)
		return ".".join(part for part in parts if part)

	def on_preset_loaded(self, variables, widget_state=None):
		"""Merge persisted preset state from the facade and replay legacy dial values."""

		data = variables or {}
		widget_state = widget_state or {}

		if isinstance(data, dict):
			data = dict(data)
		elif not hasattr(data, "get"):
			data = {}

		facade_state = self._load_preset_facade_state()
		if facade_state:
			merged = dict(facade_state)
			try:
				merged.update(data)
			except Exception:
				try:
					merged.update(dict(data))
				except Exception:
					merged.update({})
			data = merged

		saved_instrument = (
			data.get("preset_instrument")
			or widget_state.get("current_instrument")
			or data.get("current_instrument")
			or self.current_instrument
			or "snare"
		)
		saved_instrument = (saved_instrument or "snare").strip().lower()
		if saved_instrument not in {"snare", "kick"}:
			saved_instrument = "snare"

		preset_bank_a = data.get("preset_bank_a_values")
		preset_bank_b = data.get("preset_bank_b_values")

		for instrument in ("snare", "kick"):
			state = self._instrument_bank_values.setdefault(
				instrument, {"A": [0] * 8, "B": [0] * 8}
			)

			source_a = None
			source_b = None

			if instrument == saved_instrument:
				source_a = preset_bank_a
				source_b = preset_bank_b

			legacy_a = data.get(f"{instrument}_a_values")
			legacy_b = data.get(f"{instrument}_b_values")

			if source_a is None:
				source_a = legacy_a
			if source_b is None:
				source_b = legacy_b

			if source_a is not None:
				state["A"] = normalize_bank(source_a)
			if source_b is not None:
				state["B"] = normalize_bank(source_b)

		target = saved_instrument
		if not target:
			try:
				button_state = self.button_states.get("1") if isinstance(self.button_states, dict) else None
				if button_state == 1:
					target = "kick"
				elif button_state == 0:
					target = "snare"
			except Exception:
				target = None

		if target:
			self._set_instrument(target, force_apply=True)
			self._replay_loaded_dials(target)
		else:
			self._apply_instrument_values(self.current_instrument)
			self._replay_loaded_dials(self.current_instrument)

		self._push_button_states()
		self._update_preset_snapshot()

	def _parse_env_int(self, key: str):
		raw = os.environ.get(key)
		value = parse_int(key)
		if raw is not None and value is None:
			showlog.warn(f"[Drumbo] Ignoring non-integer {key}='{raw}'")
		return value

	def _parse_env_bool(self, key: str):
		raw = os.environ.get(key)
		value = parse_bool(key)
		if raw is None:
			return None
		if value is None:
			showlog.warn(f"[Drumbo] Ignoring non-boolean {key}='{raw}'")
		return value

	# ------------------------------------------------------------------
	# Sampler event handlers
	# ------------------------------------------------------------------

	def _handle_note_event(self, payload: Dict[str, Any]) -> None:
		note, velocity, channel = self._extract_note_payload(payload)
		if note is None:
			showlog.debug("[Drumbo] Ignoring note event without note value")
			return
		self.on_midi_note(note, velocity, channel)

	def _handle_dial_event(self, payload: Dict[str, Any]) -> None:
		label, value = self._extract_dial_payload(payload)
		if label is None or value is None:
			showlog.debug(f"[Drumbo] Ignoring dial event payload={payload}")
			return
		resolved = self._resolve_dial_label(label)
		self.on_dial_change(resolved, value)

	def _handle_button_event(self, payload: Dict[str, Any]) -> None:
		btn_id, state_index, state_data = self._extract_button_payload(payload)
		if btn_id is None:
			showlog.debug(f"[Drumbo] Ignoring button event payload={payload}")
			return
		self.button_states[str(btn_id)] = state_index
		self.on_button(str(btn_id), state_index, dict(state_data) if state_data else None)

	def _handle_preset_event(self, payload: Dict[str, Any]) -> None:
		variables, widget_state = self._extract_preset_payload(payload)
		self.on_preset_loaded(variables, widget_state)

	def _handle_bank_event(self, payload: Dict[str, Any]) -> None:
		bank_key = (
			payload.get("bank")
			or payload.get("id")
			or payload.get("label")
			or next(iter(payload.get("args", []) or []), None)
		)
		if bank_key is None:
			showlog.debug(f"[Drumbo] Ignoring bank event payload={payload}")
			return
		bank = str(bank_key).strip().upper()
		if bank not in {"A", "B"}:
			showlog.debug(f"[Drumbo] Unsupported bank '{bank}' in payload={payload}")
			return
		self._activate_bank(bank)

	def _handle_instrument_event(self, payload: Dict[str, Any]) -> None:
		target = (
			payload.get("instrument")
			or payload.get("id")
			or payload.get("name")
			or next(iter(payload.get("args", []) or []), None)
		)
		if target is None:
			showlog.debug(f"[Drumbo] Ignoring instrument event payload={payload}")
			return
		self._set_instrument(str(target), force_apply=bool(payload.get("force", False)))

	def _handle_widget_event(self, payload: Dict[str, Any]) -> None:
		widget = payload.get("widget")
		if widget is None and payload.get("args"):
			widget = payload["args"][0]
		self.attach_widget(widget)

	def _load_audio_config(self):
		if self._audio_config_loaded:
			return self._audio_config_module

		try:
			from config import audio as audio_config
		except Exception:
			audio_config = None

		self._audio_config_loaded = True
		self._audio_config_module = audio_config
		return audio_config

	def _resolve_instrument(self, note: int):
		for instrument, notes in self.NOTE_MAP.items():
			if note in notes:
				return instrument
		return None

	# ------------------------------------------------------------------
	# Event normalization helpers
	# ------------------------------------------------------------------

	@staticmethod
	def _normalize_event(event: SamplerEvent) -> Tuple[Optional[str], Dict[str, Any]]:
		if event is None:
			return None, {}

		if isinstance(event, dict):
			event_type = (
				event.get("type")
				or event.get("event")
				or event.get("action")
				or event.get("name")
			)
			if not event_type:
				return None, {}
			data = {
				key: value
				for key, value in event.items()
				if key not in {"type", "event", "action", "name"}
			}
			return str(event_type).lower(), data

		if isinstance(event, (list, tuple)) and event:
			event_type = str(event[0]).lower()
			if len(event) == 2 and isinstance(event[1], dict):
				payload = dict(event[1])
			else:
				payload = {"args": list(event[1:])}
			return event_type, payload

		if isinstance(event, str):
			return event.lower(), {}

		return None, {}

	@staticmethod
	def _extract_note_payload(payload: Dict[str, Any]) -> Tuple[Optional[int], int, Optional[int]]:
		args = payload.get("args") or ()
		note = payload.get("note")
		velocity = payload.get("velocity")
		channel = payload.get("channel")

		if note is None and args:
			note = args[0]
		if velocity is None and len(args) > 1:
			velocity = args[1]
		if channel is None and len(args) > 2:
			channel = args[2]

		try:
			note_int = int(note)
		except (TypeError, ValueError):
			return None, 0, None

		try:
			velocity_int = int(velocity) if velocity is not None else 0
		except (TypeError, ValueError):
			velocity_int = 0

		try:
			channel_int = int(channel) if channel is not None else None
		except (TypeError, ValueError):
			channel_int = None

		return note_int, velocity_int, channel_int

	@staticmethod
	def _extract_dial_payload(payload: Dict[str, Any]) -> Tuple[Optional[str], Optional[int]]:
		args = payload.get("args") or ()
		label = payload.get("label") or payload.get("dial_label")
		value = payload.get("value")

		if label is None and payload.get("slot") is not None:
			label = payload["slot"]
		if label is None and args:
			label = args[0]
		if value is None and len(args) > 1:
			value = args[1]

		if label is None:
			return None, None

		try:
			value_int = int(value) if value is not None else None
		except (TypeError, ValueError):
			value_int = None

		return str(label), value_int

	@staticmethod
	def _extract_button_payload(
		payload: Dict[str, Any]
	) -> Tuple[Optional[str], int, Optional[Mapping[str, Any]]]:
		args = payload.get("args") or ()
		button_id = payload.get("id") or payload.get("button") or payload.get("button_id")
		state_index = payload.get("state_index", 0)
		state_data = payload.get("state_data")

		if button_id is None and args:
			button_id = args[0]
		if state_index is None and len(args) > 1:
			state_index = args[1]
		if state_data is None and len(args) > 2:
			state_data = args[2]

		if button_id is None:
			return None, 0, None

		try:
			state_index_int = int(state_index)
		except (TypeError, ValueError):
			state_index_int = 0

		mapping = state_data if isinstance(state_data, Mapping) else None
		return str(button_id), state_index_int, mapping

	@staticmethod
	def _extract_preset_payload(
		payload: Dict[str, Any]
	) -> Tuple[Optional[Mapping[str, Any]], Optional[Mapping[str, Any]]]:
		args = payload.get("args") or ()
		variables = payload.get("variables")
		widget_state = payload.get("widget_state") or payload.get("state")

		if variables is None and args:
			variables = args[0]
		if widget_state is None and len(args) > 1:
			widget_state = args[1]

		if variables is not None and not isinstance(variables, Mapping):
			try:
				variables = dict(variables)  # type: ignore[arg-type]
			except Exception:
				variables = None

		if widget_state is not None and not isinstance(widget_state, Mapping):
			try:
				widget_state = dict(widget_state)  # type: ignore[arg-type]
			except Exception:
				widget_state = None

		return variables, widget_state

	def _resolve_dial_label(self, raw_label: str) -> str:
		label = (raw_label or "").strip()
		if not label:
			return label

		if not label.isdigit():
			return label

		try:
			slot_index = int(label)
		except ValueError:
			return label

		registry = self.REGISTRY if isinstance(self.REGISTRY, Mapping) else {}
		scoped = registry.get("drumbo") if isinstance(registry, Mapping) else None
		scoped = scoped if isinstance(scoped, Mapping) else {}
		entry = scoped.get(f"{slot_index:02d}") if isinstance(scoped, Mapping) else None
		resolved = entry.get("label") if isinstance(entry, Mapping) else None
		return str(resolved) if resolved else label

	@staticmethod
	def _invoke_with_payload(handler: Callable[..., Any], payload: Dict[str, Any]) -> None:
		try:
			code = handler.__code__  # type: ignore[attr-defined]
			arg_names = code.co_varnames[: code.co_argcount]
		except AttributeError:
			arg_names = ()

		kwargs: Dict[str, Any] = {}
		for name in arg_names:
			if name == "self":
				continue
			if name in payload:
				kwargs[name] = payload[name]

		try:
			handler(**kwargs)
		except TypeError:
			handler(*payload.get("args", []))
		except Exception as exc:  # pragma: no cover - defensive logging
			handler_name = getattr(handler, "__name__", handler.__class__.__name__)
			showlog.debug(f"[Drumbo] Handler '{handler_name}' raised during event dispatch: {exc}")


__all__ = ["DrumboInstrument"]
