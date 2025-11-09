# Drumbo Backend Manual

_Last updated: 2025-11-07_

This manual documents how the Drumbo mini-dial drum machine works end-to-end inside the refactored UI stack. It is intended for developers who will maintain or extend Drumbo’s code paths, from dial rendering and bank management to audio playback and controller integration.

---

## 1. System Overview

Drumbo is implemented as a module-plus-plugin pair:

- **`plugins/drumbo_plugin.py`** defines the `Drumbo` module class (UI + state) and the `DrumboPlugin` adapter that registers the module as a page with the global plugin manager. The module inherits from `system.module_core.ModuleBase` for shared hardware latch state.
- **`widgets/drumbo_main_widget.py`** supplies the rectangular visualization widget that lives behind the overlayed mini dials.
- **`pages/module_base.py`** owns the reusable dial grid, dirty-rect rendering, dial bank infrastructure, and hook points that Drumbo uses.
- **`assets/dial.py`, `widgets/dial_widget.py`, and `pages/page_dials.py`** provide the dial primitives and rendering surfaces consumed by the bank manager.
- **Audio stack**: Drumbo uses pygame’s mixer to play multi-sampled WAVs stored under `assets/samples/drums/`.
- **Metadata + discovery**: `plugins/drumbo_instrument_scanner.py` walks the sample tree, auto-creates `meta.json` files when absent, and assembles the instrument specs consumed by the runtime metadata loader in `plugins/drumbo_plugin.py`.

The module exposes two banks of eight “mini” dials (mic levels 1–16) that sit on top of the `DrumboMainWidget` surface. Bank switching maps hardware-slot input to the appropriate mic controls while keeping UI and state synchronized.

---

## 2. Initialization Flow

1. **Plugin registration**
   - `DrumboPlugin.on_load()` registers `Drumbo`’s page (`page_id="drumbo_main"`) with the app’s `page_registry`, using `pages.module_base` as the renderer. Rendering metadata marks the page as “high FPS” and dirty-rect friendly.

2. **Module construction**
   - `Drumbo.__init__()` initializes button state, sample caches, audio preferences, and default bank selection. It calls `_ensure_bank_setup()` so bank widgets exist as soon as the module is created.

3. **Widget attachment**
   - The module base creates `DrumboMainWidget` and calls `Drumbo.attach_widget()`. This rehydrates the dial bank manager and stores dial references (`mic_dials_row_1` / `mic_dials_row_2`) on the widget.

4. **Dial registry + state manager integration**
   - Each bank defines `REGISTRY` metadata (`BANK_A_REGISTRY`, `BANK_B_REGISTRY`). `_activate_bank()` copies the appropriate registry into `Drumbo.REGISTRY` and informs `system.cc_registry.load_from_module()` so preset/state systems know about the active controls.

5. **Layout**
   - `_position_mini_dials()` reads layout constants from `config/layout.py` (e.g., `MINI_DIAL_PADDING_X`, `MINI_DIALS_BANK_PADDING_Y`, `MINI_DIAL_TOP_PADDING`) to position the rows of dial widgets over the widget rect. These constants control edge spacing, vertical stacking, and label offsets.

6. **Metadata-driven instrument load**
   - When an instrument is selected from the metadata browser, `load_instrument_from_spec()` stores the spec in `_metadata_specs`, applies dial metadata via `_apply_metadata_bank()`, and refreshes cached bank values. Slots that lack explicit defaults inherit the global fallback `DEFAULT_METADATA_DIAL_VALUE` (default 100) so mic banks produce audio on first load. The same method updates `_sample_path_override` when the metadata points at a non-standard samples directory.

---

## 3. Dial + Bank Infrastructure

### 3.1 Dial widgets

- The bank manager (`pages.module_base.DialBankManager`) builds `DialWidget` instances for each control listed in `DIAL_BANK_CONFIG` (one entry per bank `A`/`B`).
- `DialWidget` wraps a core `Dial` (`assets/dial.py`), applying config from `custom_controls.py` (label, range, options) plus Drumbo’s `dial_size` override (25px radius mini dials).
- Drawing is delegated to `pages.page_dials.redraw_single_dial()` so the mini dials benefit from shared caching and label rendering.

### 3.2 Bank manager lifecycle

- `_ensure_bank_setup()`
  - Retrieves/creates the singleton `DialBankManager` inside `module_base`.
  - Calls `configure_dial_banks()` with `Drumbo.DIAL_BANK_CONFIG`. The config declares `ctrl_ids` (keys into `config/custom_dials.json`), layout hints (grid cell, y-offset), and per-bank dial size.
  - Establishes the `SLOT_TO_CTRL` map so hardware slot indices align to control IDs for the active bank.
  - Updates `button_states["2"]` to mirror the active bank (0 for A, 1 for B).

- `DialBankManager`
  - Builds the per-bank `DialWidget` list and keeps a parallel `bank_values` snapshot for each bank.
  - `set_active_bank()` switches visibility state and replays cached values onto the newly active bank.
  - `capture_active_values()` is called before swaps to persist UI values into the snapshot map.
  - `get_active_widgets()` returns the eight visible widgets; `module_base` hands their `Dial` objects to `dialhandlers.set_dials()` so controller input can target them.

### 3.3 Hardware + controller routing

- When a physical controller sends CC data, `dialhandlers.on_dial_change()` is invoked. The `DialLatchManager` (see below) may defer updates until the hardware crosses the UI value.
- Accepted updates call `midiserver.enqueue_device_message()` with device metadata, CC overrides, and references to the active dial object (for state persistence).
- When UI dials move (mouse drag), `Drumbo.on_dial_change()` delegates to `_apply_mic_value()`, which updates the widget dial in-place, refreshes per-instrument caches, sets the backing module attribute, and flags only that dial as dirty for efficient redraw.

### 3.4 Slot mapping + metadata

- `Drumbo.SLOT_TO_CTRL` maps UI slot numbers (1–8) to specific control IDs from the active bank. `module_base.set_slot_to_ctrl_mapping()` stores this on the module for the dial handlers.
- `config/custom_dials.json` supplies human-readable labels, ranges, and optional enumerations for each mic dial (`"mic_1"` … `"mic_16"`). When adding new controls, update this file so the bank manager inherits the metadata.
- `Drumbo.LABEL_TO_VARIABLE` is auto-generated from the bank registries so every dial label (`M1`…`M16`) can be resolved to its backing attribute (`mic_1_level`, …, `mic_16_level`). The helper `_apply_mic_value()` consumes this map to write module attributes, update the widget, and refresh per-instrument caches in a single call.

### 3.5 Metadata-driven bank wiring

- `load_instrument_from_spec()` is the entry point invoked by the metadata browser. It loads the selected `InstrumentSpec`, resolves the destination slot (`snare`/`kick`), and delegates to `_apply_metadata_bank()` for each declared bank.
- `_apply_metadata_bank()` maps metadata dials onto existing bank widgets, applies label/range defaults, and records a per-bank registry for `module_base`. When every dial in a bank would otherwise default to zero, it injects `DEFAULT_METADATA_DIAL_VALUE` (configurable via `cfg.DRUMBO_METADATA_DEFAULT_LEVEL`, default 100) to guarantee audible mic levels on fresh loads.
- The metadata layer extends `Drumbo.LABEL_TO_VARIABLE` so mic labels from the spec immediately map to module attributes (`mic_1_level` etc.). This ensures per-mic playback discovers the correct gain value without waiting for a dial change event.
- For builds that run without UI control over the bank manager (e.g., headless scans), the fallback logic mirrors the same defaults into the cached bank values so preset exports remain consistent even when widgets are unavailable.
- Metadata originates from `plugins/drumbo_instrument_scanner.py`, which either reads existing `meta.json` files or auto-generates them on the fly. Auto-generated specs seed each mic dial with `AUTO_DIAL_DEFAULT` (100) so runtime defaults and generated metadata stay aligned.

---

## 4. Mini Dial Layout + Rendering

### 4.1 Geometry constants (`config/layout.py`)

- `MINI_DIAL_PADDING_X`: Edge-to-edge horizontal spacing between adjacent mini dials.
- `MINI_DIALS_BANK_PADDING_Y`: Vertical gap between the centerlines of Bank A and Bank B rows.
- `MINI_DIAL_LABEL_PADDING_Y`: Gap between dial circumference and label background.
- `MINI_DIAL_TOP_PADDING`: Distance from widget top edge to the top of the first dial row.

These values are consumed by `Drumbo._position_mini_dials()`, which computes available width inside the widget rect, maintains circular bounds (so dials do not clip), and centers each row. For a single dial the method pins it to the widget center; otherwise it calculates equal spacing using radius + padding.

### 4.2 Label rendering (`assets/ui_label.py`)

- Mini dial detection is radius-based: mini dials use the `radius < cfg.DIAL_SIZE` branch.
- Background rectangles are aligned flush with the dial edge, using the `MINI_DIAL_LABEL_PADDING_Y` offset.
- Theme-aware fill color is resolved through `helper.device_theme.get(...)`, letting Drumbo’s theme override `dial_label_color`.

### 4.3 Dial face renderer (`pages/page_dials.py`)

- Shared caches accelerate painting: dial face surfaces (`_FACE_CACHE`), font objects, and label surfaces per dial.
- Dial shading uses optional supersampling (`cfg.DIAL_SUPERSAMPLE`) and AA shells (`cfg.DIAL_RING_AA_SHELLS`), but Drumbo currently relies on default values for consistency across banks.
- Value formatting respects `Dial.range` or `Dial.options`. Since Drumbo mic levels use raw `[0,127]`, labels render integer values without a unit suffix.

### 4.4 Widget dirty rectangles (`widgets/drumbo_main_widget.py`)

- `DrumboMainWidget.mark_dirty(dial)` stores a reference to the specific dial that changed. During `draw()`, the widget can return the exact union rect of dial + label, avoiding full background redraws.
- MIDI note flashes call `mark_dirty()` to animate the “MIDI [ * ]” indicator; once the flash expires `_midi_settle_pending` triggers a cleanup redraw.

---

## 5. Bank Switching + Buttons

- Button `2` toggles between banks. `Drumbo.on_button()` reads `state_data['label']` when provided, otherwise uses the state index (0 → A, 1 → B) before calling `_activate_bank()` to refresh registries, slot map, and widget bindings.
- Button `1` flips the instrument selection between snare and kick. The module updates `self.current_instrument`, the widget footer text, and associated button state so hardware LEDs stay in sync.
- Buttons `7`, `9`, and `10` use the shared navigation behaviors from `module_base` (presets browser, save dialog, device select). Their metadata lives in `Drumbo.BUTTONS` and uses the `pages.page_dials` schema.
- Other button slots follow the standard pattern; unused buttons render as disabled because no entry exists in the metadata map.

### 5.1 `_activate_bank()` responsibilities

- Deep-copies the selected bank registry (`BANK_A_REGISTRY` or `BANK_B_REGISTRY`) into `Drumbo.REGISTRY`.
- Rebuilds `SLOT_TO_CTRL` for the chosen bank and sends the mapping back through `module_base.set_slot_to_ctrl_mapping()`.
- Captures current dial values, switches the `DialBankManager` active bank, reapplies cached values, and updates the widget `active_bank` property.
- Calls `cc_registry.load_from_module()` so persisted state points at the correct parameter family.
- Writes the new state index into `button_states['2']` before logging the transition.
- Triggers `_push_button_states()` so both `dialhandlers` and `module_base._BUTTON_STATES` reflect the selection immediately (required for button labels/LEDs to stay in sync).

### 5.2 Button state synchronisation

- `button_states["1"]` tracks the snare/kick toggle; `button_states["2"]` tracks the active bank. These values feed hardware LEDs and the on-screen button captions.
- `_push_button_states()` pushes the full dict to `dialhandlers.update_button_state(...)` and mirrors each entry into `module_base._BUTTON_STATES`. A lightweight `("force_redraw", 5)` message is queued so the button row repaint happens without user interaction.
- `_set_instrument()`, `_activate_bank()`, preset loads (`on_preset_loaded()`), MIDI-triggered instrument switches, and module initialization all call `_push_button_states()` to avoid desynchronisation regardless of the trigger.

---

## 6. Hardware Latch & Controller Sync

- `dialhandlers.DialLatchManager` is configured from `config` defaults (`DIAL_LATCH_ENABLED`, `DIAL_LATCH_THRESHOLD`, `DIAL_LATCH_RELEASE`). Drumbo shares this manager with every module that uses the global dial pipeline.
- When a controller value arrives, `DialLatchManager.evaluate()` compares it with the UI dial value. If the delta exceeds the pickup threshold the dial is latched until the hardware crosses back within the release window.
- `Drumbo.on_dial_change()` resets the latch for the affected slot when the move originated from the UI to prevent stale latches.
- Discrete or option-based dials may require lower thresholds. See `docs/bugs/2025-11-05-quadraverb-dial-latch.md` for mitigation strategies if you introduce quantized controls.

---

## 7. Audio & Sample Playback

### 7.1 Sample set layout

- Samples live under `assets/samples/drums/<instrument>/`. Default folders: `snare` and `kick`.
- `_load_samples_for()` lazily loads `.wav` files into `self.sample_sets`. It honours metadata-provided `audio_files` lists, deduplicates paths, and resets the cache to an empty dict when a folder is missing or contains no usable audio so subsequent loads retry cleanly.
- Filenames are tokenised by `_extract_sample_tokens()`, which expects `<instrument>_<category?>_<label>_<seq?>.wav`. The label segment (e.g., `OH`, `ROOM`, `TOP`) becomes the mic key; numeric suffixes drive round-robin sequencing. Both label and sequence metadata are cached in `self.sample_meta` for telemetry.
- Metadata overrides (`spec.samples_path`) update `_sample_path_override` so instruments can reference alternate directories (e.g., shared sample pools). The override is cleared when a new instrument is loaded.
- Round-robin state is primed from the first label’s metadata and clamped to a minimum cycle size of one, protecting against divide-by-zero behaviour when a mic bank contains a single hit.

### 7.2 Mixer initialization

- `_ensure_mixer()` composes mixer kwargs from environment variables and `config/audio.py`: `DRUMBO_SAMPLE_RATE`, `DRUMBO_SAMPLE_SIZE`, `DRUMBO_SAMPLE_CHANNELS`, `DRUMBO_AUDIO_BUFFER`, `DRUMBO_MIXER_CHANNELS`, `DRUMBO_FORCE_AUDIO_REINIT`, `DRUMBO_AUDIO_DEVICE`, `DRUMBO_AUDIO_DEVICE_INDEX`, `DRUMBO_AUDIO_DEVICE_KEYWORD`.
- Tries `pygame.mixer.pre_init()` followed by `pygame.mixer.init()`, retrying without a preferred device if initialization fails. Mixer channels default to 16 but can be overridden.

### 7.3 Playback path

- `_play_sample()` ensures the mixer is ready, resolves the next sound index per mic label, scales volume by MIDI velocity, `self.master_volume`, and the relevant mic dial (`LABEL_TO_VARIABLE`). Each mic label is triggered in sequence so all layers (OH, ROOM, TOP, etc.) fire simultaneously from a single MIDI note.
- The round-robin cursor (`self.sample_indices[...]`) advances independently per mic, while `self.round_robin_index` / `self.round_robin_cycle_size` are updated from the metadata stored during `_load_samples_for()` for UI telemetry.
- Latency diagnostics use `time.perf_counter()` when a note timestamp is provided; helpful when tuning buffer sizes or spotting audio thread stalls.

---

## 8. Drumbo Widget Details

- `DrumboMainWidget` draws the rounded background, footer label block, and MIDI flash indicator (`MIDI [   ]`).
- `set_instrument()` updates the footer instrument text and marks the widget dirty so the change renders immediately.
- `on_midi_note()` triggers a short-lived flash by updating `midi_note_time` and `midi_note_detected`.
- The widget keeps `mic_dials_row_1` and `mic_dials_row_2` populated with dial objects for Banks A and B so minimal dirty rectangles can be computed when a single dial moves.

---

## 9. State Persistence & Presets

- `cc_registry.load_from_module()` registers the active bank controls under the `drumbo` namespace, generating stable `sm_param_id` hashes from labels.
- `dialhandlers.on_dial_change()` persists dial values through `state_manager.manager`, both for UI moves and hardware events.
- Standard preset flows run through `preset_manager` and `preset_ui`. Button `9` opens the save dialog; Button `7` navigates to the preset browser. Drumbo dials participate because they expose the same metadata schema as device pages.

### 9.1 Instrument-specific snapshots

- Drumbo saves only the active instrument’s dials per preset. `PRESET_STATE['variables']` contains:
   - `preset_instrument` (lower-case `snare`/`kick`).
   - `preset_bank_a_values` and `preset_bank_b_values` (eight-element lists for Bank A/B of that instrument).
- `prepare_preset_save()` calls `_capture_instrument_values(self.current_instrument)` before exporting so caches reflect UI edits, then `_update_preset_snapshot()` copies the normalized values into the preset fields.
- `_capture_instrument_values()` / `_apply_instrument_values()` perform a round-trip via `module_base.get_dial_bank_values()` / `set_dial_bank_values()` and refresh `_instrument_bank_values` for the relevant instrument.
- Legacy presets that stored `snare_a_values`, `kick_b_values`, etc., are still supported; `on_preset_loaded()` probes for the new keys first and falls back to the historical schema when missing.

### 9.2 Preset load replay pipeline

- `on_preset_loaded()` resolves the saved instrument (new field, widget state, or legacy data), merges values into `_instrument_bank_values`, and calls `_replay_loaded_dials()`.
- `_replay_loaded_dials()` iterates both banks for the target instrument and funnels every value through `_apply_mic_value()` with `instrument_key_override`:
   - Widget mini dials update in place (dirty rect optional).
   - Module attributes (`mic_X_level`) stay coherent with the visuals.
   - Instrument caches remain isolated—loading a snare preset leaves cached kick values untouched.
   - Snapshot updates are deferred until the replay completes to avoid redundant work.
- After replay the module invokes `_update_preset_snapshot()` and `_push_button_states()` so future saves and button labels/LEDs match the restored instrument immediately.

---

## 10. Configuration Touchpoints

| Area | File(s) | Notes |
| --- | --- | --- |
| Mini dial spacing & layout | `config/layout.py` | Adjust padding constants to reposition dial rows or label offsets. |
| Control metadata | `config/custom_dials.json` | Update labels, ranges, or add new mic controls. |
| Metadata defaults | `plugins/drumbo_plugin.py` (`DEFAULT_METADATA_DIAL_VALUE`), `config/__init__.py` (`DRUMBO_METADATA_DEFAULT_LEVEL`) | Sets the fallback mic level applied when metadata omits dial defaults. |
| Auto-generated meta | `plugins/drumbo_instrument_scanner.py` (`AUTO_DIAL_DEFAULT`) | Controls the default mic level written into newly created `meta.json` files. |
| Bank definitions | `plugins/drumbo_plugin.py` (`DIAL_BANK_CONFIG`, `BANK_A_REGISTRY`, `BANK_B_REGISTRY`) | Ensure `ctrl_ids` align with custom dial keys and registries mirror labels. |
| Theme colors | `plugins/drumbo_plugin.py` (`THEME`) | Overrides dial fill, outlines, button colors, and widget backgrounds. |
| Audio prefs | `config/audio.py`, environment variables | Control sample rate, device selection, buffer sizes, and allowed mixer reconfiguration. |
| Hardware latch tuning | `config/__init__.py` (or whichever config exports `DIAL_LATCH_*`) | Balance pickup responsiveness against jump prevention. |

---

## 11. Extending Drumbo

1. **Add another bank or swap controls**
   - Extend `DIAL_BANK_CONFIG` with a new key (for example `C`) and create a matching registry (`BANK_C_REGISTRY`). Update `_activate_bank()` and `SAMPLE_FOLDERS` as needed.
   - Ensure every `ctrl_id` exists in `config/custom_dials.json` so dial metadata resolves cleanly.

2. **Alter dial geometry**
   - Adjust each bank's `dial_size` or tweak global constants in `config/layout.py`. If you mix sizes, teach `_position_mini_dials()` how to compute spacing per radius.

3. **Add instruments or round robin variants**
   - Populate new folders under `assets/samples/drums/`, extend `SAMPLE_FOLDERS`, and map MIDI notes in `NOTE_MAP`.
   - Update button behavior or introduce a new control to switch instruments if more than two choices exist.

4. **Draw additional HUD elements**
   - Modify `DrumboMainWidget.draw()` to render meters or status text. Maintain correct dirty-rect reporting so the renderer stays efficient.

5. **Expose automation data**
   - If you promote Drumbo controls to device-level automation, call `cc_registry.load_from_device()` or add hybrid registries so other subsystems (network sync, remote keyboard) can discover them.

---

## 12. Debugging Tips

- Use `showlog` to raise logging verbosity; Drumbo emits events tagged `[Drumbo]` plus structured info lines such as `*[Drumbo]` for highlighted logs.
- Per-mic playback logs (`[Drumbo] Mic '<label>' idx=... volume=...`) confirm that each mic layer is firing and report the effective gain after metadata defaults and dial scaling.
- Query `module_base.get_dial_bank_manager()` in a REPL to inspect `bank_values`, `active_bank`, and widget lists during development.
- Audio failures set `_mixer_failed`; check `_mixer_ready` and `_mixer_device` for diagnostics. Forcing a reinit via `DRUMBO_FORCE_AUDIO_REINIT=1` can recover from driver changes.
- Hardware desyncs often indicate latch thresholds that are too tight; temporarily disable latching (`DIAL_LATCH_ENABLED = False`) to confirm the diagnosis.
- Rendering artifacts typically stem from stale caches in `page_dials`; tweak `cfg.DIAL_SUPERSAMPLE` only after clearing caches or bumping the cache key.

---

## 13. Related Documentation

- `docs/DRUMBO_IMPLEMENTATION_MANUAL.md` – Historical context predating the mini dial overhaul.
- `docs/mini_multi_bank_dials_quick_start.md` – Short how-to for multi-bank overlays reused by Drumbo.
- `docs/PLUGIN_HARDWARE_DIALS_QUICKSTART.md` – Deeper explanation of latch expectations and slot mapping.
- `docs/bugs/2025-11-05-quadraverb-dial-latch.md` – Example investigation for latch edge cases.

---

## 14. Operational Fix Log (November 2025)

- **Dirty overlay delay (purple boxes) fixed** – Drumbo stayed in full-frame mode for ~10 seconds after load because `("force_redraw", 5)` was being treated as “five seconds” of full redraws. `_handle_force_redraw()` now interprets integers as raw frame counts (so `5` = five frames). To request a time duration, pass floats (`0.5`) or strings with an `s` suffix (`"0.5s"`). This change lets Drumbo enter dirty mode immediately after the first burst frame, restoring the overlay and avoiding needless CPU spikes.
- **Drumbo partial redraw compatibility** – Keep the page registered with `supports_dirty_rect=True` and ensure there are no lingering entries in `cfg.EXCLUDE_DIRTY` for `"drumbo_main"`. If a profile overrides the config, remove Drumbo from any exclusion tuple so the dirty rect manager can honour widget-level dirty rects.
- **Label background persistence** – Cached label radii (`page_dials`) stop the label background from vanishing during burst redraws. If future label artifacts appear, verify the cache invalidation path (`DialWidget.invalidate_label_cache()`), especially when changing dial sizes dynamically.
- **Inactive bank dimming** – The widget now fades inactive-bank dial visuals. When adding new banks or theming tweaks, reuse the `inactive_alpha` helper so the active bank remains obvious without requiring a full widget repaint.
- **Render flow instrumentation** – `_render()` logs the chosen path (`full`, `dirty-burst`, `idle`). When debugging redraws, search for `[RENDER_FLOW]` in `ui_log.txt` to confirm why the renderer picked a mode. This has proven useful for diagnosing missed dirty marks or plugins that accidentally request long full-frame streaks.

---

## 15. Best Practices for Drumbo & Future Module Pages

- **Request redraws sparingly** – Keep `force_redraw` durations to the minimum frames you need. For UI nudges, 2–5 frames suffice; reserve longer bursts for transitions that truly need them. Document every long-running request so future devs understand the dependency.
- **Treat ints vs. seconds consistently** – Since integers are now frames, use dict syntax (`{"seconds": 1.5}`) or strings (`"1.5s"`) when you really mean seconds. This avoids regressions if FPS targets change per page.
- **Validate dirty-rect readiness** – When introducing a new module widget, confirm it marks dirty regions (via `mark_dirty()`) and does not leak into legacy full-frame paths. Run with `DEBUG_DIRTY_OVERLAY=True` to verify magenta boxes appear around widget updates.
- **Instrument before optimising** – Add scoped logs (e.g., `[DrumboDirty]`, `[BankSwap]`) while investigating, but remove or demote them after solving the issue to keep `ui_log.txt` readable.
- **Snapshot before mutating** – Follow the `_capture_instrument_values()` pattern whenever you mirror UI values into presets or live state caches. This guarantees replay routines have synchronized data and prevents race conditions between widget redraws and preset exports.
- **Respect latch semantics** – When adding new controls, ensure their ranges suit the pickup threshold. Continuous parameters should span enough values that a 10-unit latch threshold feels natural; discrete selectors may need explicit latch disablement to avoid stutter.
- **Coordinate theme keys** – Any new theme fields for module widgets should be mirrored in both the module `THEME` dict and `DrumboMainWidget.apply_theme()` so fallback logic stays predictable.
- **Update documentation alongside code** – Record non-obvious fixes (like force-redraw semantics or cache invalidation strategies) in this manual immediately. Future contributors rely on this log to avoid reintroducing old behaviour bugs.
- **Validate metadata defaults** – When shipping new instruments, confirm their `meta.json` includes sensible dial defaults (or rely on the global fallback). A bank full of zeroes now auto-promotes to the configured default, but explicit metadata remains clearer for future maintainers.

By following this manual a developer can trace Drumbo end to end: mini dial construction and placement, bank orchestration, hardware synchronization, audio playback, and state persistence. That foundation should make future enhancements safer and faster.