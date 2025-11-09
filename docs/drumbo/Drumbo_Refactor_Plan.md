# Sampler Architecture & Drumbo Integration Plan

## ✅ Overview
We are transitioning from a Drumbo-only plugin to a sampler platform that can host multiple instrument modules (drums, guitars, synths, etc.). The goal is to:

- Introduce a `plugins/sampler/` hierarchy with a shared core and pluggable instruments.
- Migrate Drumbo into the first instrument module under this structure.
- Keep the existing UI operational during the migration by providing compatibility shims.

This document lays out the target directory structure, dependency boundaries, migration phases, and deliverables so the team can execute in stages without breaking current builds.

---

## Debug Logging Guidelines

Before diving into the plan, align on how we emit diagnostics while refactoring:

- Use `showlog.debug("*message {vars}")` when you need loop-mode visibility; the leading `*` keeps the entry highlighted in the log stream.
- Prefix every debug line with a clear tag that includes the function (or logical block) and the current step, e.g. `[DRAW_UI_STEP_1] preparing bank widgets`.
- Avoid placing debug statements in tight loops or high-frequency code paths—excess chatter makes real issues harder to spot.

Additional logging rules:

- Routine status updates should call `showlog.debug("message")` without the loop-mode asterisk.
- Use `showlog.warn(...)` for non-fatal anomalies, `showlog.error(...)` for actual failures, and reserve `showlog.info(...)` for rare, high-level milestones the end user would benefit from seeing.

---

## 1. Target Directory Layout

Create the following hierarchy, bringing Drumbo under the new sampler umbrella:

```
plugins/
└── sampler/
    ├── __init__.py            # exposes SamplerPlugin entry point (future)
    ├── plugin.py              # temporary wrapper registering the active instrument
    ├── core/
    │   ├── __init__.py
    │   ├── config.py          # shared settings (paths, defaults)
    │   ├── engine.py          # base InstrumentModule / SampleEngine interfaces
    │   ├── event_bridge.py    # shared event adapters
    │   ├── mixer_facade.py    # pygame/config bridging
    │   ├── preset_facade.py   # preset manager integration
    │   ├── utils/             # shared helpers (paths, logging, type coercion)
    │   │   └── __init__.py
    │   ├── services/
    │   │   ├── instrument_registry.py
    │   │   ├── instrument_scanner.py
    │   │   └── sample_loader.py
    │   └── tests/
    │       ├── __init__.py
    │       └── run_tests.py   # standalone core test harness
    ├── instruments/
    │   ├── __init__.py
    │   └── drumbo/
    │       ├── __init__.py                # exports DrumboInstrument descriptor
    │       ├── module.py                  # Drumbo InstrumentModule implementation
    │       ├── ui/
    │       │   └── main_widget.py
    │       ├── config.py                  # Drumbo-specific theme/layout defaults
    │       ├── services/
    │       │   └── metadata.py            # per-instrument helpers (optional)
    │       └── tests/
    │           ├── test_metadata.py
    │           └── test_sample_loading.py
    └── docs/
        └── README.md
```

Drumbo-specific documentation (like this plan and the backend manual) moves under `plugins/sampler/instruments/drumbo/docs/`, with a root sampler README describing the overall architecture.

---

## 2. Compatibility Layer

Maintain the current import surface until all callers migrate:

- `plugins/drumbo_plugin.py` remains but forwards to `plugins.sampler.instruments.drumbo.module import DrumboInstrument`. Export both `Plugin = DrumboInstrument` and `Drumbo = DrumboInstrument` so callers using either entry name continue to succeed.
- `plugins/drumbo_instrument_scanner.py` forwards to `plugins.sampler.core.services.instrument_scanner`.
- Any other top-level Drumbo files become thin shims importing from the new location.

This lets the existing preset browser, global control handlers, and module routing continue to function while the sampler shell is under construction.

---

## 3. Dependency Boundaries

We will enforce strict layering to keep instruments isolated:

1. **Sampler core** (under `plugins/sampler/core/`) owns integrations with `module_base`, `preset_manager`, `event_bus`, and mixer configuration.
2. **Instrument modules** only communicate with the core through well-defined interfaces exported by `engine.py` and associated facades. No instrument should import `module_base` or other global modules directly.
3. **UI shell** (eventually `plugins/sampler/plugin.py`) coordinates the instrument registry, handles user selection, and instantiates the active instrument module.

For Drumbo, that means replacing direct calls to `_ensure_bank_setup()`, preset hooks, or pygame init with invocations of core facades—in many cases just moving the existing logic into those facades and calling them from Drumbo.

---

## 4. Phase Plan

### Phase 1 – Core Scaffolding
- Create `plugins/sampler/core/` with stubbed interfaces and service wrappers that simply proxy to current global systems.
- Introduce `InstrumentModule` base class (lifecycle hooks, event registration) and `InstrumentDescriptor` metadata struct.
- Write compatibility shims so the legacy Drumbo module can keep running.

### Phase 2 – Drumbo Migration
- Move `Drumbo` class into `instruments/drumbo/module.py`, updating imports to use the new core facades.
- Relocate widget code to `instruments/drumbo/ui/main_widget.py` (simple move + import fix).
- Extract Drumbo-specific constants into `instruments/drumbo/config.py`.
- Ensure metadata loading uses the shared `instrument_scanner` via dependency injection.

### Phase 3 – Sampler Shell
- Build a minimal `SamplerPlugin` that reads the instrument registry and instantiates Drumbo as the default instrument.
- Update the entry point so the UI loads the sampler shell rather than the Drumbo plugin directly (the legacy shim keeps old code working).
- Add event routing through `core/event_bridge.py`, feeding instrument modules via the abstract interface.

### Phase 4 – Testing & Hardening
- Port existing manual test cases into `instruments/drumbo/tests/` and `core/services/tests/` if needed.
- Add sanity tests that confirm the instrument registry discovers Drumbo, loads metadata, and can trigger sample playback via mocked mixer channels.
- Document the extension points for future instruments in `plugins/sampler/docs/README.md`.

---

## 5. Core Facades & Interfaces

`engine.py` will define both the descriptor dataclass and base module interfaces consumed by every instrument.

- `InstrumentDescriptor` is a mutable `@dataclass` so the registry can update metadata at runtime. It should expose a `to_dict()` helper for interoperability with existing JSON payloads.

```python
@dataclass
class InstrumentDescriptor:
    id: str
    display_name: str
    category: str
    version: str
    entry_module: str
    metadata_path: Optional[str] = None
    icon_path: Optional[str] = None
    default_preset: Optional[str] = None

    def to_dict(self) -> dict[str, Optional[str]]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "category": self.category,
            "version": self.version,
            "entry_module": self.entry_module,
            "metadata_path": self.metadata_path,
            "icon_path": self.icon_path,
            "default_preset": self.default_preset,
        }
```

- `InstrumentContext` is another dataclass that injects the shared facades so instrument modules never touch globals directly.

```python
@dataclass
class InstrumentContext:
    mixer: MixerFacade
    presets: PresetFacade
    events: EventBridge
    config: dict[str, Any]
```

Import `Optional` and `Any` from `typing` so the annotations stay explicit without leaking implementation types.

`InstrumentModule` provides the minimal set of lifecycle hooks an instrument must implement:

```python
class InstrumentModule(abc.ABC):
    @abc.abstractmethod
    def activate(self, context: InstrumentContext) -> None:
        ...

    @abc.abstractmethod
    def deactivate(self) -> None:
        ...

    @abc.abstractmethod
    def handle_event(self, event: SamplerEvent) -> None:
        ...
```

`SamplerEvent` can start life as a lightweight `NamedTuple` or protocol in `core/event_bridge.py`—during scaffolding, provide a stub or alias (`SamplerEvent = Any`) so instrument modules have a type to reference before real event structures are defined.

`InstrumentContext` provides access to shared services (mixer, preset service, metadata cache). Drumbo receives this context on activation and stores the handles instead of importing modules directly.

`instrument_registry.py` exposes `register_instrument(descriptor)` and `get_descriptors()` so the sampler shell can enumerate available modules. For now we register Drumbo in Phase 2; future instruments plug in via the same mechanism.

---

## 6. Configuration Strategy

- Shared defaults (sample root, cache directories, fallback dial values) move into `core/config.py`.
- Instrument-specific overrides live in each module’s `config.py` so they can diverge (for example, different dial layouts or theme colors).
- Allow environment overrides via core config when needed, but keep instruments isolated from global config constants.

---

## 7. Testing & Tooling

- Add `plugins/sampler/instruments/drumbo/tests/` with focused unit tests (metadata parsing, sample grouping, fallback defaults).
- Provide fixtures in `core/tests/` to mock the mixer and preset facades so modules can run without the full UI, and wire the lightweight `run_tests.py` harness so the core suite can run standalone during scaffolding.
- Long-term: integrate these tests into CI so new instruments must ship with similar coverage.

---

## 8. Documentation Updates

- Move existing Drumbo manuals under the new instrument folder and update references to the sampler architecture.
- Create `plugins/sampler/docs/README.md` outlining:
  - Core architecture
  - How to create a new instrument module
  - Expectations for config, services, and tests
- Update any external docs or onboarding guides to point to the sampler plugin rather than `drumbo_plugin`.

---

## 9. Compatibility & Rollout

- Keep shims in place until every caller (UI presets, controls, automation) migrates to the new sampler entry points.
- Track the migration with feature flags if needed (e.g., `SAMPLER_SHELL_ENABLED`).
- Once the sampler shell is the default, schedule a cleanup pass to remove the shims and obsolete files.

---

## 10. Initial Scaffolding Runbook

Execute the kickoff in this exact sequence before moving any production logic:

1. Create every directory and empty module outlined in the structure above (include docstrings so imports succeed).
2. Implement the `InstrumentDescriptor`, `InstrumentModule`, and `InstrumentContext` stubs inside `core/engine.py`.
3. Add placeholder facades: `mixer_facade.py`, `preset_facade.py`, and `event_bridge.py` exporting minimal classes with docstrings.
4. Scaffold `services/instrument_registry.py` with registration functions and a dummy Drumbo descriptor (no real wiring yet).
5. Drop in the compatibility shims (`plugins/drumbo_instrument_scanner.py`, and any other legacy entry points).  *(The historic `plugins/drumbo_plugin.py` shim has now been fully removed once all callers migrated to the sampler shell.)*
6. Add minimal tests validating imports and registry discovery (e.g., create a placeholder test case under `core/tests` that asserts the dummy descriptor is registered).
    - In `core/tests/run_tests.py`, call `unittest.main("plugins.sampler.core.tests", exit=False, verbosity=2)` so IDE invocations do not trigger a hard exit.

Pause for review after step 6; do not migrate Drumbo internals until the team signs off.

## 11. Verification & Pause Gates

After scaffolding, confirm all of the following before proceeding:

- `from plugins.sampler.plugin import Plugin` resolves without side effects.  (Importing `plugins.drumbo_plugin` now raises an ImportError, signalling any lingering legacy dependency.)
- Running `python -m plugins.sampler.core.tests.run_tests` executes the placeholder suite successfully.
- A snapshot of the new directory tree (e.g., via `tree` or scripted output) matches the plan.
- Legacy Drumbo flows still boot through the compatibility shim.

Once these checks pass, halt the migration and request review. The next phase will populate the facades and begin moving Drumbo logic.

## 12. Deliverables Checklist

1. **Directory scaffolding** committed with placeholder files and documentation.
2. **Core interfaces** (`InstrumentModule`, facades, registry) implemented and unit-tested.
3. **Drumbo module** relocated, using only injected dependencies.
4. **Sampler shell plugin** registering Drumbo as the first instrument.
5. **Compatibility shims** in legacy paths verified by running existing UI flows.
6. **Core test harness** runnable via `python -m plugins.sampler.core.tests.run_tests`.
7. **Updated documentation** (sampler README, Drumbo manual references) merged.
8. **Test suite** (core + Drumbo) passing in automation.

---

## ✅ Summary

Executing this plan gives us a modular sampler architecture ready to host additional instruments. Drumbo becomes the first instrument module but no longer dictates the plugin structure. The separation between core services and instrument implementations keeps future growth manageable, supports independent testing, and allows for feature development without destabilising the UI stack.

Once Phase 1 scaffolding is merged, add a pointer to `plugins/sampler/docs/README.md` so contributors can find the high-level architecture diagrams and extension guidelines.
