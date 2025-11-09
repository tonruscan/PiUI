# Feedback for Code GPT – Sampler Architecture & Drumbo Integration Plan

This feedback refines and validates the **Sampler Architecture & Drumbo Integration Plan** to ensure implementation proceeds safely and consistently with the existing modular plugin system.

---

## ✅ Summary of Feedback

The proposed plan is strong and aligns with your current architecture.  
Below are detailed implementation notes for Code GPT to follow when executing the migration.

---

## 🧩 1. Folder Structure Adjustments

Keep the proposed structure but add:

- `plugins/sampler/core/tests/` → placeholder for early test scaffolding.
- `plugins/sampler/core/utils/` → small helper utilities (path, config, logging).

This ensures later expansions don’t clutter the facades or engine.

---

## ⚙️ 2. Core Interfaces (`engine.py`)

Introduce both a base class and a descriptor type for consistency with the current Drumbo metadata model.

```python
class InstrumentDescriptor:
    id: str
    display_name: str
    category: str
    version: str
    entry_module: str
    icon_path: Optional[str] = None
    default_preset: Optional[str] = None
```

Add an abstract base class for all instrument modules:

```python
class InstrumentModule(abc.ABC):
    @abc.abstractmethod
    def activate(self, context: InstrumentContext) -> None: ...
    @abc.abstractmethod
    def deactivate(self) -> None: ...
    @abc.abstractmethod
    def handle_event(self, event: SamplerEvent) -> None: ...
```

The `InstrumentContext` dataclass should inject facades instead of using globals:

```python
@dataclass
class InstrumentContext:
    mixer: MixerFacade
    presets: PresetFacade
    event_bus: EventBridge
    config: dict
```

---

## 🪄 3. Compatibility & Rollout

Maintain shims for now.  
Example:

```python
# plugins/sampler/plugin.py
from plugins.sampler.instruments.drumbo.module import DrumboInstrument
Plugin = DrumboInstrument
```

Legacy paths like `drumbo_plugin.py` and `drumbo_instrument_service.py` remain forwarding wrappers until full migration.

---

## 🎛️ 4. Facade Responsibilities

| Facade | Responsibility | Notes |
|--------|----------------|-------|
| **mixer_facade.py** | Initialize pygame.mixer, manage sample playback | Use singleton pattern |
| **preset_facade.py** | Interface with preset_manager | Stateless proxy |
| **event_bridge.py** | Translate global events to module handlers | Add rate limiting or type filtering |
| **instrument_registry.py** | Manage instrument discovery and registration | Supports async scan later |

Facades should log via `showlog` and avoid throwing errors—return status or result objects instead.

---

## 🧠 5. Phase-by-Phase Refinements

| Phase | Recommendation |
|--------|----------------|
| **Phase 1** | Create `InstrumentContext` and stubs with docstrings. Add dummy Drumbo registration. |
| **Phase 2** | Move Drumbo logic incrementally (metadata → UI → mixer). Verify after each stage. |
| **Phase 3** | Build minimal sampler shell (just selects Drumbo). Avoid UI overhaul yet. |
| **Phase 4** | Verify parity using both legacy and sampler entry points before cleanup. |

---

## 🧩 6. Testing Strategy

Tests to include:

- `test_registry_discovery`: ensure Drumbo descriptor registers.
- `test_mixer_playback_mocked`: verify samples can be resolved and queued.
- `test_event_bridge_routing`: confirm events reach instrument handlers.

Early tests guarantee that migration doesn’t regress existing Drumbo behavior.

---

## 🗃️ 7. Documentation

Add to `plugins/sampler/docs/README.md`:

- **Architecture diagram:** `UI → EventBridge → InstrumentModule → MixerFacade → Audio`
- **Module registration example:** `instrument_registry.register_instrument(descriptor)`
- **How to extend:** minimal boilerplate example for a new instrument module.

---

## 🧩 8. Integration Edge Cases

Make sure to handle:

- **Reinitialization:** Stop audio channels and reset preset states when switching instruments.
- **Shared cache:** Use central registry cache under `core/services/instrument_registry.py`.
- **Thread safety:** Protect shared registry and mixer resources during async scans.

---

## ✅ 9. Deliverables for Code GPT

Ask GPT to:

1. Scaffold the **entire directory tree** (empty files + docstrings).
2. Implement **stubs** for:
   - `InstrumentModule`, `InstrumentDescriptor`
   - `InstrumentContext` dataclass
   - Empty facades (mixer, preset, event)
   - Dummy Drumbo registration in registry
3. Provide **compatibility shims** for legacy Drumbo imports.
4. Output the **folder tree** confirming paths.
5. Include **minimal tests** (mocked mixer + metadata) so the core runs standalone.

---

## 🔍 10. Final Assessment

The plan is robust, modular, and future-proof. Following these refinements will:

- Preserve full backward compatibility during migration.
- Enable parallel development of other instruments.
- Support test automation and clear dependency separation.
- Keep the UI stable while introducing the new sampler shell.

---

**In short:** proceed exactly as planned, but scaffold the stubs, facades, and compatibility layer first before moving any Drumbo logic.
