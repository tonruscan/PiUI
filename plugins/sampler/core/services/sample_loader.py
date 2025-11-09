"""Shared helpers for sampler mixer coordination and sample loading."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Optional, Tuple

import showlog

from plugins.sampler.core.utils import extract_sample_tokens, match_device_by_name


@dataclass
class MixerStatus:
	"""Result metadata returned by legacy mixer preparation."""

	ready: bool
	selected_device: Optional[str] = None
	used_fallback: bool = False
	message: Optional[str] = None


@dataclass
class SampleLoadResult:
	"""Metadata describing the outcome of a sample load attempt."""

	loaded: bool
	total_files: int = 0
	usable_files: int = 0


@dataclass
class PlaybackResult:
	"""Breakdown of how a playback request was fulfilled."""

	played: bool
	facade_paths: List[str]
	fallback_paths: List[str]


class LegacySampleLoader:
	"""Encapsulates Drumbo's legacy pygame mixer and sample logic."""

	def __init__(self, instrument: Any) -> None:
		self._instrument = instrument

	def ensure_mixer(self) -> MixerStatus:
		instrument = self._instrument
		mixer_module = instrument._get_pygame_mixer()
		if mixer_module is None:
			return MixerStatus(ready=False, used_fallback=True, message="pygame mixer unavailable")

		try:
			mixer_kwargs, mixer_channels, allow_changes, force_reinit = self._get_mixer_init_kwargs()
		except Exception as exc:
			return MixerStatus(ready=False, used_fallback=True, message=str(exc))

		try:
			if mixer_module.get_init():
				actual = mixer_module.get_init()
				instrument._mixer_ready = True
				instrument._mixer_channel_count = mixer_module.get_num_channels()
				instrument._mixer_device = instrument._mixer_device or "external"
				if force_reinit and not instrument._forced_reinit:
					showlog.info("[Drumbo] Forcing mixer reinitialization with configured audio settings")
					showlog.debug("*[Drumbo] Forcing mixer reinitialization with configured audio settings")
					try:
						mixer_module.quit()
					except Exception as exc:
						showlog.warn(f"[Drumbo] Mixer quit during reinit request failed: {exc}")
					instrument._forced_reinit = True
				else:
					log_kwargs = {
						"device": instrument._mixer_device,
						"requested": mixer_kwargs,
						"allowedchanges": allow_changes,
						"actual": {
							"freq": actual[0] if actual else None,
							"format": actual[1] if actual else None,
							"channels": actual[2] if actual else None,
						},
						"mixer_channels": instrument._mixer_channel_count,
						"force_reinit": force_reinit,
					}
					showlog.info(
						"[Drumbo] Mixer already active; using existing configuration: "
						f"params={log_kwargs}. Set DRUMBO_FORCE_AUDIO_REINIT=1 to override."
					)
					showlog.debug(f"*[Drumbo] Mixer active params={log_kwargs}")
					return MixerStatus(ready=True, selected_device=instrument._mixer_device, used_fallback=True)

			if not mixer_module.get_init():
				mixer_kwargs, mixer_channels, allow_changes, force_reinit = self._get_mixer_init_kwargs()

			pre_init_kwargs = {
				"frequency": mixer_kwargs.get("freq"),
				"size": mixer_kwargs.get("size"),
				"channels": mixer_kwargs.get("channels"),
				"buffer": mixer_kwargs.get("buffer"),
			}
			init_kwargs = dict(pre_init_kwargs)
			if allow_changes is not None:
				init_kwargs["allowedchanges"] = int(allow_changes)

			preferred_device = self._resolve_preferred_device(init_kwargs)
			if preferred_device:
				init_kwargs["devicename"] = preferred_device

			try:
				mixer_module.pre_init(**pre_init_kwargs)
			except TypeError as exc:
				showlog.debug(f"[Drumbo] mixer.pre_init argument mismatch: {exc}")
			except Exception as exc:
				showlog.debug(f"[Drumbo] mixer.pre_init failed: {exc}")

			attempt_kwargs = dict(init_kwargs)
			final_kwargs: Optional[dict[str, Any]] = None

			while True:
				try:
					mixer_module.init(**attempt_kwargs)
					final_kwargs = dict(attempt_kwargs)
					break
				except TypeError as exc:
					if "allowedchanges" in attempt_kwargs:
						showlog.debug(f"[Drumbo] Removing unsupported allowedchanges during init: {exc}")
						attempt_kwargs = dict(attempt_kwargs)
						attempt_kwargs.pop("allowedchanges", None)
						continue
					raise
				except Exception as exc:
					if attempt_kwargs.get("devicename"):
						failing_device = attempt_kwargs.get("devicename")
						showlog.warn(
							f"[Drumbo] Mixer init failed on '{failing_device}', retrying with system default: {exc}"
						)
						attempt_kwargs = dict(attempt_kwargs)
						attempt_kwargs.pop("devicename", None)
						preferred_device = None
						continue
					raise

			mixer_module.set_num_channels(mixer_channels)
			instrument._mixer_ready = True
			instrument._mixer_device = (final_kwargs or {}).get("devicename") or "default"
			instrument._mixer_channel_count = mixer_channels

			actual = mixer_module.get_init()
			log_kwargs = dict(mixer_kwargs)
			log_kwargs["frequency"] = log_kwargs.pop("freq", None)
			log_kwargs["device"] = instrument._mixer_device
			if allow_changes is not None:
				log_kwargs["requested_allowedchanges"] = allow_changes
			if final_kwargs and "allowedchanges" in final_kwargs:
				log_kwargs["effective_allowedchanges"] = final_kwargs["allowedchanges"]
			elif allow_changes is not None:
				log_kwargs["effective_allowedchanges"] = "driver_default"
			if actual:
				log_kwargs["actual"] = {
					"freq": actual[0],
					"format": actual[1],
					"channels": actual[2],
				}
			log_kwargs["force_reinit"] = force_reinit
			showlog.info(f"[Drumbo] Mixer ready: params={log_kwargs}, mixer_channels={mixer_channels}")
			showlog.debug(f"*[Drumbo] Mixer ready params={log_kwargs}, channels={mixer_channels}")
			instrument._forced_reinit = bool(force_reinit)
			return MixerStatus(ready=True, selected_device=instrument._mixer_device, used_fallback=True)
		except Exception as exc:
			instrument._mixer_failed = True
			showlog.error(f"[Drumbo] Mixer init failed: {exc}")
			return MixerStatus(ready=False, used_fallback=True, message=str(exc))

	def load_samples_for(self, instrument_key: str) -> SampleLoadResult:
		instrument = self._instrument
		mixer_module = instrument._get_pygame_mixer()
		if mixer_module is None:
			showlog.warn("[Drumbo] pygame mixer unavailable; cannot load samples")
			instrument.sample_sets[instrument_key] = {}
			instrument.sample_meta[instrument_key] = {}
			instrument.sample_indices[instrument_key] = {}
			return SampleLoadResult(loaded=False)

		override_path = instrument._sample_path_override.get(instrument_key)
		if override_path:
			base_path = Path(override_path)
		else:
			folder_name = instrument.SAMPLE_FOLDERS.get(instrument_key)
			if not folder_name:
				return SampleLoadResult(loaded=False)
			base_path = instrument.sample_root / folder_name

		if instrument.sample_sets.get(instrument_key) and instrument.sample_meta.get(instrument_key):
			return SampleLoadResult(loaded=True)

		path_str = str(base_path)
		if not base_path.exists():
			if path_str not in instrument._missing_sample_paths:
				showlog.warn(f"[Drumbo] Sample folder missing: {base_path}")
				instrument._missing_sample_paths.add(path_str)
			instrument.sample_sets[instrument_key] = {}
			instrument.sample_meta[instrument_key] = {}
			instrument.sample_indices[instrument_key] = {}
			return SampleLoadResult(loaded=False)

		spec = instrument._metadata_specs.get(instrument_key)
		wav_paths: List[Path] = []
		if spec and getattr(spec, "audio_files", None):
			for rel_path in getattr(spec, "audio_files", []):
				candidate = Path(rel_path)
				if not candidate.is_absolute():
					candidate = base_path / Path(rel_path)
				if candidate.exists():
					wav_paths.append(candidate)
		if not wav_paths:
			wav_paths = list(base_path.glob("*.wav"))

		if not wav_paths:
			if path_str not in instrument._empty_sample_paths:
				showlog.warn(f"[Drumbo] No samples found in {base_path}")
				instrument._empty_sample_paths.add(path_str)
			instrument.sample_sets[instrument_key] = {}
			instrument.sample_meta[instrument_key] = {}
			instrument.sample_indices[instrument_key] = {}
			return SampleLoadResult(loaded=False, total_files=0, usable_files=0)

		label_sounds: dict[str, list[Any]] = {}
		label_meta: dict[str, list[dict[str, Any]]] = {}
		total_files = 0
		for wav_path in list(dict.fromkeys(wav_paths)):
			total_files += 1
			label, seq = extract_sample_tokens(wav_path)
			try:
				sound = mixer_module.Sound(str(wav_path))
			except Exception as exc:
				showlog.warn(f"[Drumbo] Failed to load sample '{wav_path.name}': {exc}")
				continue

			bucket = label_sounds.setdefault(label, [])
			bucket.append(sound)
			sequence = seq if seq is not None else len(bucket)
			label_meta.setdefault(label, []).append(
				{
					"label": label,
					"sequence": sequence,
					"group_size": 0,
					"filename": wav_path.name,
					"path": str(wav_path),
				}
			)

		if not label_sounds:
			if path_str not in instrument._empty_sample_paths:
				showlog.warn(f"[Drumbo] No usable samples loaded in {base_path}")
				instrument._empty_sample_paths.add(path_str)
			instrument.sample_sets[instrument_key] = {}
			instrument.sample_meta[instrument_key] = {}
			instrument.sample_indices[instrument_key] = {}
			return SampleLoadResult(loaded=False, total_files=total_files, usable_files=0)

		for label, entries in label_meta.items():
			group_size = len(label_sounds.get(label, []))
			for entry in entries:
				entry["group_size"] = group_size

		instrument.sample_sets[instrument_key] = label_sounds
		instrument.sample_meta[instrument_key] = label_meta
		instrument.sample_indices[instrument_key] = {label: 0 for label in label_sounds.keys()}

		first_label = next(iter(label_sounds.keys()), None)
		first_meta_list = label_meta.get(first_label) if first_label else []
		if first_meta_list:
			first_meta = first_meta_list[0]
			instrument.round_robin_index = int(first_meta.get("sequence", 0) or 0)
			instrument.round_robin_cycle_size = max(1, int(first_meta.get("group_size", len(first_meta_list)) or 1))
		else:
			instrument.round_robin_index = 0
			instrument.round_robin_cycle_size = max((len(sounds) for sounds in label_sounds.values()), default=1)

		return SampleLoadResult(loaded=True, total_files=total_files, usable_files=sum(len(v) for v in label_sounds.values()))

	def play_samples(
		self,
		instrument_key: str,
		velocity: int,
		note_ts: Optional[float],
		facade,
	) -> PlaybackResult:
		instrument = self._instrument
		mixer_module = instrument._get_pygame_mixer()
		if mixer_module is None:
			return PlaybackResult(played=False, facade_paths=[], fallback_paths=[])

		label_sounds = instrument.sample_sets.get(instrument_key) or {}
		if not label_sounds:
			return PlaybackResult(played=False, facade_paths=[], fallback_paths=[])

		label_meta = instrument.sample_meta.get(instrument_key) or {}
		indices = instrument.sample_indices.setdefault(instrument_key, {})

		base_gain = (velocity / 127.0) * (instrument.master_volume / 127.0)
		base_gain = max(0.0, min(1.0, base_gain))

		any_played = False
		facade_paths: List[str] = []
		fallback_paths: List[str] = []
		rr_value = None
		rr_total = None

		for label, sounds in label_sounds.items():
			if not sounds:
				continue

			idx = indices.get(label, 0)
			sound = sounds[idx % len(sounds)]
			indices[label] = (idx + 1) % len(sounds)

			meta_list = label_meta.get(label) or []
			meta_info = meta_list[idx % len(meta_list)] if meta_list else None
			if meta_info and rr_value is None:
				rr_value = meta_info.get("sequence")
				rr_total = meta_info.get("group_size") or len(sounds)
			elif rr_value is None:
				rr_value = (idx % len(sounds)) + 1
				rr_total = len(sounds)

			variable = instrument.LABEL_TO_VARIABLE.get(label)
			if variable:
				try:
					mic_value = int(getattr(instrument, variable, 0))
				except Exception:
					mic_value = 0
			else:
				mic_value = 127

			mic_gain = max(0.0, min(1.0, mic_value / 127.0))
			volume = max(0.0, min(1.0, base_gain * mic_gain))
			if volume <= 0:
				continue

			sample_path = meta_info.get("path") if isinstance(meta_info, dict) else None
			facade_consumed = False
			if facade is not None and sample_path:
				try:
					result = facade.play_sample(sample_path, volume)
					if isinstance(result, bool):
						facade_consumed = result
					elif result is not None:
						facade_consumed = bool(result)
				except Exception:
					facade_consumed = False

			if facade_consumed:
				any_played = True
				facade_paths.append(sample_path or label)
				continue

			try:
				channel = mixer_module.find_channel()
				if channel is None:
					channel = mixer_module.find_channel(True)
				if channel:
					channel.set_volume(volume)
					channel.play(sound)
					any_played = True
					fallback_paths.append(sample_path or label)
					if note_ts is not None:
						delta = time.perf_counter() - note_ts
						showlog.debug(
							f"[Drumbo] Mic '{label}' idx={idx % len(sounds)} channel={channel} volume={volume:.3f}"
							+ (f" latency={delta * 1000:.2f}ms" if delta is not None else "")
						)
				else:
					fallback = sound.play()
					if fallback:
						fallback.set_volume(volume)
						any_played = True
						fallback_paths.append(sample_path or label)
						if note_ts is not None:
							delta = time.perf_counter() - note_ts
							showlog.debug(
								f"[Drumbo] Mic '{label}' idx={idx % len(sounds)} channel={fallback} volume={volume:.3f}"
								+ (f" latency={delta * 1000:.2f}ms" if delta is not None else "")
							)
					else:
						showlog.warn(f"[Drumbo] No mixer channel available for mic '{label}'")
			except Exception as exc:
				showlog.warn(f"[Drumbo] Sample playback failed for mic '{label}': {exc}")

		if rr_value is not None:
			instrument.round_robin_index = int(rr_value or 0)
			instrument.round_robin_cycle_size = int(rr_total or instrument.round_robin_cycle_size or 1)
		else:
			instrument.round_robin_index = 0
			instrument.round_robin_cycle_size = max((len(s) for s in label_sounds.values()), default=0)

		return PlaybackResult(played=any_played, facade_paths=facade_paths, fallback_paths=fallback_paths)

	def _get_audio_preferences(self) -> Tuple[Optional[str], Optional[int], List[str]]:
		instrument = self._instrument
		if instrument._audio_pref_cache is not None:
			return instrument._audio_pref_cache

		name = os.environ.get("DRUMBO_AUDIO_DEVICE")
		index = os.environ.get("DRUMBO_AUDIO_DEVICE_INDEX")
		keywords: List[str] = []

		env_keyword = os.environ.get("DRUMBO_AUDIO_DEVICE_KEYWORD")
		if env_keyword:
			keywords.append(env_keyword)

		audio_config = instrument._load_audio_config()
		if audio_config:
			name = name or getattr(audio_config, "PREFERRED_AUDIO_DEVICE_NAME", None)
			if index is None:
				index = getattr(audio_config, "PREFERRED_AUDIO_DEVICE_INDEX", None)
			extra_keywords = getattr(audio_config, "PREFERRED_AUDIO_DEVICE_KEYWORDS", ())
			if extra_keywords:
				if isinstance(extra_keywords, (list, tuple, set)):
					keywords.extend(extra_keywords)
				else:
					keywords.append(str(extra_keywords))

		if isinstance(index, str) and index.strip():
			try:
				index = int(index.strip())
			except ValueError:
				showlog.warn(f"[Drumbo] Ignoring non-integer DRUMBO_AUDIO_DEVICE_INDEX='{index}'")
				index = None

		instrument._audio_pref_cache = (name, index, keywords)
		return instrument._audio_pref_cache

	def _enumerate_output_devices(self) -> List[str]:
		instrument = self._instrument
		if instrument._output_device_cache is not None:
			return instrument._output_device_cache

		pygame_mod = instrument._get_pygame()
		devices: List[str] = []
		if pygame_mod is None:
			showlog.debug("[Drumbo] pygame unavailable; skipping SDL device query")
			instrument._output_device_cache = []
			return []

		try:
			sdl2_module = getattr(pygame_mod, "_sdl2", None)
			audio_module = getattr(sdl2_module, "audio", None) if sdl2_module else None
			if audio_module is None:
				raise AttributeError("pygame._sdl2.audio missing")

			raw_devices = list(audio_module.get_audio_device_names(False))
			for device in raw_devices:
				if isinstance(device, str):
					devices.append(device)
				else:
					try:
						devices.append(device.decode("utf-8", "ignore"))
					except Exception:
						devices.append(str(device))
		except Exception as exc:
			showlog.debug(f"[Drumbo] SDL2 audio device query unavailable: {exc}")

		instrument._output_device_cache = devices
		if devices:
			showlog.info(f"[Drumbo] Output playback devices detected: {devices}")
		else:
			showlog.info("[Drumbo] SDL audio device list unavailable; mixer will try system default")
		return devices

	def _resolve_preferred_device(self, init_kwargs: dict) -> Optional[str]:
		name_pref, index_pref, keyword_list = self._get_audio_preferences()
		devices = self._enumerate_output_devices()

		resolved = None
		if name_pref:
			resolved = match_device_by_name(name_pref, devices) or name_pref

		if not resolved and index_pref is not None and devices:
			try:
				if index_pref >= 0 and index_pref < len(devices):
					resolved_candidate = devices[index_pref]
				elif index_pref > 0 and index_pref <= len(devices):
					resolved_candidate = devices[index_pref - 1]
				else:
					resolved_candidate = None
				if resolved_candidate is not None:
					resolved = resolved_candidate
			except Exception as exc:
				showlog.warn(f"[Drumbo] Failed to resolve device index {index_pref}: {exc}")

		keywords = list(keyword_list or [])
		if not keywords:
			keywords = list(self._instrument.DEFAULT_AUDIO_DEVICE_KEYWORDS)

		if not resolved and devices:
			for keyword in keywords:
				resolved = match_device_by_name(keyword, devices)
				if resolved:
					break

		if resolved and not isinstance(resolved, str):
			try:
				resolved = resolved.decode("utf-8", "ignore")
			except Exception:
				resolved = str(resolved)

		if resolved:
			showlog.info(f"[Drumbo] Preferring audio device '{resolved}'")
		elif name_pref or index_pref:
			showlog.warn("[Drumbo] Preferred audio device not found; using SDL default")

		return resolved

	def _get_mixer_init_kwargs(self) -> Tuple[dict, int, Optional[int], bool]:
		instrument = self._instrument
		audio_config = instrument._load_audio_config()

		freq = instrument._parse_env_int("DRUMBO_SAMPLE_RATE")
		size = instrument._parse_env_int("DRUMBO_SAMPLE_SIZE")
		channels = instrument._parse_env_int("DRUMBO_SAMPLE_CHANNELS")
		buffer_len = instrument._parse_env_int("DRUMBO_AUDIO_BUFFER")
		mixer_channels = instrument._parse_env_int("DRUMBO_MIXER_CHANNELS")

		if audio_config:
			freq = freq or getattr(audio_config, "SAMPLE_RATE", None)
			size = size or getattr(audio_config, "SAMPLE_SIZE", None)
			channels = channels or getattr(audio_config, "CHANNELS", None)
			buffer_len = buffer_len or getattr(audio_config, "BUFFER_SIZE", None)
			mixer_channels = mixer_channels or getattr(audio_config, "MIXER_NUM_CHANNELS", None)

		freq = freq or 44100
		size = size or -16
		channels = channels or 2
		buffer_len = buffer_len or 1024
		mixer_channels = mixer_channels or 16

		kwargs = {
			"freq": int(freq),
			"size": int(size),
			"channels": int(channels),
			"buffer": int(buffer_len),
		}

		allow_changes = instrument._parse_env_int("DRUMBO_ALLOW_AUDIO_CHANGES")
		if allow_changes is None and audio_config:
			allow_changes = getattr(audio_config, "ALLOW_AUDIO_CHANGES", None)

		if allow_changes is not None:
			try:
				allow_changes = int(allow_changes)
			except (TypeError, ValueError):
				showlog.warn(f"[Drumbo] Ignoring invalid audio change allowance '{allow_changes}'")
				allow_changes = None

		force_reinit = instrument._parse_env_bool("DRUMBO_FORCE_AUDIO_REINIT")
		if force_reinit is None and audio_config is not None:
			force_reinit = getattr(audio_config, "FORCE_AUDIO_CONFIG", False)
		force_reinit = bool(force_reinit)

		instrument._mixer_init_kwargs_cache = (dict(kwargs), int(mixer_channels), allow_changes, force_reinit)
		return dict(kwargs), int(mixer_channels), allow_changes, force_reinit