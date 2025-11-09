# Presets & Patches – Developer Guide

This document summarizes how presets and patches work across these modules:

- device_presets.py
- device_patches.py
- pages/presets.py
- control/presets_control.py

It also outlines the Internal vs External flows and key config knobs.

## Concepts

- Internal patches: Built-in/device patches defined in `config/patches.json`.
  - Access via `device_patches.list_patches(device_name)` → list of `(program_number, name)` pairs
  - Displayed as: `NN: Name`
- External presets (Pi presets): User-saved presets on the Pi in `config/device_presets.json`.
  - Access via `device_presets.list_presets(device_name, page_id)` → list of names (no numbers)
  - Hold 8 dial values per preset

Current page-init preference: Try Internal (device patches) first; fall back to External (Pi presets).

---

## device_presets.py (Pi presets + patch lookup)

- load() / save()
  - Loads/saves `config/device_presets.json` into `_presets_cache`.

- store_preset(device_name, page_id, preset_name, dial_values)
  - Persists 8-value dial arrays under device/page/preset.

- get_pi_preset(device_name, page_id, preset_name)
  - Returns the stored 8 dial values for Quadraverb-like devices.

- list_presets(device_name, page_id=None)
  - With `page_id`: returns names for that page or falls back to first available among `Reverb`, `01`, `Presets`, `Main`.
  - Without `page_id`: returns top-level page IDs for a device.

- delete_preset(...)
  - Removes a preset from cache and persists changes.

- get_patch(device_name, preset_name)
  - For flat devices (non-Quadraverb), matches names against internal patches from `patches.json` and returns `{ "program": int, "name": str }`.

- get_preset(device_name, page_id, preset_name)
  - Wrapper: If Quadraverb-like, returns Pi preset values. Otherwise returns patch info for Program Change.

- load_patches() / list_device_patches(device_name)
  - Loads `config/patches.json` into a process-wide cache and returns sorted names per device.

Notes:
- Auto-load: `load()` is called on import to populate `_presets_cache`.

---

## device_patches.py (Internal/device patches)

- load()
  - Loads `config/patches.json` into `_patch_cache`.

- list_patches(device_name)
  - Returns a list of `(program_number, name)` pairs.
  - Supports partial-name device matching.
  - Results sorted numerically by program key.

Notes:
- Auto-load: `load()` runs on import.

---

## pages/presets.py (Presets page UI)

- init(screen, device_name, section_name)
  - Sets page state and builds buttons:
    1) Tries `device_patches.list_patches(device)` and formats as `NN: Name`.
    2) If none found, falls back to `device_presets.list_presets(device, section)`.
  - Uses `_build_preset_buttons` (shared) for formatting/layout.
  - Calls `control.presets_control.set_context_menu()` to wire header dropdown.

- reload_presets(screen, preset_names)
  - Clears and rebuilds the buttons with provided names and redraws.

- _build_preset_buttons(screen, preset_names)
  - Shared builder used by both `init` and `reload_presets`.
  - Trims names to `cfg.PRESET_NAME_MAX_LENGTH` (default 22) with `rstrip()`.
  - Lays out a grid based on config: columns, margins, spacing, button sizes.

- draw(screen, offset_y=0)
  - Renders header, buttons (with highlight), a scrollbar, and logs.
  - `offset_y` comes from the header dropdown animation so content shifts down when the menu opens.

- handle_event(event, msg_queue, screen=None)
  - On press: detects which preset was tapped and either:
    - Sends full dial values for Pi presets (Quadraverb-like), or
    - Sends MIDI Program Change for flat devices.
  - Updates LED/LCD labels (network or local I²C).
  - On drag: scrolls with `cfg.PRESET_SCROLL_SPEED`.

- highlight_preset(screen, raw_message)
  - Reacts to `[PATCH_SELECT] DEVICE|NN.Name` messages; highlights matching button.

- ensure_visible(preset_num, screen)
  - Scrolls so the highlighted preset is fully visible (accounts for header height).

---

## control/presets_control.py (Header dropdown wiring)

- set_context_menu()
  - Defines two header buttons and their actions:
    - External → action `set_mode_presets`
    - Internal → action `set_mode_patches`
  - Sends to header via `showheader.set_context_buttons(buttons)`.

- handle_header_action(action, ui)
  - `set_mode_patches`: Gets device patches via `device_patches.list_patches`, formats `NN: Name`, calls `pages.presets.reload_presets(...)`.
  - `set_mode_presets`: Gets Pi presets via `device_presets.list_presets(device, section)`, calls `reload_presets(...)`.

- handle_message(tag, payload, ui)
  - For tag `PATCH` with an integer `payload["preset"]`, updates `pages.presets.selected_preset`.

---

## Internal vs External flow

- On page init (`pages/presets.init`):
  1) Internal/device patches (from `patches.json`) → “NN: Name” list.
  2) If none, fall back to External/Pi presets (`device_presets.json`).

- On header toggle (`control/presets_control.handle_header_action`):
  - Internal button → loads device patches and formats `NN: Name`.
  - External button → loads Pi presets by page.

- On selection (`pages/presets.handle_event`):
  - Quadraverb-like: Send 8 dial values via `midiserver.send_preset_values`.
  - Flat devices: Send MIDI Program Change via `midiserver.send_program_change`.

---

## Styling & config hooks (header dropdown)

Defined in `showheader.py` with fallbacks to these `cfg` keys:

- Menu panel:
  - `MENU_HEIGHT` (default 60–200 depending on recent edits)
  - `MENU_COLOR` (default `#1A1A1A`)
  - `MENU_ANIM_SPEED` (default 0.25)

- Buttons:
  - `MENU_BUTTON_WIDTH` (140), `MENU_BUTTON_HEIGHT` (44), `MENU_BUTTON_GAP` (12)
  - `MENU_BUTTON_RADIUS` (10), `MENU_BUTTON_TOP_PAD` (8)
  - `MENU_BUTTON_COLOR` (`#333333` or current theme), `MENU_BUTTON_PRESSED_COLOR` (`#555555`)
  - `MENU_BUTTON_BORDER_COLOR` (`#000000`), `MENU_BUTTON_BORDER_WIDTH` (0)
  - `MENU_BUTTON_FONT` (falls back to `MENU_FONT` then `cfg.dial_font()`)
  - `MENU_BUTTON_FONT_SIZE` (falls back to `MENU_FONT_SIZE` then 20)
  - `MENU_BUTTON_TEXT_COLOR` (falls back to `MENU_FONT_COLOR` then `#FFFFFF`)
  - `MENU_BUTTON_ANCHOR` ("center" to move with menu, "top" to sit under header)

Header bar itself uses:
- `HEADER_HEIGHT`, `HEADER_TEXT_COLOR`, `HEADER_BACKGROUND`
- Back/burger metrics and padding: `BACK_BUTTON_SIZE`, `BACK_BUTTON_LEFT_PAD`, `BACK_BUTTON_TOP_PAD`, `BURGER_BUTTON_SIZE`, `BURGER_BUTTON_RIGHT_PAD`, `BURGER_BUTTON_TOP_PAD`

---

## Preset button styling (Presets page)

Use these `config.py` keys in `pages/presets.py`:
- Colors: `PRESET_LABEL_HIGHLIGHT`, `PRESET_FONT_HIGHLIGHT`, `PRESET_BUTTON_COLOR`, `PRESET_TEXT_COLOR`, `SCROLL_BAR_COLOR`
- Layout: `NUMBER_OF_PRESET_COLUMNS`, `PRESET_BUTTON_WIDTH`, `PRESET_BUTTON_HEIGHT`, `PRESET_MARGIN_X`, `PRESET_MARGIN_Y`, `PRESET_SPACING_Y`
- Text: `PRESET_FONT_SIZE`, `PRESET_NAME_MAX_LENGTH`
- Scrolling: `PRESET_SCROLL_SPEED`

---

## Tips

- Consistent formatting: `_build_preset_buttons` is the single source of truth for button layout and name trimming.
- Numbered display: Only internal/device patches are formatted as `NN: Name`.
- Highlight logic relies on the `NN:` prefix when present.
- If you change `HEADER_HEIGHT`, also review any usages that assume a default in scrolling/visibility.

