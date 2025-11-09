import json
from pathlib import Path

# Patch module_base before Drumbo import to avoid UI-heavy routines
from pages import module_base

module_base.capture_active_dial_bank_values = lambda: None
module_base.get_dial_bank_values = lambda bank_key: [42] * 8
module_base.set_dial_bank_values = lambda bank_key, values: True
module_base.set_slot_to_ctrl_mapping = lambda mapping: True
module_base.set_active_dial_bank = lambda bank: True
module_base.configure_dial_banks = lambda config, default_bank=None: default_bank or "A"
module_base.get_dial_bank_manager = lambda: None
module_base._BUTTON_STATES = {}

# Lightweight dialhandlers + cc_registry hooks
import dialhandlers
from system import cc_registry

dialhandlers.update_button_state = lambda module_id, key, value: None
dialhandlers.msg_queue = None
cc_registry.load_from_module = lambda module_id, registry, meta=None: None

# Stub pygame mixer interactions so tests do not touch SDL
import pygame

class _DummyChannel:
    def __init__(self, name: str):
        self.name = name
    def set_volume(self, value: float) -> None:
        pass
    def play(self, sound) -> None:
        pass

class _DummySound:
    def __init__(self, path: str):
        self.path = path
    def play(self):
        return _DummyChannel("fallback")

pygame.mixer.get_init = lambda: (44100, -16, 2)
pygame.mixer.get_num_channels = lambda: 16
pygame.mixer.pre_init = lambda **kwargs: None
pygame.mixer.init = lambda **kwargs: None
pygame.mixer.quit = lambda: None
pygame.mixer.set_num_channels = lambda count: None
pygame.mixer.find_channel = lambda force=False: _DummyChannel("forced" if force else "primary")
pygame.mixer.Sound = lambda path: _DummySound(path)

# Stub Drumbo sample loading to avoid filesystem IO
from plugins.sampler.instruments.drumbo.module import DrumboInstrument as Drumbo

def _stub_load_samples_for(self, instrument_key):
    key = (instrument_key or "snare").strip().lower()
    self.sample_sets[key] = {"M1": [_DummySound(f"{key}_stub.wav")]}
    self.sample_meta[key] = {
        "M1": [
            {
                "label": "M1",
                "sequence": 1,
                "group_size": 1,
                "filename": f"{key}_stub.wav",
                "path": f"{key}_stub.wav",
            }
        ]
    }
    self.sample_indices[key] = {"M1": 0}
    return True

Drumbo._load_samples_for = _stub_load_samples_for


class LoggingPresetFacade:
    def __init__(self, name: str):
        self.name = name
        self.calls: list[tuple] = []
        self.state = {
            "preset_instrument": "kick",
            "preset_bank_a_values": [5] * 8,
            "preset_bank_b_values": [9] * 8,
        }
    def save_state(self, instrument_id: str, state: dict) -> None:
        snapshot = {
            "instrument": state.get("preset_instrument"),
            "bank_a": list(state.get("preset_bank_a_values", [])),
            "bank_b": list(state.get("preset_bank_b_values", [])),
        }
        self.calls.append((self.name, "save_state", instrument_id, snapshot))
    def load_state(self, instrument_id: str):
        self.calls.append((self.name, "load_state", instrument_id))
        return dict(self.state)


class LoggingMixerFacade:
    def __init__(self, name: str, *, ensure_ready_result: bool, play_sample_result: bool):
        self.name = name
        self.ensure_ready_result = ensure_ready_result
        self.play_sample_result = play_sample_result
        self.ensure_calls: list[bool] = []
        self.play_calls: list[tuple] = []
    def ensure_ready(self) -> bool:
        self.ensure_calls.append(self.ensure_ready_result)
        return self.ensure_ready_result
    def play_sample(self, path: str, volume: float) -> bool:
        if path is None:
            raise RuntimeError(f"{self.name} received None path")
        entry = (path, round(float(volume), 3), self.play_sample_result)
        self.play_calls.append(entry)
        return self.play_sample_result


class LoggingEventBridge:
    def __init__(self, name: str):
        self.name = name
        self.events: list[dict] = []
    def publish(self, event):
        if isinstance(event, dict) and "timestamp" in event:
            event = dict(event)
            try:
                event["timestamp"] = round(float(event["timestamp"]), 4)
            except Exception:
                pass
        self.events.append(event)


def run_case(name: str, ensure_ready_result: bool, play_sample_result: bool):
    preset_facade = LoggingPresetFacade(name)
    mixer_facade = LoggingMixerFacade(name, ensure_ready_result=ensure_ready_result, play_sample_result=play_sample_result)
    event_bridge = LoggingEventBridge(name)

    drumbo = Drumbo()
    drumbo.widget = None
    drumbo.configure_sampler_facades(mixer=mixer_facade, presets=preset_facade, events=event_bridge)

    # Seed mic levels so sample playback computes a non-zero gain.
    drumbo.master_volume = 127
    for idx in range(1, 17):
        setattr(drumbo, f"mic_{idx}_level", 127)

    drumbo.on_preset_loaded({"preset_instrument": "snare"}, {})
    drumbo.prepare_preset_save()
    played = drumbo.on_midi_note(38, 96, channel=10)

    if ensure_ready_result and not mixer_facade.play_calls:
        raise RuntimeError(f"Mixer facade did not receive play_sample calls for scenario '{name}'")

    return {
        "scenario": name,
        "mixer_ensure_calls": mixer_facade.ensure_calls,
        "mixer_play_calls": mixer_facade.play_calls,
        "preset_calls": preset_facade.calls,
        "event_count": len(event_bridge.events),
        "event_played_flags": [bool(evt.get("played")) for evt in event_bridge.events if isinstance(evt, dict)],
        "preset_snapshot": {
            "instrument": drumbo.preset_instrument,
            "bank_a": drumbo.preset_bank_a_values[:2],
            "bank_b": drumbo.preset_bank_b_values[:2],
        },
        "note_return": played,
    }


results = [
    run_case("facade", ensure_ready_result=True, play_sample_result=True),
    run_case("fallback", ensure_ready_result=False, play_sample_result=False),
]

print(json.dumps(results, indent=2))
