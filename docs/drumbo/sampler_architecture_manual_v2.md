# UI MIDI Pi – **Sampler Ecosystem Manual** (with Drumbo Integration)

> This manual brings a new Code‑GPT up to speed on the **current sampler architecture**, how **Drumbo** fits inside it, what was migrated, how startup wiring works, where the facades live, how to test, and how not to break the UI again. It assumes the project root is `T:\UI\build` (or equivalent on your system).

---

## 0) High‑level Overview

We evolved from a single **Drumbo** drum plugin into a **Sampler Platform** that can host multiple instrument modules (drums first; others later). The key design:

- **Sampler Core** exposes **stable contracts** (facades & context) to instruments.
- **Instruments** (like Drumbo) are **decoupled** from global singletons (pygame, module_base, preset_manager) and talk only to injected facades.
- A **compatibility layer** keeps legacy paths running during migration.

### Golden Rule
> **Runtime** must inject an `InstrumentContext` into the instrument **before** legacy UI registration; otherwise instruments fall back to `Null*Facade` and the UI degenerates (e.g., 8 dials only, no redraws).

---

## 1) Directory Layout (Authoritative)

```
plugins/
└── sampler/
    ├── __init__.py
    ├── plugin.py                      # Sampler shell (entry plugin)
    ├── core/
    │   ├── __init__.py
    │   ├── config.py                  # Shared defaults (paths, env overrides)
    │   ├── engine.py                  # InstrumentDescriptor/Context/Module
    │   ├── event_bridge.py            # Event facade contracts + Null
    │   ├── mixer_facade.py            # Mixer facade contracts + Null
    │   ├── preset_facade.py           # Preset facade contracts + Null
    │   ├── services/
    │   │   ├── instrument_registry.py # Register/lookup instruments
    │   │   └── sample_loader.py       # LegacySampleLoader, MixerStatus
    │   ├── utils/
    │   │   ├── __init__.py            # re-exports promoted helpers
    │   │   └── (bank/env/audio/token helpers)
    │   └── tests/
    │       ├── __init__.py
    │       ├── run_tests.py
    │       └── test_utils.py
    ├── instruments/
    │   ├── __init__.py
    │   └── drumbo/
    │       ├── __init__.py            # exports DrumboInstrument descriptor
    │       ├── module.py              # Drumbo InstrumentModule (future location)
    │       ├── ui/
    │       │   ├── main_widget.py     # Drumbo UI widget (legacy-friendly)
    │       │   └── ui_service.py      # LegacyUISyncService (positioning, apply)
    │       ├── services/
    │       │   └── metadata.py        # per-instrument helpers
    │       ├── config.py              # theme/layout/note maps/sample roots
    │       └── tests/
    │           ├── test_metadata.py
    │           └── test_sample_loading.py
    └── docs/
        └── README.md                  # Architecture & authoring guide
```

### Legacy shims that still exist
- `plugins/drumbo_plugin.py` — still the working Drumbo class & legacy plugin wrapper, but now **facade‑aware**.
- Legacy pages/widgets under `pages/` still used for registration via `DrumboPlugin.on_load()`.

---

## 2) Core Contracts

### 2.1 `engine.py`
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

@dataclass
class InstrumentContext:
    mixer: MixerFacade
    presets: PresetFacade
    events: EventBridge
    config: dict[str, Any]

class InstrumentModule(abc.ABC):
    @abc.abstractmethod
    def activate(self, context: InstrumentContext) -> None: ...
    @abc.abstractmethod
    def deactivate(self) -> None: ...
    @abc.abstractmethod
    def handle_event(self, event: 'SamplerEvent') -> None: ...
```

### 2.2 Facades
All three have **real** and **Null** variants. Real facades may be **proxy objects** (methods via `__getattr__`).

- **MixerFacade**: `ensure_ready() -> bool`, `play_sample(path: str, gain: float, ts: float|None) -> bool`
- **PresetFacade**: `load_state(module_id: str) -> dict|None`, `save_state(module_id: str, data: dict) -> None`
- **EventBridge**: `publish(event: dict) -> None`

> **Important**: Do **not** hard‑reject proxies; they may not have attributes until first access.

---

## 3) Drumbo – Current Responsibilities

`plugins/drumbo_plugin.py` remains the **operational module** while migration completes. It now:

- Pulls **theme/layout/note maps** from `plugins.sampler.instruments.drumbo.config`.
- Uses **promoted utils** from `plugins.sampler.core.utils` (normalize_bank, parse_int/bool, token/device helpers).
- Routes audio through **MixerFacade** first, falls back to **LegacySampleLoader**.
- Routes preset snapshots through **PresetFacade**, merges with legacy data on load.
- Publishes note events via **EventBridge**.
- Delegates dial layout/updates to **LegacyUISyncService** (in `ui_service.py`).

### Drumbo public hooks used by the shell
- `bind_instrument_context(ctx)` — stores `InstrumentContext` and legacy handles.
- `configure_sampler_facades(mixer, presets, events)` — chooses real vs Null facades.
- `_play_sample(instrument, velocity, ts)` — facade‑first playback.
- `_activate_bank('A'|'B')`, `_ensure_bank_setup()` — builds 2 × 8 mic dials.

---

## 4) Sampler Shell – Startup Wiring (Critical Path)

The **only** reliable way to keep UI, events, and audio alive is:

```
App boot → SamplerPlugin.on_load(app)
    ├─ build real facades (or obtain from services)
    ├─ ctx = InstrumentContext(mixer, presets, events, config)
    ├─ drumbo = DrumboInstrument()
    ├─ drumbo.bind_instrument_context(ctx)
    ├─ drumbo.configure_sampler_facades(mixer, presets, events)
    └─ register Drumbo page with app.page_registry (no legacy plugin)
```

> The legacy `plugins.drumbo_plugin` entry point has been removed; attempting to import it now raises an ImportError. All boots must run through the sampler shell to ensure facades, context binding, and page registration.

### Entry plugin selection
- Ensure configuration selects **`plugins.sampler.plugin:Plugin`** as the entry plugin, not `plugins.drumbo_plugin:Plugin`.

---

## 5) Verification Harnesses

### 5.1 CLI harness (non‑visual)
`verify_sampler_phase2.py` performs two runs:
- **Facade path**: MixerFacade handles playback (`ensure_ready=True`, `play_sample=True`).
- **Fallback path**: returns False so pygame legacy branch is exercised.

It validates:
- Saved/loaded preset snapshots
- Mixer calls & chosen sample path
- Event publish semantics

### 5.2 Visual spot‑check (manual)
On normal UI boot, expect to see logs:
```
[SamplerPlugin] Facades bound: ...
*[Drumbo] _activate_bank requested target=A
```
UI must show:
- **16 dials** (8 per bank) in the right‑side panel box
- Mic labels populated after loading samples
- MIDI note triggers audio and UI feedback

---

## 6) Common Failure Modes & Fixes

### A) Facade proxies rejected (UI collapses to 8 dials)
**Symptom:** No background box, one row of 8 dials, silent playback.
**Cause:** `configure_sampler_facades()` rejects proxy facades (no hasattr for each method) → replaced by `Null*Facade`.
**Fix:** Relax `_resolve` logic to accept objects with `__getattr__` (and not instances of Null variants). Rebind from `InstrumentContext`.

### B) Context injection never happens on real startup
**Symptom:** Harness passes; live UI broken. No `Facades bound` log; no `_activate_bank` log.
**Fix:** Ensure SamplerPlugin is the **entry plugin**, and it calls `bind_instrument_context()` + `configure_sampler_facades()` **before** delegating to legacy `on_load()`.

### C) Bank manager not built / no second row
**Symptom:** Still 8 dials after facades injected.
**Fix:** Verify `_ensure_bank_setup()` and `_refresh_widget_bank_refs()` are called after widget/page registration; ensure `LegacyUISyncService` is used by Drumbo and has access to the widget instance.

---

## 7) Coding Standards for Further Migration

- **No direct imports** of `pygame`, `pages.module_base`, `preset_manager` inside instrument logic; access via injected handles only.
- Keep **Legacy fallback paths** until real facades cover parity; log with `"Legacy hookup"` comments.
- Add **docstrings** to facade methods, state clearly when fallbacks are expected.
- Promote generic helpers to `core/utils`, re‑export in `__init__.py` for clean imports.

---

## 8) Drumbo UI Notes

- Two banks of mic dials: **A (M1–M8)** and **B (M9–M16)**.
- Positioning happens in `ui_service.py::position_mini_dials()` (invoked by Drumbo wrappers).
- Bank switching via `_activate_bank()` updates:
  - `widget.mic_dials_row_1` and `widget.mic_dials_row_2`
  - SLOT_TO_CTRL mapping via `module_base`
  - button states (`1` for snare/kick, `2` for bank A/B)

---

## 9) Minimal Code Snippets (Safe Patterns)

**Relaxed resolver (inside Drumbo):**
```python
def _resolve(self, candidate, expected_methods, fallback):
    if candidate is None:
        return fallback
    for name in expected_methods:
        if hasattr(candidate, name):
            continue
        if hasattr(candidate, "__getattr__") and not isinstance(candidate, type(fallback)):
            return candidate
        return fallback
    return candidate
```

**SamplerPlugin.on_load (ordering):**
```python
ctx = InstrumentContext(mixer, presets, events, config={})
self._drumbo = Drumbo()
self._drumbo.bind_instrument_context(ctx)
self._drumbo.configure_sampler_facades(mixer, presets, events)
LegacyDrumboPlugin.on_load(self, app)  # register pages after binding
```

---

## 10) Bring‑Up Checklist for New Changes

1. Ensure entry plugin is **SamplerPlugin**.
2. On boot, confirm `Facades bound` log appears.
3. Confirm `*_activate_bank requested target=A` appears once.
4. Visual check: 16 dials in two rows; background box & labels visible.
5. Run `verify_sampler_phase2.py` — both scenarios pass.
6. Save & load a preset, confirm snapshot merges (facade + legacy) unchanged.

---

## 11) Troubleshooting Commands

```powershell
# Run non-visual verification
C:/venvs/midi39/Scripts/python.exe verify_sampler_phase2.py

# Print Drumbo’s facade types at runtime (temporary debug)
# inside configure_sampler_facades():
showlog.info(f"[DEBUG] Mixer facade = {type(self._mixer_facade).__name__}")
showlog.info(f"[DEBUG] Preset facade = {type(self._preset_facade).__name__}")
showlog.info(f"[DEBUG] Event bridge = {type(self._event_bridge).__name__}")
```

---

## 12) Migration Status Snapshot

- ✅ Sampler scaffolding in place; utils promoted & tested.
- ✅ Drumbo consumes sampler config & utils; facade‑first playback & presets in place.
- ✅ Verification harness covers facade vs legacy fallback parity.
- ⚠️ Critical: Real UI must bind context/facades through SamplerPlugin **before** legacy registration. If not, UI collapses to 8 dials.

---

## 13) Final Notes for Code‑GPT

- Treat `plugins/drumbo_plugin.py` as the **operational source of truth** until Drumbo is fully relocated to `instruments/drumbo/module.py`.
- Any refactor must preserve: (1) facade‑first, (2) fallback‑safe, (3) UI bank manager invocation order.
- When adding new instruments, mirror Drumbo’s binding/registration order; use the same tests and visual checklist.

