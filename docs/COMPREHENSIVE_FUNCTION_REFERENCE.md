# Comprehensive Function Reference Manual
## UI Application V2 - Complete Codebase Documentation

**Generated:** October 31, 2025  
**Purpose:** Complete reference for all functions, modules, and dependencies in the UI application

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Core System (`core/`)](#core-system)
3. [Managers (`managers/`)](#managers)
4. [System (`system/`)](#system)
5. [Rendering (`rendering/`)](#rendering)
6. [Pages (`pages/`)](#pages)
7. [Devices (`device/`)](#devices)
8. [Control Modules (`control/`)](#control-modules)
9. [Assets & UI Components (`assets/`)](#assets--ui-components)
10. [Utilities (`utils/`)](#utilities)
11. [Handlers (`handlers/`)](#handlers)
12. [Initialization (`initialization/`)](#initialization)
13. [Root Level Modules](#root-level-modules)
14. [Dependency Map](#dependency-map)
15. [Data Flow](#data-flow)

---

## Architecture Overview

### Modern V2 Architecture

The application has been refactored from a monolithic 1000+ line `ui.py` into a modular, service-oriented architecture:

```
ui.py (50 lines)
  └─> core/app.py (UIApplication)
       ├─> core/display.py (DisplayManager)
       ├─> core/loop.py (EventLoop)
       ├─> core/services.py (ServiceRegistry)
       ├─> core/event_bus.py (EventBus)
       ├─> core/page_registry.py (PageRegistry)
       ├─> managers/* (DialManager, ButtonManager, ModeManager, etc.)
       ├─> rendering/* (Renderer, DirtyRectManager, FrameController)
       ├─> handlers/* (GlobalEventHandler, DialsEventHandler, etc.)
       ├─> pages/* (page_dials, device_select, patchbay, mixer, etc.)
       └─> system/* (StateManager, CCRegistry, EntityRegistry, etc.)
```

### Key Design Patterns

1. **Service Registry Pattern**: Centralized dependency injection container
2. **Page Registry Pattern**: Dynamic page loading and routing
3. **Event Bus Pattern**: Decoupled pub/sub messaging
4. **Mixin Pattern**: Composable functionality (HardwareMixin, RenderMixin, MessageMixin)
5. **Manager Pattern**: Separated concerns for dials, buttons, modes, presets
6. **State Management**: Centralized state with StateManager + CCRegistry

---

## Core System (`core/`)

### `core/app.py` - UIApplication

**Purpose:** Main application coordinator. Manages application lifecycle, subsystems, and event loop.

#### Functions:

##### `__init__(self)`
Initializes all core components and sets up initial state.
- Creates ServiceRegistry, EventBus, PageRegistry
- Initializes manager placeholders
- Sets up shared state (device_behavior_map, exit_rect)

##### `initialize(self)`
Initializes all subsystems in correct order.
- Display initialization (`_init_display()`)
- Logging setup (`_init_logging()`)
- State management (`_init_state_management()`)
- Device loading (`_init_devices()`)
- Manager creation (`_init_managers()`)
- Page registration (`_init_pages()`)
- Hardware connections (`_init_hardware()`)
- Event handling setup (`_init_event_handling()`)
- Initial page setup (`_init_initial_page()`)

##### `run(self)`
Main application event loop.
- Processes pygame events (mouse, keyboard, quit)
- Updates state (`_update()`)
- Renders frame (`_render()`)
- Controls frame rate (adaptive FPS based on mode)

##### `_handle_event(self, event: pygame.event.Event)`
Routes events to appropriate handlers.
- Checks for burst mode (mouse clicks end burst)
- Global event handling (exit, back button)
- Header event handling (burger menu, navigation)
- Page-specific event routing via PageRegistry

##### `_update(self)`
Updates application state each frame.
- Updates header animation
- Creates UIContext for current state
- Processes message queue
- Persists state to StateManager

##### `_render(self)`
Renders the current frame.
- Checks if full frame redraw needed
- Renders log bar only (idle mode) or full frame
- Handles header animation offset
- Controls dirty rect optimization

##### `_draw_full_frame(self, offset_y: int)`
Draws a complete frame.
- Delegates to Renderer with current mode context

##### Message Callback Handlers:

- **`_handle_dial_update(dial_id, value, ui_context)`**: Updates dial value, persists to StateManager, triggers burst mode
- **`_handle_mode_change(new_mode)`**: Switches UI mode/page
- **`_handle_device_selected(msg)`**: Loads device, button behavior, registry, switches to device page
- **`_handle_entity_select(msg)`**: Handles entity selection (devices/modules)
- **`_handle_force_redraw(msg)`**: Forces full redraw for N frames
- **`_handle_remote_char(msg, ui_context)`**: Handles remote keyboard input
- **`_handle_patch_select(msg, ui_context)`**: Handles patch/preset selection

##### `cleanup(self)`
Cleans up resources on exit.

**Dependencies:**
- `core.display.DisplayManager`
- `core.loop.EventLoop`
- `core.services.ServiceRegistry`
- `core.event_bus.EventBus`
- `core.page_registry.PageRegistry`
- `core.ui_context.UIContext`
- `core.mixins.*`
- `managers.*`
- `rendering.*`
- `handlers.*`
- `pages.*`
- `system.*`
- `config`, `showlog`, `showheader`, `dialhandlers`, `navigator`, `devices`

---

### `core/display.py` - DisplayManager

**Purpose:** Manages pygame display and screen initialization.

#### Functions:

##### `__init__(self, width=800, height=480, fullscreen=True)`
Initializes display configuration.

##### `initialize(self) -> pygame.Surface`
Creates pygame display surface.
- Initializes pygame
- Sets display mode (fullscreen or windowed)
- Hides cursor
- Returns screen surface

##### `get_screen(self) -> pygame.Surface`
Returns current screen surface.

##### `get_size(self) -> Tuple[int, int]`
Returns screen dimensions.

##### `cleanup(self)`
Cleans up pygame display.

**Dependencies:** `pygame`

---

### `core/event_bus.py` - EventBus

**Purpose:** Publish/subscribe event system for decoupled messaging.

#### Functions:

##### `__init__(self)`
Initializes empty subscriber dictionary.

##### `subscribe(self, event_type: str, callback: Callable)`
Subscribes a callback to an event type.

##### `unsubscribe(self, event_type: str, callback: Callable)`
Removes a callback subscription.

##### `publish(self, event_type: str, data: Any = None)`
Publishes an event to all subscribers.
- Calls all subscribed callbacks with data
- Catches and logs errors in callbacks

##### `clear(self, event_type: str = None)`
Clears subscribers (all or specific event type).

##### `subscriber_count(self, event_type: str) -> int`
Returns count of subscribers for an event.

##### `list_events(self) -> List[str]`
Returns list of all event types with subscribers.

**Dependencies:** `showlog`

---

### `core/loop.py` - EventLoop

**Purpose:** Main event loop coordinator with frame timing.

#### Functions:

##### `__init__(self)`
Initializes event loop and clock.

##### `add_handler(self, handler: Callable)`
Adds an event handler to the loop.

##### `run(self, update_callback: Callable, render_callback: Callable, target_fps=60)`
Runs the main event loop.
- Processes pygame events
- Calls update callback
- Calls render callback
- Controls frame rate

##### `stop(self)`
Stops the event loop.

##### `get_fps(self) -> float`
Returns current FPS.

**Dependencies:** `pygame`

---

### `core/page_base.py` - Page

**Purpose:** Base class for UI pages (optional inheritance).

#### Functions:

##### `handle_event(self, event, msg_queue, screen=None)`
Handles pygame events for this page.

##### `draw(self, screen, offset_y=0, **kwargs)`
Draws the page.

##### `draw_ui(self, screen, *args, **kwargs)`
Alternative draw method.

##### `update(self)`
Updates page state.

##### `init(self, *args, **kwargs)`
Initializes/reinitializes page.

##### `on_enter(self)` / `on_exit(self)`
Called when page becomes active/inactive.

**Dependencies:** `pygame`, `queue`

---

### `core/page_registry.py` - PageRegistry

**Purpose:** Dynamic page registration and lookup system. Eliminates hardcoded page branching.

#### Functions:

##### `__init__(self)`
Initializes empty page registry.

##### `register(self, page_id, module, label=None, meta=None)`
Registers a page with its handlers.
- Extracts `handle_event`, `draw`, `draw_ui`, `update`, `init` from module
- Stores metadata

##### `get(self, page_id) -> Optional[Dict]`
Returns page dictionary by ID.

##### `has(self, page_id) -> bool`
Checks if page exists.

##### `all(self) -> list`
Returns all registered pages.

##### `list_ids(self) -> list`
Returns list of all page IDs.

##### `unregister(self, page_id)`
Removes a page from registry.

##### `get_handler(self, page_id, handler_name) -> Optional[Callable]`
Gets specific handler for a page.

##### `call_handler(self, page_id, handler_name, *args, **kwargs) -> Any`
Calls a page handler if it exists.

**Dependencies:** `showlog`

---

### `core/services.py` - ServiceRegistry

**Purpose:** Dependency injection container for loosely coupling components.

#### Functions:

##### `__init__(self)`
Initializes empty service registry.

##### `register(self, key: str, instance: Any)`
Registers a service instance.

##### `get(self, key: str) -> Optional[Any]`
Gets a service by key.

##### `require(self, key: str) -> Any`
Gets a required service, raises exception if missing.

##### `has(self, key: str) -> bool`
Checks if service is registered.

##### `unregister(self, key: str)`
Removes a service.

##### `clear(self)`
Clears all services.

##### `list_services(self) -> list`
Returns list of all service keys.

**Dependencies:** None

---

### `core/ui_context.py` - UIContext

**Purpose:** Type-safe container for UI state passed between components.

#### DataClass Fields:

- `ui_mode: str` - Current UI mode/page
- `screen: pygame.Surface` - Screen surface
- `msg_queue: queue.Queue` - Message queue
- `dials: list` - List of Dial objects
- `select_button: Callable` - Button selection function
- `header_text: str` - Header text
- `prev_mode: Optional[str]` - Previous mode
- `selected_buttons: Optional[set]` - Selected button set
- `device_name: Optional[str]` - Current device name
- `page_id: Optional[str]` - Current page ID

**Dependencies:** `pygame`, `queue`, `dataclasses`

---

### `core/mixins/` - Mixins

#### `hardware_mixin.py` - HardwareMixin

**Purpose:** Hardware initialization and cleanup.

##### `_init_hardware(self)`
Initializes MIDI, CV, network connections.

##### `_cleanup_hardware(self)`
Cleans up hardware connections.

**Dependencies:** `showlog`, `dialhandlers`, `initialization.HardwareInitializer`

#### `message_mixin.py` - MessageMixin

**Purpose:** Message queue handling and callback routing.

##### Message Handlers:
- `_handle_dial_update()` - Dial value updates
- `_handle_mode_change()` - Mode switching
- `_handle_device_selected()` - Device selection
- `_handle_entity_select()` - Entity selection
- `_handle_force_redraw()` - Force redraw
- `_handle_remote_char()` - Remote input
- `_handle_patch_select()` - Patch selection
- `_persist_current_page_dials()` - State persistence

**Dependencies:** `showlog`, `dialhandlers`, `system.state_manager`, `system.entity_handler`

#### `render_mixin.py` - RenderMixin

**Purpose:** Rendering operations.

##### `_render(self)`
Renders current frame with dirty rect optimization.

##### `_draw_full_frame(self, offset_y: int)`
Draws complete frame.

**Dependencies:** `pygame`, `showlog`, `showheader`

---

## Managers (`managers/`)

### `dial_manager.py` - DialManager

**Purpose:** Manages dial creation, state, and MIDI CC mapping.

#### Functions:

##### `__init__(self, screen_width=800)`
Initializes dial manager with layout configuration.

##### `rebuild_dials(self, device_name=None) -> List[Dial]`
Rebuilds all 8 dials with current configuration.
- Calculates grid layout
- Creates Dial objects
- Assigns CC numbers
- Attaches StateManager mapping if device provided

##### `_attach_state_manager_mapping(self, device_name: str)`
Attaches StateManager source and param_id to each dial using device REGISTRY.

##### `get_dials(self) -> List[Dial]`
Returns current dial list.

##### `get_dial_by_id(self, dial_id: int) -> Optional[Dial]`
Finds dial by ID.

##### `update_dial_value(self, dial_id: int, value: int)`
Updates dial value and display text.

##### `clear_dials(self)`
Clears all dials.

**Dependencies:** `assets.dial.Dial`, `config`, `dialhandlers`, `showlog`, `system.cc_registry`

---

### `button_manager.py` - ButtonManager

**Purpose:** Manages button selection, behavior, and per-device memory.

#### Functions:

##### `__init__(self)`
Initializes button state tracking.

##### `select_button(self, which: Optional[str])`
Selects a button (1-10 or None).

##### `get_selected_left_page_or_none(self) -> Optional[str]`
Returns selected left page button (1-4) or None.

##### `remember_left_page(self)`
Remembers currently selected left page button.

##### `restore_left_page(self, default="1") -> str`
Restores last selected left page button.

##### `set_button_behavior_map(self, behavior_map: Dict)`
Sets active button behavior map from device.

##### `get_button_behavior(self, button_id: str) -> str`
Returns behavior type for a button ("state", "nav", "transient").

##### `remember_device_button(self, device_name: str, button_id: str)`
Remembers which button was last active for a device.

##### `get_device_button(self, device_name: str) -> Optional[str]`
Gets last remembered button for a device.

##### `set_default_device_button(self, device_name: str, button_id: str)`
Sets default button if none exists.

##### `get_pressed_button(self) -> Optional[str]`
Returns currently pressed button.

##### `get_selected_buttons(self) -> Set[str]`
Returns set of selected buttons.

**Dependencies:** `showlog`

---

### `mode_manager.py` - ModeManager

**Purpose:** Manages UI mode/page switching and transitions.

#### Functions:

##### `__init__(self, dial_manager, button_manager, screen=None)`
Initializes mode manager with references to other managers.

##### `get_current_mode(self) -> str` / `get_previous_mode(self) -> Optional[str]`
Returns current/previous UI mode.

##### `get_header_text(self) -> str` / `set_header_text(self, text: str)`
Gets/sets header text.

##### `request_full_frames(self, count: int)`
Requests N full redraw frames.

##### `needs_full_frame(self) -> bool`
Checks if full frame redraw needed.

##### `switch_mode(self, new_mode: str, persist_callback=None, device_behavior_map=None)`
Switches to a new UI mode/page.
- Persists current page state
- Updates navigation history
- Sets up new page
- Requests full frames for transition

##### Mode Setup Functions:
- `_setup_device_select()` - Setup device selection
- `_setup_dials(device_behavior_map)` - Setup dials page
- `_setup_presets()` - Setup presets page
- `_setup_patchbay()` - Setup patchbay
- `_setup_mixer()` - Setup mixer
- `_setup_vibrato()` - Setup vibrato maker
- `_setup_module_presets()` - Setup module presets

##### Context Handlers:
- `_handle_dials_from_device_select()` - Entry from device select
- `_handle_dials_from_presets()` - Entry from presets
- `_handle_dials_restore_last_button()` - Restore last button state
- `_restore_preset(device_name, preset_info)` - Restore preset values

**Dependencies:** `navigator`, `dialhandlers`, `showlog`, `config`, `managers.preset_manager`, `control.global_control`, `devices`, `midiserver`, `unit_router`, `system.cc_registry`

---

### `preset_manager.py` - PresetManager

**Purpose:** Modular preset save/load system for any page/module.

#### Functions:

##### `__init__(self, config_path="config/save_state_vars.json")`
Initializes preset manager and starts autosave thread.

##### `_load_config(self) -> Dict`
Loads save state variables configuration.

##### `get_page_config(self, page_id: str, module_instance=None) -> Optional[Dict]`
Gets configuration for a page/module.
- Priority: module's PRESET_STATE → auto-discovered from REGISTRY → save_state_vars.json

##### `_auto_discover_from_registry(self, module_instance, registry: Dict) -> Optional[Dict]`
Auto-discovers preset configuration from module's REGISTRY.

##### `save_preset(self, page_id: str, preset_name: str, module_instance, widget=None) -> bool`
Saves a preset.
- Saves module variables
- Saves widget state
- Saves button states
- Writes to JSON file

##### `load_preset(self, page_id: str, preset_name: str, module_instance, widget=None) -> bool`
Loads a preset.
- Stops vibrato before load (if applicable)
- Restores button states first
- Restores module variables
- Calls `on_dial_change` for each variable (to apply CV)
- Restores widget state
- Restarts vibrato if needed

##### `list_presets(self, page_id: str) -> List[str]`
Lists all presets for a page.

##### `delete_preset(self, page_id: str, preset_name: str) -> bool`
Deletes a preset file.

##### `get_preset_data(self, page_id: str, preset_name: str) -> Optional[Dict]`
Gets raw preset data without applying it.

**Dependencies:** `json`, `os`, `pathlib`, `showlog`

---

## System (`system/`)

### `state_manager.py` - StateManager

**Purpose:** Centralized runtime state management. Stores live runtime state (value/semantic/uid/active/family/cc). Canonical dial metadata lives in registry.

#### Functions:

##### `init(base_dir=None)`
Initializes paths and global StateManager instance.

##### `create_knob(self, source_type, source_name, param_id, label, value=0, range_=None)`
Registers a new knob entry for a device or module.

##### `set_value(self, source_name: str, param_id: str, value: int)`
Updates stored value for a knob, marks dirty.

##### `get_value(self, source_name: str, param_id: str)`
Returns value for a knob or None if not found.

##### `get_all_for_source(self, source_name: str) -> dict`
Returns {param_id: value} for all knobs from a source.

##### `save_now(self)`
Immediately writes all knob states to disk (atomic).

##### `_load_from_disk(self)`
Loads knob states from disk if present.

##### `_autosave_loop(self, interval=5.0)`
Background autosave thread loop.

##### Legacy Static Functions:
- `register_instance()` - Create/upsert live instance entry
- `set_value()` - Update value for live instance
- `get_state()` - Return snapshot of all live states
- `load()` - Load from JSON
- `save_now()` - Write to JSON atomically

**Dependencies:** `os`, `json`, `time`, `tempfile`, `threading`, `config`, `showlog`

---

### `cc_registry.py` - CCRegistry

**Purpose:** CC number allocation and device/module REGISTRY loading into StateManager.

#### Functions:

##### `init()`
Loads existing CC registry from JSON.

##### `allocate(family: str, label: str) -> int`
Allocates a new CC number for a family/label pair (0-127).

##### `lookup(family: str, label: str) -> int`
Returns CC for given family/label, or -1 if missing.

##### `_make_param_id(device: str, label: str) -> str`
Generates 4-digit hex hash from device + label.

##### `load_from_device(device_name: str)`
Imports /device/{name}.py and registers dials into StateManager.
- Loads device REGISTRY
- Creates knobs in StateManager (8 dials)
- Handles EMPTY dials

##### `load_from_module(module_name: str, registry=None, device_name=None)`
Registers module's REGISTRY into StateManager.
- Namespace: `{DEVICE}:{MODULE}` if device_name provided
- Creates knobs for all slots

##### `attach_mapping_to_dials(device_name: str, dials: list)`
Attaches sm_source_name/sm_param_id to Dial objects based on labels.

**Dependencies:** `os`, `sys`, `json`, `threading`, `hashlib`, `importlib`, `showlog`, `config`, `system.state_manager`

---

### `entity_registry.py` / `entity_handler.py`

**Purpose:** Entity (device/module) registration and handling.

(Similar pattern to cc_registry - manages entity metadata and lifecycle)

**Dependencies:** `showlog`, `importlib`

---

## Rendering (`rendering/`)

### `renderer.py` - Renderer

**Purpose:** Main rendering coordinator for all UI pages.

#### Functions:

##### `__init__(self, screen, preset_manager=None, page_registry=None)`
Initializes renderer with references.

##### `draw_current_page(self, ui_mode, header_text, dials, radius, pressed_button, offset_y=0)`
Renders the current page.
- Clears background
- Guards for transitions
- Uses PageRegistry for dynamic dispatch
- Special handling for preset pages (UnifiedPresetManager)
- Draws header and log bar

##### `_draw_header(self, ui_mode, header_text, offset_y=0)`
Draws header with optional device theme.

##### `_draw_log_bar(self)`
Draws footer/log bar with FPS, CPU, time.

##### `present_frame(self)`
Presents rendered frame (`pygame.display.flip()`).

##### `draw_log_bar_only(self, fps: float)`
Draws only log bar (for dirty rect optimization).

**Dependencies:** `pygame`, `showlog`, `showheader`, `dialhandlers`, `navigator`, `config`

---

### `dirty_rect.py` - DirtyRectManager

**Purpose:** Optimizes rendering using dirty rectangles.

(Tracks dirty regions, manages burst mode for dial updates)

---

### `frame_control.py` - FrameController

**Purpose:** Adaptive frame rate control.

(Manages FPS targets based on page type and activity)

---

## Pages (`pages/`)

### `page_dials.py` - Dials Page

**Purpose:** Main 8-dial page with optimized rendering.

#### Functions:

##### `draw_ui(screen, dials, radius, exit_rect, header_text, pressed_button=None, offset_y=0)`
Draws the full dials page.
- Renders 8 dials with caching
- Draws 10 buttons (left column 1-5, right column 6-10)
- Uses device BUTTONS configuration
- Handles mute state visualization
- Theme-aware colors

##### `get_device_button_specs(device_name: str)`
Loads BUTTONS from device module.
- Tries multiple import paths
- Returns dict { "1": spec, ..., "10": spec }

##### `_get_font(size: int)`
Cached font loading.

##### `_build_dial_face(radius, panel_color, fill_color, outline_color, outline_w)`
Pre-renders dial face with supersampling.

##### `_get_dial_face(...)`
Cached dial face retrieval.

##### `_get_label_surface_for_dial(d, main_font, text_color, unit_text)`
Cached label surface for dial.

##### `redraw_single_dial(screen, d, offset_y=0, device_name=None, is_page_muted=False, update_label=True, force_label=True)`
Repaints just one dial (optimization).
- Returns update rect for `pygame.display.update()`

**Features:**
- Supersampling for smooth dials
- Font caching
- Surface caching (faces, labels)
- Fast single-dial updates
- Theme support
- Mute state visualization
- Device-specific button configuration

**Dependencies:** `math`, `pygame`, `pygame.gfxdraw`, `showlog`, `helper`, `config`, `quadraverb_driver`, `importlib`, `assets.ui_button`, `assets.ui_label`, `dialhandlers`

---

### Other Pages

- **`device_select.py`** - Device selection grid
- **`patchbay.py`** - Patchbay with ports and connections
- **`mixer.py`** - Mixer page with faders
- **`presets.py`** - Preset browser
- **`module_base.py`** (vibrato) - Vibrato Maker module
- **`module_presets.py`** - Module preset loader

(Each has similar pattern: `init()`, `draw_ui()`, `handle_event()`)

---

## Devices (`device/`)

### Device Module Structure

Each device has a Python module (e.g., `device/quadraverb.py`, `device/bmlpf.py`) with:

#### Required Attributes:

```python
DEVICE_INFO = {
    "id": "01",
    "name": "QUADRAVERB",
    "default_page": "dials",
    "pages": {
        "01": {
            "name": "Reverb",
            "type": "dials",
            "dials": {
                "01": {"label": "Mix", "cc": 70, "range": [0, 100], ...},
                ...
            }
        },
        ...
    }
}

REGISTRY = {
    "QUADRAVERB": {
        "01": {"label": "Mix", "cc": 70, ...},
        ...
    }
}

BUTTONS = [
    {"id": "1", "label": "Reverb", "enabled": True},
    ...
]

THEME = {
    "dial_panel_color": "#123456",
    ...
}
```

#### Optional Attributes:

- `TRANSPORT = "cv"` or `"midi"`
- `CV_MAP = {"01": 1, ...}` - Dial to CV channel mapping
- `CV_RESOLUTION = 4095` - DAC resolution
- `CC_OVERRIDE = {"01": 30, ...}` - Override CC numbers

#### Optional Functions:

##### `on_button_press(button_index: int) -> bool`
Device-specific button handling.
- Return True if handled, False to fall through to default

##### `handle_cv_send(dial_id, value, current_page_id) -> bool`
Custom CV sending logic.
- Return True if handled

---

## Control Modules (`control/`)

Control modules handle specific UI interactions:

- **`dials_control.py`** - Dial interaction logic
- **`global_control.py`** - Global controls and shortcuts
- **`mixer_control.py`** - Mixer interactions
- **`patchbay_control.py`** - Patchbay connections
- **`presets_control.py`** - Preset management
- **`tremolo_control.py`** / **`vibrato_control.py`** - Effect controls

---

## Assets & UI Components (`assets/`)

### `dial.py` - Dial

**Purpose:** Dial widget with physics and rendering.

#### Functions:

##### `__init__(self, cx, cy, radius=None, arc_start=240, arc_end=660)`
Creates dial at position.

##### `update_from_mouse(self, mx, my)`
Updates dial from mouse position.
- Circular clamping with hysteresis
- Snapping to steps (options or range)

##### `draw(self, surface)`
High-quality dial rendering with pygame.gfxdraw.

##### `set_value(self, val: int)`
Sets dial value programmatically.

##### `on_mouse_up(self)`
Resets sticky edge flags.

**Private:**
- `_circular_clamp_and_progress()` - Arc math
- `_snap_cc()` - Step snapping

**Dependencies:** `math`, `helper`, `config`, `pygame.gfxdraw`

---

### `ui_button.py` / `ui_label.py` / `fader.py`

UI component rendering helpers.

---

## Utilities (`utils/`)

- **`valueconvert.py`** - Value conversion utilities
- **`rotating_state.py`** - State machine for rotating buttons
- **`grid_layout.py`** - Grid layout calculations
- **`font_helper.py`** - Font loading and caching
- **`debug_overlay_grid.py`** - Debug grid overlay
- **`config_helpers.py`** - Config file helpers

---

## Handlers (`handlers/`)

### `global_handler.py` - GlobalEventHandler

**Purpose:** Handles global events (exit, quit).

### `dials_handler.py` - DialsEventHandler

**Purpose:** Handles dial page mouse events.

### `device_select_handler.py` - DeviceSelectEventHandler

**Purpose:** Handles device selection clicks.

---

## Initialization (`initialization/`)

### `registry_init.py` - RegistryInitializer

**Purpose:** Initializes CCRegistry and EntityRegistry.

#### Functions:

##### `initialize_cc_registry()`
Loads CC registry.

##### `initialize_entity_registry()`
Loads entity registry.

##### `load_device_registry(device_name: str)`
Loads device into registries.

---

### `hardware_init.py` - HardwareInitializer

**Purpose:** Initializes all hardware connections.

#### Functions:

##### `initialize_all(midi_cc_callback, midi_sysex_callback, screen)`
Initializes MIDI, CV client, network, LCD, LED.

##### `get_status() -> dict`
Returns hardware connection status.

---

### `device_loader.py` - DeviceLoader

**Purpose:** Loads devices from files and modules.

#### Functions:

##### `load_all_devices()`
Scans and loads all device modules.

##### `get_button_behavior(device_name: str) -> dict`
Returns button behavior map for device.

##### `get_device_info(device_name: str) -> dict`
Returns device info dictionary.

##### `send_cv_calibration(device_name: str)`
Sends CV calibration if needed.

---

## Root Level Modules

### `config.py`

**Purpose:** Central configuration file.

Contains all settings:
- Logging configuration
- Display settings
- FPS targets
- Dial appearance
- Button appearance
- Mixer settings
- Patchbay settings
- Preset settings
- Paths

---

### `helper.py`

**Purpose:** Helper functions for colors, text, themes.

#### Functions:

##### `hex_to_rgb(value)`
Converts hex color to RGB tuple.

##### `render_text_with_spacing(text, font, color, spacing=0)`
Renders text with custom letter spacing.

##### `apply_text_case(text, uppercase=False)`
Applies case transformation.

##### `device_theme.get(device_name, key, fallback=None)`
Resolves theme value with fallback chain.

##### `theme_rgb(device_name, key, default)`
Unified theme lookup returning RGB tuple.

---

### `network.py`

**Purpose:** TCP server for PC communication, LED/LCD forwarding.

#### Functions:

##### `tcp_server(msg_queue)`
Receives lines from PC, forwards to Pico or local I²C.

##### `send_led_line(msg: str)`
Routes LED/LCD message with throttling.

##### `forward_to_pico(msg: str)`
Direct network send to Pico.

**Features:**
- Throttled LED updates (per-device independent)
- Message sanitization
- Automatic Pico connection management
- Local I²C fallback

---

### `devices.py`

**Purpose:** Device database and definition management.

#### Functions:

##### `load(path=None)`
Loads devices from JSON + preloads Python modules.

##### `get(device_id)` / `get_by_name(name)` / `get_id_by_name(name)`
Device lookup functions.

##### `get_dial_map(device_name, page_id="01")`
Returns dial layout for device/page.

##### `get_theme(device_name)`
Returns THEME dict (with module inheritance).

##### `get_init_state(device_name)` / `get_announce_msg(device_name)`
Returns init state / announce message.

##### `update_from_device(device_id, layer_id, dials, header_text_ref)`
Updates dials and header text from device definition.

##### `get_button_index_by_page_name(device_name, page_name)`
Returns button index (1-5) for page name.

---

### `device_states.py`

**Purpose:** Manages device/page init states.

#### Functions:

##### `load()` / `save()`
Load/save states from/to JSON.

##### `store_init(device_name, page_id, values, button_states=None)`
Stores INIT preset for device/page.
- Supports modern format (dict with dials/buttons)
- Supports legacy format (list)

##### `get_init(device_name, page_id)`
Returns stored init state.

##### `get_page_state(device_name, page_id)`
Returns best available state (current or init).

##### `send_init_state(device_name)`
Sends all INIT values over MIDI.

---

### `device_presets.py`

**Purpose:** Named preset management separate from INIT states.

#### Functions:

##### `load()` / `save()`
Load/save presets from/to JSON.

##### `store_preset(device_name, page_id, preset_name, dial_values)`
Saves named preset.

##### `get_preset(device_name, page_id, preset_name)`
Wrapper choosing between Pi presets and patches.json.

##### `list_presets(device_name, page_id=None)`
Lists all presets for device(/page).

##### `delete_preset(device_name, page_id, preset_name)`
Deletes preset.

##### `load_patches()` / `list_device_patches(device_name)`
Loads factory patches from patches.json.

---

### `preset_manager.py`

See Managers section above.

---

### `dialhandlers.py`

**Purpose:** Central hub for dial/button events, MIDI routing, state management.

#### Global State:

- `current_device_id` / `current_device_name` / `current_page_id`
- `live_states` - In-memory dial values per device/page
- `live_button_states` - Button states for module pages
- `visited_pages` - Track first-load init

#### Functions:

##### `init(msg_q)` / `set_dials(dials_ref)`
Initialization.

##### `load_device(device_name)`
Switches active device mapping.
- Sets current_device_name and current_device_id
- Applies default mute state (Quadraverb)
- Returns starting page

##### `on_dial_change(dial_id, value)`
Outgoing dial changes.
- Checks for CV transport
- Handles custom CV sending
- Sends MIDI (SysEx or CC)
- Updates LIVE state
- Persists to StateManager

##### `route_param(target_device, dial_id, value, page_id=None)`
Routes value to specific device (for router pages).

##### `on_button_press(button_index)`
Button press handling.
- UI navigation (presets, text_input, device_select)
- Save INIT (button 6)
- Mute/unmute page (button 8)
- Standard page switching (1-5)
- Mixer/module page switches
- State recall (LIVE or INIT)

##### `on_midi_cc(dial_id, value)`
Incoming MIDI CC.
- Updates dial value
- Queues UI update

##### `on_midi_sysex(device, layer, dial_id, value, cc_num)`
Incoming MIDI SysEx.
- Lightweight patch SysEx
- Button 6 save trigger
- Normal page/parameter SysEx

##### `store_init_state()` / `recall_init_state()`
Init state management.

##### `update_button_state(page_id, var_name, value)` / `get_button_states(page_id)`
Module button state tracking.

---

### `navigator.py`

**Purpose:** Page navigation history.

#### Functions:

##### `set_page(page_name, record=True)`
Sets current page, optionally records in history.

##### `go_back()`
Returns to previous page.

##### `current()` / `is_transitioning()`
Returns current page / transition status.

---

### `showlog.py`

**Purpose:** Logging system with on-screen bar, file output, network forwarding.

#### Functions:

##### `init(screen, font_name, font_size)`
Initializes logging.

##### `log(*args)`
Main logging entry point.
- Accepts `log(msg)` or `log(screen, msg)`
- Auto-tags with module name
- Writes to file
- Forwards to remote
- Updates on-screen bar

##### `draw_bar(screen=None, fps_value=None)`
Draws bottom log bar with:
- Log message
- Clock
- CPU meter
- FPS (if provided)

##### `error(msg, exc=None)` / `warn(msg)` / `info(msg)` / `debug(msg)` / `verbose(msg)`
Level-specific logging.

##### `log_process(screen, msg, color)`
Internal processing function.
- Parses tags
- Applies verbosity filters
- Updates display text
- Writes to file
- Forwards to network

**Features:**
- Loupe mode (only messages starting with `*`)
- Verbosity levels (ERROR, WARN, INFO, DEBUG, VERBOSE)
- Network forwarding (TCP)
- File logging with separators
- VSCode clickable links
- Module auto-tagging
- Emoji indicators
- CPU meter
- FPS display

---

### `showheader.py`

**Purpose:** Header bar with dropdown menu, back button, burger menu.

#### Functions:

##### `init(screen, font_name, font_size, spacing)`
Initializes header.

##### `show(screen, msg, device_name=None)`
Draws header bar.
- Centered text
- Back arrow (left)
- Screenshot button
- Burger menu (right)
- Animated dropdown

##### `handle_event(event)`
Handles clicks on header elements.
- Returns action: "go_back", "toggle_menu", "screenshot_taken", button actions

##### `set_menu_open(is_open: bool)` / `update(dt: float)` / `get_offset() -> int`
Dropdown animation control.

##### `set_context_buttons(buttons)`
Sets dropdown menu buttons.

##### `take_screenshot()`
Takes screenshot, saves to screenshots/ folder.

**Features:**
- Animated dropdown menu
- Device-aware themes
- Screenshot capability
- Context-sensitive menu
- Icon support (arrow, burger, screenshot)

---

### `midiserver.py`

**Purpose:** MIDI I/O management and message routing.

#### Functions:

##### `init(dial_cb, sysex_cb)`
Initializes MIDI ports and callbacks.

##### `send_cc(target_type, index, value)`
Sends MIDI CC (for dials or buttons).

##### `send_cc_raw(cc_num, value)`
Sends specific CC number directly.

##### `send_bytes(data)`
Sends raw 3-byte MIDI message.

##### `send_program_change(program_num, channel=None)`
Sends MIDI Program Change.

##### `send_device_message(device_name, dial_index, value, param_range, section_id, page_offset, dial_obj, cc_override)`
Routes outgoing control message to correct device driver.
- Quadraverb: SysEx
- Other devices: CC (with optional override)

##### `send_preset_values(device_name, section_name, values)`
Sends entire preset (8 dial values) to device.

##### `send_cv(channel, value)`
Sends voltage to CV Server (Pi Zero).

##### Background Worker:
- `_midi_send_worker()` - Background thread for non-blocking sends
- `start_send_worker()` / `stop_send_worker()` - Worker lifecycle
- `enqueue_device_message(**kwargs)` - Non-blocking enqueue

##### `_on_midi_in(msg)`
Incoming MIDI handler.
- CC messages → dial_handler
- SysEx messages → sysex_handler

---

### `ui.py`

**Purpose:** Entry point (V2 refactored).

#### Functions:

##### `main()`
Application entry point.
- Creates UIApplication
- Initializes subsystems
- Runs event loop
- Handles cleanup

**Lines:** ~50 (down from 1000+)

---

## Dependency Map

### Core Dependencies

```
ui.py
 └─> core/app.py
      ├─> core/display.py [pygame]
      ├─> core/loop.py [pygame]
      ├─> core/services.py
      ├─> core/event_bus.py [showlog]
      ├─> core/page_registry.py [showlog]
      ├─> core/ui_context.py [pygame, queue]
      ├─> core/mixins/* [showlog, dialhandlers, system/*, initialization/*]
      ├─> managers/* (see below)
      ├─> rendering/* (see below)
      ├─> handlers/* (see below)
      ├─> pages/* (see below)
      ├─> system/* (see below)
      ├─> config
      ├─> showlog
      ├─> showheader
      ├─> dialhandlers
      ├─> navigator
      └─> devices
```

### Manager Dependencies

```
managers/dial_manager.py
 ├─> assets/dial.py [math, helper, config, pygame.gfxdraw]
 ├─> config
 ├─> dialhandlers
 ├─> showlog
 └─> system/cc_registry

managers/button_manager.py
 └─> showlog

managers/mode_manager.py
 ├─> navigator
 ├─> dialhandlers
 ├─> showlog
 ├─> config
 ├─> managers/preset_manager
 ├─> control/global_control
 ├─> devices
 ├─> midiserver
 ├─> unit_router
 └─> system/cc_registry

managers/preset_manager.py
 ├─> json, os, pathlib
 └─> showlog
```

### System Dependencies

```
system/state_manager.py
 ├─> os, json, time, tempfile, threading
 ├─> config
 └─> showlog

system/cc_registry.py
 ├─> os, sys, json, threading, hashlib, importlib
 ├─> showlog
 ├─> config
 └─> system/state_manager
```

### Rendering Dependencies

```
rendering/renderer.py
 ├─> pygame
 ├─> showlog
 ├─> showheader
 ├─> dialhandlers
 ├─> navigator
 └─> config
```

### Page Dependencies

```
pages/page_dials.py
 ├─> math, pygame, pygame.gfxdraw
 ├─> showlog
 ├─> helper
 ├─> config
 ├─> quadraverb_driver
 ├─> importlib
 ├─> assets/ui_button
 ├─> assets/ui_label
 └─> dialhandlers
```

### Root Module Dependencies

```
dialhandlers.py
 ├─> midiserver
 ├─> devices
 ├─> showlog
 ├─> device_states
 ├─> cv_client
 ├─> unit_router
 └─> device/{device modules}

midiserver.py
 ├─> mido
 ├─> showlog
 ├─> config
 ├─> quadraverb_driver
 └─> traceback

devices.py
 ├─> json, os
 ├─> showlog
 ├─> config
 └─> importlib

showlog.py
 ├─> pygame, os, sys, time, datetime
 ├─> helper
 ├─> config
 ├─> socket, threading, queue
 └─> traceback

showheader.py
 ├─> pygame
 ├─> helper
 ├─> config
 ├─> os
 ├─> showlog
 └─> datetime

network.py
 ├─> socket, threading, time, traceback
 ├─> showlog
 ├─> config
 └─> string
```

---

## Data Flow

### Startup Flow

```
1. ui.py::main()
2. core/app.py::UIApplication()
3. app.initialize()
   ├─> DisplayManager.initialize() → screen
   ├─> showlog.init(screen)
   ├─> showheader.init(screen)
   ├─> state_manager.init()
   ├─> RegistryInitializer.initialize_*()
   ├─> DeviceLoader.load_all_devices()
   ├─> Create managers (Dial, Button, Mode, Message, Preset)
   ├─> Renderer(screen, preset_manager, page_registry)
   ├─> Register services
   ├─> Register pages in PageRegistry
   ├─> HardwareInitializer.initialize_all()
   ├─> Create event handlers (Global, Dials, DeviceSelect)
   ├─> EventLoop.add_handler()
   └─> navigator.set_page("device_select")
4. app.run() → event loop
```

### Event Flow

```
pygame.event
 └─> EventLoop
      └─> UIApplication._handle_event()
           ├─> GlobalEventHandler (exit, quit)
           ├─> showheader.handle_event() (back, burger, menu)
           └─> Page-specific via PageRegistry
                ├─> page_dials (DialsEventHandler)
                ├─> device_select (DeviceSelectEventHandler)
                ├─> presets/module_presets (UnifiedPresetManager)
                └─> other pages (PageRegistry.call_handler())
```

### Dial Change Flow

```
Mouse Move (on dial)
 └─> DialsEventHandler.handle_event()
      └─> Dial.update_from_mouse()
           ├─> Dial.value updated
           └─> msg_queue.put(("update_dial_value", dial_id, value))
                └─> MessageQueueProcessor.process_all()
                     └─> on_dial_update callback
                          └─> dialhandlers.on_dial_change()
                               ├─> Check CV transport
                               │    └─> cv_client.send() or device.handle_cv_send()
                               ├─> OR midiserver.enqueue_device_message()
                               │    └─> Background worker → midiserver.send_device_message()
                               │         ├─> Quadraverb: qv.send_sysex()
                               │         └─> Other: send_cc()
                               ├─> Update live_states[device][page][dial]
                               └─> Persist to StateManager
                                    └─> state_manager.set_value(source, param_id, value)
                                         └─> Autosave thread → JSON
```

### Mode Switch Flow

```
Button Press or msg_queue.put(("ui_mode", "new_mode"))
 └─> MessageQueueProcessor._handle_mode_change()
      └─> ModeManager.switch_mode()
           ├─> Persist current page dials (_persist_current_page_dials)
           ├─> navigator.set_page(new_mode, record=True/False)
           ├─> Update prev_mode, ui_mode
           └─> Setup new mode (_setup_*)
                ├─> Clear/rebuild dials (DialManager)
                ├─> Load device/module registry (cc_registry)
                ├─> Update button behavior (ButtonManager)
                ├─> Initialize page (page.init() or preset_manager.init_for_*)
                └─> Request full frames (FrameController)
```

### Render Flow

```
Every Frame (UIApplication.run())
 └─> app._render()
      ├─> Check if full frame needed
      │    ├─> FrameController.needs_full_frame()
      │    ├─> ModeManager.needs_full_frame()
      │    └─> showheader.is_animating()
      ├─> Idle dials mode: Renderer.draw_log_bar_only()
      │    └─> DirtyRectManager.present_dirty()
      └─> Full frame: app._draw_full_frame()
           └─> Renderer.draw_current_page()
                ├─> Clear background
                ├─> Check navigator.is_transitioning()
                ├─> Route to page (PageRegistry or UnifiedPresetManager)
                │    └─> page.draw_ui() or preset_manager.draw()
                ├─> showheader.show() (with theme)
                └─> showlog.draw_bar() (with FPS, CPU)
```

### State Persistence Flow

```
Dial Value Change
 └─> dialhandlers.on_dial_change()
      └─> state_manager.set_value(source, param_id, value)
           ├─> Find knob in registry
           ├─> Update value
           ├─> Mark dirty
           └─> Autosave thread (every 5s)
                └─> state_manager.save_now()
                     └─> Atomic write to states/device_state.json
```

### Preset Save Flow

```
User Action (Save Preset)
 └─> preset_ui or module page
      └─> preset_manager.save_preset()
           ├─> Get page config (PRESET_STATE or auto-discover from REGISTRY)
           ├─> Collect module variables
           ├─> Collect widget state (widget.get_state())
           ├─> Collect button states
           └─> Write to config/presets/{page_id}/{preset_name}.json
```

### Preset Load Flow

```
User Action (Load Preset)
 └─> preset_ui or module page
      └─> preset_manager.load_preset()
           ├─> Load JSON file
           ├─> Stop vibrato (if applicable)
           ├─> Restore button states FIRST
           ├─> Restore module variables
           ├─> Call module.on_dial_change() for each variable (apply CV)
           ├─> Restore widget state (widget.set_from_state())
           ├─> Trigger widget CV update (widget.on_change())
           └─> Restart vibrato (if was on)
```

---

## Key Design Decisions

### Why Service Registry?
- **Loose coupling**: Components don't directly import each other
- **Testability**: Easy to mock services
- **Flexibility**: Services can be replaced at runtime

### Why Page Registry?
- **Eliminates branching**: No more giant if/elif chains
- **Dynamic loading**: Pages can be added without modifying core
- **Metadata**: Each page carries its own configuration

### Why Event Bus?
- **Decoupled messaging**: Publishers don't know subscribers
- **Future-ready**: Easy to add new subscribers
- **Debugging**: Centralized event logging

### Why Mixins?
- **Composability**: UIApplication gets functionality without bloat
- **Separation**: Hardware, Rendering, Messages are independent
- **Reusability**: Can be used by other classes if needed

### Why StateManager + CCRegistry?
- **Persistence**: Dial values survive restarts
- **Registry**: Canonical metadata separate from runtime state
- **Flexible**: Supports devices, modules, arbitrary parameters
- **Autosave**: Background thread prevents blocking

### Why Dirty Rect Optimization?
- **Performance**: Only redraw changed regions
- **Burst mode**: Special handling for dial updates
- **Adaptive**: Falls back to full frame when needed

### Why Theme System?
- **Per-device customization**: Each device can have unique colors
- **Fallback chain**: Device THEME → config → default
- **Unified keys**: Same keys across devices

---

## Common Workflows

### Adding a New Device

1. Create `device/{device_name}.py`
2. Define `DEVICE_INFO`, `REGISTRY`, `BUTTONS`, `THEME`
3. Optional: Add `TRANSPORT`, `CV_MAP`, `CC_OVERRIDE`
4. Optional: Implement `on_button_press()`, `handle_cv_send()`
5. Add device to `devices.json` (if using JSON fallback)
6. Restart application - device auto-loaded

### Adding a New Page

1. Create `pages/{page_name}.py`
2. Implement `init()`, `draw_ui()`, `handle_event()`
3. Register in `core/app.py::_init_pages()`:
   ```python
   self.page_registry.register("page_id", page_module, "Page Label",
                                meta={"themed": True})
   ```
4. Add to `navigator` logic if needed
5. Create handler in `handlers/` if complex

### Adding a New Preset Type

1. Update `config/save_state_vars.json` OR
2. Add `PRESET_STATE` to module class OR
3. Use auto-discovery via `REGISTRY`
4. Call `preset_manager.save_preset()` / `load_preset()`
5. Presets auto-saved to `config/presets/{page_id}/`

### Adding a New Manager

1. Create `managers/{manager_name}.py`
2. Implement required methods
3. Instantiate in `core/app.py::_init_managers()`
4. Register in ServiceRegistry
5. Access via `services.get('manager_name')`

---

## Performance Optimizations

### Caching

- **Font cache** (`page_dials._FONT_CACHE`)
- **Dial face cache** (`page_dials._FACE_CACHE`)
- **Label surface cache** (per-dial `cached_surface`)
- **Device button specs cache** (`page_dials._BTN_CACHE`)
- **Theme cache** (`showheader._current_theme`)

### Rendering

- **Supersampling** - High-quality dials downscaled
- **Dirty rects** - Only update changed regions
- **Burst mode** - Special handling for continuous dial updates
- **Single dial redraw** - `redraw_single_dial()` for partial updates
- **Adaptive FPS** - Lower FPS for static pages

### Threading

- **Autosave thread** - StateManager saves in background
- **MIDI send worker** - Non-blocking MIDI sends
- **Log forwarding thread** - Non-blocking network logging
- **Log writer thread** - Non-blocking file writing

### Message Queue

- **Throttled LED updates** - Per-device independent throttling
- **Batched processing** - Process multiple messages per frame
- **Queue dropping** - Drop oldest on overflow

---

## Testing Strategy

### Unit Tests

Test individual components:
- `test_state_manager.py` - State persistence
- `test_cc_registry.py` - CC allocation
- `test_preset_manager.py` - Preset save/load
- `test_dial.py` - Dial physics

### Integration Tests

Test component interactions:
- `test_mode_switching.py` - Mode transitions
- `test_device_loading.py` - Device initialization
- `test_event_routing.py` - Event handling

### Manual Tests

UI validation:
- Visual regression (screenshots)
- Performance profiling (FPS, CPU)
- Hardware tests (MIDI, CV, network)

---

## Future Improvements

### Planned Features

1. **Module System V2**
   - Hot-reload modules
   - Module marketplace
   - Module dependencies

2. **Preset System V2**
   - Preset tags/categories
   - Preset morphing
   - Preset randomization

3. **UI Improvements**
   - Touch gestures
   - Animations
   - Themes selector

4. **Network Features**
   - Multi-client support
   - WebSocket API
   - Remote control web UI

5. **Performance**
   - GPU acceleration (pygame2)
   - Parallel rendering
   - Smarter caching

### Technical Debt

- Migrate from `mido` to custom MIDI (more control)
- Replace `pygame` with modern framework (pygame2, pyglet)
- TypeScript types for messages
- GraphQL API for remote control
- Docker deployment

---

## Troubleshooting

### Common Issues

**Issue:** Dials don't respond
- Check MIDI connections (`midiserver.py::init()`)
- Verify device loaded (`dialhandlers.current_device_name`)
- Check StateManager registry (`state_manager.knobs`)

**Issue:** Presets don't load
- Verify preset file exists (`config/presets/{page_id}/{name}.json`)
- Check `save_state_vars.json` or `PRESET_STATE`
- Ensure `preset_manager` initialized

**Issue:** Display glitches
- Check dirty rect logic (`rendering/dirty_rect.py`)
- Force full redraw (`msg_queue.put(("force_redraw", 60))`)
- Verify screen surface valid

**Issue:** Network not working
- Check `config.LOG_REMOTE_ENABLED`
- Verify host/port (`config.LOG_REMOTE_HOST`)
- Test with `telnet {host} {port}`

**Issue:** State not persisting
- Check StateManager autosave thread running
- Verify write permissions (`states/device_state.json`)
- Check knob registered in StateManager

---

## Glossary

- **Dial** - Rotary control (knob)
- **Button** - Clickable control (1-10)
- **Page** - UI screen (dials, presets, mixer, etc.)
- **Mode** - Synonym for page
- **Device** - Hardware synth (Quadraverb, BMLPF, etc.)
- **Module** - Software effect (Vibrato Maker, etc.)
- **Entity** - Device or module
- **Registry** - Metadata definition (REGISTRY, CCRegistry, EntityRegistry)
- **StateManager** - Runtime state persistence
- **Preset** - Saved parameter values
- **Init** - Default/initialization values
- **Live State** - Current runtime values (not persisted immediately)
- **CC** - MIDI Control Change
- **SysEx** - MIDI System Exclusive message
- **CV** - Control Voltage (analog control)
- **Burst Mode** - Fast update mode during dial dragging
- **Dirty Rect** - Changed screen region
- **Service** - Registered component in ServiceRegistry
- **Mixin** - Composable class functionality

---

## Contact & Contributions

For questions, bug reports, or contributions, please:
1. Check this documentation
2. Review code comments
3. Check git history for context
4. Open an issue

---

**End of Documentation**

This manual covers all major functions, dependencies, and workflows in the UI application. For specific implementation details, refer to the source code and inline comments.
