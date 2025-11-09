# Sampler Architecture (Scaffolding)

This documentation placeholder will be expanded once the sampler core and
multi-instrument shell are fully implemented. For now it simply marks the
location where architecture diagrams, extension guides, and migration notes
will live.

## Adding a New Instrument (Drumbo Example)

The Drumbo refactor demonstrates the current best-practice path for wiring an
instrument into the sampler shell:

- Add a package under `plugins/sampler/instruments/<instrument>` housing
	configuration data, services, and any sampler-specific widgets. Drumbo keeps
	UI helpers in `services/ui_service.py`.
- Implement the instrument plugin (e.g. `plugins/drumbo_plugin.py`) so it
	consumes the shared facades (`MixerFacade`, `PresetFacade`, `EventBridge`) and
	delegates UI concerns to a service class. Legacy fallbacks stay isolated in
	helpers like `LegacySampleLoader`.
- Export the service helpers via the instrument package's `__init__.py` so the
	plugin can import them without reaching into implementation details.
- Register metadata such as sample folders, dial layouts, and button maps in an
	adjacent `config.py`. Drumbo's `config.py` doubles as a single source of truth
	for UI theming and MIDI note mappings.
- Add verification coverage that exercises both the facade path and the legacy
	fallback path. Drumbo uses `verify_sampler_phase2.py` to confirm mixer routing
	and preset persistence.

Following this pattern keeps sampler integrations consistent and allows the
legacy runtime to coexist with the emerging facade-first architecture.
