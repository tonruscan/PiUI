# Plugin Creation Quick Checklist

Use this as a quick reference when creating a new module-based plugin.

## Pre-Flight
- [ ] Choose unique `MODULE_ID` (e.g., "vk8m", "tremolo")
- [ ] Choose unique `page_id` (e.g., "vk8m_main", "tremolo_main")
- [ ] Decide on controls (up to 8 dials)
- [ ] Pick control IDs (e.g., "distortion", "reverb_level")

## Step 1: Plugin File
- [ ] Create `plugins/<name>_plugin.py`
- [ ] Define `YourModule(ModuleBase)` class
- [ ] Set `MODULE_ID`, `BUTTONS`, `SLOT_TO_CTRL`
- [ ] Implement `__init__(self)` with NO parameters
- [ ] Implement `on_button(btn_id)` and `on_dial_change(dial_index, value)`
- [ ] Implement `export_state()` and `import_state(state)` for presets
- [ ] Define `YourPlugin(PluginBase)` class with `on_load(app)` method
- [ ] Add module exports at bottom (MODULE_ID, BUTTONS, etc.)
- [ ] Add `Plugin = YourPlugin` at end

## Step 2: Control Definitions
- [ ] Open `config/custom_dials.json`
- [ ] Add entries for each control in `SLOT_TO_CTRL`
- [ ] Each entry needs: `label`, `range`, `type`, `page`

## Step 3: Device Page Button
- [ ] Open `config/device_page_layout.json`
- [ ] Add button entry with `"plugin": "<page_id>"`

## Step 4: Mode Manager
- [ ] Open `managers/mode_manager.py`
- [ ] Add `elif new_mode == "<page_id>": self._setup_<name>()` (line ~135)
- [ ] Add `"<page_id>"` to navigator record list (line ~163)
- [ ] Add `_setup_<name>()` function at end of class

## Step 5: Renderer
- [ ] Open `rendering/renderer.py`
- [ ] Add `"<page_id>"` to page list in line ~89
- [ ] Add `"<page_id>"` to themed_pages list in line ~118

## Step 6: Hardware Driver (Optional)
- [ ] Create `drivers/<device>.py`
- [ ] Implement MIDI/SysEx message functions

## Testing
- [ ] Plugin appears on device page
- [ ] Navigation to plugin works
- [ ] Correct header displays
- [ ] Buttons render with correct labels
- [ ] Dials show proper names (not "Slot 1")
- [ ] Button presses work
- [ ] Dial changes work
- [ ] MIDI output works (if applicable)
- [ ] Preset save works (button 9)
- [ ] Preset load works (button 7)
- [ ] Return to device page works (button 10)

## Common Mistakes to Avoid
- ❌ `def __init__(self, app):` → ✅ `def __init__(self):`
- ❌ Forgetting to add page_id to renderer.py
- ❌ Control IDs in SLOT_TO_CTRL not matching custom_dials.json
- ❌ Calling `set_active_module()` in plugin's on_load()
- ❌ Using `import showlog as log` → ✅ `import showlog`
- ❌ Using `%s` formatting with showlog → ✅ Use f-strings

## Quick Numbers
- **10 buttons** total (IDs "1"-"10")
- **8 dials** max (2 rows x 4 cols, IDs 1-8)
- **5 files** to edit (plugin + 4 config/system files)
- **~30 minutes** for a basic working plugin

## Reference
See `plugins/vk8m_plugin.py` for complete working example.
See `docs/PLUGIN_CREATION_GUIDE.md` for detailed explanations.
