# 🧾 UI-Midi-Pi Issue Tracker

| ID | Issue | Description | Status | Priority | Key Files / Components |
|----|--------|--------------|---------|-----------|-------------------------|
| **#1** | **Dirty Rect Fragility** | Widgets would update logic but not redraw visually due to wrong rect sizes, missing clears, or offset errors. | ✅ **Resolved** (DirtyDraw v3) | 🔺 High | `core/app.py`, `widgets/*`, `rendering/dirtydraw.py` |
| **#2** | **Plugin Attribute Misplacement** | Plugin configs (e.g. `SLOT_TO_CTRL`, `CUSTOM_WIDGET`) defined outside class caused silent failures — plugins loaded but drew nothing. | ✅ **Resolved** (class-level enforcement) | 🔺 High | `plugins/vibrato_plugin.py`, `pages/module_base.py` |
| **#3** | **Preset Save/Load Integration** | Plugins had inconsistent preset handling and didn’t restore hardware states properly. | ✅ **Resolved** (PluginBase integration) | 🔺 High | `core/plugin_base.py`, `core/preset_manager.py`, `pages/module_base.py` |
| **#4** | **Preset Dialog Not Updating** | PresetSaveUI text input didn’t render while typing; overlay persisted after closing. | ✅ **Resolved** (force full-frame redraws) | 🔺 High | `preset_ui.py`, `pages/module_base.py`, `core/app.py` |
| **#5** | **No Overlay Redraw Framework** | Overlays lacked dirty-rect integration, causing redraw issues for all modal components. | 🏗️ **Fix in progress** (OverlayBase class) | 🔸 Medium | `core/overlay_base.py`, `preset_ui.py` |
| **#6** | **Plugin Validation Missing** | No automatic checks for malformed or incomplete plugins. | ✅ **Resolved** (`@plugin` decorator + CLI validator) | 🔸 Medium | `core/plugin_registry.py`, `tools/validate_plugins.py` |
| **#7** | **Render System Over-Complexity** | Burst/full/idle modes required manual management; hard to follow logic flow. | 🧠 **Ongoing simplification** under DirtyDraw v3 framework | 🔹 Low | `core/app.py`, `core/frame_controller.py`, `pages/module_base.py` |

---

## 🔧 Notes

- **DirtyDraw v3** now handles all widget drawing safely — offset, padding, clear, and present in one call.  
- **PluginBase** standardizes plugin creation, preset handling, and rendering lifecycle.  
- **OverlayBase** (in development) will unify redraw behavior for all dialogs and modals.  
- **Validation Tools** prevent future misconfiguration errors at import time.  
