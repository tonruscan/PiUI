# Drumbo Sampler Migration Notes

_Last updated: 2025-11-07_

## Context Snapshot

- Goal: retire the legacy Drumbo plugin and rebuild it on top of the sampler architecture (`plugins/sampler`).
- Current state: sampler scaffolding exists (instrument interfaces, facades, registry), but Drumbo still runs through the legacy module with compatibility shims.
- Legacy UI and control wiring remain active through `widgets/drumbo_main_widget.py` and `pages.module_base` dial-bank services.

## Key Findings So Far

### UI Layer

- The sampler copy of the Drumbo widget (`plugins/sampler/instruments/drumbo/ui/main_widget.py`) was a placeholder. The live UI continued to import `widgets/drumbo_main_widget.py`, so only eight dials rendered and the MIDI footer features disappeared.
- The legacy widget supports two simultaneous dial banks (16 mic controls), round-robin counters, and MIDI flash indicators. Any sampler rebuild must preserve these behaviours.

### Module Behaviour

- `plugins/drumbo_plugin.py` still hosts the full legacy implementation. It provides compatibility hooks into sampler facades but duplicates logic that should live inside `plugins/sampler/instruments/drumbo/module.py`.
- Mixer, preset, and event facades are injected, but playback still falls back to `LegacySampleLoader` because the sampler mixer facade is a stub.
- Environment parsing for audio overrides currently calls `parse_int` / `parse_bool` with environment variable names, so sampler-specific audio tweaks are ignored.

### Bundled Services

- `LegacyUISyncService` centralises dial-bank setup, widget wiring, metadata-driven bank updates, and CC registry refreshes. This code is sampler-ready once the new instrument API is in place.
- Core sampler utilities (`engine.py`, `mixer_facade.py`, `preset_facade.py`, `event_bridge.py`) are solid scaffolding but need real adapters to platform services (`preset_manager`, audio mixer, event bus).

### Observed Issues

| Issue | Impact | Status |
| --- | --- | --- |
| `module 'pages' has no attribute 'get_dial_bank_manager'` warning | Dial banks failed to initialise during module `__init__` | **Fixed** – switched legacy importer to `importlib.import_module`, restoring access to `pages.module_base`. |
| Sampler widget placeholder | UI shows single row of dials; no MIDI footer | Needs rebuild – migrate full widget into sampler tree and point config to it. |
| Legacy module duplication | Hard to maintain, blocks sampler-first architecture | Needs rebuild – implement real `InstrumentModule` and retire legacy class. |
| Mixer facade stub | Forces pygame fallback, no sampler audio pipeline | Needs rebuild – supply sampler-backed mixer facade. |
| Preset facade stub | Presets persist only in memory | Needs rebuild – wrap `preset_manager`. |

## Completed Actions

1. Patched legacy import helper to use `importlib.import_module`, eliminating dial-bank initialisation warning.

## Next Steps (Suggested Sequence)

1. **UI Migration** – Move the full widget implementation into the sampler package, update `drumbo_config.CUSTOM_WIDGET` to reference it, and ensure both dial banks render.
2. **Instrument Core Extraction** – Port the legacy `Drumbo` class logic into a sampler-friendly `DrumboInstrument` that implements `InstrumentModule` and relies on injected facades instead of globals.
3. **Sampler Plugin Shell** – Replace the legacy plugin bootstrap in `plugins/sampler/plugin.py` with a shell that instantiates the new instrument via the sampler registry and real facades.
4. **Service Adapters** – Implement concrete mixer, preset, and event facades so Drumbo uses the sampler ecosystem end-to-end.
5. **Testing & Cleanup** – Add focused unit tests under `plugins/sampler/instruments/drumbo/tests/`, update docs, and phase out legacy shims once confidence is high.

## Considerations for the Full Rebuild

- Preserve bank-switch hotkeys, button state propagation, and UI dirty-rect optimisations to avoid regressions in performance-sensitive code paths.
- Keep compatibility exports (`Plugin`, `Drumbo`) alive until all callers migrate, but restrict them to importing the new sampler instrument to prevent drift.
- Use structured sampler events (`sampler.note_on`, etc.) so downstream consumers can evolve without touching instrument internals.
- Capture existing manual verification steps (bank switching, preset load/save, MIDI playback) as automated tests wherever possible.

## Reference Paths

- Legacy module: `plugins/drumbo_plugin.py`
- Legacy widget: `widgets/drumbo_main_widget.py`
- Sampler scaffolding: `plugins/sampler/`
- Sampler Drumbo package: `plugins/sampler/instruments/drumbo/`
- Dial bank coordination: `plugins/sampler/instruments/drumbo/services/ui_service.py`

---

Continue appending notable findings and decisions here as the migration progresses so the team has a single source of truth for the Drumbo sampler rebuild.
