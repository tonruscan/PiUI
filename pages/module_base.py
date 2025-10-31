# /build/pages/module_base.py  (rename of your vibrato.py)
import pygame
import config as cfg
import custom_controls
import showlog
from typing import Optional, Dict, Any
import helper
import dialhandlers
from system import state_manager, cc_registry
from assets import ui_button
from system.module_core import ModuleBase
from plugins import vibrato_plugin as mod
from widgets.dial_widget import DialWidget
from preset_manager import get_preset_manager
from preset_ui import PresetSaveUI
from utils.debug_overlay_grid import draw_debug_grid
from utils.grid_layout import get_grid_cell_rect, get_zone_rect_tight, get_grid_geometry

# ----------------------------------------------------------------------------
# Shared UI state
# ----------------------------------------------------------------------------
button_rects = []
button_rects_map = {}
pressed_button = None
selected_buttons = set()

_SLOT_META: Dict[int, Dict[str, Any]] = {}
_MAPPED_SRC: Optional[str] = None
_LOGTAG = mod.MODULE_ID.upper()

_MOD_INSTANCE = None
_PRESET_UI = None  # Preset save overlay UI

def _get_mod_instance():
    """Create/cache the active module instance (class discovered dynamically)."""
    global _MOD_INSTANCE
    if _MOD_INSTANCE is not None:
        return _MOD_INSTANCE
    try:
        # 1) explicit factory wins
        factory = getattr(mod, "get_instance", None)
        if callable(factory):
            _MOD_INSTANCE = factory()
            return _MOD_INSTANCE

        target_id = getattr(mod, "MODULE_ID", None)

        # 2) find a real subclass (not the base) with matching MODULE_ID
        candidates = []
        for name in dir(mod):
            obj = getattr(mod, name)
            if not (isinstance(obj, type) and issubclass(obj, ModuleBase)):
                continue
            if obj is ModuleBase:
                continue  # skip the base class re-exported by the module
            mid = getattr(obj, "MODULE_ID", None)
            score = 0
            if mid and target_id and mid == target_id:
                score += 10
            if name.lower() == "vibrato":  # friendly hint
                score += 1
            candidates.append((score, obj))

        if candidates:
            candidates.sort(reverse=True)
            cls = candidates[0][1]
            _MOD_INSTANCE = cls()
            return _MOD_INSTANCE

        showlog.warn(f"[{_LOGTAG}] No ModuleBase subclass found in module.")
    except Exception as e:
        showlog.warn(f"[{_LOGTAG}] _get_mod_instance failed: {e}")
    return None

def _dispatch_hook(name: str, *args):
    """Call a hook on the active module instance if it exists."""
    try:
        inst = _get_mod_instance()
        if not inst:
            return
        method = getattr(inst, name, None)
        if callable(method):
            return method(*args)
    except Exception as e:
        showlog.warn(f"[{_LOGTAG}] hook '{name}' failed: {e}")


_CUSTOM_WIDGET_INSTANCE = None

def _load_custom_widget():
    """Load and position a module's custom widget (if declared)."""
    global _CUSTOM_WIDGET_INSTANCE

    # Return cached instance if already created
    if _CUSTOM_WIDGET_INSTANCE:
        return _CUSTOM_WIDGET_INSTANCE

    spec = getattr(mod, "CUSTOM_WIDGET", None)
    if not spec:
        return None

    try:
        import importlib

        # ─────────────────────────────────────────────
        # Ensure grid geometry exists (for grid-space sizing)
        # ─────────────────────────────────────────────
        geom = get_grid_geometry()
        if not geom:
            get_grid_cell_rect(0, 0)  # trigger geometry calc
            geom = get_grid_geometry()

        # ─────────────────────────────────────────────
        # Resolve widget rect
        # ─────────────────────────────────────────────
        rect = None

        # 1️⃣ Prefer explicit grid_size
        if "grid_size" in spec:
            w_cells, h_cells = spec["grid_size"]
            # Anchor default: row 0, col 1 (same area as old zone C)
            row, col = spec.get("grid_pos", [0, 1])
            rect = get_zone_rect_tight(row, col, w_cells, h_cells, geom)
            
            # Debug: Show detailed grid calculations
            showlog.verbose(
                f"*[VIBRATO] Widget grid calculation: "
                f"pos=({col},{row}) size={w_cells}×{h_cells} → rect={rect}"
            )
            
            # Debug: Compare with individual dial positions for alignment verification
            dial_rect_tl = get_grid_cell_rect(0, 1)  # Top-left dial of widget area
            dial_rect_tr = get_grid_cell_rect(0, 3)  # Top-right dial of widget area  
            dial_rect_bl = get_grid_cell_rect(1, 1)  # Bottom-left dial of widget area
            dial_rect_br = get_grid_cell_rect(1, 3)  # Bottom-right dial of widget area
            
            showlog.verbose(
                f"*[{mod.MODULE_ID}] Individual dials in widget area:"
            )
            showlog.verbose(f"*[{mod.MODULE_ID}]   TL(0,1): {dial_rect_tl}")
            showlog.verbose(f"*[{mod.MODULE_ID}]   TR(0,3): {dial_rect_tr}")
            showlog.verbose(f"*[{mod.MODULE_ID}]   BL(1,1): {dial_rect_bl}")
            showlog.verbose(f"*[{mod.MODULE_ID}]   BR(1,3): {dial_rect_br}")

            # Calculate what the perfect widget rect should be
            perfect_left = dial_rect_tl.left
            perfect_top = dial_rect_tl.top
            perfect_right = dial_rect_tr.right
            perfect_bottom = dial_rect_br.bottom
            perfect_rect = pygame.Rect(perfect_left, perfect_top, 
                                     perfect_right - perfect_left, 
                                     perfect_bottom - perfect_top)

            showlog.verbose(f"*[{mod.MODULE_ID}] Perfect widget rect: {perfect_rect}")
            showlog.verbose(f"*[{mod.MODULE_ID}] Actual widget rect:  {rect}")
            showlog.verbose(
                f"*[{mod.MODULE_ID}] Differences: "
                f"left={rect.left - perfect_left}, top={rect.top - perfect_top}, "
                f"right={rect.right - perfect_right}, bottom={rect.bottom - perfect_bottom}"
            )

        # 2️⃣ Fallback to manual rect
        elif "rect" in spec:
            rect = pygame.Rect(spec["rect"])
            showlog.verbose(f"*[VIBRATO] Custom widget manual rect {rect}")

        # 3️⃣ Default rectangle
        else:
            rect = pygame.Rect(120, 80, 660, 300)
            showlog.verbose(f"*[VIBRATO] Custom widget default rect {rect}")

        # ─────────────────────────────────────────────
        # Import class and instantiate
        # ─────────────────────────────────────────────
        mod_widget = importlib.import_module(spec["path"])
        cls = getattr(mod_widget, spec["class"])

        # Instantiate widget without wiring it directly to module logic.
        # The module may provide an `attach_widget(widget)` hook to wire callbacks.

        from helper import theme_rgb
        device_name = getattr(dialhandlers, "current_device_name", None)

        # Strictly pass through your device theme colors from cfg/helper. No alpha, no transforms.
        theme = {
            "bg":       theme_rgb(device_name, "DIAL_MUTE_PANEL"),     # background panel
            "fill":     theme_rgb(device_name, "DIAL_FILL_COLOR"),     # middle selection band
            "outline":  theme_rgb(device_name, "DIAL_OUTLINE_COLOR"),  # frame + dots
            "guides":   (255, 255, 255),                               # white lines
            "solid_mode": True,                                        # hard disable any alpha logic
        }

        _CUSTOM_WIDGET_INSTANCE = cls(rect, on_change=None, theme=theme)


        showlog.info(
            f"[{mod.MODULE_ID}] Custom widget loaded → "
            f"{spec['class']} from {spec['path']} (rect={rect})"
        )
        # If the active module exposes an attach_widget hook, call it to let the
        # module wire the widget's on_change handler (e.g. Vibrato.attach_widget).
        try:
            _dispatch_hook("attach_widget", _CUSTOM_WIDGET_INSTANCE)
            showlog.debug(f"[{mod.MODULE_ID}] attach_widget() dispatched to module instance")
        except Exception:
            # ignore: not all modules implement attach_widget
            pass

        return _CUSTOM_WIDGET_INSTANCE

    except Exception as e:
        showlog.error(f"[{mod.MODULE_ID}] custom widget load failed: {e}")
        return None


# ----------------------------------------------------------------------------
# Initialization
# ----------------------------------------------------------------------------
def init_page():
    """Called once when page becomes active."""
    global _PRESET_UI
    
    dials = getattr(dialhandlers, "dials", None)
    if not dials:
        return

    sm = getattr(state_manager, "manager", None)
    if not sm:
        showlog.warn(f"[{_LOGTAG}] StateManager not ready during init")
        return
    
    # Initialize preset UI overlay if not already created
    if _PRESET_UI is None:
        try:
            screen_w = getattr(cfg, "SCREEN_WIDTH", 800)
            screen_h = getattr(cfg, "SCREEN_HEIGHT", 480)
            _PRESET_UI = PresetSaveUI((screen_w, screen_h))
            showlog.debug(f"[{_LOGTAG}] PresetSaveUI initialized")
        except Exception as e:
            showlog.error(f"[{_LOGTAG}] Failed to initialize PresetSaveUI: {e}")

    # Keep module state independent of device page state
    # (If you later need device names in the module key, add it here.)
    global _MAPPED_SRC
    if _MAPPED_SRC != mod.MODULE_ID:
        # Ensure knobs exist for this module; attach happens after labels in draw_ui()
        try:
            cc_registry.load_from_module(mod.MODULE_ID, mod.REGISTRY, None)
        except Exception as e:
            showlog.warn(f"[{_LOGTAG}] cc_registry.load_from_module failed: {e}")
        _MAPPED_SRC = None  # force (re)attach in draw_ui

    # Clear first-load flags so new module state is recalled
    try:
        for d in dials:
            if hasattr(d, "_mod_init"):
                delattr(d, "_mod_init")
    except Exception:
        pass

    owned_slots = set(_get_owned_slots())
    attached = sum(1 for d in dials if d.id in owned_slots and getattr(d, "sm_param_id", None))
    showlog.debug(f"*[{_LOGTAG}] init_page linked {attached} dials to StateManager (src={mod.MODULE_ID})")

# ----------------------------------------------------------------------------
# Utilities
# ----------------------------------------------------------------------------
def _dial_hit(d, pos):
    dx = pos[0] - d.cx
    dy = pos[1] - d.cy
    return (dx * dx + dy * dy) <= (d.radius * d.radius)

def _ensure_meta():
    _SLOT_META.clear()
    for slot, ctrl_id in mod.SLOT_TO_CTRL.items():
        meta = custom_controls.get(ctrl_id)
        if not meta:
            showlog.warn(f"[{_LOGTAG}] Missing controller '{ctrl_id}' in custom_dials.json")
        _SLOT_META[slot] = meta or {}


def _get_owned_slots():
    """Return the slot ids that this module actually owns."""
    def _normalize(values):
        out = []
        for v in values:
            try:
                out.append(int(v))
            except (TypeError, ValueError):
                continue
        return sorted(set(out))

    slots = getattr(mod, "OWNED_SLOTS", None)
    if slots:
        return _normalize(slots)

    ctrl_map = getattr(mod, "SLOT_TO_CTRL", {}) or {}
    if isinstance(ctrl_map, dict):
        return _normalize(ctrl_map.keys())

    return []

def _snap_for_meta_default(meta) -> int:
    """Return a snapped 0..127 default based on control meta defaults (center-ish)."""
    opts = (meta or {}).get("options")
    rng = (meta or {}).get("range")

    if isinstance(opts, list) and len(opts) > 1:
        steps = len(opts)
        idx = (steps - 1) // 2
        return int(round(idx * (127.0 / (steps - 1))))

    if isinstance(rng, (list, tuple)) and len(rng) == 2 and all(isinstance(v, int) for v in rng):
        lo, hi = rng
        steps = (hi - lo) + 1
        if 1 < steps <= 16:
            idx = (steps - 1) // 2
            return int(round(idx * (127.0 / (steps - 1))))
        return int(round(127.0 * 0.5))

    return 0


def _module_value_to_raw(meta, value):
    """Translate a module variable back to a 0..127 dial position."""
    if value is None:
        return None

    meta = meta or {}
    opts = meta.get("options")
    rng = meta.get("range")

    try:
        if isinstance(opts, list) and len(opts) > 1:
            idx = int(round(value))
            idx = max(0, min(len(opts) - 1, idx))
            step = 127.0 / (len(opts) - 1)
            return int(round(idx * step))

        if isinstance(rng, (list, tuple)) and len(rng) == 2 and all(isinstance(x, (int, float)) for x in rng):
            lo = float(rng[0])
            hi = float(rng[1])
            if hi == lo:
                return 0
            val = max(lo, min(hi, float(value)))
            norm = (val - lo) / (hi - lo)
            return int(round(norm * 127.0))

        return int(value)
    except Exception:
        return None


def _sync_module_state_to_dials(module_instance):
    """Push freshly loaded preset values into the on-screen dials."""
    registry = getattr(mod, "REGISTRY", {}) or {}
    slot_map = {}

    for entry in registry.values():
        if not isinstance(entry, dict) or entry.get("type") != "module":
            continue
        for slot_key, slot_data in entry.items():
            if slot_key in {"type", "label", "description"}:
                continue
            if not isinstance(slot_data, dict):
                continue
            var = slot_data.get("variable")
            if not var:
                continue
            try:
                slot_idx = int(slot_key)
            except Exception:
                continue
            slot_map[var] = (slot_idx, slot_data)

    if not slot_map:
        return

    widgets = globals().get("_ACTIVE_WIDGETS", []) or []
    dial_list = getattr(dialhandlers, "dials", None)
    sm = getattr(state_manager, "manager", None)

    for var_name, payload in slot_map.items():
        slot_idx, slot_meta = payload
        if not hasattr(module_instance, var_name):
            continue

        value = getattr(module_instance, var_name)
        meta = (_SLOT_META.get(slot_idx) or {}).copy()
        if not meta:
            meta = slot_meta.copy()
        raw = _module_value_to_raw(meta, value)
        if raw is None:
            continue

        dial_obj = None

        for widget in widgets:
            dial = getattr(widget, "dial", None)
            if dial and getattr(dial, "id", None) == slot_idx:
                try:
                    dial.set_value(raw)
                except Exception:
                    dial.value = raw
                dial_obj = dial
                break

        if dial_list and 1 <= slot_idx <= len(dial_list):
            try:
                dial_list[slot_idx - 1].set_value(raw)
            except Exception:
                dial_list[slot_idx - 1].value = raw
            if dial_obj is None:
                dial_obj = dial_list[slot_idx - 1]

        if sm and dial_obj and getattr(dial_obj, "sm_param_id", None):
            src = getattr(dial_obj, "sm_source_name", None) or mod.MODULE_ID
            try:
                sm.set_value(src, dial_obj.sm_param_id, int(dial_obj.value))
            except Exception:
                pass

# ----------------------------------------------------------------------------
# Preset Save/Load Functions
# ----------------------------------------------------------------------------
def save_current_preset(preset_name: str):
    """
    Save the current module state as a preset.
    
    Args:
        preset_name: Name for the preset
    """
    try:
        preset_mgr = get_preset_manager()
        module_instance = _get_mod_instance()
        widget = globals().get("_CUSTOM_WIDGET_INSTANCE")
        
        if not module_instance:
            showlog.error(f"[{_LOGTAG}] Cannot save preset - no module instance")
            return False
        
        page_id = mod.MODULE_ID
        success = preset_mgr.save_preset(page_id, preset_name, module_instance, widget)
        
        if success:
            showlog.info(f"[{_LOGTAG}] Saved preset '{preset_name}'")
        else:
            showlog.error(f"[{_LOGTAG}] Failed to save preset '{preset_name}'")
        
        return success
        
    except Exception as e:
        showlog.error(f"[{_LOGTAG}] Exception saving preset: {e}")
        return False

def load_preset(preset_name: str, msg_queue=None):
    """
    Load a saved preset and apply it to the current module.
    
    Args:
        preset_name: Name of the preset to load
        msg_queue: Optional message queue for UI updates
    """
    try:
        preset_mgr = get_preset_manager()
        module_instance = _get_mod_instance()
        widget = globals().get("_CUSTOM_WIDGET_INSTANCE")
        
        if not module_instance:
            showlog.error(f"[{_LOGTAG}] Cannot load preset - no module instance")
            return False
        
        page_id = mod.MODULE_ID
        success = preset_mgr.load_preset(page_id, preset_name, module_instance, widget)
        
        if success:
            showlog.info(f"[{_LOGTAG}] Loaded preset '{preset_name}'")
            try:
                _ensure_meta()
                _sync_module_state_to_dials(module_instance)
            except Exception as e:
                showlog.warn(f"[{_LOGTAG}] Failed to sync dials after preset load: {e}")
            if msg_queue:
                msg_queue.put(("invalidate", None))
        else:
            showlog.error(f"[{_LOGTAG}] Failed to load preset '{preset_name}'")
        
        return success
        
    except Exception as e:
        showlog.error(f"[{_LOGTAG}] Exception loading preset: {e}")
        return False

def show_preset_save_ui():
    """Show the preset save UI overlay."""
    global _PRESET_UI
    if _PRESET_UI:
        _PRESET_UI.show(on_save_callback=save_current_preset)
    else:
        showlog.warn(f"[{_LOGTAG}] PresetSaveUI not initialized")

def is_preset_ui_active():
    """Check if the preset save UI is currently active."""
    global _PRESET_UI
    return _PRESET_UI and _PRESET_UI.active

def handle_remote_input(data):
    """
    Handle remote keyboard input for preset UI.
    
    Args:
        data: Character or special key from remote keyboard
    """
    global _PRESET_UI
    if _PRESET_UI and _PRESET_UI.active:
        _PRESET_UI.handle_remote_input(data)


# ----------------------------------------------------------------------------
# Draw UI
# ----------------------------------------------------------------------------
def draw_ui(screen, offset_y=0):
    if not _SLOT_META:
        _ensure_meta()


    # --------------------------------------------------------------
    # Build DialWidgets using grid layout from module
    # --------------------------------------------------------------
    global _ACTIVE_WIDGETS
    owned_slots = set(_get_owned_slots())

    if "_ACTIVE_WIDGETS" not in globals():
        try:
            _ACTIVE_WIDGETS = []
            
            # Get grid layout from module (default to 2x4 if not specified)
            grid_layout = getattr(mod, "GRID_LAYOUT", {"rows": 2, "cols": 4})
            total_rows = grid_layout.get("rows", 2)
            total_cols = grid_layout.get("cols", 4)
            
            sm = getattr(state_manager, "manager", None)

            for i in range(8):
                row = i // total_cols
                col = i % total_cols
                rect = get_grid_cell_rect(row, col, total_rows, total_cols)
                dial_id = i + 1

                ctrl_id = mod.SLOT_TO_CTRL.get(dial_id)
                meta = _SLOT_META.get(dial_id) or custom_controls.get(ctrl_id) or {}

                owned = dial_id in owned_slots
                if owned:
                    label = meta.get("label", f"Slot {dial_id}")
                    rng = meta.get("range", [0, 127])
                    opts = meta.get("options")
                    typ = meta.get("type", "raw")
                    greyed_out = False
                else:
                    label = "EMPTY"
                    rng = [0, 127]
                    opts = None
                    typ = "raw"
                    greyed_out = True

                uid = f"{mod.MODULE_ID}.{label}.{dial_id}"
                cfg_dict = {
                    "id": dial_id,
                    "label": label,
                    "range": rng,
                    "options": opts,
                    "type": typ,
                    "greyed_out": greyed_out,
                }

                # Only create visible dials that belong to the module
                if not greyed_out:
                    w = DialWidget(uid, rect, cfg_dict)
                    _ACTIVE_WIDGETS.append(w)
                else:
                    showlog.debug(f"[{mod.MODULE_ID}] Skipping empty dial slot {dial_id}")


            showlog.debug(f"[MODULE_BASE] Created {_LOGTAG} DialWidgets with real metadata")

        except Exception as e:
            showlog.error(f"[MODULE_BASE] Failed to create DialWidgets: {e}")



    device_name = getattr(dialhandlers, "current_device_name", None)

    # ---------- draw side buttons (match page_dials style) ----------
    btn_fill          = helper.theme_rgb(device_name, "BUTTON_FILL",           "#3C3C3C")
    btn_outline       = helper.theme_rgb(device_name, "BUTTON_OUTLINE",        "#646464")
    btn_text          = helper.theme_rgb(device_name, "BUTTON_TEXT",           "#FFFFFF")
    btn_disabled_fill = helper.theme_rgb(device_name, "BUTTON_DISABLED_FILL",  "#1E1E1E")
    btn_disabled_text = helper.theme_rgb(device_name, "BUTTON_DISABLED_TEXT",  "#646464")
    btn_active_fill   = helper.theme_rgb(device_name, "BUTTON_ACTIVE_FILL",    "#960096")
    btn_active_text   = helper.theme_rgb(device_name, "BUTTON_ACTIVE_TEXT",    "#FFFFFF")

    font_label = pygame.font.SysFont("arial", 20)
    btn_w, btn_h = 50, 50

    global button_rects
    button_rects.clear()
    _local_map = {}

    # ------------------------------------------------------------------
    # Resolve button labels from the module's own BUTTONS config
    # ------------------------------------------------------------------
    # Define sy function to apply offset_y (match page_dials pattern)
    def sy(y):
        return y + offset_y

    # Build simple id→label map from plugins.<plugin>.BUTTONS
    module_buttons = getattr(mod, "BUTTONS", [])
    button_label_map = {}
    for entry in module_buttons:
        if not isinstance(entry, dict):
            continue
        btn_id = str(entry.get("id", "")).strip()
        label = str(entry.get("label", "")).strip()
        # fallback to short form of action if no label
        if not label:
            act = str(entry.get("action", "")).strip()
            label = act[:2].upper() if act else btn_id
        button_label_map[btn_id] = label

    # Provide empty defaults if missing
    left_label_map = {k: v for k, v in button_label_map.items() if k in {"1","2","3","4","5"}}
    right_label_map = {k: v for k, v in button_label_map.items() if k in {"6","7","8","9","10"}}


    # LEFT column (1–5)
    for i, name in enumerate(["1", "2", "3", "4", "5"]):
        x = cfg.BUTTON_OFFSET_X
        y = sy(cfg.BUTTON_OFFSET_Y + i * (btn_h + cfg.BUTTON_SPACING_Y))
        rect = pygame.Rect(x, y, btn_w, btn_h)
        button_rects.append((rect, name))
        _local_map[name] = rect

        display_label = left_label_map.get(name, name)
        is_disabled = name not in left_label_map

        ui_button.draw_button(
            screen, rect, display_label, font_label,
            pressed_button, selected_buttons,
            button_id=name, disabled=is_disabled,
            fill_color=btn_fill, outline_color=btn_outline, text_color=btn_text,
            disabled_fill=btn_disabled_fill, disabled_text=btn_disabled_text,
            active_fill=btn_active_fill, active_text=btn_active_text
        )

    # RIGHT column (6–10)
    for i, name in enumerate(["6", "7", "8", "9", "10"]):
        x = screen.get_width() - cfg.BUTTON_OFFSET_X - btn_w
        y = sy(cfg.BUTTON_OFFSET_Y + i * (btn_h + cfg.BUTTON_SPACING_Y))
        rect = pygame.Rect(x, y, btn_w, btn_h)
        button_rects.append((rect, name))
        _local_map[name] = rect

        display_label = right_label_map.get(name, name)
        is_disabled = name not in right_label_map

        ui_button.draw_button(
            screen, rect, display_label, font_label,
            pressed_button, selected_buttons,
            button_id=name, disabled=is_disabled,
            fill_color=btn_fill, outline_color=btn_outline, text_color=btn_text,
            disabled_fill=btn_disabled_fill, disabled_text=btn_disabled_text,
            active_fill=btn_active_fill, active_text=btn_active_text
        )


    try:
        if "_ACTIVE_WIDGETS" in globals():
            for w in _ACTIVE_WIDGETS:
                w.draw(screen, device_name=device_name, offset_y=offset_y)
    except Exception as e:
        showlog.warn(f"[MODULE_BASE] draw grid DialWidgets failed: {e}")
   

    # check for modular widget first
    widget = _load_custom_widget()
    if widget:
        widget.draw(screen, offset_y=offset_y)

    globals()["button_rects_map"] = _local_map
    
    # Debug grid overlay (uncomment to enable)
    # Get GRID_ZONES from module if available
    # geom = get_grid_geometry()
    # if geom:
    #     grid_zones = getattr(mod, "GRID_ZONES", [])
    #     draw_debug_grid(screen, geom, grid_zones)

    # Draw preset save UI overlay (always drawn last, on top of everything)
    global _PRESET_UI
    if _PRESET_UI:
        _PRESET_UI.update()
        _PRESET_UI.draw(screen)




# ----------------------------------------------------------------------------
# Shared logic for handling dial changes (UI or hardware)
# ----------------------------------------------------------------------------
def _process_dial_change(dial_obj, meta, src_name, sm, msg_queue):
    """
    Process a dial value change (from either hardware or UI).
    Normalizes value to 0–127 and dispatches via _apply_snap_and_dispatch.
    """
    if not dial_obj:
        return
    try:
        v = max(0, min(127, int(getattr(dial_obj, "value", 0))))
    except Exception:
        v = 0

    _apply_snap_and_dispatch(
        d=dial_obj,
        meta=meta or {},
        raw127=v,
        src_name=src_name,
        sm=sm,
        msg_queue=msg_queue
    )

def _apply_snap_and_dispatch(d, meta, raw127, src_name, sm, msg_queue):
    """
    Snap/scale raw127 using meta, update dial UI, dispatch module hook,
    persist state, and invalidate.
    """
    try:
        v = max(0, min(127, int(raw127)))
    except Exception:
        v = 0

    label = (meta or {}).get("label")
    opts  = (meta or {}).get("options")
    rng   = (meta or {}).get("range")

    # --- Discrete options ---
    if isinstance(opts, list) and len(opts) > 1:
        step = 127.0 / (len(opts) - 1)
        idx = int(round(v / step))
        idx = max(0, min(len(opts) - 1, idx))
        snapped = int(round(idx * step))
        try:
            d.set_value(snapped)
        except Exception:
            d.value = snapped

        _dispatch_hook("on_dial_change", label, idx)

    # --- Ranged numeric ---
    elif isinstance(rng, (list, tuple)) and len(rng) == 2 and all(isinstance(x, int) for x in rng):
        lo, hi = rng
        steps = (hi - lo) + 1
        if 1 < steps <= 16:
            step = 127.0 / (steps - 1)
            idx = int(round(v / step))
            idx = max(0, min(steps - 1, idx))
            snapped = int(round(idx * step))
            out = lo + idx
        else:
            snapped = v
            out = int(round(lo + (hi - lo) * (v / 127.0)))

        try:
            d.set_value(snapped)
        except Exception:
            d.value = snapped

        _dispatch_hook("on_dial_change", label, out)

    # --- Default continuous ---
    else:
        try:
            d.set_value(v)
        except Exception:
            d.value = v
        _dispatch_hook("on_dial_change", label, int(d.value))

    # Persist state (if mapped)
    if sm and getattr(d, "sm_param_id", None):
        src = getattr(d, "sm_source_name", None) or src_name
        sm.set_value(src, d.sm_param_id, int(d.value))
    elif sm and not getattr(d, "sm_param_id", None):
        showlog.warn(f"[{_LOGTAG}] Dial {getattr(d,'id','?')} has no sm_param_id; state not updated")

    if msg_queue is not None:
        msg_queue.put(("invalidate", None))


def handle_event(event, msg_queue):
    global pressed_button, selected_buttons, _PRESET_UI

    # Check preset UI first (it blocks other events when active)
    if _PRESET_UI and _PRESET_UI.handle_event(event):
        if msg_queue:
            msg_queue.put(("invalidate", None))
        return

    sm = getattr(state_manager, "manager", None)
    src_name = mod.MODULE_ID

    widget = globals().get("_CUSTOM_WIDGET_INSTANCE")
    if widget and widget.handle_event(event):
        return

    # --------------------------------------------------------------
    # TEMP TEST — route event to new DialWidgets first
    # --------------------------------------------------------------
    try:
        if "_ACTIVE_WIDGETS" in globals():
            for w in _ACTIVE_WIDGETS:
                if w.handle_event(event):
                    _process_dial_change(
                        dial_obj=w.dial,
                        meta=_SLOT_META.get(w.dial.id) or {},
                        src_name=mod.MODULE_ID,
                        sm=sm,
                        msg_queue=msg_queue
                    )
                    return
    except Exception as e:
        showlog.warn(f"[MODULE_BASE] DialWidget event dispatch failed: {e}")

    # --------------------------------------------------------------
    # Side button press detection → dispatch to module hook
    # --------------------------------------------------------------
    if event.type == pygame.MOUSEBUTTONDOWN and hasattr(event, "pos"):
        hit_any = False
        for d in (dialhandlers.dials or []):
            if _dial_hit(d, event.pos):
                d.dragging = True
                hit_any = True
        if not hit_any:
            for rect, name in button_rects:
                if rect.collidepoint(event.pos):
                    pressed_button = name
                    
                    # Special handling for preset load button (button 7)
                    if name == "7":
                        # Navigate to module presets page
                        if msg_queue:
                            msg_queue.put(("ui_mode", "module_presets"))
                            msg_queue.put(("invalidate", None))
                    # Special handling for preset save button (button 9)
                    elif name == "9":
                        show_preset_save_ui()
                        pressed_button = None
                        selected_buttons.discard(name)
                        if msg_queue:
                            msg_queue.put(("invalidate", None))
                    else:
                        _dispatch_hook("on_button", str(name))
                        if msg_queue:
                            msg_queue.put(("invalidate", None))
                    break

    elif event.type == pygame.MOUSEBUTTONUP:
        pressed_button = None  # <— reset visual state
        for d in (dialhandlers.dials or []):
            if getattr(d, "dragging", False):
                d.dragging = False

    elif event.type == pygame.MOUSEMOTION and hasattr(event, "pos"):
        for d in (dialhandlers.dials or []):
            if getattr(d, "dragging", False):
                d.update_from_mouse(*event.pos)
                ctrl_id = mod.SLOT_TO_CTRL.get(d.id)
                if not ctrl_id:
                    continue
                meta = _SLOT_META.get(d.id) or {}
                _apply_snap_and_dispatch(
                    d=d, meta=meta, raw127=int(d.value),
                    src_name=src_name, sm=sm, msg_queue=msg_queue
                )


# ----------------------------------------------------------------------------
# Hardware dial handler
# ----------------------------------------------------------------------------
def handle_hw_dial(dial_id: int, value: int, msg_queue=None) -> bool:
    """
    Handle a hardware/touchscreen dial move on the module page.
    Routes to new DialWidgets or legacy dials as fallback.
    """
    global _ACTIVE_WIDGETS

    dial_id = int(dial_id)
    v = max(0, min(127, int(value)))
    sm = getattr(state_manager, "manager", None)
    src_name = mod.MODULE_ID
    meta = _SLOT_META.get(dial_id) or {}

    # 1️⃣ Try new widget system first
    try:
        if "_ACTIVE_WIDGETS" in globals():
            for w in _ACTIVE_WIDGETS:
                if getattr(w.dial, "id", None) == dial_id:
                    w.dial.set_value(v)
                    _process_dial_change(
                        dial_obj=w.dial,
                        meta=meta,
                        src_name=src_name,
                        sm=sm,
                        msg_queue=msg_queue
                    )
                    return True
    except Exception as e:
        showlog.warn(f"[MODULE_BASE] handle_hw_dial (widget) failed: {e}")

    # 2️⃣ Fallback to legacy dials (for modules still using dialhandlers)
    try:
        dials = getattr(dialhandlers, "dials", None)
        if not dials or dial_id < 1 or dial_id > len(dials):
            return False
        d = dials[dial_id - 1]
        d.set_value(v)
        _process_dial_change(
            dial_obj=d,
            meta=meta,
            src_name=src_name,
            sm=sm,
            msg_queue=msg_queue
        )
        return True
    except Exception as e:
        showlog.error(f"[MODULE_BASE] handle_hw_dial legacy failed: {e}")
        return False


