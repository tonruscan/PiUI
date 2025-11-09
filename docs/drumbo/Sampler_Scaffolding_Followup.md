# Follow-Up Instructions for Code GPT – Sampler Scaffolding Kickoff

These are the precise instructions to begin the **Sampler + Drumbo migration scaffolding** phase based on prior feedback and GPT’s proposed refinements.

---

## ✅ Objectives

Proceed with scaffolding the new `plugins/sampler/` hierarchy while maintaining backward compatibility with all current Drumbo integrations.

---

## 1. InstrumentDescriptor Dataclass

Implement `InstrumentDescriptor` as a dataclass with optional metadata and helper methods:

```python
from dataclasses import dataclass
from typing import Optional

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

    def to_dict(self):
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

Make sure the class remains **mutable** so future registry updates can modify descriptors dynamically.

---

## 2. Compatibility Exports

Keep legacy imports working by exporting both the plugin entry and the raw class:

```python
# plugins/drumbo_plugin.py
from plugins.sampler.instruments.drumbo.module import DrumboInstrument

Plugin = DrumboInstrument
Drumbo = DrumboInstrument
```

This ensures existing code using either `from plugins import drumbo_plugin` or direct imports like `from plugins.drumbo_plugin import Drumbo` will continue functioning during migration.

---

## 3. Core Test Runner

Add a lightweight standalone test harness:

```
plugins/sampler/core/tests/__init__.py
plugins/sampler/core/tests/run_tests.py
```

### `run_tests.py`
```python
# plugins/sampler/core/tests/run_tests.py
import unittest

if __name__ == "__main__":
    unittest.main("plugins.sampler.core.tests", verbosity=2)
```

This allows running `python -m plugins.sampler.core.tests.run_tests` without requiring integration into the global test system.

---

## 4. Scaffolding Order

Execute in this exact order:

1. Create all directories and empty modules with docstrings.
2. Implement `InstrumentDescriptor`, `InstrumentModule`, and `InstrumentContext` in `engine.py`.
3. Add empty stubs for `mixer_facade.py`, `preset_facade.py`, and `event_bridge.py`.
4. Scaffold the `instrument_registry` with a dummy registration for Drumbo.
5. Add compatibility shims (`drumbo_plugin.py`, `drumbo_instrument_service.py`).
6. Add minimal tests verifying imports and registry discovery.

---

## 5. Verification Checklist

After scaffolding, confirm:

- ✅ Folder structure matches the plan.
- ✅ `from plugins.drumbo_plugin import Drumbo` imports successfully.
- ✅ `from plugins.sampler.plugin import Plugin` imports successfully.
- ✅ Running `python plugins/sampler/core/tests/run_tests.py` discovers placeholder tests.

Print the folder tree and created files for review before moving on to facade implementation.

---

## 6. Pause for Review

After scaffolding and stubs are created, **pause before populating the facades or moving any functional code**.  
The next phase will review the interfaces and confirm how the core interacts with instrument modules before continuing migration.

---

This ensures a controlled, verifiable transition with zero regressions.
